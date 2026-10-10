---
name: moin-wiki
description: >-
  Searches and reads the private MoinMoin wiki at wiki.qis.family over XML-RPC
  using MOIN_USERNAME and MOIN_PASSWORD. Use when the user asks about WiQi /
  wiki.qis.family content, or to look up home/network/finance/identity notes
  stored on that wiki.
---

# Moin Wiki (wiki.qis.family)

When the user asks to search or look up information on the personal Moin wiki
(`wiki.qis.family` / WiQi), use this helper immediately. Do not scrape HTML login
pages; do not invent wiki content from memory.

## Required env vars

- `MOIN_USERNAME` — Moin login name
- `MOIN_PASSWORD` — Moin password

Optional:

- `MOIN_URL` — XML-RPC endpoint (default `https://wiki.qis.family/?action=xmlrpc2`)

If username/password are missing, stop and tell the user to export them. Never
print the password (or a session token).

## Auth model (important)

Moin XML-RPC auth only sticks when `applyAuthToken` is in the **same MultiCall**
as the data method. The helper does this for you. Do not call bare `getAllPages`
/ `searchPages` after a separate `applyAuthToken` — you will only see public pages.

## Steps

1. Confirm credentials are present (presence only; do not echo values):

```bash
test -n "$MOIN_USERNAME" && test -n "$MOIN_PASSWORD" && echo ok
```

2. Prefer **search** for questions; use **get** when you already know the page title:

```bash
# Full-text search (titles + body). JSON hits with name/snippet/url.
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py search "QUERY"

# Search and pull excerpts from matching pages
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py search "QUERY" --fetch

# Search and pull full page markup for matches
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py search "QUERY" --fetch --full --limit 5

# Exact page fetch
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py get "Page Name"

# Page metadata only
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py info "Page Name"

# List / filter titles
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py list --contains thermostat
python3 .cursor/skills/moin-wiki/scripts/moin-wiki.py list --limit 50
```

3. Answer from the JSON stdout (`hits`, `pages[].text`, `acl`). Quote page names
   and link as `https://wiki.qis.family/<urlencoded-name>` when useful.
4. On non-zero exit, summarize the stderr / JSON `error` without leaking credentials.

## Workflow tips

- Start with `search "keywords"`; if snippets are thin, re-run with `--fetch` (or
  `get` on the best hit).
- System/help pages often carry `#acl -All:write Default`. Content pages may have
  no page ACL (wiki default). Treat ACLs as informational unless asked.
- Page names are exact and case-sensitive for `get` / `info`.
- Keep answers concise: cite the page name, then the relevant facts from the markup.

## Notes

- Endpoint: `https://wiki.qis.family/?action=xmlrpc2`
- Prefer the helper over ad-hoc `curl`/HTML scraping so MultiCall auth stays correct.
- Read-only by default — this skill does not edit or delete wiki pages.
