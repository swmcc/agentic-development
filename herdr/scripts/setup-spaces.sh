#!/bin/bash
# Setup Herdr workspaces with standard tabs for all projects.
#
# Superseded by spreader.yaml (`herdr-spreader apply --file ~/.config/herdr/spreader.yaml`),
# which is the source of truth for the workspace list and tab layout. Kept as a
# dependency-free fallback for when herdr-spreader isn't installed.

projects=(
    "second_breakfast|~/Documents/Code/second_breakfast"
    "the-mcculloughs.org|~/Documents/Code/the-mcculloughs.org"
    "swmcc.github.io|~/Documents/Code/swmcc.github.io"
    "thoughts|~/Documents/Code/thoughts"
    "experiments.swm.cc|~/Documents/Code/experiments.swm.cc"
    "agentic-development|~/Documents/Code/agentic-development"
    "searchforaproperty.com|~/Documents/Code/searchforaproperty.com"
    "funeralsni|~/Documents/Code/funeralsni"
    "jotter|~/Documents/Code/jotter"
)

for project in "${projects[@]}"; do
    IFS='|' read -r label path <<< "$project"
    expanded_path="${path/#\~/$HOME}"

    if [ ! -d "$expanded_path" ]; then
        echo "Skipping $label - $expanded_path does not exist"
        continue
    fi

    echo "Creating workspace: $label"

    # Create workspace and capture the ID
    result=$(herdr workspace create --cwd "$expanded_path" --label "$label" 2>/dev/null)
    ws_id=$(echo "$result" | grep -o '"workspace_id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$ws_id" ]; then
        # Rename first tab, then add the rest
        herdr tab rename "${ws_id}:t1" "agentic" 2>/dev/null

        herdr tab create --workspace "$ws_id" --label "git" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "obsidian" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "system" 2>/dev/null
    fi
done

echo "Done - all workspaces and tabs created"
echo "Run 'herdr-scaffold-workspace --all' to start the agents and lazygit."
