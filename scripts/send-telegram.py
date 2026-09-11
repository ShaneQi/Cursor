#!/usr/bin/env python3
"""Send a Telegram message using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.telegram.org"


def send_message(token: str, chat_id: str, text: str, parse_mode: str | None = None) -> dict:
    url = f"{API_BASE}/bot{token}/sendMessage"
    payload: dict[str, str] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Telegram API HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach Telegram API: {exc.reason}") from exc

    result = json.loads(body)
    if not result.get("ok"):
        raise SystemExit(f"Telegram API error: {body}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message",
        nargs="?",
        help="Message text to send. If omitted, read from stdin.",
    )
    parser.add_argument(
        "--parse-mode",
        choices=("HTML", "Markdown", "MarkdownV2"),
        help="Optional Telegram parse mode.",
    )
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        print("TELEGRAM_BOT_TOKEN is not set", file=sys.stderr)
        return 1
    if not chat_id:
        print("TELEGRAM_CHAT_ID is not set", file=sys.stderr)
        return 1

    if args.message is not None:
        text = args.message
    else:
        text = sys.stdin.read()

    text = text.strip()
    if not text:
        print("Message text is empty", file=sys.stderr)
        return 1

    result = send_message(token, chat_id, text, parse_mode=args.parse_mode)
    message = result.get("result", {})
    print(
        json.dumps(
            {
                "ok": True,
                "message_id": message.get("message_id"),
                "chat_id": (message.get("chat") or {}).get("id"),
                "date": message.get("date"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
