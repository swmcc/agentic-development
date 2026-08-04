# Agentic Development

Configuration and tooling for agentic development workflows.

## Quick Start

```bash
# Clone the repo
git clone git@github.com:swmcc/agentic-development.git ~/Code/agentic-development
cd ~/Code/agentic-development

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
| `Makefile` | Installation and setup automation |

## What's Herdr?

Herdr is a modern terminal multiplexer with first-class support for AI coding agents. It provides:

- Workspace management with tabs and panes
- Native integrations with Claude Code, Codex, and other agents
- Agent state tracking (working/idle indicators)
- Popup commands (like lazygit)
- Gruvbox and other themes

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

## See Also

- [herdr/README.md](herdr/README.md) - Detailed herdr configuration docs
