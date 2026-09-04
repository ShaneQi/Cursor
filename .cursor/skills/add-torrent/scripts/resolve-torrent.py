#!/usr/bin/env python3
"""Resolve torrent title and kind (movie|show) from an enclosure URL or magnet."""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


RELEASE_TAGS = re.compile(
    r"(?i)[.\s_-]("
    r"720p|1080p|2160p|480p|576p|4k|uhd|hdr|dv|hdr10|"
    r"web[\s_.-]?dl|webrip|bluray|blu[\s_.-]?ray|hdtv|hdrip|dvdrip|bdrip|brrip|"
    r"x264|x265|h264|h265|hevc|avc|aac|dts|truehd|atmos|"
    r"proper|repack|extended|unrated|directors[\s_.-]?cut|"
    r"internal|limited|remux|multi|dual[\s_.-]?audio|"
    r"complete|pack"
    r")\b.*"
)

SHOW_PATTERNS = [
    re.compile(r"(?i)\bS\d{1,2}E\d{1,2}\b"),
    re.compile(r"(?i)\b\d{1,2}x\d{2}\b"),
    re.compile(r"(?i)\bSeason[\s._-]*\d+\b"),
    re.compile(r"(?i)\bEpisode[\s._-]*\d+\b"),
    re.compile(r"(?i)\bE\d{2,3}\b"),
]


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


def torrent_name_from_bytes(data: bytes) -> str | None:
    try:
        meta, _ = bdecode(data)
    except Exception:
        return None
    if not isinstance(meta, dict):
        return None
    info = meta.get(b"info")
    if not isinstance(info, dict):
        return None
    name = info.get(b"name")
    if isinstance(name, bytes):
        return name.decode("utf-8", "replace")
    return None


def magnet_display_name(link: str) -> str | None:
    parsed = urllib.parse.urlparse(link)
    qs = urllib.parse.parse_qs(parsed.query)
    dn = qs.get("dn") or qs.get("DN")
    if not dn:
        return None
    return urllib.parse.unquote_plus(dn[0])


def clean_title(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    base = re.sub(r"\.torrent$", "", base, flags=re.I)
    base = RELEASE_TAGS.sub("", base)
    base = base.replace(".", " ").replace("_", " ").replace("-", " ")
    base = re.sub(r"\s+", " ", base).strip(" -._")
    # Drop trailing year for lookup helpers, keep original for API when needed
    return base


def year_from_name(name: str) -> str | None:
    m = re.search(r"\b(19\d{2}|20\d{2})\b", name)
    return m.group(1) if m else None


def looks_like_show(name: str) -> bool:
    return any(p.search(name) for p in SHOW_PATTERNS)


def tvmaze_suggests_show(title: str, year: str | None) -> bool | None:
    """Return True/False if TVMaze gives a clear signal, else None."""
    q = clean_title(title)
    q = re.sub(r"\b(19\d{2}|20\d{2})\b", "", q).strip()
    if not q:
        return None
    url = "https://api.tvmaze.com/search/shows?" + urllib.parse.urlencode({"q": q})
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            results = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    if not results:
        return None

    q_tokens = {t.lower() for t in re.findall(r"[a-z0-9]+", q, flags=re.I)}
    for item in results[:5]:
        show = item.get("show") or {}
        name = (show.get("name") or "").lower()
        name_tokens = set(re.findall(r"[a-z0-9]+", name))
        if not q_tokens or not name_tokens:
            continue
        # Require strong token overlap
        overlap = len(q_tokens & name_tokens) / max(len(q_tokens), 1)
        if overlap < 0.6:
            continue
        if year:
            premiered = show.get("premiered") or ""
            # Annual pageants / long-running shows: year match on episode is enough signal
            # that this title exists as a TV show in metadata.
            show_id = show.get("id")
            if show_id and episode_year_exists(show_id, year):
                return True
            if premiered.startswith(year):
                return True
        else:
            return True
    return None


def episode_year_exists(show_id: int, year: str) -> bool:
    url = f"https://api.tvmaze.com/shows/{show_id}/episodes"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            episodes = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    for ep in episodes:
        airdate = ep.get("airdate") or ""
        name = ep.get("name") or ""
        if airdate.startswith(year) or year in name:
            return True
    return False


def normalize_kind(kind: str | None) -> str | None:
    if kind is None:
        return None
    k = kind.strip().lower()
    if k in {"movie", "movies", "film", "films"}:
        return "movie"
    if k in {"show", "shows", "tv", "series"}:
        return "show"
    raise SystemExit(f'Unknown kind "{kind}". Use movie or show.')


def resolve(link: str, kind: str | None, title: str | None) -> dict[str, str]:
    resolved_title = title
    source_name = None

    if link.lower().startswith("magnet:"):
        source_name = magnet_display_name(link)
    else:
        data = fetch_torrent(link)
        source_name = torrent_name_from_bytes(data)

    if not resolved_title:
        if not source_name:
            raise SystemExit("Could not determine torrent title from link; pass NAME explicitly.")
        resolved_title = source_name

    resolved_kind = normalize_kind(kind)
    if not resolved_kind:
        probe = source_name or resolved_title
        if looks_like_show(probe):
            resolved_kind = "show"
        else:
            suggestion = tvmaze_suggests_show(probe, year_from_name(probe))
            if suggestion is True:
                resolved_kind = "show"
            else:
                # Default: movie when no TV signal
                resolved_kind = "movie"

    return {"kind": resolved_kind, "title": resolved_title, "enclosure": link}


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: resolve-torrent.py LINK [KIND] [TITLE]",
            file=sys.stderr,
        )
        raise SystemExit(2)

    link = sys.argv[1]
    kind = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    title = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None

    if kind in {"", "-"}:
        kind = None
    if title in {"", "-"}:
        title = None

    print(json.dumps(resolve(link, kind, title), ensure_ascii=False))


if __name__ == "__main__":
    main()
