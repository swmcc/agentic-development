#!/usr/bin/env bash
# Shared helpers for the C2 collectors.
#
# Every collector writes one file into the state directory, and they all share
# the same envelope so the board can tell "nothing is waiting on you" apart from
# "this source failed and I have no idea what is waiting on you". Those two look
# identical in a naive dashboard, and only one of them is good news.

C2_ROOT="${C2_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
C2_STATE="${C2_STATE:-$C2_ROOT/state}"

# Where the sibling repos live — the directory holding development-stack/.
c2_workspace() {
  if [ -n "${COLLECTIVE_WORKSPACE:-}" ]; then
    printf '%s' "$COLLECTIVE_WORKSPACE"; return
  fi
  local dir="$PWD"
  while [ "$dir" != "/" ]; do
    [ -f "$dir/development-stack/Makefile" ] && { printf '%s' "$dir"; return; }
    dir=$(dirname "$dir")
  done
  printf '%s' "$HOME/Documents/Code"
}

c2_now()  { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Jira credentials come from the Keychain, the same entry prefix+j already uses,
# so there is still no token in the repo or in a dotfile.
JIRA_SITE="${JIRA_SITE:-https://whitespaceventures.atlassian.net}"
JIRA_EMAIL="${JIRA_EMAIL:-stephen.mccullough@white.space}"
c2_jira_token() {
  security find-generic-password -s "${JIRA_KEYCHAIN_SERVICE:-jira-api-token}" \
    -a "$JIRA_EMAIL" -w 2>/dev/null
}

# c2_emit <source> <ok> <error> <data-json>
# Wraps a collector's payload in the envelope and writes it atomically, so a
# board rendering mid-refresh never reads half a file.
c2_emit() {
  local source="$1" ok="$2" err="$3" data="$4"
  mkdir -p "$C2_STATE"
  python3 - "$C2_STATE/$source.json" "$source" "$ok" "$err" "$data" <<'PY'
import json, os, sys, tempfile
path, source, ok, err, data = sys.argv[1:6]
try:
    payload = json.loads(data) if data.strip() else None
except json.JSONDecodeError as e:
    payload, ok, err = None, "false", f"collector produced invalid JSON: {e}"
envelope = {
    "source": source,
    "collected_at": __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "ok": ok == "true",
    "error": err or None,
    "data": payload,
}
d = os.path.dirname(path)
fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
with os.fdopen(fd, "w") as fh:
    json.dump(envelope, fh, indent=1)
os.replace(tmp, path)
PY
}

# c2_fail <source> <message> — record a failure without destroying the last good
# payload's shape. The board shows the stale data greyed out, with the reason.
c2_fail() { c2_emit "$1" false "$2" 'null'; }

# c2_stale <source> <ttl-seconds> — true when the file is missing or older
# than the TTL. Age is measured on the envelope, not the mtime, because an
# atomic replace of unchanged data still bumps the mtime.
c2_stale() {
  local f="$C2_STATE/$1.json" ttl="$2"
  [ -f "$f" ] || return 0
  python3 - "$f" "$ttl" <<'PY'
import datetime as dt, json, sys
try:
    with open(sys.argv[1]) as fh:
        env = json.load(fh)
    at = dt.datetime.strptime(env["collected_at"], "%Y-%m-%dT%H:%M:%SZ") \
           .replace(tzinfo=dt.timezone.utc)
except Exception:
    sys.exit(0)                                   # unreadable counts as stale
age = (dt.datetime.now(dt.timezone.utc) - at).total_seconds()
sys.exit(0 if age > float(sys.argv[2]) else 1)
PY
}
