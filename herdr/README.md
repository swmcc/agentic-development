# Herdr Configuration

My [Herdr](https://herdr.io) terminal multiplexer configuration for agentic development workflows.

## Files

| File | Purpose |
|------|---------|
| `config.toml` | Keybindings, UI settings, theme (gruvbox) — the personal defaults |
| `spreader.yaml` | Workspace definitions for herdr-spreader — the personal repo list |
| `scripts/resolve-repos.sh` | Work out which repo list is in effect, and print it |
| `scripts/gen-spreader.sh` | Generate a repo list by scanning a directory |
| `scripts/scaffold-workspace.sh` | Apply the standard tab layout to a live workspace |
| `scripts/setup-spaces.sh` | Automation script for workspace creation |
| `scripts/setup-tabs.sh` | Tab creation helper script |
| `hooks/claude-agent-state.sh` | Claude Code integration hook |
| `hooks/codex-agent-state.sh` | Codex integration hook |

## Machine-local overrides

Everything in this directory is the *personal* config and gets committed. A
machine that needs a different setup — a work laptop whose repo list has no
business in a public GitHub repo — drops an override into `~/.config/herdr`:

| Local file | Replaces |
|------------|----------|
| `~/.config/herdr/repos.local.yaml` | `spreader.yaml` (the repo list) |
| `~/.config/herdr/config.local.toml` | `config.toml` (keys, theme, UI) |

**Overrides replace, they never merge.** When `repos.local.yaml` exists the
committed list is ignored outright, so a work machine shows work repos and
nothing else. `make setup-config` picks whichever applies and points
`~/.config/herdr/{config.toml,spreader.yaml}` at it; `make status` says which one
won.

Build a local list by scanning your code directory:

```bash
make repos-local                      # scans ~/Code, writes repos.local.yaml, relinks
make repos-local CODE_DIR=~/work      # scan somewhere else
make repos                            # show the active list, ✓/✗ per directory
```

Or drive the generator directly for finer control:

```bash
herdr-gen-spreader --scan ~/Code --exclude talks,notes \
  -o ~/.config/herdr/repos.local.yaml --force

herdr-gen-spreader --scan ~/work ~/side/one-off   # stdout, extra paths appended
```

It is a plain generated file — edit it by hand afterwards if a workspace needs a
non-standard layout. Regenerating overwrites those edits.

For a one-off list that isn't either of the above, point `$HERDR_REPOS` at any
file; it beats both. A `$HERDR_REPOS` that doesn't exist is an error rather than
a silent fallback, so a typo can't quietly hand you the wrong repos.

`make unlink` leaves both local files alone — they're yours, and nothing in the
repo can reconstruct their contents.

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
ln -sf ~/Code/agentic-development/herdr/config.toml ~/.config/herdr/config.toml

# Symlink spreader config (if using herdr-spreader)
ln -sf ~/Code/agentic-development/herdr/spreader.yaml ~/.config/herdr/spreader.yaml

# Symlink automation scripts
ln -sf ~/Code/agentic-development/herdr/scripts/setup-spaces.sh ~/.config/herdr/setup-spaces.sh
ln -sf ~/Code/agentic-development/herdr/scripts/setup-tabs.sh ~/.config/herdr/setup-tabs.sh

# Put the scripts on PATH
mkdir -p ~/.local/bin
ln -sf ~/Code/agentic-development/herdr/scripts/scaffold-workspace.sh ~/.local/bin/herdr-scaffold-workspace
ln -sf ~/Code/agentic-development/herdr/scripts/gen-spreader.sh ~/.local/bin/herdr-gen-spreader
```

Symlink `config.local.toml` / `repos.local.yaml` instead of the repo copies where
they exist — see [Machine-local overrides](#machine-local-overrides).

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

Defines one workspace per project, each with the same four tabs:

| Tab | Contents |
|-----|----------|
| `agentic` | Claude Code (left pane) + Codex (right pane) |
| `git` | lazygit |
| `obsidian` | Plain shell |
| `system` | Plain shell |

Roots live under `~/Code`.

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
herdr-scaffold-workspace --cwd ~/Code/some-project

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
# Run the setup script — reads whichever repo list is active
~/.config/herdr/setup-spaces.sh
```

It takes its project list from `resolve-repos.sh` rather than carrying its own
copy, so it can't drift from `spreader.yaml`. Directories that don't exist are
reported and skipped.

## Customisation

Edit `spreader.yaml` for your personal list, or `~/.config/herdr/repos.local.yaml`
for this machine's. Each workspace follows this structure:

```yaml
- name: project-name
  root: ~/Code/project-directory
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

`setup-spaces.sh` parses this shape without a YAML library, matching a `- name:`
line followed by a `root:` line. Reordering those two keys within a workspace
will hide it from that script (herdr-spreader itself doesn't care).
