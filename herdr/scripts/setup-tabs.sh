#!/bin/bash
# Setup standard tabs for all workspaces

# Get workspace IDs (skip w2 which is current session)
workspaces="w5 w6 w7 w8 w9 wA wB wC wD wE wF"

for ws in $workspaces; do
    echo "Setting up tabs for $ws..."

    # Rename first tab to Agentic
    herdr tab rename "${ws}:t1" "Agentic"

    # Create additional tabs
    herdr tab create --workspace "$ws" --label "Git"
    herdr tab create --workspace "$ws" --label "Neovim"
    herdr tab create --workspace "$ws" --label "System"
    herdr tab create --workspace "$ws" --label "Obsidian"
done

echo "Done - all tabs created"
