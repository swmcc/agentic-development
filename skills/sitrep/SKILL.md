---
name: sitrep
description: Read the command centre and say what actually needs you — refreshes every source, including the calendar and inbox that only a Claude session can reach, then reports the state of the world with judgement rather than counts. Use when the user types /sitrep, or asks what is waiting on them, what they should pick up now, where things stand, or to refresh the C2 board.
---

`prefix+shift+c` shows the board. This says what it **means** — which of those rows actually needs the user, and which are noise wearing a number.

The division of labour is the whole design: shell collects, you reason. Never re-fetch
by hand what `c2` already holds, and never fetch through an MCP what a collector
covers — one Jira REST call returns the full queue in under a second, where the
Atlassian MCP ignores `fields`, returns every description in full, and truncates
at about five issues.

## Step 1 — Refresh what shell can reach

```bash
C2=~/Documents/Code/agentic-development/c2
$C2/bin/c2 refresh          # jira, mrs, repos — about a second, all in parallel
```

If a collector fails it says so in its envelope and the board greys that block
out. Carry the failure into your report; never paper over it. A quiet section
and a broken section look identical to a reader, and only one is good news.

## Step 2 — Collect what only a session can reach

These three have no CLI, so they come through the MCP connectors and get handed
to the bridge. Each writes one JSON object on stdin:

```bash
... | $C2/collectors/ingest.sh calendar   # or mail, or rovo
```

**Calendar** — `mcp__claude_ai_Google_Calendar__list_events`, today 00:00 to
23:59, `timeZone: Europe/London`, `orderBy: startTime`. Shape each event as:

```json
{"start":"2026-10-01T16:00:00+01:00","end":"2026-10-01T16:30:00+01:00",
 "summary":"...","response_status":"accepted","conference_url":"...","location":"..."}
```

Keep `start`/`end` absolute and do **not** precompute "minutes until" — the
board derives that at render time, so an hour-old pull is still right about what
is next. Take `response_status` from the user's own attendee entry. Pass
declined events through unchanged; the board drops them, because a declined slot
is free time.

**Mail** — this is the one that needs judgement, and the naive query is worse
than useless. A plain `is:unread in:inbox` returns ~200 threads here, essentially
all of them calendar accept-notifications and Jira digest mail. Filter hard:

```
is:unread in:inbox newer_than:14d
  -from:jira@whitespaceventures.atlassian.net
  -subject:(Accepted OR Declined OR Tentative OR Invitation OR "Updated invitation" OR "Cancelled event")
  -category:promotions -category:social -category:updates -category:forums
```

Then apply the rule the query cannot: **a thread earns a row only if a human
wrote to the user and is waiting on them.** A notification, a digest, a
broadcast to `engineering@` — none of those are waiting on anybody. Write:

```json
{"needs_reply":[{"thread_id":"...","from":"A Colleague","subject":"...","age_hours":52,"url":"..."}],
 "unread_total":201,"filtered_out":{"note":"what you dropped and why"}}
```

Keep `needs_reply` short. Four rows that genuinely need a reply beat forty that
might. If nothing qualifies, write an empty list — that is a real answer.

**Rovo** (optional, for an ad-hoc question) — `mcp__claude_ai_Atlassian_Rovo__search`
or `getTeamworkGraphContext` when the user asks something that spans Jira and
Confluence. Shape as `{"query":"...","hits":[{"title","url","source","snippet"}]}`.
Skip it on a routine sitrep; it is slow and rarely changes the answer.

## Step 3 — Read the fused state

```bash
$C2/bin/c2 state            # every source, with per-source timestamps
$C2/bin/c2 state mrs        # just one
```

## Step 4 — Report with judgement, not counts

The board already shows the numbers. Your value is everything the numbers do not
say. Lead with the single thing that most needs them, then:

- **Age is the story.** A review open eight days and one open an hour are
  different objects. An issue idle 90-odd days in In Progress is not in
  progress — say so, and suggest it is closed or re-sized.
- **Cross-reference the sources.** A repo on a feature branch whose key is Done
  in Jira means unlanded work. An issue in Peer Review with no open MR means the
  MR merged and Jira is behind. Those contradictions are the highest-value
  output here, and no single source can see them.
- **Size against the calendar.** "Pick this up now" is wrong if a meeting starts
  in nine minutes. Say what fits in the gap that actually exists.
- **Name the stale sources.** If mail was collected two hours ago, the inbox
  claim is two hours old. Say it.
- **Never invent.** Nothing waiting is a good day, not a failure to find
  something. Say "nothing is blocked on you" and stop.

Keep it to what changes a decision. The board is there for the detail.

## Phase boundary — read, don't write

This skill is read-only by design. It does not transition issues, approve merge
requests, reply to mail or push anything. When it identifies an action, it names
it and leaves it to the user. Acting on the board is a later phase and a
separate decision; nothing here should quietly become the thing that does it.
