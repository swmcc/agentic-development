#!/bin/bash
# Setup Herdr workspaces with standard tabs for every project in the active
# workspace list.
#
# Superseded by `herdr-spreader apply --file ~/.config/herdr/spreader.yaml`, which
# also builds the panes. Kept as a dependency-free fallback for when
# herdr-spreader isn't installed.
#
# The project list is not hardcoded here — it comes from resolve-repos.sh, which
# prefers ~/.config/herdr/repos.local.yaml over the committed spreader.yaml. So
# this script and spreader.yaml can never drift apart.
set -uo pipefail

# Real path of this script, following symlinks, so resolve-repos.sh is findable
# when we run as ~/.config/herdr/setup-spaces.sh. Not `readlink -f`: absent from
# older BSD userlands.
self="${BASH_SOURCE[0]}"
while [ -L "$self" ]; do
  link=$(readlink "$self")
  case "$link" in
    /*) self="$link" ;;
    *)  self="$(dirname "$self")/$link" ;;
  esac
done
SCRIPTS_DIR="$(cd "$(dirname "$self")" && pwd)"

entries=$(bash "$SCRIPTS_DIR/resolve-repos.sh" --entries) || exit 1
if [ -z "$entries" ]; then
    echo "No workspaces in $(bash "$SCRIPTS_DIR/resolve-repos.sh")" >&2
    exit 1
fi

echo "Workspace list: $(bash "$SCRIPTS_DIR/resolve-repos.sh")"
echo

while IFS=$'\t' read -r label path; do
    [ -n "$label" ] || continue

    if [ ! -d "$path" ]; then
        echo "Skipping $label - $path does not exist"
        continue
    fi

    echo "Creating workspace: $label"

    # Create workspace and capture the ID
    result=$(herdr workspace create --cwd "$path" --label "$label" 2>/dev/null)
    ws_id=$(echo "$result" | grep -o '"workspace_id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$ws_id" ]; then
        # Rename first tab, then add the rest
        herdr tab rename "${ws_id}:t1" "agentic" 2>/dev/null

        herdr tab create --workspace "$ws_id" --label "git" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "obsidian" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "system" 2>/dev/null
    fi
done <<< "$entries"

echo "Done - all workspaces and tabs created"
echo "Run 'herdr-scaffold-workspace --all' to start the agents and lazygit."
