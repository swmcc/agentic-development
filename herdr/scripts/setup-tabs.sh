#!/bin/bash
# Setup standard tabs for all existing workspaces.
#
# Superseded by scripts/scaffold-workspace.sh, which also starts the agents and
# lazygit and is idempotent. Kept as a minimal fallback: tabs only, no panes.

# Every workspace except the one this script is run from
workspaces=$(herdr workspace list \
    | grep -o '"workspace_id":"[^"]*"' \
    | cut -d'"' -f4 \
    | grep -v "^${HERDR_WORKSPACE_ID:-none}$")

for ws in $workspaces; do
    echo "Setting up tabs for $ws..."

    # Rename first tab, then add the rest
    herdr tab rename "${ws}:t1" "agentic"

    herdr tab create --workspace "$ws" --label "git"
    herdr tab create --workspace "$ws" --label "obsidian"
    herdr tab create --workspace "$ws" --label "system"
done

echo "Done - all tabs created"
