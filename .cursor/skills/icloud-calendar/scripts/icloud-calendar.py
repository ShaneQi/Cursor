#!/usr/bin/env python3
"""Interact with iCloud Calendar via CalDAV.

Auth (required env vars — never printed):
  ICLOUD_EMAIL   — Apple ID email
  ICLOUD_CALDAV  — app-specific password

Default target calendar display name: Qi
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import sys
import uuid
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

CALDAV_ROOT = "https://caldav.icloud.com/"
DEFAULT_CALENDAR = "Qi"
DEFAULT_TZ = "America/Chicago"
USER_AGENT = "cursor-icloud-calendar/1.0"

NS = {
    "d": "DAV:",
    "c": "urn:ietf:params:xml:ns:caldav",
    "cs": "http://calendarserver.org/ns/",
    "ic": "http://apple.com/ns/ical/",
}


class CalDAVError(SystemExit):
    pass


@dataclass
class CalendarInfo:
    href: str
    name: str
    components: list[str]
    color: str = ""


def _require_env() -> tuple[str, str]:
    email = os.environ.get("ICLOUD_EMAIL", "").strip()
    password = os.environ.get("ICLOUD_CALDAV", "").strip()
    missing = [n for n, v in (("ICLOUD_EMAIL", email), ("ICLOUD_CALDAV", password)) if not v]
    if missing:
        raise CalDAVError(f"Missing required env var(s): {', '.join(missing)}")
    return email, password


def _auth_header(email: str, password: str) -> str:
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return f"Basic {token}"


def _origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return "https://caldav.icloud.com"
    return f"{parsed.scheme}://{parsed.netloc}"


def _absolute_url(href: str, base: str = CALDAV_ROOT) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if not href.startswith("/"):
        href = "/" + href
    return _origin(base) + href


def _request(
    method: str,
    url: str,
    *,
    auth: str,
    body: str | bytes | None = None,
    depth: str | int | None = None,
    content_type: str = "application/xml; charset=utf-8",
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    headers = {
        "Authorization": auth,
        "User-Agent": USER_AGENT,
    }
    data: bytes | None
    if body is None:
        data = None
    else:
        data = body.encode("utf-8") if isinstance(body, str) else body
        headers["Content-Type"] = content_type
    if depth is not None:
        headers["Depth"] = str(depth)
    if extra_headers:
        headers.update(extra_headers)

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise CalDAVError(f"CalDAV HTTP {exc.code} {exc.reason} for {method} {url}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise CalDAVError(f"Failed to reach iCloud CalDAV: {exc.reason}") from exc


def _xml(data: bytes) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise CalDAVError(f"Invalid CalDAV XML response: {exc}") from exc


def _text(el: ET.Element | None, path: str, default: str = "") -> str:
    if el is None:
        return default
    found = el.find(path, NS)
    if found is None or found.text is None:
        return default
    return found.text.strip()


def discover(auth: str) -> tuple[str, str]:
    """Return (principal_url, calendar_home_url)."""
    body = """<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop><d:current-user-principal/></d:prop>
</d:propfind>"""
    _, data, _ = _request("PROPFIND", CALDAV_ROOT, auth=auth, body=body, depth=0)
    root = _xml(data)
    principal = _text(root, ".//d:current-user-principal/d:href")
    if not principal:
        raise CalDAVError("Could not discover CalDAV current-user-principal")
    principal_url = _absolute_url(principal, CALDAV_ROOT)

    body = """<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><c:calendar-home-set/></d:prop>
</d:propfind>"""
    _, data, _ = _request("PROPFIND", principal_url, auth=auth, body=body, depth=0)
    root = _xml(data)
    home = _text(root, ".//c:calendar-home-set//d:href")
    if not home:
        raise CalDAVError("Could not discover CalDAV calendar-home-set")
    return principal_url, _absolute_url(home, principal_url)


def list_calendars(auth: str, home_url: str) -> list[CalendarInfo]:
    body = """<?xml version="1.0" encoding="UTF-8"?>
<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"
            xmlns:cs="http://calendarserver.org/ns/" xmlns:ic="http://apple.com/ns/ical/">
  <d:prop>
    <d:displayname/>
    <d:resourcetype/>
    <c:supported-calendar-component-set/>
    <ic:calendar-color/>
  </d:prop>
</d:propfind>"""
    _, data, _ = _request("PROPFIND", home_url, auth=auth, body=body, depth=1)
    root = _xml(data)
    calendars: list[CalendarInfo] = []
    for resp in root.findall("d:response", NS):
        href = _text(resp, "d:href")
        rtype = resp.find(".//d:resourcetype", NS)
        if rtype is None or rtype.find("c:calendar", NS) is None:
            continue
        comps = [
            c.get("name", "")
            for c in resp.findall(".//c:supported-calendar-component-set/c:comp", NS)
            if c.get("name")
        ]
        calendars.append(
            CalendarInfo(
                href=href,
                name=_text(resp, ".//d:displayname"),
                components=comps,
                color=_text(resp, ".//ic:calendar-color"),
            )
        )
    return calendars


def resolve_calendar(calendars: list[CalendarInfo], name: str) -> CalendarInfo:
    wanted = name.strip().casefold()
    for cal in calendars:
        if cal.name.casefold() == wanted:
            return cal
    available = ", ".join(repr(c.name) for c in calendars) or "(none)"
    raise CalDAVError(f"Calendar {name!r} not found. Available: {available}")


def _unfold_ics(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n[ \t]", "", text)


def _unescape_ics(value: str) -> str:
    return (
        value.replace("\\\\", "\\")
        .replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
    )


def _escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _parse_vevents(ics: str) -> list[dict[str, str]]:
    ics = _unfold_ics(ics)
    events: list[dict[str, str]] = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics, re.S):

        def field(key: str) -> tuple[str, str]:
            match = re.search(rf"^{re.escape(key)}([^:]*):(.*)$", block, re.M)
            if not match:
                return "", ""
            return match.group(1), match.group(2).strip()

        params_start, dtstart = field("DTSTART")
        params_end, dtend = field("DTEND")
        _, summary = field("SUMMARY")
        _, location = field("LOCATION")
        _, description = field("DESCRIPTION")
        _, uid = field("UID")
        _, status = field("STATUS")
        _, rrule = field("RRULE")
        events.append(
            {
                "uid": uid,
                "summary": _unescape_ics(summary),
                "location": _unescape_ics(location),
                "description": _unescape_ics(description),
                "dtstart": dtstart,
                "dtend": dtend,
                "dtstart_params": params_start,
                "dtend_params": params_end,
                "status": status,
                "rrule": rrule,
            }
        )
    return events


def _parse_window(start: str | None, end: str | None, days: int) -> tuple[str, str]:
    """Return CalDAV time-range stamps in UTC (YYYYMMDDTHHMMSSZ)."""
    now = datetime.now(timezone.utc)
    if start:
        start_dt = _parse_user_dt(start, default_tz=DEFAULT_TZ).astimezone(timezone.utc)
    else:
        start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if end:
        end_dt = _parse_user_dt(end, default_tz=DEFAULT_TZ).astimezone(timezone.utc)
    else:
        end_dt = start_dt + timedelta(days=days)
    if end_dt <= start_dt:
        raise CalDAVError("--end must be after --start")
    return (
        start_dt.strftime("%Y%m%dT%H%M%SZ"),
        end_dt.strftime("%Y%m%dT%H%M%SZ"),
    )


def _parse_user_dt(value: str, *, default_tz: str) -> datetime:
    value = value.strip()
    if re.fullmatch(r"\d{8}T\d{6}Z", value):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}$", value):
        d = date.fromisoformat(value)
        return datetime(d.year, d.month, d.day, tzinfo=ZoneInfo(default_tz))
    # ISO-8601 with optional offset / Z
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CalDAVError(
            f"Invalid datetime {value!r}. Use ISO-8601, YYYY-MM-DD, or YYYYMMDDTHHMMSSZ."
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(default_tz))
    return dt


def list_events(
    auth: str,
    calendar: CalendarInfo,
    *,
    start: str,
    end: str,
    home_url: str,
) -> list[dict[str, Any]]:
    report = f"""<?xml version="1.0" encoding="UTF-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop>
    <d:getetag/>
    <c:calendar-data/>
  </d:prop>
  <c:filter>
    <c:comp-filter name="VCALENDAR">
      <c:comp-filter name="VEVENT">
        <c:time-range start="{start}" end="{end}"/>
      </c:comp-filter>
    </c:comp-filter>
  </c:filter>
</c:calendar-query>"""
    url = _absolute_url(calendar.href, home_url)
    _, data, _ = _request("REPORT", url, auth=auth, body=report, depth=1)
    root = _xml(data)
    events: list[dict[str, Any]] = []
    for resp in root.findall("d:response", NS):
        href = _text(resp, "d:href")
        etag = _text(resp, ".//d:getetag")
        caldata = _text(resp, ".//c:calendar-data")
        if not caldata:
            # ElementTree may leave large text; try find text again with itertext
            node = resp.find(".//c:calendar-data", NS)
            caldata = "".join(node.itertext()).strip() if node is not None else ""
        for ev in _parse_vevents(caldata):
            events.append(
                {
                    **ev,
                    "calendar": calendar.name,
                    "href": href,
                    "etag": etag,
                }
            )
    events.sort(key=lambda e: (e.get("dtstart") or "", e.get("summary") or ""))
    return events


def _fold_ics_line(line: str) -> str:
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(parts)


def _ics_dt(dt: datetime, *, all_day: bool) -> tuple[str, str]:
    """Return (prop_suffix_with_colon_or_params, value) for DTSTART/DTEND."""
    if all_day:
        return ";VALUE=DATE:", dt.date().isoformat().replace("-", "")
    local = dt.astimezone(ZoneInfo(DEFAULT_TZ))
    return f";TZID={DEFAULT_TZ}:", local.strftime("%Y%m%dT%H%M%S")


def build_vevent_ics(
    *,
    uid: str,
    summary: str,
    start: datetime,
    end: datetime,
    all_day: bool,
    location: str,
    description: str,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    start_suffix, start_val = _ics_dt(start, all_day=all_day)
    end_suffix, end_val = _ics_dt(end, all_day=all_day)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cursor//iCloud Calendar Skill//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART{start_suffix}{start_val}",
        f"DTEND{end_suffix}{end_val}",
        f"SUMMARY:{_escape_ics(summary)}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape_ics(location)}")
    if description:
        lines.append(f"DESCRIPTION:{_escape_ics(description)}")
    lines.extend(["END:VEVENT", "END:VCALENDAR", ""])
    return "\r\n".join(_fold_ics_line(line) for line in lines if line or line == "")


def create_event(
    auth: str,
    calendar: CalendarInfo,
    *,
    home_url: str,
    summary: str,
    start: datetime,
    end: datetime,
    all_day: bool,
    location: str,
    description: str,
) -> dict[str, Any]:
    if end <= start and not all_day:
        raise CalDAVError("Event end must be after start")
    if all_day and end < start:
        raise CalDAVError("All-day end date must be on or after start date")
    # For all-day, CalDAV DTEND is exclusive; if user passed same day, bump +1
    if all_day and end.date() == start.date():
        end = end + timedelta(days=1)

    object_id = str(uuid.uuid4()).upper()
    uid = f"{object_id}@cursor-icloud-calendar"
    ics = build_vevent_ics(
        uid=uid,
        summary=summary,
        start=start,
        end=end,
        all_day=all_day,
        location=location,
        description=description,
    )
    href = calendar.href if calendar.href.endswith("/") else calendar.href + "/"
    # Filename must be a simple token; keep @ out of the path segment.
    event_url = _absolute_url(href + object_id + ".ics", home_url)
    status, _, headers = _request(
        "PUT",
        event_url,
        auth=auth,
        body=ics,
        content_type="text/calendar; charset=utf-8",
        extra_headers={"If-None-Match": "*"},
    )
    return {
        "ok": True,
        "status": status,
        "uid": uid,
        "href": event_url,
        "etag": headers.get("ETag") or headers.get("etag") or "",
        "calendar": calendar.name,
        "summary": summary,
        "dtstart": start.isoformat(),
        "dtend": end.isoformat(),
        "all_day": all_day,
        "location": location,
        "description": description,
    }


def delete_event(auth: str, href: str, *, home_url: str) -> dict[str, Any]:
    url = _absolute_url(href, home_url)
    status, _, _ = _request("DELETE", url, auth=auth)
    return {"ok": True, "status": status, "href": url}


def find_event_href(
    auth: str,
    calendar: CalendarInfo,
    *,
    home_url: str,
    uid: str | None,
    href: str | None,
    start: str,
    end: str,
) -> str:
    if href:
        return href
    if not uid:
        raise CalDAVError("Provide --uid or --href to delete an event")
    events = list_events(auth, calendar, start=start, end=end, home_url=home_url)
    matches = [e for e in events if e.get("uid") == uid]
    if not matches:
        raise CalDAVError(f"No event with uid={uid!r} in the search window")
    # Prefer exact .ics href
    return matches[0]["href"]


def _print(data: Any) -> None:
    json.dump(data, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def _session(calendar_name: str) -> tuple[str, str, list[CalendarInfo], CalendarInfo]:
    email, password = _require_env()
    auth = _auth_header(email, password)
    _, home = discover(auth)
    calendars = list_calendars(auth, home)
    target = resolve_calendar(calendars, calendar_name)
    return auth, home, calendars, target


def cmd_list_calendars(_: argparse.Namespace) -> None:
    email, password = _require_env()
    auth = _auth_header(email, password)
    _, home = discover(auth)
    calendars = list_calendars(auth, home)
    _print(
        {
            "ok": True,
            "calendar_home": home,
            "calendars": [
                {
                    "name": c.name,
                    "href": c.href,
                    "components": c.components,
                    "color": c.color,
                }
                for c in calendars
            ],
        }
    )


def cmd_list_events(args: argparse.Namespace) -> None:
    auth, home, _, calendar = _session(args.calendar)
    start, end = _parse_window(args.start, args.end, args.days)
    events = list_events(auth, calendar, start=start, end=end, home_url=home)
    _print(
        {
            "ok": True,
            "calendar": calendar.name,
            "href": calendar.href,
            "window": {"start": start, "end": end},
            "count": len(events),
            "events": events,
        }
    )


def cmd_create_event(args: argparse.Namespace) -> None:
    auth, home, _, calendar = _session(args.calendar)
    start = _parse_user_dt(args.start, default_tz=args.timezone)
    if args.end:
        end = _parse_user_dt(args.end, default_tz=args.timezone)
    elif args.all_day:
        end = start + timedelta(days=1)
    else:
        end = start + timedelta(hours=args.duration_hours)
    result = create_event(
        auth,
        calendar,
        home_url=home,
        summary=args.summary,
        start=start,
        end=end,
        all_day=args.all_day,
        location=args.location or "",
        description=args.description or "",
    )
    _print(result)


def cmd_delete_event(args: argparse.Namespace) -> None:
    auth, home, _, calendar = _session(args.calendar)
    start, end = _parse_window(args.start, args.end, args.days)
    href = find_event_href(
        auth,
        calendar,
        home_url=home,
        uid=args.uid,
        href=args.href,
        start=start,
        end=end,
    )
    _print(delete_event(auth, href, home_url=home))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="iCloud Calendar via CalDAV")
    parser.add_argument(
        "--calendar",
        default=DEFAULT_CALENDAR,
        help=f'Target calendar display name (default: "{DEFAULT_CALENDAR}")',
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-calendars", help="List all calendars")

    p_list = sub.add_parser("list-events", help="List events in a time window")
    p_list.add_argument("--start", help="Window start (ISO / YYYY-MM-DD / ...Z)")
    p_list.add_argument("--end", help="Window end (ISO / YYYY-MM-DD / ...Z)")
    p_list.add_argument(
        "--days",
        type=int,
        default=14,
        help="Days ahead from start/today when --end omitted (default: 14)",
    )

    p_create = sub.add_parser("create-event", help="Create an event")
    p_create.add_argument("--summary", required=True, help="Event title")
    p_create.add_argument("--start", required=True, help="Start datetime/date")
    p_create.add_argument("--end", help="End datetime/date")
    p_create.add_argument(
        "--duration-hours",
        type=float,
        default=1.0,
        help="Duration in hours when --end omitted (default: 1)",
    )
    p_create.add_argument("--all-day", action="store_true", help="All-day event")
    p_create.add_argument("--location", default="", help="Location")
    p_create.add_argument("--description", default="", help="Description")
    p_create.add_argument(
        "--timezone",
        default=DEFAULT_TZ,
        help=f"Timezone for naive datetimes (default: {DEFAULT_TZ})",
    )

    p_del = sub.add_parser("delete-event", help="Delete an event by uid or href")
    p_del.add_argument("--uid", help="Event UID")
    p_del.add_argument("--href", help="Event href URL/path")
    p_del.add_argument("--start", help="Search window start when resolving --uid")
    p_del.add_argument("--end", help="Search window end when resolving --uid")
    p_del.add_argument(
        "--days",
        type=int,
        default=365,
        help="Search window days when resolving --uid (default: 365)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    commands = {
        "list-calendars": cmd_list_calendars,
        "list-events": cmd_list_events,
        "create-event": cmd_create_event,
        "delete-event": cmd_delete_event,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
