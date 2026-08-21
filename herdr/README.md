# Herdr Configuration

My [Herdr](https://herdr.io) terminal multiplexer configuration for agentic development workflows.

## Files

| File | Purpose |
|------|---------|
| `config.toml` | Keybindings, UI settings, theme (gruvbox) |
| `spreader.yaml` | Workspace definitions for herdr-spreader |
| `scripts/scaffold-workspace.sh` | Apply the standard tab layout to a live workspace |
| `scripts/setup-spaces.sh` | Automation script for workspace creation |
| `scripts/setup-tabs.sh` | Tab creation helper script |
| `hooks/claude-agent-state.sh` | Claude Code integration hook |
| `hooks/codex-agent-state.sh` | Codex integration hook |

## Installation

### Prerequisites

1. Install [Herdr](https://herdr.io)
2. Optionally install herdr-spreader: `cargo install herdr-spreader`
3. `jq` and `lazygit` are required by the standard layout

The simplest route is `make setup-config` from the repo root, which creates every
symlink below. To do it by hand:

```bash
# Create config directory if it doesn't exist
mkdir -p ~/.config/herdr

# Symlink the main config
ln -sf ~/Documents/Code/agentic-development/herdr/config.toml ~/.config/herdr/config.toml

# Symlink spreader config (if using herdr-spreader)
ln -sf ~/Documents/Code/agentic-development/herdr/spreader.yaml ~/.config/herdr/spreader.yaml

# Symlink automation scripts
ln -sf ~/Documents/Code/agentic-development/herdr/scripts/setup-spaces.sh ~/.config/herdr/setup-spaces.sh
ln -sf ~/Documents/Code/agentic-development/herdr/scripts/setup-tabs.sh ~/.config/herdr/setup-tabs.sh

# Put the scaffold script on PATH
mkdir -p ~/.local/bin
ln -sf ~/Documents/Code/agentic-development/herdr/scripts/scaffold-workspace.sh ~/.local/bin/herdr-scaffold-workspace
```

### Agent Integration Hooks

The hooks in `hooks/` are typically installed by Herdr itself when you enable integrations. They're included here for reference. If you need to manually install:

```bash
# Claude Code hook
mkdir -p ~/.claude/hooks
ln -sf ~/Documents/Code/agentic-development/herdr/hooks/claude-agent-state.sh ~/.claude/hooks/herdr-agent-state.sh

# Codex hook
mkdir -p ~/.codex
ln -sf ~/Documents/Code/agentic-development/herdr/hooks/codex-agent-state.sh ~/.codex/herdr-agent-state.sh
```

## Configuration Overview

### Keybindings (`config.toml`)

- **Prefix**: `Ctrl+a` (like tmux/screen)
- **`prefix+g`**: Open lazygit in a popup (80% width/height)

### Theme

Using **gruvbox** with `auto_switch = false`.

### Workspaces (`spreader.yaml`)

Defines one workspace per project, each with the same four tabs:

| Tab | Contents |
|-----|----------|
| `agentic` | Claude Code (left pane) + Codex (right pane) |
| `git` | lazygit |
| `obsidian` | Plain shell |
| `system` | Plain shell |

Roots live under `~/Documents/Code`.

## Usage

### Using herdr-spreader

Builds every workspace in `spreader.yaml` from scratch:

```bash
herdr-spreader apply --file ~/.config/herdr/spreader.yaml

# Preview without touching anything
herdr-spreader apply --file ~/.config/herdr/spreader.yaml --dry-run
```

### Scaffolding a live workspace

`spreader.yaml` covers workspaces created at setup time. For a workspace that
already exists, or a one-off project not in the YAML, use the scaffold script.
It must be run from inside a herdr pane (`HERDR_ENV=1`):

```bash
# Create a workspace for a directory and lay it out in one step
herdr-scaffold-workspace --cwd ~/Documents/Code/some-project

# Apply the layout to a workspace that already exists
herdr-scaffold-workspace --workspace w7

# Apply it to every workspace except the one you're running from
herdr-scaffold-workspace --all
```

The script is idempotent: existing tabs are left alone and agents are only
started in panes that don't already host one, so re-running is safe.

Agents are named `cc-<slug>` (Claude) and `cx-<slug>` (Codex), where `<slug>` is
the workspace label reduced to `[a-z][a-z0-9_-]{0,31}`. On first launch in a new
directory, Codex asks whether you trust its contents; the script reports the
agent as not ready and moves on, leaving the prompt for you to answer.

### Manual workspace setup

```bash
# Run the setup script
~/.config/herdr/setup-spaces.sh
```

## Customisation

Edit `spreader.yaml` to add/remove workspaces. Each workspace follows this structure:

```yaml
- name: project-name
  root: ~/Documents/Code/project-directory
  tabs:
    - label: agentic
      panes:
        - command: claude
        - command: codex
    - label: git
      panes:
        - command: lazygit
    - label: obsidian
      panes:
        - command: zsh
    - label: system
      panes:
        - command: zsh
```

Give every tab at least one pane — spreader warns about tabs declared with a
bare label and no `panes:` block.
