#!/usr/bin/env bash
# Where every repo in the workspace actually stands: branch, dirty count,
# stashes, drift from upstream, and stranded worktrees.
#
# Pure git, so it is the one collector that cannot be wrong about anything and
# cannot be slowed down by a network. When Jira and the board disagree with
# this, this wins.
set -uo pipefail
. "$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)/c2.sh"

ROOT="$(c2_workspace)"
[ -d "$ROOT" ] || { c2_fail repos "workspace '$ROOT' does not exist"; exit 0; }

TSV=$(
  for repo in "$ROOT"/*/; do
    [ -d "$repo/.git" ] || continue
    name=$(basename "$repo")
    branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD 2>/dev/null)
    dirty=$(git -C "$repo" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    stashes=$(git -C "$repo" stash list 2>/dev/null | wc -l | tr -d ' ')
    # Worktrees beyond the main checkout. Merged branches left behind here are
    # the quiet mess that eventually eats a morning.
    worktrees=$(( $(git -C "$repo" worktree list 2>/dev/null | wc -l | tr -d ' ') - 1 ))
    ahead=0; behind=0; upstream=""
    if upstream=$(git -C "$repo" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null); then
      counts=$(git -C "$repo" rev-list --left-right --count "$upstream"...HEAD 2>/dev/null)
      behind=$(printf '%s' "$counts" | awk '{print $1+0}')
      ahead=$(printf '%s' "$counts" | awk '{print $2+0}')
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$name" "$branch" "$dirty" "$stashes" "${worktrees:-0}" "$ahead" "$behind" "$upstream"
  done
)

DATA=$(printf '%s' "$TSV" | python3 -c '
import json, sys
repos = []
for line in sys.stdin.read().splitlines():
    p = line.split("\t")
    if len(p) != 8:
        continue
    name, branch, dirty, stashes, worktrees, ahead, behind, upstream = p
    n = lambda v: int(v) if v.isdigit() else 0
    r = {
        "name": name, "branch": branch,
        "dirty": n(dirty), "stashes": n(stashes), "worktrees": n(worktrees),
        "ahead": n(ahead), "behind": n(behind),
        "upstream": upstream or None,
    }
    # "Quiet" means nothing here needs a human. The board hides these.
    r["quiet"] = (r["dirty"] == 0 and r["stashes"] == 0 and r["worktrees"] == 0
                  and r["ahead"] == 0 and branch in ("main", "master"))
    repos.append(r)
repos.sort(key=lambda r: (r["quiet"], r["name"]))
print(json.dumps({"root": sys.argv[1], "repos": repos,
                  "noisy": sum(0 if r["quiet"] else 1 for r in repos)}))
' "$ROOT")

if [ -z "$DATA" ]; then c2_fail repos "no repos found under $ROOT"; else c2_emit repos true "" "$DATA"; fi
