#!/usr/bin/env python3
"""Inspect a torrent/magnet and print JSON metadata (title, files) for kind/title resolution."""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from typing import Any


def bdecode(data: bytes, i: int = 0) -> tuple[Any, int]:
    if data[i : i + 1] == b"i":
        j = data.index(b"e", i)
        return int(data[i + 1 : j]), j + 1
    if data[i : i + 1] == b"l":
        i += 1
        out: list[Any] = []
        while data[i : i + 1] != b"e":
            v, i = bdecode(data, i)
            out.append(v)
        return out, i + 1
    if data[i : i + 1] == b"d":
        i += 1
        out_d: dict[Any, Any] = {}
        while data[i : i + 1] != b"e":
            k, i = bdecode(data, i)
            v, i = bdecode(data, i)
            out_d[k] = v
        return out_d, i + 1
    colon = data.index(b":", i)
    n = int(data[i:colon])
    start = colon + 1
    return data[start : start + n], start + n


def fetch_torrent(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; add-torrent/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def decode_str(value: Any) -> str | None:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, str):
        return value
    return None


def inspect_torrent_bytes(data: bytes) -> dict[str, Any]:
    meta, _ = bdecode(data)
    if not isinstance(meta, dict):
        raise SystemExit("Invalid torrent metadata.")
    info = meta.get(b"info")
    if not isinstance(info, dict):
        raise SystemExit("Torrent missing info dict.")

    title = decode_str(info.get(b"name"))
    files: list[dict[str, Any]] = []
    if b"files" in info and isinstance(info[b"files"], list):
        for entry in info[b"files"]:
            if not isinstance(entry, dict):
                continue
            path_parts = entry.get(b"path") or []
            path = "/".join(decode_str(p) or "" for p in path_parts)
            files.append({"path": path, "length": entry.get(b"length")})
    elif title is not None:
        files.append({"path": title, "length": info.get(b"length")})

    return {"title": title, "files": files, "source": "torrent"}


def magnet_display_name(link: str) -> str | None:
    parsed = urllib.parse.urlparse(link)
    qs = urllib.parse.parse_qs(parsed.query)
    dn = qs.get("dn") or qs.get("DN")
    if not dn:
        return None
    return urllib.parse.unquote_plus(dn[0])


def inspect_link(link: str) -> dict[str, Any]:
    if link.lower().startswith("magnet:"):
        title = magnet_display_name(link)
        return {"title": title, "files": [], "source": "magnet"}
    data = fetch_torrent(link)
    return inspect_torrent_bytes(data)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: resolve-torrent.py LINK", file=sys.stderr)
        raise SystemExit(2)

    result = inspect_link(sys.argv[1])
    if not result.get("title"):
        raise SystemExit("Could not determine torrent title from link.")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
