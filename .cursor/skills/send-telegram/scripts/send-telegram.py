#!/usr/bin/env python3
"""Send a Telegram message or photo using TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_BASE = "https://api.telegram.org"


def _post_form(url: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return _read_api(request)


def _post_multipart(
    url: str,
    fields: dict[str, str],
    *,
    file_field: str,
    file_path: Path,
) -> dict:
    boundary = "----cursorTelegramBoundary7f3a9c"
    body = bytearray()

    def add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for name, value in fields.items():
        add_field(name, value)

    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    data = file_path.read_bytes()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{file_path.name}"\r\n'
        ).encode()
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(data)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        url,
        data=bytes(body),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return _read_api(request, timeout=60)


def _read_api(request: urllib.request.Request, timeout: int = 30) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
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


def send_message(token: str, chat_id: str, text: str, parse_mode: str | None = None) -> dict:
    payload: dict[str, str] = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return _post_form(f"{API_BASE}/bot{token}/sendMessage", payload)


def send_photo(
    token: str,
    chat_id: str,
    photo_path: Path,
    caption: str | None = None,
    parse_mode: str | None = None,
) -> dict:
    if not photo_path.is_file():
        raise SystemExit(f"Photo file not found: {photo_path}")
    fields: dict[str, str] = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    if parse_mode:
        fields["parse_mode"] = parse_mode
    return _post_multipart(
        f"{API_BASE}/bot{token}/sendPhoto",
        fields,
        file_field="photo",
        file_path=photo_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "message",
        nargs="?",
        help="Message text (or photo caption when --photo is set). "
        "If omitted, read from stdin unless --photo is used with no caption.",
    )
    parser.add_argument(
        "--parse-mode",
        choices=("HTML", "Markdown", "MarkdownV2"),
        help="Optional Telegram parse mode.",
    )
    parser.add_argument(
        "--photo",
        help="Path to an image to send via sendPhoto (caption = message).",
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
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        text = ""

    text = text.strip()

    if args.photo:
        result = send_photo(
            token,
            chat_id,
            Path(args.photo),
            caption=text or None,
            parse_mode=args.parse_mode,
        )
        kind = "photo"
    else:
        if not text:
            print("Message text is empty", file=sys.stderr)
            return 1
        result = send_message(token, chat_id, text, parse_mode=args.parse_mode)
        kind = "message"

    message = result.get("result", {})
    print(
        json.dumps(
            {
                "ok": True,
                "kind": kind,
                "message_id": message.get("message_id"),
                "chat_id": (message.get("chat") or {}).get("id"),
                "date": message.get("date"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
