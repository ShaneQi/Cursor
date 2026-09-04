---
name: add-movie-torrent
description: >-
  Adds a movie torrent by POSTing title and enclosure URL to the torrents
  worker API. Use immediately when the user provides a movie name/title and a
  magnet or torrent link, or asks to add/submit a movie torrent.
---

# Add Movie Torrent

When the user gives a **name** (title) and a **link** (magnet or torrent URL), run the add request right away. Do not ask for confirmation unless the title or link is missing/ambiguous.

## Steps

1. Extract `NAME` (movie title) and `LINK` (enclosure URL) from the message.
2. Ensure `PATH_SECRET` is set in the environment. If missing, stop and tell the user to export it.
3. Run the helper from this skill (preferred — handles JSON escaping):

```bash
.cursor/skills/add-movie-torrent/scripts/add-movie.sh "NAME" "LINK"
```

4. Report the HTTP response briefly (success vs error). Do not print `PATH_SECRET`.

## Curl equivalent

```bash
curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/movies/add" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"NAME\",\"enclosure\":\"LINK\"}"
```

## Notes

- `PATH_SECRET` comes from the environment — never hardcode it.
- Escape/quoting: always prefer the helper script so magnets with `&`/`?` stay valid JSON.
