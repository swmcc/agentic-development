# Herdr Configuration

My [Herdr](https://herdr.io) terminal multiplexer configuration for agentic development workflows.

## Files

| File | Purpose |
|------|---------|
| `config.toml` | Keybindings, UI settings, theme (gruvbox) |
| `spreader.yaml` | Workspace definitions for herdr-spreader |
| `scripts/setup-spaces.sh` | Automation script for workspace creation |
| `scripts/setup-tabs.sh` | Tab creation helper script |
| `hooks/claude-agent-state.sh` | Claude Code integration hook |
| `hooks/codex-agent-state.sh` | Codex integration hook |

## Installation

### Prerequisites

1. Install [Herdr](https://herdr.io)
2. Optionally install herdr-spreader: `cargo install herdr-spreader`

### Setup via Symlinks

Link the config file to Herdr's config directory:

```bash
# Create config directory if it doesn't exist
mkdir -p ~/.config/herdr

# Symlink the main config
ln -sf ~/Code/agentic-development/herdr/config.toml ~/.config/herdr/config.toml

# Symlink spreader config (if using herdr-spreader)
ln -sf ~/Code/agentic-development/herdr/spreader.yaml ~/.config/herdr/spreader.yaml

# Symlink automation scripts
ln -sf ~/Code/agentic-development/herdr/scripts/setup-spaces.sh ~/.config/herdr/setup-spaces.sh
ln -sf ~/Code/agentic-development/herdr/scripts/setup-tabs.sh ~/.config/herdr/setup-tabs.sh
```

### Agent Integration Hooks

The hooks in `hooks/` are typically installed by Herdr itself when you enable integrations. They're included here for reference. If you need to manually install:

```bash
# Claude Code hook
mkdir -p ~/.claude/hooks
ln -sf ~/Code/agentic-development/herdr/hooks/claude-agent-state.sh ~/.claude/hooks/herdr-agent-state.sh

# Codex hook
mkdir -p ~/.codex
ln -sf ~/Code/agentic-development/herdr/hooks/codex-agent-state.sh ~/.codex/herdr-agent-state.sh
```

## Configuration Overview

### Keybindings (`config.toml`)

- **Prefix**: `Ctrl+a` (like tmux/screen)
- **`prefix+g`**: Open lazygit in a popup (80% width/height)

### Theme

Using **gruvbox** with `auto_switch = false`.

### Workspaces (`spreader.yaml`)

Defines 11 project workspaces, each with standard tabs:
- **Agentic** - Claude Code session
- **Git** - Git operations
- **Neovim** - Editor
- **System** - General terminal
- **Obsidian** - Notes

## Usage

### Using herdr-spreader

```bash
# Create all workspaces from spreader.yaml
herdr-spreader --config ~/.config/herdr/spreader.yaml
```

### Manual workspace setup

```bash
# Run the setup script
~/.config/herdr/setup-spaces.sh
```

## Customisation

Edit `spreader.yaml` to add/remove workspaces. Each workspace follows this structure:

```yaml
- name: Project Name
  root: ~/Code/project-directory
  tabs:
    - label: Agentic
      panes:
        - command: claude
    - label: Git
    - label: Neovim
    - label: System
    - label: Obsidian
```
