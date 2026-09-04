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
right away. Type and title are optional from the user; if omitted, resolve them
as described below before posting.

## Parameter order

1. `LINK` (enclosure URL) — required
2. `KIND` (`movie` or `show`) — optional from the user
3. `NAME` (title) — optional from the user

Prefer explicit user cues for kind when present (`movie`, `film`, `show`, `series`, `TV`, `episode`).

## Steps

1. Ensure `PATH_SECRET` is set in the environment. If missing, stop and tell the user to export it.
2. If `KIND` or `NAME` is missing, inspect the link first:

```bash
python3 .cursor/skills/add-torrent/scripts/resolve-torrent.py "LINK"
```

This prints JSON with `title` and `files` from the `.torrent` (or magnet `dn=`).

3. If `NAME` is missing, use the resolved `title` as `NAME`.
4. If `KIND` is missing, **you (the language model) must decide** `movie` or `show`:
   - Use the torrent `title` and `files` as primary evidence.
   - Release tags like `S01E02` / `1x02` usually mean `show`.
   - A single feature-length `.mkv`/`.mp4` with a film-style name usually means `movie`.
   - Ambiguous titles (pageants, concerts, stand-up, documentaries, TV specials): check IMDb / TheTVDB / TMDB when needed. Map **TV Series**, **TV Mini Series**, **TV Special**, and episodes → `show`; map theatrical/feature **Movie** → `movie`.
   - Do **not** fall back to regex/TVMaze auto-classification scripts; decide `KIND` yourself, then pass it into `add-torrent.sh`.
5. Post with the helper (handles JSON escaping):

```bash
.cursor/skills/add-torrent/scripts/add-torrent.sh "LINK" "KIND" "NAME"
```

Examples:

```bash
# Fully specified
.cursor/skills/add-torrent/scripts/add-torrent.sh "magnet:?xt=..." "movie" "Inception"

# Inspect, then add after deciding kind
python3 .cursor/skills/add-torrent/scripts/resolve-torrent.py "https://example.com/file.torrent"
.cursor/skills/add-torrent/scripts/add-torrent.sh "https://example.com/file.torrent" "show" "Severance.S01E01.720p"
```

If `add-torrent.sh` is run without `KIND`, it prints torrent metadata on stderr and exits `2` so you can choose `KIND` and re-run.

6. Report the HTTP response briefly (success vs error), including the kind/title you used. Do not print `PATH_SECRET`.

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
