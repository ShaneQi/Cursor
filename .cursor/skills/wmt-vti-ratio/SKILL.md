---
name: wmt-vti-ratio
description: >-
  Fetches WMT and VTI prices, computes the WMT/VTI ratio, renders a 45-day
  ratio chart (today = live/spot), and always sends the chart photo first then
  a text summary via the send-telegram skill. Uses live market price when the
  US regular session is open, otherwise the latest close. Use when asked for
  WMT vs VTI (or former FSKAX) prices, their ratio, or to Telegram that ratio.
---

# WMT / VTI Ratio

When the user asks for WMT and VTI prices, their ratio (`WMT/VTI`), a former
WMT/FSKAX ratio request, or invokes this skill, run the helper immediately and
**always** send the result via the `send-telegram` skill. Do not invent prices
from memory. Do not skip Telegram delivery.

VTI is the liquid total-market ETF proxy for FSKAX-style exposure, so both legs
share the same intraday price clock.

## Price rules

- If the **US regular equity session is open**: use the **live market price**
  for both WMT and VTI.
- If the session is **closed**: use the **latest regular-session close** for
  both.
- The **45-day chart** uses daily closes for prior days, and uses the same
  spot quote as **today's** ratio point (live while open).

## Required env vars

- `TELEGRAM_BOT_TOKEN` — BotFather bot token
- `TELEGRAM_CHAT_ID` — destination chat/user/channel id

If either is missing, stop and tell the user to export it. Never print the
token or chat id.

## Dependencies

- `matplotlib` (for chart PNG rendering)

## Steps

1. Confirm Telegram env vars are set (presence only; do not echo values):

```bash
test -n "$TELEGRAM_BOT_TOKEN" && test -n "$TELEGRAM_CHAT_ID" && echo ok
```

2. Fetch prices, ratio, and chart:

```bash
python3 .cursor/skills/wmt-vti-ratio/scripts/wmt-vti-ratio.py
```

Stdout is JSON with `market_open`, `wmt`, `vti`, `ratio`, `history`,
`chart_path`, and `chart` stats.

3. **Always send the chart photo first** via `send-telegram`:

```bash
python3 .cursor/skills/send-telegram/scripts/send-telegram.py \
  --photo "$CHART_PATH" \
  "WMT/VTI — past 45 days (today = live|close)
High HIGH (MAX_DATE) · Low LOW (MIN_DATE) · Mean MEAN · Now RATIO"
```

Use `chart_path` plus `chart.max`, `chart.max_date`, `chart.min`,
`chart.min_date`, `chart.mean`, `chart.last`, and `chart.today_price_type`
(`live` or `close`) from the JSON.

4. **Then** send the text summary:

```text
WMT/VTI ratio

Market: CLOSED (close) | OPEN (market)
WMT:   $PRICE (price_type)
VTI:   $PRICE (price_type)
Ratio: RATIO
As of: TIMESTAMP
```

```bash
python3 .cursor/skills/send-telegram/scripts/send-telegram.py "MESSAGE"
```

5. Report briefly: market open/closed, both prices with `price_type`, ratio,
   chart `message_id`, and text `message_id`. Never print `TELEGRAM_BOT_TOKEN`
   or `TELEGRAM_CHAT_ID`.

## Notes

- Prefer this helper over ad-hoc Yahoo/`curl` scrapes so open vs close selection
  stays consistent.
- Requires outbound HTTPS to Yahoo Finance chart endpoints and Telegram.
- Telegram delivery is mandatory on every run: **photo first**, then text.
- Do not skip the chart unless rendering fails after installing matplotlib;
  if chart render fails, stop and report the error (do not send text-only).
