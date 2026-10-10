#!/usr/bin/env python3
"""Query the wiki.qis.family MoinMoin instance over XML-RPC."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xmlrpc.client
from html import unescape
from typing import Any

DEFAULT_URL = "https://wiki.qis.family/?action=xmlrpc2"
ACL_RE = re.compile(r"(?im)^#acl\s+(.+)$")
TAG_RE = re.compile(r"<[^>]+>")


def _require_env() -> tuple[str, str]:
    user = os.environ.get("MOIN_USERNAME", "").strip()
    password = os.environ.get("MOIN_PASSWORD", "")
    if not user or not password:
        raise SystemExit(
            "Missing MOIN_USERNAME and/or MOIN_PASSWORD in the environment."
        )
    return user, password


def _proxy(url: str) -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(url, allow_none=True)


def _auth_token(proxy: xmlrpc.client.ServerProxy, user: str, password: str) -> str:
    token = proxy.getAuthToken(user, password)
    if not isinstance(token, str) or not token:
        raise SystemExit("Moin getAuthToken failed (empty token).")
    return token


def _multicall(
    proxy: xmlrpc.client.ServerProxy,
    token: str,
    calls: list[tuple[str, tuple[Any, ...]]],
) -> list[Any]:
    mc = xmlrpc.client.MultiCall(proxy)
    mc.applyAuthToken(token)
    for name, args in calls:
        getattr(mc, name)(*args)
    results = list(mc())
    if not results or results[0] != "SUCCESS":
        raise SystemExit(f"Moin applyAuthToken failed: {results[:1]!r}")
    return results[1:]


def _strip_html(text: str) -> str:
    text = TAG_RE.sub("", text)
    return unescape(text).replace("\xa0", " ").strip()


def _serialize(value: Any) -> Any:
    if isinstance(value, xmlrpc.client.DateTime):
        return value.value
    if isinstance(value, dict):
        return {str(k): _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def cmd_search(proxy: xmlrpc.client.ServerProxy, token: str, args: argparse.Namespace) -> dict:
    raw = _multicall(proxy, token, [("searchPages", (args.query,))])[0]
    if not isinstance(raw, list):
        raise SystemExit(f"Unexpected searchPages result: {type(raw).__name__}")

    hits: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        name = str(item[0])
        snippet_html = str(item[1])
        hits.append(
            {
                "name": name,
                "snippet": _strip_html(snippet_html),
                "url": f"https://wiki.qis.family/{_quote_page(name)}",
            }
        )
        if args.limit and len(hits) >= args.limit:
            break

    pages: list[dict[str, Any]] = []
    if args.fetch and hits:
        names = [h["name"] for h in hits]
        bodies = _multicall(
            proxy,
            token,
            [("getPage", (name,)) for name in names],
        )
        for hit, body in zip(names, bodies):
            text = body if isinstance(body, str) else str(body)
            pages.append(
                {
                    "name": hit,
                    "acl": ACL_RE.findall(text),
                    "text": text if args.full else _excerpt(text, args.query, args.excerpt_chars),
                }
            )

    return {
        "ok": True,
        "action": "search",
        "query": args.query,
        "count": len(hits),
        "hits": hits,
        "pages": pages,
    }


def _quote_page(name: str) -> str:
    from urllib.parse import quote

    return quote(name, safe="/")


def _excerpt(text: str, query: str, width: int) -> str:
    if width <= 0:
        return text
    lower = text.lower()
    needle = query.lower()
    idx = lower.find(needle)
    if idx < 0:
        # try first non-comment content line
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        body = "\n".join(lines)
        return body[:width] + ("…" if len(body) > width else "")
    start = max(0, idx - width // 4)
    end = min(len(text), start + width)
    snippet = text[start:end]
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return prefix + snippet + suffix


def cmd_get(proxy: xmlrpc.client.ServerProxy, token: str, args: argparse.Namespace) -> dict:
    body, info = _multicall(
        proxy,
        token,
        [("getPage", (args.page,)), ("getPageInfo", (args.page,))],
    )
    text = body if isinstance(body, str) else str(body)
    return {
        "ok": True,
        "action": "get",
        "name": args.page,
        "url": f"https://wiki.qis.family/{_quote_page(args.page)}",
        "acl": ACL_RE.findall(text),
        "info": _serialize(info) if isinstance(info, dict) else info,
        "text": text,
    }


def cmd_info(proxy: xmlrpc.client.ServerProxy, token: str, args: argparse.Namespace) -> dict:
    info = _multicall(proxy, token, [("getPageInfo", (args.page,))])[0]
    return {
        "ok": True,
        "action": "info",
        "name": args.page,
        "url": f"https://wiki.qis.family/{_quote_page(args.page)}",
        "info": _serialize(info) if isinstance(info, dict) else info,
    }


def cmd_list(proxy: xmlrpc.client.ServerProxy, token: str, args: argparse.Namespace) -> dict:
    pages = _multicall(proxy, token, [("getAllPages", ())])[0]
    if not isinstance(pages, list):
        raise SystemExit(f"Unexpected getAllPages result: {type(pages).__name__}")
    names = sorted(str(p) for p in pages)
    if args.contains:
        needle = args.contains.lower()
        names = [n for n in names if needle in n.lower()]
    total = len(names)
    if args.limit:
        names = names[: args.limit]
    return {
        "ok": True,
        "action": "list",
        "count": total,
        "returned": len(names),
        "pages": names,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search and fetch pages from wiki.qis.family via Moin XML-RPC.",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("MOIN_URL", DEFAULT_URL),
        help=f"XML-RPC endpoint (default: {DEFAULT_URL})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Full-text search (searchPages)")
    search.add_argument("query", help="Search query")
    search.add_argument("--limit", type=int, default=20, help="Max hits (default 20)")
    search.add_argument(
        "--fetch",
        action="store_true",
        help="Also fetch matching page bodies (excerpts by default)",
    )
    search.add_argument(
        "--full",
        action="store_true",
        help="With --fetch, return full page text instead of excerpts",
    )
    search.add_argument(
        "--excerpt-chars",
        type=int,
        default=1200,
        help="Excerpt size when using --fetch without --full (default 1200)",
    )

    get_p = sub.add_parser("get", help="Fetch one page's wiki markup")
    get_p.add_argument("page", help="Exact page name")

    info = sub.add_parser("info", help="Fetch page metadata")
    info.add_argument("page", help="Exact page name")

    list_p = sub.add_parser("list", help="List page titles (getAllPages)")
    list_p.add_argument("--contains", help="Filter titles containing this substring")
    list_p.add_argument("--limit", type=int, default=0, help="Max titles to return (0=all)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    user, password = _require_env()
    proxy = _proxy(args.url)
    try:
        token = _auth_token(proxy, user, password)
        if args.command == "search":
            payload = cmd_search(proxy, token, args)
        elif args.command == "get":
            payload = cmd_get(proxy, token, args)
        elif args.command == "info":
            payload = cmd_info(proxy, token, args)
        elif args.command == "list":
            payload = cmd_list(proxy, token, args)
        else:
            parser.error(f"unknown command: {args.command}")
    except xmlrpc.client.Fault as exc:
        print(json.dumps({"ok": False, "error": f"XML-RPC fault: {exc.faultString}"}))
        return 1
    except xmlrpc.client.ProtocolError as exc:
        print(json.dumps({"ok": False, "error": f"XML-RPC protocol error: {exc.errcode} {exc.errmsg}"}))
        return 1
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"Network error: {exc}"}))
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
