---
name: wmt-fskax-ratio
description: >-
  Fetches WMT and FSKAX prices, computes the WMT/FSKAX ratio, and optionally
  sends it via Telegram. Uses live market price when the US regular session is
  open, otherwise the latest close/NAV. Use when asked for WMT vs FSKAX prices,
  their ratio, or to Telegram that ratio.
---

# WMT / FSKAX Ratio

When the user asks for WMT and FSKAX prices, their ratio (`WMT/FSKAX`), or to
send that ratio via Telegram, run the helper immediately. Do not invent prices
from memory.

## Price rules

- If the **US regular equity session is open**: use the **live market price**.
- If the session is **closed**: use the **latest regular-session close** (for
  FSKAX, the latest published NAV).
- FSKAX is a mutual fund (end-of-day NAV only). While the equity market is open,
  its price is still the prior NAV until the next NAV publishes after close.

## Steps

1. Fetch prices and ratio:

```bash
python3 .cursor/skills/wmt-fskax-ratio/scripts/wmt-fskax-ratio.py
```

Stdout is JSON with `market_open`, `wmt`, `fskax`, and `ratio`.

Optional human summary on stderr:

```bash
python3 .cursor/skills/wmt-fskax-ratio/scripts/wmt-fskax-ratio.py --message
```

2. If the user asked to send/notify via Telegram, follow the `send-telegram`
   skill with a short message built from the JSON, for example:

```text
WMT/FSKAX ratio

Market: CLOSED (close) | OPEN (market)
WMT:   $PRICE (price_type)
FSKAX: $PRICE (price_type)
Ratio: RATIO
As of: TIMESTAMP
```

```bash
python3 .cursor/skills/send-telegram/scripts/send-telegram.py "MESSAGE"
```

3. Report briefly: market open/closed, both prices with `price_type`, ratio,
   and Telegram `message_id` when sent. Never print `TELEGRAM_BOT_TOKEN` or
   `TELEGRAM_CHAT_ID`.

## Notes

- Prefer this helper over ad-hoc Yahoo/`curl` scrapes so open vs close selection
  stays consistent.
- Requires outbound HTTPS to Yahoo Finance chart endpoints.
- Requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` only when sending.
