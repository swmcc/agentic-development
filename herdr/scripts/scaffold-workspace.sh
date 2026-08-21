#!/bin/bash
# Scaffold a herdr workspace into the standard tab layout:
#   agentic  - claude code (left pane) + codex (right pane)
#   git      - lazygit
#   obsidian - plain shell
#   system   - plain shell
#
# spreader.yaml builds these workspaces from scratch at setup time; this script
# applies the same layout to a workspace that already exists, or creates one and
# scaffolds it in a single step.
#
# Usage:
#   scaffold-workspace.sh --cwd <path> [--label <name>]   create a workspace, then scaffold it
#   scaffold-workspace.sh --workspace <id>                 scaffold an existing workspace
#   scaffold-workspace.sh --all                            scaffold every workspace except the caller's
#
# Idempotent: tabs that already exist by label are left alone, and agents are
# only started in panes that do not already host one, so it is safe to re-run.

set -uo pipefail

TABS_PLAIN=(obsidian system)
AGENTIC_TAB="agentic"
GIT_TAB="git"

die() { printf 'scaffold-workspace: %s\n' "$1" >&2; exit 1; }
note() { printf '  %s\n' "$1"; }

command -v herdr >/dev/null || die "herdr not found in PATH"
command -v jq >/dev/null || die "jq not found in PATH"
[ "${HERDR_ENV:-}" = 1 ] || die "not running inside a herdr-managed pane (HERDR_ENV != 1)"

# Turn a workspace label into a valid agent-name fragment: [a-z][a-z0-9_-]{0,31}.
# tr, not sed: BSD sed on macOS has no \+ and would silently pass dots through,
# producing an agent name herdr rejects.
slugify() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -c 'a-z0-9_\n' '-' \
    | tr -s '-' \
    | sed -e 's/^-//' -e 's/-$//' \
    | cut -c1-26
}

ws_label() { herdr workspace get "$1" 2>/dev/null | jq -r '.result.workspace.label // ""'; }
ws_cwd() {
  herdr pane list --workspace "$1" 2>/dev/null \
    | jq -r --arg w "$1" '[.result.panes[] | select(.workspace_id==$w) | .cwd] | first // ""'
}
tab_id_by_label() {
  herdr tab list --workspace "$1" 2>/dev/null \
    | jq -r --arg l "$2" '[.result.tabs[] | select(.label==$l) | .tab_id] | first // ""'
}
first_tab_id() {
  herdr tab list --workspace "$1" 2>/dev/null | jq -r '[.result.tabs[].tab_id] | first // ""'
}
panes_of_tab() {
  herdr pane list --workspace "${1%%:*}" 2>/dev/null \
    | jq -r --arg t "$1" '.result.panes[] | select(.tab_id==$t) | .pane_id'
}
pane_has_agent() {
  herdr agent list 2>/dev/null | jq -e --arg p "$1" '[.result.agents[]?.pane_id] | index($p)' >/dev/null
}

# Create a tab with the given label unless one already exists; echo its first pane id.
ensure_tab() {
  local ws="$1" label="$2" cwd="$3" tab pane
  tab=$(tab_id_by_label "$ws" "$label")
  if [ -z "$tab" ]; then
    local out
    out=$(herdr tab create --workspace "$ws" --label "$label" --cwd "$cwd" --no-focus 2>&1)
    tab=$(printf '%s' "$out" | jq -r '.result.tab.tab_id // ""' 2>/dev/null)
    [ -n "$tab" ] || { note "FAILED to create tab '$label': $out"; return 1; }
    pane=$(printf '%s' "$out" | jq -r '.result.root_pane.pane_id // ""' 2>/dev/null)
  fi
  [ -n "${pane:-}" ] || pane=$(panes_of_tab "$tab" | head -1)
  printf '%s' "$pane"
}

# Agents may legitimately come back "not ready" while sitting on a first-run
# trust or preference prompt; the name still resolves, so report and move on.
start_agent() {
  local name="$1" kind="$2" pane="$3" out
  if pane_has_agent "$pane"; then
    note "$kind: pane $pane already hosts an agent, skipping"
    return 0
  fi
  out=$(herdr agent start "$name" --kind "$kind" --pane "$pane" 2>&1)
  if printf '%s' "$out" | jq -e '.result' >/dev/null 2>&1; then
    note "$kind started as '$name' in $pane"
  else
    note "$kind in $pane: $(printf '%s' "$out" | head -c 200)"
  fi
}

scaffold() {
  local ws="$1" label cwd slug tab pane_left pane_right git_pane
  label=$(ws_label "$ws"); [ -n "$label" ] || die "unknown workspace '$ws'"
  cwd=$(ws_cwd "$ws"); [ -n "$cwd" ] || cwd="$HOME"
  slug=$(slugify "$label")
  printf '\n%s (%s)  cwd=%s\n' "$ws" "$label" "$cwd"

  # tab 1: agentic — reuse the workspace's existing root tab rather than adding one
  tab=$(tab_id_by_label "$ws" "$AGENTIC_TAB")
  if [ -z "$tab" ]; then
    tab=$(first_tab_id "$ws")
    [ -n "$tab" ] || { note "no root tab found"; return 1; }
    herdr tab rename "$tab" "$AGENTIC_TAB" >/dev/null 2>&1
    note "renamed $tab -> $AGENTIC_TAB"
  fi

  pane_left=$(panes_of_tab "$tab" | head -1)
  pane_right=$(panes_of_tab "$tab" | sed -n 2p)
  if [ -z "$pane_right" ]; then
    pane_right=$(herdr pane split "$pane_left" --direction right --cwd "$cwd" --no-focus 2>&1 \
      | jq -r '.result.pane.pane_id // ""')
    [ -n "$pane_right" ] || { note "split failed"; return 1; }
    note "split $pane_left -> $pane_right"
  fi

  start_agent "cc-$slug" claude "$pane_left"
  start_agent "cx-$slug" codex "$pane_right"

  # tab 2: git — lazygit
  if [ -z "$(tab_id_by_label "$ws" "$GIT_TAB")" ]; then
    git_pane=$(ensure_tab "$ws" "$GIT_TAB" "$cwd") || return 1
    herdr pane run "$git_pane" lazygit >/dev/null 2>&1 && note "git: lazygit running in $git_pane"
  else
    note "git: tab already exists, skipping"
  fi

  # tabs 3 and 4: plain shells
  for t in "${TABS_PLAIN[@]}"; do
    if [ -z "$(tab_id_by_label "$ws" "$t")" ]; then
      ensure_tab "$ws" "$t" "$cwd" >/dev/null && note "$t: shell tab created"
    else
      note "$t: tab already exists, skipping"
    fi
  done
}

main() {
  local mode="" ws="" cwd="" label=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --workspace) mode=existing; ws="${2:-}"; shift 2 ;;
      --cwd)       mode=new;      cwd="${2:-}"; shift 2 ;;
      --label)     label="${2:-}"; shift 2 ;;
      --all)       mode=all; shift ;;
      -h|--help)   sed -n '2,19p' "$0"; exit 0 ;;
      *)           die "unknown argument: $1" ;;
    esac
  done

  case "$mode" in
    new)
      [ -d "$cwd" ] || die "no such directory: $cwd"
      cwd=$(cd "$cwd" && pwd)
      [ -n "$label" ] || label=$(basename "$cwd")
      ws=$(herdr workspace create --cwd "$cwd" --label "$label" --no-focus 2>&1 \
        | jq -r '.result.workspace.workspace_id // ""')
      [ -n "$ws" ] || die "workspace create failed"
      scaffold "$ws"
      ;;
    existing)
      [ -n "$ws" ] || die "--workspace needs an id"
      scaffold "$ws"
      ;;
    all)
      for w in $(herdr workspace list | jq -r '.result.workspaces[].workspace_id'); do
        # never touch the workspace this script is being run from
        [ "$w" = "${HERDR_WORKSPACE_ID:-}" ] && continue
        scaffold "$w"
      done
      ;;
    *) die "need one of --cwd <path> | --workspace <id> | --all (see --help)" ;;
  esac
  printf '\ndone.\n'
}

main "$@"
