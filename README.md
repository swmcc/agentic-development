# Agentic Development

Configuration and tooling for agentic development workflows.

## Quick Start

```bash
# Clone the repo
git clone git@github.com:swmcc/agentic-development.git ~/Documents/Code/agentic-development
cd ~/Documents/Code/agentic-development

# Install everything and configure
make all

# Or step by step:
make install    # Install herdr, herdr-spreader, lazygit
make setup      # Symlink configs and create workspaces

# Check status
make status
```

## Contents

| Path | Purpose |
|------|---------|
| `herdr/` | [Herdr](https://herdr.io) terminal multiplexer configuration |
| `thrawn/` | ⚔ Parallel agent orchestrator — plan with fable, execute with opus/haiku/codex/local in worktrees |
| `Makefile` | Installation and setup automation |

## What's Herdr?

Herdr is a modern terminal multiplexer with first-class support for AI coding agents. It provides:

- Workspace management with tabs and panes
- Native integrations with Claude Code, Codex, and other agents
- Agent state tracking (working/idle indicators)
- Popup commands (like lazygit)
- Gruvbox and other themes

Workspaces are defined in `herdr/spreader.yaml`, one per project under
`~/Documents/Code`, each laid out with the same four tabs: `agentic` (Claude Code
+ Codex), `git` (lazygit), `obsidian` and `system`. To apply that layout to a
workspace that already exists, use `herdr-scaffold-workspace` — see
[herdr/README.md](herdr/README.md).

## Make Targets

| Target | Description |
|--------|-------------|
| `make all` | Install everything and configure |
| `make install` | Install herdr, herdr-spreader, lazygit |
| `make setup` | Symlink configs and create workspaces |
| `make status` | Show installation status |
| `make update` | Update all tools to latest versions |
| `make unlink` | Remove symlinks (keeps tools installed) |
| `make uninstall` | Remove everything |

Run `make help` for the full list.

## Thrawn

Give it a ticket, get a PR:

```bash
thrawn 123                       # plan (fable) → parallel agents in worktrees → merge → green
thrawn status                    # the board, with ship code when green
thrawn ship gh-123 --code 482913 # push + PR/MR (gated behind the code)
```

See [thrawn/README.md](thrawn/README.md).

## See Also

- [herdr/README.md](herdr/README.md) - Detailed herdr configuration docs
- [thrawn/README.md](thrawn/README.md) - Parallel agent orchestrator
