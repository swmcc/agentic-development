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
| `c2/` | 🛰 Command centre — one view of what is waiting on you, bound to `prefix+shift+c` |
| `herdr/` | [Herdr](https://herdr.dev) terminal multiplexer configuration |
| `skills/` | Claude Code skills, symlinked into `~/.claude/skills` |
| `souls/` | 🎭 Character roster for agents — one file per persona, consumed by thrawn, `~/.claude/agents` wrappers and `/soul` |
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
`~/Code`, each laid out with the same four tabs: `agentic` (Claude Code
+ Codex), `git` (lazygit), `obsidian` and `system`. To apply that layout to a
workspace that already exists, use `herdr-scaffold-workspace` — see
[herdr/README.md](herdr/README.md).

## Per-machine config

`herdr/spreader.yaml` and `herdr/config.toml` are the personal setup, and they're
committed. A machine that needs something else — a work laptop whose repo list
shouldn't be public — puts an override in `~/.config/herdr`, outside the repo:

| Local file | Replaces |
|------------|----------|
| `~/.config/herdr/repos.local.yaml` | `herdr/spreader.yaml` (the repo list) |
| `~/.config/herdr/config.local.toml` | `herdr/config.toml` (keys, theme, UI) |

An override **replaces** its counterpart rather than merging with it, so a work
machine shows work repos and nothing else. `make setup-config` links whichever
applies; `make status` reports which won.

```bash
make repos          # show the active list, with ✓/✗ per directory
make repos-local    # build this machine's list by scanning ~/Code
```

`$HERDR_REPOS` beats both if you need to point at a list somewhere else.

## Make Targets

| Target | Description |
|--------|-------------|
| `make all` | Install everything and configure |
| `make install` | Install herdr, herdr-spreader, lazygit |
| `make setup` | Symlink configs and create workspaces |
| `make repos` | Show the workspace list currently in effect |
| `make repos-local` | Generate this machine's list from `$CODE_DIR` |
| `make status` | Show installation status |
| `make update` | Update all tools to latest versions |
| `make unlink` | Remove symlinks (keeps tools installed) |
| `make uninstall` | Remove everything |

Run `make help` for the full list.

## Skills

Claude Code skills live in `skills/`, one directory each, and `make setup-skills`
symlinks them into `~/.claude/skills`.

`/logbook` records commits, PRs and issues from any workspace in one shared
[Commit Logbook](https://claude.ai/artifact/ShBvWRL1NJcuWo4AP1EwHK).

| Skill | Purpose |
|-------|---------|
| `dependabot-automerge` | Set up, audit, or fix Dependabot auto-merge so patch/minor merge only after tests pass and majors never do |
| `sitrep` | Read the command centre and say what actually needs you — the judgement layer over `c2` |
| `postie` | Send a Slack ask on my behalf, drafted in my voice and sent only once I say so, signed as Postie |
| `sweep` | Pick who reviews an MR from the Sweep family below, and run it |
| `test-plan` | Write the "QA by tests" plan on a ticket from its merged MR: each acceptance criterion mapped to the test that proves it, real counts on main, revert proof, then label it `needs-native-tests`. The Drover runs it on every merge on the RBAC/GBAC epic |

Audit any repo without changing it:

```bash
skills/dependabot-automerge/audit.sh swmcc/second_breakfast
skills/dependabot-automerge/audit.sh --dir ~/Code
```

### The Sweep family

Review agents that work to the same written review standards and the same
blocking rules. They differ in what they look at hardest and how they say it.
Every MR gets one review with one verdict.

| Skill | Who | Job |
|-------|-----|-----|
| `mr-sweep` | 🧑‍🌾 Mr. Sweep | The default. Runs the review rounds every 15 minutes |
| `dr-sweep` | 🧑‍⚕️ Dr. Sweep, his evil twin | Leads in the core repos: reads every changed file whole, runs the tests, checks the MR description against the code |
| `sergeant-sweep` | 👮 Sergeant Sweep, the cousin in the police | Security consult: traces each access-control change from the caller to the gate to the audit row |
| `prof-sweep` | 🧑‍🏫 Prof. Sweep, the academic uncle | Tests consult: maps each acceptance criterion to a test and checks the tests fail without the fix |
| `granny-sweep` | 👵 Granny Sweep | Signs for the more junior members of the team, explaining the why behind every comment; anyone else gets her 1 time in 5 |

`/sweep` picks the lead (Dr. in collective-engine, collective-engine-api and
graph-manager, Mr. everywhere else), calls in Sergeant or Prof. when the diff
needs them, and decides who signs. The Sergeant and the Prof. never review on
their own unless called by name. `mr-sweep`'s rounds use the same table.

Each persona keeps notes on the people it reviews (`patients.md`,
`suspects.md`, `class-list.md`, `grandchildren.md`) and `sweep/juniors.md`
lists who gets Granny by default. They're gitignored: they name colleagues and
this repo is public. A fresh machine needs them copied over, or the Sweeps fall
back to a neutral, friendly tease for everyone.

## C2

One keypress for the state of your world — what is blocked on your review, what
you have in flight, which repos are not where you left them:

```bash
c2            # the board (prefix+shift+c in herdR)
c2 state      # the fused state as JSON, for a skill to reason over
c2 doctor     # credentials, dependencies, and how old each source is
```

Collection is shell, not agent: Jira over REST, GitLab over `glab`, git locally,
so the whole board refreshes in well under a second. Calendar and Gmail have no
CLI and are collected by `/sitrep`, which also does the reasoning.

See [c2/README.md](c2/README.md).

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
