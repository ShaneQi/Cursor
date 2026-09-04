#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: add-movie.sh \"TITLE\" \"ENCLOSURE_URL\"" >&2
  exit 1
fi

TITLE="$1"
ENCLOSURE="$2"

if [[ -z "${PATH_SECRET:-}" ]]; then
  echo "PATH_SECRET is not set in the environment." >&2
  exit 1
fi

BODY=$(python3 -c 'import json,sys; print(json.dumps({"title":sys.argv[1],"enclosure":sys.argv[2]}))' "$TITLE" "$ENCLOSURE")

curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/movies/add" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo
