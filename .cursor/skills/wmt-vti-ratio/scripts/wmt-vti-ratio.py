#!/usr/bin/env python3
"""Fetch WMT and VTI prices and print WMT/VTI ratio as JSON.

Price selection:
- If the US regular equity session is open: use the live market price.
- If the session is closed: use the latest regular-session close.

VTI (Vanguard Total Stock Market ETF) is the liquid proxy for FSKAX-style
total-market exposure, so both legs share the same intraday clock.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
USER_AGENT = "Mozilla/5.0 (compatible; wmt-vti-ratio/1.0)"


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--message",
        action="store_true",
        help="Also print a short human-readable summary line on stderr.",
    )
    args = parser.parse_args()

    # Use WMT's session calendar as the US equity market clock.
    session_meta = _chart("WMT", interval="1d", range_="5d").get("meta") or {}
    now = datetime.now(timezone.utc).timestamp()
    market_open = _is_regular_session_open(session_meta, now)

    wmt = fetch_quote("WMT", market_open=market_open)
    vti = fetch_quote("VTI", market_open=market_open)

    ratio = wmt["price"] / vti["price"]
    payload = {
        "ok": True,
        "market_open": market_open,
        "as_of_check": datetime.now(timezone.utc).isoformat(),
        "wmt": wmt,
        "vti": vti,
        "ratio": round(ratio, 6),
        "ratio_formula": "WMT/VTI",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
