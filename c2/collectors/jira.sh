#!/usr/bin/env bash
# Everything currently assigned to you that is not Done.
#
# This talks to the REST API rather than the Atlassian MCP for two reasons. It
# is roughly a hundred times faster, which is the difference between a keypress
# and a coffee break. And REST honours `fields`, so one request returns the
# whole queue — the MCP ignores `fields`, returns every description in full, and
# truncates at about five issues, which is why the other skills all carry a
# page-by-exclusion workaround. None of that is needed here.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/c2.sh"

TOKEN="$(c2_jira_token)"
[ -n "$TOKEN" ] || { c2_fail jira "no Jira token in the Keychain for $JIRA_EMAIL"; exit 0; }

JQL="${C2_JIRA_JQL:-assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC}"

# The response goes to python on stdin, never through the shell — a stray quote
# or backslash in a ticket summary would otherwise rewrite the program.
DATA=$(curl -s --max-time 20 -u "$JIRA_EMAIL:$TOKEN" -H "Accept: application/json" \
  --get "$JIRA_SITE/rest/api/3/search/jql" \
  --data-urlencode "jql=$JQL" \
  --data-urlencode "fields=summary,status,priority,updated,issuetype,parent" \
  --data-urlencode "maxResults=100" \
  | python3 -c '
import json, sys, datetime as dt
site = sys.argv[1]
raw = sys.stdin.read()
if not raw.strip():
    print(json.dumps({"_error": "empty response from " + site})); raise SystemExit
try:
    d = json.loads(raw)
except json.JSONDecodeError:
    print(json.dumps({"_error": raw[:300]})); raise SystemExit
if "issues" not in d:
    msg = "; ".join(d.get("errorMessages") or []) or str(d)[:300]
    print(json.dumps({"_error": msg})); raise SystemExit

now = dt.datetime.now(dt.timezone.utc)
issues, counts = [], {}
for it in d["issues"]:
    f = it["fields"]
    st = f.get("status") or {}
    status = st.get("name", "Unknown")
    upd = f.get("updated")
    try:
        idle = (now - dt.datetime.fromisoformat(upd).astimezone(dt.timezone.utc)).days
    except Exception:
        idle = None
    issues.append({
        "key": it["key"],
        "summary": f.get("summary", ""),
        "status": status,
        "category": (st.get("statusCategory") or {}).get("name"),
        "type": (f.get("issuetype") or {}).get("name"),
        "priority": (f.get("priority") or {}).get("name"),
        "parent": (f.get("parent") or {}).get("key"),
        "updated": upd,
        "idle_days": idle,
        "url": site + "/browse/" + it["key"],
    })
    counts[status] = counts.get(status, 0) + 1
print(json.dumps({"total": d.get("total", len(issues)), "counts": counts, "issues": issues}))
' "$JIRA_SITE")

ERR=$(printf '%s' "$DATA" | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("_error") or "")
except Exception: print("collector produced no usable output")')

if [ -n "$ERR" ]; then c2_fail jira "$ERR"; else c2_emit jira true "" "$DATA"; fi
