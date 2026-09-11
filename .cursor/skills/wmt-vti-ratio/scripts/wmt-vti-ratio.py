#!/usr/bin/env python3
"""Fetch WMT and VTI prices, build a 45-day ratio chart, print JSON.

Price selection for the spot quote:
- If the US regular equity session is open: use the live market price.
- If the session is closed: use the latest regular-session close.

History chart:
- Past 45 calendar days of daily closes for both symbols.
- The current day's point uses the same spot quote (live when open, close
  when closed), so the chart includes today's realtime ratio while the
  market is open.

VTI (Vanguard Total Stock Market ETF) is the liquid proxy for FSKAX-style
total-market exposure, so both legs share the same intraday clock.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
USER_AGENT = "Mozilla/5.0 (compatible; wmt-vti-ratio/1.0)"
HISTORY_DAYS = 45


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Yahoo Finance HTTP {exc.code} for {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach Yahoo Finance: {exc.reason}") from exc


def _chart(symbol: str, *, interval: str, range_: str) -> dict[str, Any]:
    url = f"{YAHOO_CHART.format(symbol=symbol)}?interval={interval}&range={range_}"
    data = _get_json(url)
    results = (data.get("chart") or {}).get("result") or []
    if not results:
        error = (data.get("chart") or {}).get("error")
        raise SystemExit(f"No chart data for {symbol}: {error}")
    return results[0]


def _is_regular_session_open(meta: dict[str, Any], now: float) -> bool:
    period = ((meta.get("currentTradingPeriod") or {}).get("regular")) or {}
    start = period.get("start")
    end = period.get("end")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
        return False
    return start <= now < end


def _last_valid(values: list[float | None] | None) -> float | None:
    if not values:
        return None
    for value in reversed(values):
        if value is not None:
            return float(value)
    return None


def _daily_close(symbol: str) -> tuple[float, int]:
    result = _chart(symbol, interval="1d", range_="10d")
    meta = result.get("meta") or {}
    # When the session is closed, Yahoo's regularMarket* fields are the last
    # official close and the correct as-of timestamp (daily bar stamps are
    # often the session open, which is misleading).
    price = meta.get("regularMarketPrice")
    ts = meta.get("regularMarketTime")
    if price is not None and ts is not None:
        return float(price), int(ts)

    timestamps = result.get("timestamp") or []
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    for bar_ts, close in zip(reversed(timestamps), reversed(closes)):
        if close is not None:
            return float(close), int(bar_ts)
    raise SystemExit(f"Could not determine close price for {symbol}")


def _live_equity_price(symbol: str) -> tuple[float, int]:
    result = _chart(symbol, interval="1m", range_="1d")
    timestamps = result.get("timestamp") or []
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    price = _last_valid(closes)
    if price is not None and timestamps:
        return price, int(timestamps[-1])

    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice")
    ts = meta.get("regularMarketTime")
    if price is None or ts is None:
        raise SystemExit(f"Could not determine live price for {symbol}")
    return float(price), int(ts)


def fetch_quote(symbol: str, *, market_open: bool) -> dict[str, Any]:
    """Return price fields for one equity symbol."""
    if market_open:
        price, as_of = _live_equity_price(symbol)
        price_type = "market"
    else:
        price, as_of = _daily_close(symbol)
        price_type = "close"

    return {
        "symbol": symbol,
        "price": round(price, 4),
        "price_type": price_type,
        "as_of": datetime.fromtimestamp(as_of, timezone.utc).isoformat(),
        "as_of_unix": as_of,
    }


def _daily_closes(symbol: str) -> dict[str, float]:
    """Map YYYY-MM-DD -> close for recent daily bars."""
    result = _chart(symbol, interval="1d", range_="3mo")
    timestamps = result.get("timestamp") or []
    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    out: dict[str, float] = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%d")
        out[day] = float(close)
    if not out:
        raise SystemExit(f"No daily closes for {symbol}")
    return out


def _build_history(
    *,
    wmt_closes: dict[str, float],
    vti_closes: dict[str, float],
    spot_wmt: float,
    spot_vti: float,
    today: str,
    cutoff: str,
    market_open: bool,
) -> list[dict[str, Any]]:
    days = sorted(set(wmt_closes) & set(vti_closes))
    days = [d for d in days if d >= cutoff]
    # On weekends/holidays there is no "today" bar — keep closes only.
    include_today = market_open or today in wmt_closes or today in vti_closes
    rows: list[dict[str, Any]] = []
    for day in days:
        if include_today and day == today:
            continue  # replaced by spot quote below
        rows.append(
            {
                "date": day,
                "wmt": round(wmt_closes[day], 4),
                "vti": round(vti_closes[day], 4),
                "ratio": round(wmt_closes[day] / vti_closes[day], 6),
                "price_type": "close",
            }
        )

    if include_today:
        # Current day uses the spot quote (live when open, close when closed).
        rows.append(
            {
                "date": today,
                "wmt": round(spot_wmt, 4),
                "vti": round(spot_vti, 4),
                "ratio": round(spot_wmt / spot_vti, 6),
                "price_type": "spot",
            }
        )
    return rows


def _render_chart(history: list[dict[str, Any]], *, out_path: Path, market_open: bool) -> dict[str, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required to render the WMT/VTI chart "
            "(pip install matplotlib)"
        ) from exc

    dates = [datetime.strptime(row["date"], "%Y-%m-%d") for row in history]
    ratios = [float(row["ratio"]) for row in history]
    mean = sum(ratios) / len(ratios)
    lo_i = min(range(len(ratios)), key=lambda i: ratios[i])
    hi_i = max(range(len(ratios)), key=lambda i: ratios[i])
    spot_label = "live" if market_open else "close"

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.facecolor": "#0f1419",
            "figure.facecolor": "#0f1419",
            "text.color": "#e7ecf3",
            "axes.labelcolor": "#c5cdd8",
            "xtick.color": "#9aa4b2",
            "ytick.color": "#9aa4b2",
            "axes.edgecolor": "#2a3340",
            "grid.color": "#1c2430",
        }
    )

    fig, ax = plt.subplots(figsize=(12, 5.5), dpi=160)
    ax.plot(
        dates,
        ratios,
        color="#3dbb8f",
        linewidth=2.2,
        solid_capstyle="round",
        label="WMT/VTI",
    )
    ax.axhline(
        mean,
        color="#7f8ea3",
        linestyle="--",
        linewidth=1.1,
        alpha=0.9,
        label=f"Mean {mean:.4f}",
    )
    ax.fill_between(
        dates,
        ratios,
        mean,
        where=[r >= mean for r in ratios],
        color="#3dbb8f",
        alpha=0.12,
        interpolate=True,
    )
    ax.fill_between(
        dates,
        ratios,
        mean,
        where=[r < mean for r in ratios],
        color="#e07a5f",
        alpha=0.14,
        interpolate=True,
    )
    ax.scatter([dates[hi_i]], [ratios[hi_i]], color="#3dbb8f", s=36, zorder=5)
    ax.scatter([dates[lo_i]], [ratios[lo_i]], color="#e07a5f", s=36, zorder=5)
    ax.scatter([dates[-1]], [ratios[-1]], color="#f2f5f9", s=28, zorder=6)
    ax.annotate(
        f"High {ratios[hi_i]:.4f}\n{history[hi_i]['date']}",
        xy=(dates[hi_i], ratios[hi_i]),
        xytext=(10, 12),
        textcoords="offset points",
        fontsize=8,
        color="#b8f0d8",
    )
    ax.annotate(
        f"Low {ratios[lo_i]:.4f}\n{history[lo_i]['date']}",
        xy=(dates[lo_i], ratios[lo_i]),
        xytext=(10, -28),
        textcoords="offset points",
        fontsize=8,
        color="#f3c4b5",
    )
    ax.annotate(
        f"Now {ratios[-1]:.4f}\n({spot_label})",
        xy=(dates[-1], ratios[-1]),
        xytext=(-70, 14),
        textcoords="offset points",
        fontsize=8,
        color="#f2f5f9",
    )

    ax.set_title(
        f"WMT / VTI Ratio — Past {HISTORY_DAYS} Days (Close + Today {spot_label})",
        fontsize=14,
        pad=14,
        color="#f2f5f9",
    )
    ax.set_ylabel("Ratio")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.grid(True, axis="y", linewidth=0.8)
    ax.legend(frameon=False, loc="upper right")
    fig.autofmt_xdate()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    return {
        "points": len(history),
        "from": history[0]["date"],
        "to": history[-1]["date"],
        "min": round(min(ratios), 6),
        "max": round(max(ratios), 6),
        "mean": round(mean, 6),
        "last": round(ratios[-1], 6),
        "min_date": history[lo_i]["date"],
        "max_date": history[hi_i]["date"],
        "today_price_type": spot_label,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--message",
        action="store_true",
        help="Also print a short human-readable summary line on stderr.",
    )
    parser.add_argument(
        "--chart-path",
        help="Where to write the PNG chart (default: a temp file).",
    )
    parser.add_argument(
        "--no-chart",
        action="store_true",
        help="Skip chart rendering (spot quote JSON only).",
    )
    args = parser.parse_args()

    # Use WMT's session calendar as the US equity market clock.
    session_meta = _chart("WMT", interval="1d", range_="5d").get("meta") or {}
    now_dt = datetime.now(timezone.utc)
    now = now_dt.timestamp()
    market_open = _is_regular_session_open(session_meta, now)

    wmt = fetch_quote("WMT", market_open=market_open)
    vti = fetch_quote("VTI", market_open=market_open)
    ratio = wmt["price"] / vti["price"]

    today = now_dt.strftime("%Y-%m-%d")
    cutoff = (now_dt - timedelta(days=HISTORY_DAYS)).strftime("%Y-%m-%d")
    wmt_closes = _daily_closes("WMT")
    vti_closes = _daily_closes("VTI")
    history = _build_history(
        wmt_closes=wmt_closes,
        vti_closes=vti_closes,
        spot_wmt=wmt["price"],
        spot_vti=vti["price"],
        today=today,
        cutoff=cutoff,
        market_open=market_open,
    )

    chart_path: str | None = None
    chart_stats: dict[str, Any] | None = None
    if not args.no_chart:
        if args.chart_path:
            out = Path(args.chart_path)
        else:
            out = Path(tempfile.gettempdir()) / "wmt-vti-ratio-45d.png"
        chart_stats = _render_chart(history, out_path=out, market_open=market_open)
        chart_path = str(out.resolve())

    payload = {
        "ok": True,
        "market_open": market_open,
        "as_of_check": now_dt.isoformat(),
        "wmt": wmt,
        "vti": vti,
        "ratio": round(ratio, 6),
        "ratio_formula": "WMT/VTI",
        "history_days": HISTORY_DAYS,
        "history": history,
        "chart_path": chart_path,
        "chart": chart_stats,
    }
    print(json.dumps(payload))

    if args.message:
        state = "OPEN (market price)" if market_open else "CLOSED (close price)"
        print(
            f"WMT ${wmt['price']:.2f} ({wmt['price_type']}) / "
            f"VTI ${vti['price']:.2f} ({vti['price_type']}) = {ratio:.6f} "
            f"[US regular session {state}]",
            file=sys.stderr,
        )
        if chart_path:
            print(f"chart: {chart_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
