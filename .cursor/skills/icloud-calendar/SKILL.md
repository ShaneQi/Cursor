---
name: icloud-calendar
description: >-
  Reads and writes iCloud Calendar via CalDAV using ICLOUD_EMAIL (Apple ID)
  and ICLOUD_CALDAV (app-specific password). Default target calendar is "Qi".
  Use when the user asks to fetch, list, create, or delete iCloud calendar
  events, or otherwise interact with their iCloud calendar.
---

# iCloud Calendar (CalDAV)

When the user asks about their iCloud calendar (list events, what’s on the
schedule, create/delete an event), run the helper immediately. Do not invent
events. Never print `ICLOUD_EMAIL` or `ICLOUD_CALDAV`.

## Required env vars

- `ICLOUD_EMAIL` — Apple ID email used for iCloud
- `ICLOUD_CALDAV` — Apple app-specific password

If either is missing, stop and tell the user to export it.

## Defaults

- Target calendar display name: **`Qi`** (override with `--calendar`)
- Naive datetimes use timezone **`America/Chicago`**
- `list-events` window: today → +14 days (override with `--start` / `--end` / `--days`)

## Steps

1. Confirm env vars are set (presence only; do not echo values):

```bash
test -n "$ICLOUD_EMAIL" && test -n "$ICLOUD_CALDAV" && echo ok
```

2. Run the helper. Stdout is JSON.

### List calendars

```bash
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py list-calendars
```

### List events (default calendar Qi)

```bash
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py list-events
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py list-events --days 7
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py list-events \
  --start 2026-10-10 --end 2026-10-24
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py \
  --calendar "Qi" list-events --days 30
```

### Create an event

```bash
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py create-event \
  --summary "Title" \
  --start "2026-10-15T09:00" \
  --end "2026-10-15T10:00" \
  --location "Place" \
  --description "Notes"
```

All-day:

```bash
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py create-event \
  --summary "Title" \
  --start 2026-10-15 \
  --all-day
```

If `--end` is omitted for timed events, duration defaults to 1 hour
(`--duration-hours`).

### Delete an event

Prefer `--href` from a prior `list-events` result. `--uid` also works (script
searches a window to resolve the href):

```bash
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py delete-event \
  --href "/…/calendars/…/UID.ics"
python3 .cursor/skills/icloud-calendar/scripts/icloud-calendar.py delete-event \
  --uid "EVENT-UID"
```

3. Report briefly from the JSON (`ok`, event summaries/times, `uid`/`href` on
   writes). On non-zero exit, summarize stderr without leaking credentials.

## Notes

- Prefer this helper over ad-hoc CalDAV/`curl` so discovery and auth stay consistent.
- Only VEVENT calendars are useful for schedule queries; reminders/VTODO collections may appear in `list-calendars`.
- Datetime inputs: ISO-8601 (`2026-10-15T09:00` or with offset), `YYYY-MM-DD`, or `YYYYMMDDTHHMMSSZ`.
