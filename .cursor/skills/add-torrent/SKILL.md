---
name: add-torrent
description: >-
  Adds a movie or TV show torrent by POSTing title and enclosure URL to the
  torrents worker API. Use immediately when the user provides a torrent/magnet
  link or tracker page link (optionally with movie/show type and title), or asks
  to add/submit a movie or show torrent.
---

# Add Torrent (Movie or Show)

When the user gives a **link** (magnet, direct `.torrent` URL, or tracker page
URL), run the add request right away. Type and title are optional from the user;
if omitted, resolve them as described below before posting.

## Parameter order

1. `LINK` (enclosure or page URL) — required
2. `KIND` (`movie` or `show`) — optional from the user
3. `NAME` (title) — optional from the user

Prefer explicit user cues for kind when present (`movie`, `film`, `show`, `series`, `TV`, `episode`).

## Steps

1. Ensure required env vars are set:
   - `TORRENT_PATH_SECRET` — API path secret. If missing, stop and tell the user to export it.
   - `TTG_TOKEN` — required when the link is a ToTheGlory **page** URL (`/t/{id}/`). Do not print this value.
2. If `KIND` or `NAME` is missing, inspect the link first:

```bash
python3 .cursor/skills/add-torrent/scripts/resolve-torrent.py "LINK"
```

This prints JSON with `title`, `files`, and `enclosure` (the direct download URL to post).

3. If `NAME` is missing, use the resolved `title` as `NAME`.
4. If `KIND` is missing, **you (the language model) must decide** `movie` or `show`:
   - Use the torrent `title` and `files` as primary evidence.
   - Release tags like `S01E02` / `1x02` usually mean `show`.
   - A single feature-length `.mkv`/`.mp4` with a film-style name usually means `movie`.
   - Ambiguous titles (pageants, concerts, stand-up, documentaries, TV specials): check IMDb / TheTVDB / TMDB when needed. Map **TV Series**, **TV Mini Series**, **TV Special**, and episodes → `show`; map theatrical/feature **Movie** → `movie`.
   - Do **not** fall back to regex/TVMaze auto-classification scripts; decide `KIND` yourself, then pass it into `add-torrent.sh`.
5. Post with the helper (handles JSON escaping and page-link rewriting):

```bash
.cursor/skills/add-torrent/scripts/add-torrent.sh "LINK" "KIND" "NAME"
```

Examples:

```bash
# Direct torrent / magnet
.cursor/skills/add-torrent/scripts/add-torrent.sh "magnet:?xt=..." "movie" "Inception"
.cursor/skills/add-torrent/scripts/add-torrent.sh "https://totheglory.im/dl/595252/${TTG_TOKEN}" "show"

# Tracker page link (rewritten to /dl/{id}/{TTG_TOKEN} automatically)
.cursor/skills/add-torrent/scripts/add-torrent.sh "https://totheglory.im/t/595252/" "show"
```

If `add-torrent.sh` is run without `KIND`, it prints torrent metadata on stderr and exits `2` so you can choose `KIND` and re-run.

6. Report the HTTP response briefly (success vs error), including the kind/title you used. Do not print `TORRENT_PATH_SECRET` or `TTG_TOKEN`.

## Page link → direct torrent link

Some tracker links are **detail pages**, not downloadable `.torrent` files, and may be inaccessible to the agent. Rewrite them before fetch/POST.

ToTheGlory:

| Kind | Example |
|------|---------|
| Page | `https://totheglory.im/t/595252/` |
| Direct | `https://totheglory.im/dl/595252/{TTG_TOKEN}` |

`resolve-torrent.py` / `add-torrent.sh` perform this rewrite when `TTG_TOKEN` is set. Always POST the **direct** `enclosure` URL to the worker API, never the page URL.

## Curl equivalents

Movies:

```bash
curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${TORRENT_PATH_SECRET}/movies/add" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"NAME\",\"enclosure\":\"DIRECT_LINK\"}"
```

Shows:

```bash
curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${TORRENT_PATH_SECRET}/shows/add" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"NAME\",\"enclosure\":\"DIRECT_LINK\"}"
```

## Notes

- Parameter order is always: **link**, then optional **type**, then optional **name**.
- `TORRENT_PATH_SECRET` and `TTG_TOKEN` come from the environment — never hardcode or print them.
- Escape/quoting: always prefer the helper script so magnets with `&`/`?` stay valid JSON.
- The only API difference between movies and shows is the path segment (`movies` vs `shows`).
