#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: add-torrent.sh \"ENCLOSURE_OR_PAGE_URL\" [movie|show] [TITLE]" >&2
  echo "When TYPE or TITLE are omitted, inspect first with resolve-torrent.py;" >&2
  echo "the agent must choose TYPE (movie|show) before posting." >&2
  echo "ToTheGlory /t/{id}/ page links are rewritten to /dl/{id}/\$TTG_TOKEN." >&2
  exit 1
fi

LINK="$1"
KIND="${2:-}"
TITLE="${3:-}"

if [[ -z "${PATH_SECRET:-}" ]]; then
  echo "PATH_SECRET is not set in the environment." >&2
  exit 1
fi

# Rewrite page links → direct enclosure (uses TTG_TOKEN when needed).
ENCLOSURE="$(python3 "$SCRIPT_DIR/resolve-torrent.py" --normalize-only "$LINK")"
# Inspect for title/files (JSON redacts token in enclosure).
META="$(python3 "$SCRIPT_DIR/resolve-torrent.py" "$LINK")"
if [[ -z "$TITLE" ]]; then
  TITLE="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["title"])' <<<"$META")"
fi

if [[ -z "$KIND" ]]; then
  echo "TYPE (movie|show) was not provided." >&2
  echo "Torrent metadata (decide TYPE with the language model, then re-run with TYPE):" >&2
  python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False), file=sys.stderr)' <<<"$META"
  exit 2
fi

case "$KIND" in
  movie|movies|film|films)
    PATH_KIND="movies"
    NORM_KIND="movie"
    ;;
  show|shows|tv|series)
    PATH_KIND="shows"
    NORM_KIND="show"
    ;;
  *)
    echo "Unknown kind \"$KIND\". Use movie or show." >&2
    exit 1
    ;;
esac

BODY="$(python3 -c 'import json,sys; print(json.dumps({"title":sys.argv[1],"enclosure":sys.argv[2]}))' "$TITLE" "$ENCLOSURE")"
echo "Resolved: kind=$NORM_KIND title=$TITLE" >&2

curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/${PATH_KIND}/add" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo
