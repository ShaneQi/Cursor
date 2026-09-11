---
name: send-telegram
description: >-
  Sends a Telegram message via the Bot API using TELEGRAM_BOT_TOKEN and
  TELEGRAM_CHAT_ID. Use when the user asks to send, notify, or message via
  Telegram, or to post a status/alert to their Telegram chat.
---

# Send Telegram Message

When the user asks to send a Telegram message (or notify/alert via Telegram),
run the helper immediately with the message text. Do not invent delivery
success — use the script output.

## Required env vars

- `TELEGRAM_BOT_TOKEN` — BotFather bot token
- `TELEGRAM_CHAT_ID` — destination chat/user/channel id

If either is missing, stop and tell the user to export it. Never print the
token or chat id.

## Steps

1. Confirm both env vars are set (presence only; do not echo values):

```bash
test -n "$TELEGRAM_BOT_TOKEN" && test -n "$TELEGRAM_CHAT_ID" && echo ok
```

2. Send the message:

```bash
python3 .cursor/skills/send-telegram/scripts/send-telegram.py "MESSAGE"
```

Or pipe multi-line / long text:

```bash
python3 .cursor/skills/send-telegram/scripts/send-telegram.py <<'EOF'
MESSAGE
EOF
```

Optional parse mode:

```bash
python3 .cursor/skills/send-telegram/scripts/send-telegram.py --parse-mode HTML "<b>MESSAGE</b>"
python3 .cursor/skills/send-telegram/scripts/send-telegram.py --parse-mode MarkdownV2 "MESSAGE"
```

3. Report briefly from the JSON stdout (`ok`, `message_id`). On non-zero exit,
   summarize the stderr error without leaking credentials.

## Notes

- Prefer the helper over ad-hoc `curl` so escaping stays correct.
- Default destination is whatever `TELEGRAM_CHAT_ID` points at; do not hardcode ids.
- Keep messages concise unless the user provided longer text to forward as-is.
