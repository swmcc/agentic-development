---
name: stray
description: Let my open MRs into #collective-mrs the way the team posts them, one line per MR, signed by a stray cow from a herd named after the team, so somebody herds them home for review. RBAC/GBAC ones also go into #rbacgbacdev. Shows the message and sends only on my word. Use when the user types /stray, or asks to post, share or put their MRs up for review in #collective-mrs, or when /raise-mr has just opened an MR.
argument-hint: "[MR links] [--drafts]"
---

🐄 Post my MRs for review in **#collective-mrs** (`C0AKFUXG80J`), in the shape most of the team uses, signed by a stray cow. Only my MRs, never anyone else's.

`S=~/.claude/skills/stray/scripts`

## 1. Find the MRs

```bash
python3 $S/stray.py find [<links from $ARGUMENTS>] [--drafts] > <scratchpad>/stray/rows.json
```

With links, it reads those. Without, it takes my open MRs across the group, leaving drafts out unless `--drafts` was given. Each row has the ticket key (from the branch, then the title, else `NoTicket`), a short title with the gitmoji and key stripped, and notes: `draft`, `stacked on !1042`.

**Drop anything already posted.** For each row, search #collective-mrs for its URL (`slack_search_public_and_private`, `in:<#C0AKFUXG80J>`, the MR's path and iid as keywords). If it's there and the MR hasn't changed since, drop it. If it changed since (new commits after that post), keep it and add `re-review` to its notes. More than 15 rows: keep the 15 newest and say what was left out.

If nothing is left, say so and stop.

## 2. RBAC/GBAC ones go to the room too

Check the keys in one JQL (cloudId `28feb242-73cf-475d-8304-4c5b3fd27dcc`):

```
key in (<keys>) AND (parent = COS-3789 OR labels = rbac-gbac)
```

Rows whose ticket comes back also go into **#rbacgbacdev** (`C0CB4EKSHDW`), as a second message with just those rows, the same cow and the same footer. Write them to `<scratchpad>/stray/rbac.json`.

## 3. Pick a cow and render

```bash
python3 $S/stray.py cow                                   # {"name", "emoji", "line"}
python3 $S/stray.py render <scratchpad>/stray/rows.json --cow "<name>" [--header "<line>"]
```

Every cow gets a turn before any repeats. The herd is in `herd.json`: puns on the team's names, each with its own emoji. A cow's name is never an @mention, so nobody is paged by their own pun. Add a header only when it helps ("Changes ready for re-review").

## 4. Show it, then stop

Show both messages and where each is going. Send only when I say so. If I change the wording, send my version.

## 5. Send and record

Send with `slack_send_message`: #collective-mrs first, then #rbacgbacdev if there are RBAC rows. Then:

```bash
python3 $S/stray.py used "<name>"
```

**Move each ticket to Peer Review.** For every key in the rows (not `NoTicket`), read its status. If it's To Do or In Progress, call `getTransitionsForJiraIssue`, pick the transition whose `to.name` is `Peer Review` and run it. Leave a ticket that's already in Peer Review, QA, Done or Not Required, and one assigned to someone else: say which you left and why. One key with several MRs moves once.

Add one line to today's daily note (`~/Documents/wiki/notes/dailies/YYYY-MM-DD.md`) under the tasks: `- 🐄 <cow> let <n> MRs into #collective-mrs ([msg](<link>))`, plus the #rbacgbacdev link when there is one. Leave the end-of-day sections alone.

## 6. Report

One line per message: where, how many MRs, the link.

## Notes

- Mr. Sweep skips my own MRs (`"mine"` in its candidates), so this asks people, not Collie.
- The Warden reads #collective-mrs for its MRs section, so posting here is what gets my RBAC MRs into its report.
- Links are markdown, `[repo!iid](url)`. Never Slack's `<url|label>`: `slack_send_message` takes markdown.
