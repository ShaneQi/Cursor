---
name: add-torrent
description: >-
  Adds a movie or TV show torrent by POSTing title and enclosure URL to the
  torrents worker API. Use immediately when the user provides a torrent/magnet
  link (optionally with movie/show type and title), or asks to add/submit a
  movie or show torrent.
---

# Add Torrent (Movie or Show)

When the user gives a **link** (magnet or torrent URL), run the add request
right away. Type and title are optional.

## Steps

1. Extract from the message, in this order of priority:
   - `LINK` (enclosure URL) — required
   - `KIND` (`movie` or `show`) — optional
   - `NAME` (title) — optional
2. Prefer explicit cues for kind when present (`movie`, `film`, `show`, `series`, `TV`, `episode`).
3. Ensure `PATH_SECRET` is set in the environment. If missing, stop and tell the user to export it.
4. Run the helper from this skill (preferred — handles JSON escaping and auto-detect):

```bash
.cursor/skills/add-torrent/scripts/add-torrent.sh "LINK" [KIND] [NAME]
```

Examples:

```bash
# Fully specified
.cursor/skills/add-torrent/scripts/add-torrent.sh "magnet:?xt=..." "movie" "Inception"
.cursor/skills/add-torrent/scripts/add-torrent.sh "https://example.com/file.torrent" "show" "Severance"

# Link only — script fetches the torrent, uses its title, and infers movie vs show
.cursor/skills/add-torrent/scripts/add-torrent.sh "https://example.com/file.torrent"

# Link + kind, title inferred from torrent
.cursor/skills/add-torrent/scripts/add-torrent.sh "https://example.com/file.torrent" "show"
```

5. Report the HTTP response briefly (success vs error), including the resolved
   kind/title when they were inferred. Do not print `PATH_SECRET`.

## Auto-detect (when KIND and/or NAME are omitted)

The helper script (`resolve-torrent.py` via `add-torrent.sh`):

1. Downloads the `.torrent` (or reads a magnet `dn=`) and takes `info.name` as the title when `NAME` is omitted.
2. Infers kind when `KIND` is omitted:
   - Season/episode patterns in the name (`S01E02`, `1x02`, etc.) → `show`
   - Otherwise checks TVMaze for a matching TV show / episode year → `show` when matched
   - Otherwise defaults to `movie`

If the link cannot be fetched or metadata is insufficient, pass `KIND` and/or `NAME` explicitly.

## Curl equivalents

Movies:

```bash
curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/movies/add" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"NAME\",\"enclosure\":\"LINK\"}"
```

Shows:

```bash
curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/shows/add" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"NAME\",\"enclosure\":\"LINK\"}"
```

## Notes

- Parameter order is always: **link**, then optional **type**, then optional **name**.
- `PATH_SECRET` comes from the environment — never hardcode it.
- Escape/quoting: always prefer the helper script so magnets with `&`/`?` stay valid JSON.
- The only API difference between movies and shows is the path segment (`movies` vs `shows`).
