#!/usr/bin/env bash
# Take a payload on stdin and file it as a collected source.
#
#   ... | ingest.sh calendar
#
# This is the bridge for the sources that have no CLI. Calendar, Gmail and Rovo
# are reachable only through the MCP connectors, which means only from inside a
# Claude session — so /sitrep collects them and hands them here, and the board
# reads them from the same state directory as everything else. The envelope
# timestamps them, so the board can show "written at 09:12" rather than
# pretending a two-hour-old inbox is live.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/c2.sh"

SOURCE="${1:?usage: ingest.sh <source>   (payload on stdin)}"
case "$SOURCE" in
  calendar|mail|rovo) ;;
  *) echo "refusing to ingest '$SOURCE' — shell collectors own their own files" >&2; exit 1 ;;
esac

PAYLOAD=$(cat)
[ -n "$PAYLOAD" ] || { c2_fail "$SOURCE" "ingest got an empty payload"; exit 1; }
c2_emit "$SOURCE" true "" "$PAYLOAD"
echo "ingested $SOURCE"
