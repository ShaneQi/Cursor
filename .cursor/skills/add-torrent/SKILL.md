---
name: add-torrent
description: >-
  Adds a movie or TV show torrent by POSTing title and enclosure URL to the
  torrents worker API. Use immediately when the user provides a movie or show
  name/title and a magnet or torrent link, or asks to add/submit a movie or
  show torrent.
---

# Add Torrent (Movie or Show)

When the user gives a **name** (title) and a **link** (magnet or torrent URL), run the add request right away. Do not ask for confirmation unless the title, link, or type (movie vs show) is missing/ambiguous.

## Steps

1. Extract `KIND` (`movie` or `show`), `NAME` (title), and `LINK` (enclosure URL) from the message.
   - Prefer explicit cues (`movie`, `film`, `show`, `series`, `TV`, `episode`).
   - If unclear, ask once whether it is a movie or a show before posting.
2. Ensure `PATH_SECRET` is set in the environment. If missing, stop and tell the user to export it.
3. Run the helper from this skill (preferred — handles JSON escaping):

```bash
.cursor/skills/add-torrent/scripts/add-torrent.sh "KIND" "NAME" "LINK"
```

Examples:

```bash
.cursor/skills/add-torrent/scripts/add-torrent.sh "movie" "Inception" "magnet:?xt=..."
.cursor/skills/add-torrent/scripts/add-torrent.sh "show" "Severance" "magnet:?xt=..."
```

4. Report the HTTP response briefly (success vs error). Do not print `PATH_SECRET`.

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

- `PATH_SECRET` comes from the environment — never hardcode it.
- Escape/quoting: always prefer the helper script so magnets with `&`/`?` stay valid JSON.
- The only API difference between movies and shows is the path segment (`movies` vs `shows`).
