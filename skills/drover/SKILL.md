---
name: drover
description: Drive Stephen's own open MRs home. Finds every MR he's put up (by hand or through /stray), fixes red pipelines, works through every outstanding review note and replies on its thread, asks the reviewers to look again through Postie in #collective-developers (grouped per person), merges what's fully approved and green, and moves its ticket to QA or Done. Logs each run to the Drover page. Use when the user types /drover, or asks to chase, finish, push through or round up his open MRs, or to check his MRs for reviews and act on them.
argument-hint: "[--round <token>] [--no-merge] [--no-fix] [--dry-run] [MR link...]"
model: sonnet
---

🐂 **The Drover**: *The strays wander in. The Drover drives them home.* /stray lets Stephen's MRs into #collective-mrs and Mr. Sweep reviews other people's. The Drover takes Stephen's own the rest of the way: fixed, answered, re-reviewed, merged and moved on in Jira.

`D=~/.claude/skills/drover`

## Arguments

| Argument | Effect |
|---|---|
| *(none)* | every open, non-draft MR Stephen authored |
| MR links | only these |
| `--no-merge` | report what's ready, but don't merge it |
| `--no-fix` | don't start fixer agents; report what needs work |
| `--dry-run` | scan and report only: no pushes, no Slack, no merges, no Jira |

## 0. On a timer, the gate comes first

When the prompt carries `--round <token>` (a `/muster` timer), run this before anything else:

```bash
python3 ~/.claude/skills/muster/scripts/round.py gate drover <token>
```

Only `go` carries on. On `superseded`, a newer `/muster` owns the rounds: `CronDelete` every job in this session whose prompt carries that token, reply with the single line `📯 superseded by a newer /muster: timers here removed`, and stop. Run by hand, with no `--round`, skip this.

## 1. Scan

```bash
python3 $D/scripts/scan.py [--only <url> ...] > <scratchpad>/drover/scan.json
```

Every open MR Stephen authored on GitLab gets one row with a `state`:

| state | meaning | what this run does |
|---|---|---|
| `running` | a pipeline is running | nothing; the next run sees the result |
| `claimed` | another Drover run is working on it | nothing |
| `parked` | its ticket is in `parked.txt` | nothing |

An MR link in `parked.txt` is forgotten outright: it gets no row at all, so it's not on the page or in the report.
| `needs_work` | a blocking job failed because of this MR, it conflicts, or a human note has no answer | fix it (step 3) |
| `waiting_review` | answered and green, but a reviewer hasn't approved this head | ask them (step 4) |
| `ready_to_merge` | every human reviewer approved, green, mergeable, and nothing unanswered except NITs (`nits`) | merge it, move its ticket, and send any NITs to a follow-up MR (step 2) |

Jobs that also fail on main's latest pipeline are listed under `failing_on_main_too` and don't count against the MR. A stacked MR (targeting another branch) is never `ready_to_merge`: it waits for the one below it.

### A quiet run stops here

Unless MR links or `--dry-run` were given, check the scan against the last finished run before reading it:

```bash
python3 $D/scripts/quiet.py check <scratchpad>/drover/scan.json; python3 $D/scripts/state.py open-asks <scratchpad>/drover/scan.json; python3 $D/scripts/state.py waiting-on <scratchpad>/drover/scan.json
```

The second command lists the Postie asks worth reading for replies (step 1b), and prints `[]` when nothing is out. The third is the Waiting on list that goes in the heartbeat (step 9).

- **`quiet` and `[]`:** nothing has moved. Write the heartbeat (step 9), reply with the single line `🐂 The Drover: nothing changed` and stop.
- **`quiet` with asks listed:** in **one message**, read each ask's thread (step 1b) and write the heartbeat as `nothing changed`, as parallel calls, so the reply check costs no extra round trip. If no reply needs anything, reply `🐂 The Drover: nothing changed` and stop.

A quiet run doesn't read `scan.json`, write a drive to the page, report or notify. Most runs on a timer are quiet, and this keeps each one to a couple of hundred tokens.

### 1b. Read replies to my asks

Every Postie ask is tracked here, not just the Drover's own re-review asks: Postie records each one it sends. People often answer a re-review ask in Slack instead of on GitLab, and every other ask is only ever answered in Slack. For each ask `open-asks` listed, call `slack_read_thread` with its `channel`, `message_ts` set to its `thread`, and `oldest` set to its `seen`. Look only at replies newer than `seen`, and skip Stephen's own (`U082BL09HK4`), since those are his answers. Then:

| The reply | What to do |
|---|---|
| Approved, looked, done, "on it", "after lunch", "back Thursday" | Nothing to act on. Record it with `state.py replied <ask ts> <reply ts> <who> <reply permalink> "<gist>"`, so Waiting on shows it, and put its gist in that MR's row `note`, e.g. `Steve: looking after lunch`. GitLab shows an approval on the next scan. |
| An answer to what a non-MR ask wanted | `state.py replied ...` as above. Once everyone it asked has answered, or the one answer settles it, `state.py done <ask ts>`. |
| A question, a review point made in Slack, "ask someone else", "fine, merge it" without approving on GitLab, a disagreement | Record it with `state.py pending <ask ts> <reply ts> <mr url, or - for a non-MR ask> <who> <reply permalink> "<gist>"`. It goes under **Needs you** until Stephen answers. Never act on it alone: never merge on a Slack word, and never add reviewers. |

After each thread, record what was read: `state.py seen <ask ts> <newest reply ts>`. For a pending reply, if Stephen has since replied in that thread, run `state.py clear <ask ts> <reply ts>`.

Every pending reply on an MR that's still open is a `needs_you` row in every drive (step 5) until it's cleared, with the reply's permalink in `link` and `<who>: <gist>` in `note`. A pending reply on a non-MR ask shows in Waiting on as needs you. If a pending reply turns up on a quiet run, the run isn't quiet: carry on and write a drive.

## 2. Merge what's ready

Unless `--no-merge` or `--dry-run`, for each `ready_to_merge` row, check again right before merging. Approvals, comments and pipelines change between the scan and now:
- every human reviewer still `approved`;
- `detailed_merge_status` still `mergeable`;
- the pipeline still `success`;
- no human note newer than Stephen's last reply, other than the row's `nits`.

If anything has changed, leave it for the next run.

```bash
glab api -X PUT "projects/<url-encoded project>/merge_requests/<iid>/merge" -f should_remove_source_branch=true
```

**Then move its ticket in the same step.**
1. Read the ticket's status. If it's already where the MR's `on_merge` says (`QA` or `Done`), leave it and say so.
2. Otherwise call `getTransitionsForJiraIssue` and pick the transition whose `to.name` is `on_merge`. In COS today, QA is `111` and Done is `31`. Run `transitionJiraIssue` (cloudId `28feb242-73cf-475d-8304-4c5b3fd27dcc`).
3. If the MR has no `on_merge` line, don't guess: report it under Needs you.

When a stacked MR's base merges, GitLab retargets the MR above to main, and the next run treats it like any other.

**Approved with only NITs left.** A `ready_to_merge` row can carry `nits`: threads labelled **NIT** that nobody has answered. Every reviewer has already approved, so the NITs don't hold the merge; another push, pipeline and re-review round costs more than they're worth. Merge it, move the ticket, then (unless `--no-fix`) take the NITs to **one follow-up MR**:

1. **Ticket it first.** The NITs get their own ticket, in the same epic as the merged MR's ticket.
   - Read the original ticket's `parent` with `getJiraIssue`.
   - Run `createJiraIssue` (cloudId `28feb242-73cf-475d-8304-4c5b3fd27dcc`, project `COS`, type `Task`) with:
     - `parent`: that epic. If the original ticket has none, leave it out and say so in the report.
     - `labels`: `["tech-debt", "review-nits", "size-XS"]`.
     - assignee: Stephen (`712020:e599b9a1-b952-4c64-979d-71455f943aae`).
     - summary: `[<Area>] | NITs from <repo>!<iid>: <a few words>`, in the board's `[Area] |` style.
     - description: a few lines naming the merged MR and its ticket, then one bullet per NIT with its reviewer and a link to its thread. Say it merged approved, which is why these are follow-up.
   - Move the new ticket to In Progress (`21`).
2. Start a background fixer with `references/fixer.md`, its **Follow-up** section, the merged MR's row (with `nits`), the merge commit and the **new ticket key**.
3. The fixer:
   - branches from main (`--no-track`) and fixes every NIT;
   - opens the follow-up MR, assigned to you, with the NIT authors as reviewers;
   - replies on each NIT thread with the follow-up link.

   The MR names the new ticket and says **On merge:** move it to **Done**. The original ticket stays where its merge put it.
4. When the fixer reports, move the new ticket to Peer Review (`81`). Later runs drive the follow-up like any other MR, and its merge moves the new ticket to Done.

A NIT that would mean reworking the change goes under Needs you instead.

## 3. Fix what needs work

Unless `--no-fix` or `--dry-run`:
1. Claim every `needs_work` row first, so an overlapping run skips them:

   ```bash
   python3 $D/scripts/state.py claim <url> ...
   ```

2. Start **one background agent per MR, all in one message** so they run in parallel. Each agent's prompt is `references/fixer.md`, followed by that MR's scan row as JSON.

   The brief makes each agent:
   - work in `<repo>/.claude/worktrees/`;
   - answer every human note and fix the pipeline;
   - update the description if it's gone stale;
   - push once and watch the pipeline;
   - reply on every thread without resolving any.

   It also repeats the no-ticket-keys-in-code rule.
3. As each agent reports, release its claim:

   ```bash
   python3 $D/scripts/state.py release <url>
   ```

   Then scan that MR again with `--only <url>`:
   - **Agent report has `NEEDS STEPHEN:`** → the MR goes under Needs you, with that line.
   - **MR now `waiting_review`** → it joins step 4 in this run.
   - **Still red, or still `needs_work`** → it goes under Needs you, with the failing job or the thread.

Never resolve a thread, never force-push, never approve, and never push to main.

## 4. Ask for re-reviews, through Postie

For every `waiting_review` row, its `ask` list holds the reviewers who haven't approved this head and haven't been asked about it yet. People already asked at this head aren't asked again; a new push makes them askable again.

**One message per run** in **#collective-developers** (`C0C2MTJMQ91`), top-level. Each person is mentioned once (`<@SLACKID>`), with their MRs under them:

```
<@U0B2DFGJ5SQ> could you have another look at these when you get a sec?
• [collective-engine!1119](url): <what changed since you last looked, in a few words>
• [logto!82](url): <...>
<@U0A6BNB0TD5> and these:
• [collective-engine!1121](url): <...>
Thanks!

📮 _Sent by Postie, Stephen's messenger: the ask is his. Reply here and he'll see it._
```

- **Voice:** Stephen's. Casual and first person, British spelling, no em or en dashes, no Oxford comma. Say what changed (from the agent's report or the latest commit), not that "the MR is ready for review".
- **Slack IDs:** find them with `slack_search_users`. Known ones: Steve Church `U0A6BNB0TD5`, Michael Sanders `U0B2DFGJ5SQ`, Herman Chan `U07E889K05D`, Ryan Wilson `U09T65AH85V`, Paddy McDermott `U0BKWHTFN3S`, Srigoutam Jagannathan `U09TLJ34N3G`, Karim Saidi `U0AF14RPC11`.
- **When nobody needs asking:** post nothing.

After sending, record every ask:

```bash
python3 $D/scripts/state.py asked <url> <sha> <reviewer username> ...
python3 $D/scripts/state.py posted C0C2MTJMQ91 <message ts> <permalink> --who "<names>" --what "re-review of <repo>!<iid>, ..." <url> <url> ...
```

`posted` takes every MR in the message, so later runs can read its thread for replies (step 1b).

With `--dry-run`, show the message and don't send it.

## 5. Log the drive to the page

Every run writes one document to the **Drover** page (https://claude.ai/artifact/LRdFyqdp2Ee5t6R3GcXFNf), even when nothing changed, so the page always shows where things stand.

Use `ArtifactData` `set`:
- `collection: "drives"`;
- `doc_id: "d<unix seconds now>"`;
- no `if_version`, since it's always a new document.

```json
{
  "at": "<ISO 8601 with offset>",
  "summary": "<one line, e.g. 1 merged, 2 fixed, 3 asked, 1 needs you>",
  "mrs": [
    {"repo": "collective-engine", "iid": 1119, "url": "<MR link>", "title": "<title>", "ticket": "COS-2115",
     "action": "merged|fixed|asked|waiting|running|needs_you|parked",
     "status": "<Jira status after this run, e.g. Done, QA, Peer Review>",
     "note": "<one line: what changed, who it waits on, or what needs Stephen>",
     "link": "<optional: the Slack reply that needs Stephen>"}
  ],
  "posts": [{"label": "re-review ask", "url": "<Slack permalink>"}]
}
```

Use one row per open MR, plus one for each MR merged this run.
- `waiting`: it was already asked at this head, so nothing was sent.
- `asked`: this run sent the Postie.
- `needs_you`: anything this run couldn't settle on its own, including every pending Slack reply from step 1b.

## 6. Report

Open with `🐂 The Drover` and the same one-line summary as the page. Then one line per MR: `repo!iid` linked, the action and the note. Put **Needs you** first if there's anything in it. End with the page link.

## 7. Notify in herdr

When this run did something (merged, moved a ticket, pushed a fix, sent a Postie) or has anything under Needs you, show **one** herdr notification. It appears inside the terminal, not as a macOS desktop notification:

```bash
command -v herdr >/dev/null && herdr notification show "🐂 Drover" --body "<one line, Needs you first>" --position top-right --sound none
```

For example, the body could be `needs you on engine!1121 · merged engine!1119, COS-2115 to Done · asked Michael, Steve`. Keep it under 200 characters, with no markdown. A run where nothing happened shows nothing. Never use `PushNotification`: desktop notifications are off.

## 8. Mark the run finished

Last of all, scan again and save it, so the next run can tell whether anything moved after this one:

```bash
python3 $D/scripts/scan.py > <scratchpad>/drover/scan.json && python3 $D/scripts/quiet.py save <scratchpad>/drover/scan.json
```

The fresh scan matters: this run's merges, pushes and asks changed the rows, and saving the first scan would make the next run look busy. Skip this for a `--dry-run` or a run given MR links.

## 9. Heartbeat

Every run that got past the gate, quiet ones included, writes one heartbeat. Send it alongside the run's last tool call, as a parallel call in the same message, never as a round trip of its own, since each round trip re-reads the whole session. It's one `ArtifactData` `set` on the **Drover** page: `collection: "beats"`, `doc_id: "b<unix seconds now>"`, no `if_version`, data `{"at": "<ISO 8601 with offset>", "outcome": "<nothing changed, or this run's one-line summary>", "waiting_on": <the waiting-on list, as printed>}`. Take `waiting_on` from the `state.py waiting-on` output this run printed, run again after any `replied`, `done`, `pending` or `clear`. The page's Waiting on section is the newest heartbeat's list. The page's last-run and next-run line reads it, along with the schedule `/muster` records, so it always says when the Drover last ran even after a quiet hour. Skip it for a `--dry-run`.

## On a timer

`/muster` runs it every half hour in working hours. `/loop 30m /drover` does the same by hand in a session left open, like Mr. Sweep. A run only acts on what changed: claims stop overlapping runs working the same MR, and the asked-at-this-head record stops a reviewer being pinged twice for the same push.
