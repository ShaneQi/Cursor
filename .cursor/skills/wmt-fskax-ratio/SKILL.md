---
name: wmt-fskax-ratio
description: >-
  Fetches WMT and FSKAX prices, computes the WMT/FSKAX ratio, and always sends
  the result via the send-telegram skill. Uses live market price when the US
  regular session is open, otherwise the latest close/NAV. Use when asked for
  WMT vs FSKAX prices, their ratio, or to Telegram that ratio.
---

# WMT / FSKAX Ratio

When the user asks for WMT and FSKAX prices, their ratio (`WMT/FSKAX`), or
invokes this skill, run the helper immediately and **always** send the result
via the `send-telegram` skill. Do not invent prices from memory. Do not skip
Telegram delivery.

## Price rules

- If the **US regular equity session is open**: use the **live market price**.
- If the session is **closed**: use the **latest regular-session close** (for
  FSKAX, the latest published NAV).
- FSKAX is a mutual fund (end-of-day NAV only). While the equity market is open,
  its price is still the prior NAV until the next NAV publishes after close.

## Required env vars

- `TELEGRAM_BOT_TOKEN` — BotFather bot token
- `TELEGRAM_CHAT_ID` — destination chat/user/channel id

If either is missing, stop and tell the user to export it. Never print the
token or chat id.

## Steps

1. Confirm Telegram env vars are set (presence only; do not echo values):

```bash
test -n "$TELEGRAM_BOT_TOKEN" && test -n "$TELEGRAM_CHAT_ID" && echo ok
```

2. Fetch prices and ratio:

```bash
python3 .cursor/skills/wmt-fskax-ratio/scripts/wmt-fskax-ratio.py
```

Stdout is JSON with `market_open`, `wmt`, `fskax`, and `ratio`.

3. **Always** send via `send-telegram` with a short message built from the JSON:

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

4. Report briefly: market open/closed, both prices with `price_type`, ratio,
   and Telegram `message_id`. Never print `TELEGRAM_BOT_TOKEN` or
   `TELEGRAM_CHAT_ID`.

## Notes

- Prefer this helper over ad-hoc Yahoo/`curl` scrapes so open vs close selection
  stays consistent.
- Requires outbound HTTPS to Yahoo Finance chart endpoints.
- Telegram delivery is mandatory on every run of this skill.
