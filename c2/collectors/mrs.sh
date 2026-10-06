#!/usr/bin/env bash
# Open merge requests in two directions: the ones blocked on your review, and
# your own waiting on someone else.
#
# This is the question the merge board cannot answer. That board scores reviews
# after the fact as a game; this says which MRs are sitting on you right now,
# and how long they have been there. Age is the whole point — a review that has
# been waiting three days is a different object from one raised an hour ago.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/c2.sh"

GROUP="${C2_GITLAB_GROUP:-whitedotspace}"
ME="${C2_GITLAB_USER:-swmcc_whitespace}"

command -v glab >/dev/null 2>&1 || { c2_fail mrs "glab is not installed"; exit 0; }

# Both group queries are a round trip each, so they go out together — this is
# meant to answer a keypress, not a coffee break.
q="state=opened&scope=all&per_page=100"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
glab api "groups/$GROUP/merge_requests?$q&reviewer_username=$ME" >"$tmp/on_you" 2>/dev/null &
glab api "groups/$GROUP/merge_requests?$q&author_username=$ME"   >"$tmp/yours"  2>/dev/null &
wait
on_you=$(cat "$tmp/on_you" 2>/dev/null)
yours=$(cat "$tmp/yours" 2>/dev/null)

if [ -z "$on_you" ] && [ -z "$yours" ]; then
  c2_fail mrs "glab returned nothing — check \`glab auth status\`"; exit 0
fi

# Approvals and pipeline need a call per MR. Only your own MRs get that
# treatment: it is your own that you need to chase, and the list is short.
printf '%s' "${yours:-[]}" | jq -r '.[]? | "\(.project_id) \(.iid)"' 2>/dev/null \
  | while read -r pid iid; do
      [ -n "${pid:-}" ] || continue
      ( a=$(glab api "projects/$pid/merge_requests/$iid/approvals" 2>/dev/null)
        printf '%s\t%s\t%s\n' "$pid" "$iid" "${a:-{}}" >>"$tmp/approvals" ) &
    done
wait
approvals=$(cat "$tmp/approvals" 2>/dev/null)

DATA=$(python3 -c '
import json, sys, datetime as dt

on_you_raw, yours_raw, approvals_raw = sys.argv[1], sys.argv[2], sys.argv[3]
now = dt.datetime.now(dt.timezone.utc)

def load(s):
    try:
        v = json.loads(s) if s.strip() else []
        return v if isinstance(v, list) else []
    except Exception:
        return []

appr = {}
for line in approvals_raw.splitlines():
    parts = line.split("\t")
    if len(parts) != 3:
        continue
    try:
        appr[(int(parts[0]), int(parts[1]))] = json.loads(parts[2])
    except Exception:
        pass

def age_days(ts):
    try:
        return (now - dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))).days
    except Exception:
        return None

def shape(m, mine):
    ref = (m.get("references") or {}).get("full", "")
    # "group/sub/project!123" — the project is what you need to recognise it.
    project = ref.rsplit("!", 1)[0].split("/")[-1] if ref else None
    out = {
        "ref": ref,
        "iid": m.get("iid"),
        "project": project,
        "title": m.get("title", ""),
        "author": (m.get("author") or {}).get("username"),
        "draft": bool(m.get("draft")),
        "url": m.get("web_url"),
        "created_age_days": age_days(m.get("created_at", "")),
        "updated_age_days": age_days(m.get("updated_at", "")),
        "conflicts": m.get("has_conflicts"),
    }
    if mine:
        a = appr.get((m.get("project_id"), m.get("iid")), {})
        out["approvals"] = len(a.get("approved_by") or [])
        out["approved"] = bool(a.get("approved"))
        out["reviewers"] = [r.get("username") for r in (m.get("reviewers") or [])]
    return out

on_you = [shape(m, False) for m in load(on_you_raw) if not m.get("draft")]
yours  = [shape(m, True)  for m in load(yours_raw)]
on_you.sort(key=lambda m: -(m["created_age_days"] or 0))
yours.sort(key=lambda m: -(m["created_age_days"] or 0))
print(json.dumps({"on_you": on_you, "yours": yours}))
' "${on_you:-[]}" "${yours:-[]}" "${approvals:-}")

if [ -z "$DATA" ]; then c2_fail mrs "could not shape the glab response"; else c2_emit mrs true "" "$DATA"; fi
