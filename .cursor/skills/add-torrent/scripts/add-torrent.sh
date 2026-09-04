#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: add-torrent.sh \"ENCLOSURE_URL\" [movie|show] [TITLE]" >&2
  echo "TYPE and TITLE are optional; when omitted they are inferred from the torrent link." >&2
  exit 1
fi

LINK="$1"
KIND="${2:-}"
TITLE="${3:-}"

if [[ -z "${PATH_SECRET:-}" ]]; then
  echo "PATH_SECRET is not set in the environment." >&2
  exit 1
fi

RESOLVED="$(python3 "$SCRIPT_DIR/resolve-torrent.py" "$LINK" "$KIND" "$TITLE")"
PATH_KIND="$(python3 -c 'import json,sys; k=json.load(sys.stdin)["kind"]; print("movies" if k=="movie" else "shows")' <<<"$RESOLVED")"
BODY="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"title":d["title"],"enclosure":d["enclosure"]}))' <<<"$RESOLVED")"

# Brief stderr summary of what was inferred (useful when TYPE/TITLE omitted)
python3 -c 'import json,sys; d=json.load(sys.stdin); print("Resolved: kind=%s title=%s" % (d["kind"], d["title"]), file=sys.stderr)' <<<"$RESOLVED"

curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/${PATH_KIND}/add" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo
