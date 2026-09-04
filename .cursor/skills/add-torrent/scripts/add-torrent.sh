#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: add-torrent.sh \"movie|show\" \"TITLE\" \"ENCLOSURE_URL\"" >&2
  exit 1
fi

KIND="$1"
TITLE="$2"
ENCLOSURE="$3"

case "$KIND" in
  movie|movies|film|films)
    PATH_KIND="movies"
    ;;
  show|shows|tv|series)
    PATH_KIND="shows"
    ;;
  *)
    echo "Unknown kind \"$KIND\". Use movie or show." >&2
    exit 1
    ;;
esac

if [[ -z "${PATH_SECRET:-}" ]]; then
  echo "PATH_SECRET is not set in the environment." >&2
  exit 1
fi

BODY=$(python3 -c 'import json,sys; print(json.dumps({"title":sys.argv[1],"enclosure":sys.argv[2]}))' "$TITLE" "$ENCLOSURE")

curl -sS -X POST "https://torrents.qizengtai.workers.dev/f/${PATH_SECRET}/${PATH_KIND}/add" \
  -H "Content-Type: application/json" \
  -d "$BODY"
echo
