#!/usr/bin/env bash
# A pane per ticket, in the repo's own workspace, on a worktree of its own.
#
# This is the review-pane trick from collie applied to work that writes. collie
# splits a pane beside an existing one in the repo's workspace and points it at
# the clone; a review only reads, so several can share that clone happily. A
# ticket branches and commits, so two of them in one checkout fight over HEAD.
#
# The fix is to keep the ticket where you expect it and move only the directory:
# it gets a tab of its own, labelled with the key, in the repo's workspace, and
# that tab stands in <repo>/.claude/worktrees/<ticket> — the same place Claude
# Code puts its own.
#
# Usage:
#   ticket-pane.sh <ticket> [--repo <name|path>] [--branch <name>] [--base <ref>]
#                           [--prompt <text>] [--ticket] [--no-agent]
#   ticket-pane.sh --list
#   ticket-pane.sh <ticket> --print-branch
#   ticket-pane.sh --close <ticket> [--repo <name|path>] [--delete-branch]
#
# Idempotent: a pane already standing in that worktree is reported rather than
# duplicated, and an existing worktree or branch for the ticket is reused.

set -uo pipefail

CODE_DIR="${CODE_DIR:-$HOME/Documents/Code}"
JIRA_DEFAULT_PROJECT="${JIRA_DEFAULT_PROJECT:-COS}"
# The tab work happens in, as spreader.yaml and scaffold-workspace both name it.
WORK_TAB="${TICKET_PANE_TAB:-agentic}"
TICKET_BODY_RATIO="${TICKET_BODY_RATIO:-0.35}"

die() { printf 'ticket-pane: %s\n' "$1" >&2; exit 1; }
note() { printf '  %s\n' "$1"; }

hjson() {
  local out
  out=$(herdr "$@" 2>&1) || return 1
  printf '%s' "$out" | jq -e . >/dev/null 2>&1 || return 1
  printf '%s' "$out"
}

# ── naming ───────────────────────────────────────────────────────────────────

# A bare number means the default project, the way jira-show reads one.
normalise_key() {
  if [[ "$1" =~ ^[0-9]+$ ]]; then
    printf '%s-%s' "$JIRA_DEFAULT_PROJECT" "$1"
  else
    printf '%s' "$1" | tr '[:lower:]' '[:upper:]'
  fi
}

# cos3670 — the directory name Claude Code's own worktrees already use, so the
# two land in the same place instead of growing a second convention beside it.
key_slug() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9'; }

slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -c 'a-z0-9\n' '-' \
    | tr -s '-' \
    | sed -e 's/^-//' -e 's/-$//'
}

# ── the ticket ───────────────────────────────────────────────────────────────

# Title and issue type off the top of jira-show's markdown: line 1 is
# "# KEY — summary", line 3 is "**Status** · Assignee · Priority · Type".
# Nothing here is load-bearing — both only seed a branch name you can override.
ticket_header() {
  command -v jira-show >/dev/null 2>&1 || return 1
  jira-show "$1" 2>/dev/null | sed -n '1p;3p'
}

derive_branch() {
  local key="$1" header summary type prefix slug
  header=$(ticket_header "$key") || return 1
  summary=$(printf '%s\n' "$header" | sed -n '1p' | sed -e 's/^# [^ ]* — //')
  type=$(printf '%s\n' "$header" | sed -n '2p' | awk -F' · ' '{print $NF}')

  # The "[Area / Thing] | " prefix the tracker puts on a title says where the
  # bug lives, which the repo and branch already say twice over.
  summary="${summary#*\] | }"

  case "$type" in
    Bug) prefix=fix ;;
    Task|Story) prefix=feat ;;
    *) prefix=chore ;;
  esac

  slug=$(slugify "$summary")
  # Cut to a readable length, then drop the word the cut landed in the middle of.
  [ ${#slug} -le 44 ] || slug=$(printf '%s' "${slug:0:44}" | sed -e 's/-[^-]*$//' -e 's/-$//')
  [ -n "$slug" ] || return 1
  printf '%s/%s-%s' "$prefix" "$key" "$slug"
}

# ── the repo ─────────────────────────────────────────────────────────────────

# The main checkout, never a worktree of it: worktrees nest under the repo and
# `git worktree add` has to be told about them from the top.
main_checkout() {
  local dir="$1" top
  top=$(git -C "$dir" worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')
  [ -n "$top" ] || return 1
  printf '%s' "$top"
}

resolve_repo() {
  local want="$1" dir
  if [ -n "$want" ]; then
    if [ -d "$want/.git" ] || [ -f "$want/.git" ]; then dir="$want"
    elif [ -d "$CODE_DIR/$want" ]; then dir="$CODE_DIR/$want"
    else die "no repo '$want' — looked at '$want' and '$CODE_DIR/$want'"; fi
  else
    dir=$(git rev-parse --show-toplevel 2>/dev/null) \
      || die "not inside a checkout — name one with --repo"
  fi
  main_checkout "$dir" || die "'$dir' is not a git repository"
}

default_base() {
  local repo="$1" head
  head=$(git -C "$repo" symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null)
  if [ -n "$head" ]; then printf '%s' "${head#refs/remotes/}"; return; fi
  for b in origin/main origin/master; do
    git -C "$repo" rev-parse --verify --quiet "$b" >/dev/null && { printf '%s' "$b"; return; }
  done
  printf 'HEAD'
}

# Branches already carrying this ticket's key, local or on the remote. One is a
# reuse; several is a question only you can answer.
#
# Listed and grepped rather than matched with a ref pattern: git's ref globs do
# not let * cross a /, so "refs/heads/*KEY*" silently matches nothing at all for
# the fix/KEY-what-it-does names every branch here uses.
matching_branches() {
  local repo="$1" key="$2"
  {
    git -C "$repo" for-each-ref --format='%(refname:short)' refs/heads
    git -C "$repo" for-each-ref --format='%(refname:short)' refs/remotes/origin \
      | sed 's|^origin/||'
  } 2>/dev/null | grep -F "$key" | grep -vx HEAD | sort -u
}

# git tracks a worktree's files like any others, and .claude/ is deliberately
# not ignored in some of these repos (agent definitions are committed), so the
# tree would show up as untracked noise in every status. info/exclude keeps that
# local — a .gitignore line would be a change to the repo nobody asked for.
ensure_excluded() {
  local repo="$1" ex
  ex="$(git -C "$repo" rev-parse --absolute-git-dir 2>/dev/null)/info/exclude"
  [ -f "$ex" ] || return 0
  grep -qxF '/.claude/worktrees/' "$ex" 2>/dev/null && return 0
  printf '/.claude/worktrees/\n' >>"$ex" && note "excluded /.claude/worktrees/ locally"
}

ensure_worktree() {
  local repo="$1" key="$2" branch="$3" base="$4" wt out held
  wt="$repo/.claude/worktrees/$(key_slug "$key")"

  if [ -d "$wt" ]; then
    git -C "$repo" worktree list --porcelain | grep -qxF "worktree $wt" \
      || die "$wt exists but is not a worktree — move it aside"
    printf '%s' "$wt"; return 0
  fi

  # A branch checked out somewhere else cannot be checked out again; say where
  # it is rather than leaving `git worktree add` to explain it.
  held=$(git -C "$repo" worktree list --porcelain \
    | awk -v b="branch refs/heads/$branch" '/^worktree /{w=$2} $0==b{print w}')
  [ -z "$held" ] || die "$branch is already checked out at $held"

  if git -C "$repo" rev-parse --verify --quiet "refs/heads/$branch" >/dev/null; then
    out=$(git -C "$repo" worktree add "$wt" "$branch" 2>&1)
  elif git -C "$repo" rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null; then
    out=$(git -C "$repo" worktree add --track -b "$branch" "$wt" "origin/$branch" 2>&1)
  else
    # --no-track: a fresh branch off the base, not a second writer on it.
    out=$(git -C "$repo" worktree add --no-track -b "$branch" "$wt" "$base" 2>&1)
  fi
  [ -d "$wt" ] || die "worktree add failed: $(printf '%s' "$out" | tail -2)"
  printf '%s' "$wt"
}

# <where it came from>TAB<branch>. Factored out of open_ticket so --print-branch
# can offer the name for editing before any of it exists.
choose_branch() {
  local repo="$1" key="$2" found count
  found=$(matching_branches "$repo" "$key")
  count=$(printf '%s\n' "$found" | grep -c .)
  case "$count" in
    0) local d; d=$(derive_branch "$key") \
         || die "could not read $key to name a branch — pass --branch"
       printf 'derived\t%s' "$d" ;;
    1) printf 'reused\t%s' "$found" ;;
    *) die "several branches carry $key, pass --branch:
$(printf '%s\n' "$found" | sed 's/^/    /')" ;;
  esac
}

# ── panes ────────────────────────────────────────────────────────────────────

panes_json() { hjson pane list || printf '{"result":{"panes":[]}}'; }

# A pane standing in the repo itself — the anchor whose workspace the new pane
# inherits, and whose tab and column it joins.
#
# Three things decide it, in order:
#
#   * the workspace holding the most of the repo's panes. A repo is open in more
#     than one: a stray pane cd'd into another checkout is enough, and the first
#     match is as likely to be the wrong home as the right one.
#   * a pane in the work tab. This beats avoiding an agent, and learning that
#     cost a ticket: preferring an agentless pane first put one ticket in the
#     system tab, because every pane in that workspace's agentic tab already had
#     an agent in it. A narrow pane in the right tab beats a wide one nobody
#     looks at.
#   * then no agent, so a split does not halve an agent mid-task, and then the
#     repo root over a subdirectory.
#
# Worktree panes are excluded throughout: splitting off another ticket's pane
# works, but it buries this ticket inside that one's column.
anchor_pane() {
  local repo="$1" home tabs
  home=$(panes_json | jq -r --arg r "$repo" '
    [ .result.panes[]
      | select((.cwd == $r) or (.cwd | startswith($r + "/")))
      | select(.cwd | startswith($r + "/.claude/worktrees/") | not) ]
    | if length == 0 then ""
      else group_by(.workspace_id) | max_by(length) | .[0].workspace_id end')
  [ -n "$home" ] || return 0

  # Tab labels live on the tab, not the pane, so they need their own call.
  tabs=$(hjson tab list --workspace "$home" | jq -c '[.result.tabs[] | {tab_id, label}]')
  [ -n "$tabs" ] || tabs='[]'

  panes_json | jq -r --arg r "$repo" --arg w "$home" --arg t "$WORK_TAB" --argjson tabs "$tabs" '
    (reduce $tabs[] as $x ({}; .[$x.tab_id] = $x.label)) as $label
    | [ .result.panes[]
        | select(.workspace_id == $w)
        | select((.cwd == $r) or (.cwd | startswith($r + "/")))
        | select(.cwd | startswith($r + "/.claude/worktrees/") | not) ]
    | sort_by([ (if ($label[.tab_id] // "") == $t then 0 else 1 end),
                (if .agent == null then 0 else 1 end),
                (if .cwd == $r then 0 else 1 end) ])
    | first | (.pane_id // "")'
}

# The pane already standing in a ticket's worktree, if any. The agent's pane
# comes first, so a ticket opened with --ticket reports the one worth focusing.
pane_in() {
  local wt="$1"
  panes_json | jq -r --arg w "$wt" '
    [ .result.panes[] | select(.cwd == $w or (.cwd | startswith($w + "/"))) ]
    | sort_by(if .agent == null then 1 else 0 end)
    | first | (.pane_id // "")'
}

pane_agent() {
  local pane="$1"
  panes_json | jq -r --arg p "$pane" \
    '[.result.panes[] | select(.pane_id==$p) | .agent] | first // ""'
}

workspace_of() {
  local pane="$1"
  panes_json | jq -r --arg p "$pane" \
    '[.result.panes[] | select(.pane_id==$p) | .workspace_id] | first // ""'
}

workspace_label() {
  hjson workspace get "$1" 2>/dev/null | jq -r '.result.workspace.label // ""'
}

# ── the commands ─────────────────────────────────────────────────────────────

open_ticket() {
  local key="$1" repo="$2" branch="$3" base="$4" prompt="$5" body="$6" agent="$7"
  local wt anchor pane ws label slug existing=""

  if [ -z "$branch" ]; then
    local chosen
    chosen=$(choose_branch "$repo" "$key") || exit 1
    branch="${chosen#*	}"
    [ "${chosen%%	*}" = reused ] && existing=1
  fi
  [ -n "$base" ] || base=$(default_base "$repo")

  ensure_excluded "$repo"
  wt=$(ensure_worktree "$repo" "$key" "$branch" "$base") || exit 1

  pane=$(pane_in "$wt")
  if [ -n "$pane" ]; then
    ws=$(workspace_of "$pane")
    label=$(workspace_label "$ws")
    note "already open in ${label:-$ws} $pane"
    note "worktree $wt"
    [ -n "$ws" ] && herdr workspace focus "$ws" >/dev/null 2>&1
  else
    anchor=$(anchor_pane "$repo")
    [ -n "$anchor" ] || die "no pane is standing in $repo — open its workspace first"

    # A tab of its own, labelled with the key, so the ticket is findable from
    # the tab bar rather than squeezed into a column of somebody else's tab.
    pane=$(hjson tab create --workspace "$(workspace_of "$anchor")" --cwd "$wt" \
      --label "$key" --no-focus | jq -r '.result.root_pane.pane_id // ""')
    [ -n "$pane" ] || die "tab create failed"

    herdr pane rename "$pane" "$key · $branch" >/dev/null 2>&1
    ws=$(workspace_of "$pane")
    label=$(workspace_label "$ws")
    note "pane $pane in ${label:-$ws}"
    note "worktree $wt"
    note "branch $branch${existing:+ — reused, not created}"

    if [ "$body" = 1 ]; then
      local bodypane
      bodypane=$(hjson pane split "$pane" --direction down --ratio "$TICKET_BODY_RATIO" \
        --cwd "$wt" --no-focus | jq -r '.result.pane.pane_id // ""')
      if [ -n "$bodypane" ]; then
        herdr pane rename "$bodypane" "$key" >/dev/null 2>&1
        herdr pane send-text "$bodypane" "exec bash -c 'jira-show $key | glow -p -'"$'\n' >/dev/null 2>&1
        note "ticket $bodypane"
      fi
    fi
  fi

  [ "$agent" = 1 ] || { note "no agent started"; return 0; }
  [ -z "$(pane_agent "$pane")" ] || { note "agent already running in $pane"; return 0; }

  slug="t-$(key_slug "$key")"
  local out
  out=$(herdr agent start "$slug" --kind claude --pane "$pane" 2>&1)
  if printf '%s' "$out" | jq -e '.result' >/dev/null 2>&1; then
    note "claude started as '$slug'"
    [ -n "$prompt" ] || prompt="Read $key with \`jira-show $key\` and tell me what you make of it. You are in a worktree on branch $branch; nothing is committed yet and we have not agreed an approach."
    herdr agent prompt "$slug" "$prompt" >/dev/null 2>&1 || note "prompt not delivered — type it in"
  else
    # An agent that is slow to come up still has a shell; hand the pane the
    # command rather than reporting a failure you would only undo by hand.
    note "agent start: $(printf '%s' "$out" | head -c 160)"
    herdr pane send-text "$pane" $'claude\n' >/dev/null 2>&1
  fi
}

# One row per ticket, not per pane: a ticket opened with --ticket owns two, and
# the pane worth naming is the one with the agent in it.
list_open() {
  local rows
  rows=$(panes_json | jq -r '
    [ .result.panes[]
      | select(.cwd | test("/\\.claude/worktrees/"))
      | . + (.cwd | capture("(?<repo>[^/]+)/\\.claude/worktrees/(?<t>[^/]+)")) ]
    | group_by(.repo + "/" + .t)
    | map( (sort_by(if .agent == null then 1 else 0 end) | first) as $b
           | $b + {panes: length} )
    | .[]
    | [ (.t | ascii_upcase | sub("(?<a>[A-Z]+)(?<n>[0-9]+)"; "\(.a)-\(.n)")),
        .repo, .pane_id, (.agent_status // "-"),
        (if .panes > 1 then "+\(.panes - 1)" else "" end) ]
    | @tsv')
  [ -n "$rows" ] || { echo "no ticket panes open"; return 0; }
  printf '%s\n' "$rows" \
    | awk -F'\t' '{printf "  %-11s %-22s %-9s %-9s %s\n", $1, $2, $3, $4, $5}'
}

close_ticket() {
  local key="$1" repo="$2" del="$3" wt pane branch
  wt="$repo/.claude/worktrees/$(key_slug "$key")"
  [ -d "$wt" ] || die "no worktree for $key under $repo"

  branch=$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null)

  # Refuse to bin work that exists only here. --force is git's to offer, not
  # this script's: a tidy-up command should never be the thing that loses a day.
  if [ -n "$(git -C "$wt" status --porcelain 2>/dev/null)" ]; then
    die "$wt has uncommitted changes — deal with them first"
  fi
  if [ -n "$branch" ] && ! git -C "$repo" rev-parse --verify --quiet "refs/remotes/origin/$branch" >/dev/null; then
    die "$branch has never been pushed — push it or remove the worktree by hand"
  fi

  while pane=$(pane_in "$wt"); [ -n "$pane" ]; do
    herdr pane close "$pane" >/dev/null 2>&1 || break
    note "closed $pane"
  done

  git -C "$repo" worktree remove "$wt" && note "removed $wt"
  if [ "$del" = 1 ] && [ -n "$branch" ]; then
    git -C "$repo" branch -d "$branch" >/dev/null 2>&1 \
      && note "deleted $branch" || note "kept $branch — not merged"
  fi
}

# ── entry ────────────────────────────────────────────────────────────────────

main() {
  local key="" repo_arg="" branch="" base="" prompt="" body=0 agent=1
  local mode=open del=0

  need() { [ $# -ge 2 ] && [ -n "$2" ] || die "$1 needs a value"; }

  while [ $# -gt 0 ]; do
    case "$1" in
      --repo) need "$@"; repo_arg="$2"; shift 2 ;;
      --branch) need "$@"; branch="$2"; shift 2 ;;
      --base) need "$@"; base="$2"; shift 2 ;;
      --prompt) need "$@"; prompt="$2"; shift 2 ;;
      --ticket) body=1; shift ;;
      --no-agent) agent=0; shift ;;
      --list) mode=list; shift ;;
      --print-branch) mode=print-branch; shift ;;
      --close) need "$@"; mode=close; key="$2"; shift 2 ;;
      --delete-branch) del=1; shift ;;
      -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
      -*) die "unknown option: $1" ;;
      *) key="$1"; shift ;;
    esac
  done

  command -v herdr >/dev/null || die "herdr not found in PATH"
  command -v jq >/dev/null || die "jq not found in PATH"
  command -v git >/dev/null || die "git not found in PATH"

  [ "$mode" = list ] && { list_open; exit 0; }
  [ -n "$key" ] || die "need a ticket (see --help)"
  key=$(normalise_key "$key")

  # Asking what a branch would be called changes nothing, so it does not need
  # to be asked from inside herdr.
  [ "$mode" = print-branch ] || [ "${HERDR_ENV:-}" = 1 ] \
    || die "not running inside a herdr pane (HERDR_ENV != 1)"

  local repo; repo=$(resolve_repo "$repo_arg") || exit 1

  case "$mode" in
    open)  open_ticket "$key" "$repo" "$branch" "$base" "$prompt" "$body" "$agent" ;;
    close) close_ticket "$key" "$repo" "$del" ;;
    print-branch)
      if [ -n "$branch" ]; then printf '%s\n' "$branch"
      else choose_branch "$repo" "$key" | cut -f2; fi ;;
  esac
}

main "$@"
