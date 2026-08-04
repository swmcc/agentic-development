#!/bin/bash
# Setup Herdr workspaces with standard tabs for all projects

projects=(
    "swm.cc|~/Code/swm.cc"
    "whatisonthe.tv|~/Code/whatisonthe.tv"
    "Search for a Property|~/Code/searchforaproperty"
    "Funerals NI|~/Code/funeralsni"
    "Second Breakfast|~/Code/second_breakfast"
    "The Only Stephen|~/Code/theonlystephen.com"
    "BMK|~/Code/bmk"
    "Jotter|~/Code/jotter"
    "The McCulloughs|~/Code/the-mcculloughs.org"
    "Agentic|~/Code/agentic"
    "Catch|~/Code/catch"
)

for project in "${projects[@]}"; do
    IFS='|' read -r label path <<< "$project"
    expanded_path="${path/#\~/$HOME}"

    echo "Creating workspace: $label"

    # Create workspace and capture the ID
    result=$(herdr workspace create --cwd "$expanded_path" --label "$label" 2>/dev/null)
    ws_id=$(echo "$result" | grep -o '"workspace_id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "$ws_id" ]; then
        # Rename first tab to Agentic
        herdr tab rename "${ws_id}:t1" "Agentic" 2>/dev/null

        # Create additional tabs
        herdr tab create --workspace "$ws_id" --label "Git" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "Neovim" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "System" 2>/dev/null
        herdr tab create --workspace "$ws_id" --label "Obsidian" 2>/dev/null
    fi
done

echo "Done - all workspaces and tabs created"
