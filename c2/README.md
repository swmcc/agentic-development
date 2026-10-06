# C2 — command and control

One view of the state of your world: what is blocked on you, what you have in
flight, and which repos are not where you left them.

```bash
c2            # the board, refreshing anything stale (prefix+shift+c in herdR)
c2 refresh    # force every shell collector
c2 state      # the fused state as JSON — what /sitrep reads
c2 doctor     # credentials, dependencies, and how old each source is
```

## The one design decision everything follows from

**Collection is shell. Reasoning is Claude.**

`herdr/scripts/jira-show.sh` found this boundary first, and its header says why:
a headless agent round trip measured 20–30s per lookup, *"which is fine for a
slash command and useless for a keybinding."* The same holds here. Jira over
REST, GitLab over `glab`, git locally — the whole board refreshes in under a
second, so `prefix+shift+c` is a glance rather than a wait.

Claude's job is `c2 state`: the contradictions between sources, the sizing
against the calendar, the ninety-day-old issue that is not actually in progress.
See `skills/sitrep`.

A happy side effect: Jira REST honours `fields`, so one request returns the
whole queue. The Atlassian MCP ignores it, returns every description in full and
truncates at about five issues — which is why every other skill in this setup
carries a page-by-exclusion workaround. None of that is needed here.

## Sources

| Source | How | Refreshed by | TTL |
|---|---|---|---|
| `repos` | git, locally | `c2` | 45s |
| `jira` | REST + Keychain token | `c2` | 180s |
| `mrs` | `glab`, group-scoped | `c2` | 180s |
| `calendar` | Google Calendar MCP | `/sitrep` | — |
| `mail` | Gmail MCP, heavily filtered | `/sitrep` | — |
| `rovo` | Atlassian Rovo search MCP | `/sitrep`, on demand | — |

The bottom three have no CLI, so they are reachable only from inside a Claude
session. `/sitrep` collects them and pipes them to `collectors/ingest.sh`, which
files them in the same state directory under the same envelope. The board shows
how old each one is rather than pretending a two-hour-old inbox is live.

Swapping any of them for a shell collector later changes nothing above the state
file — the envelope is the interface, not the fetch.

## The envelope

Every source writes one file, `state/<source>.json`:

```json
{"source":"jira","collected_at":"2026-10-01T12:16:04Z","ok":true,"error":null,"data":{…}}
```

`ok` and `collected_at` exist so the board can tell **"nothing is waiting on
you"** apart from **"I could not look."** Those render identically in a naive
dashboard, and only one of them is good news.

## What the board chooses to show

- **Quiet things are absent.** A repo clean and on `main` earns no line.
- **No count without an age.** A review raised an hour ago and one sitting three
  days are different objects, and only the age says which.
- **Declined meetings are free time.** They are dropped, not greyed.
- **Unread mail is not a signal.** ~200 unread here, almost all calendar
  accept-notifications and Jira digests. A thread earns a row only when a human
  is waiting on a reply — the filtering lives in `skills/sitrep`.

## Phase

Phase 1 is read-only: sense, fuse, display. Nothing here transitions an issue,
approves a merge request or sends anything. Acting from the board is phase 2 and
a separate decision.

## Setup

`c2 doctor` checks it. You need `glab` authenticated, `jq`, `python3`, and a
Jira API token in the Keychain — the same entry `prefix+j` already uses:

```bash
security add-generic-password -s jira-api-token \
  -a stephen.mccullough@white.space -w '<token>' -U
```

Token from <https://id.atlassian.com/manage-profile/security/api-tokens>.

Overrides, if the defaults are wrong for a machine: `COLLECTIVE_WORKSPACE`,
`C2_GITLAB_GROUP`, `C2_GITLAB_USER`, `JIRA_SITE`, `JIRA_EMAIL`, `C2_JIRA_JQL`.
