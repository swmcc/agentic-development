---
name: postie
description: Send a Slack ask on my behalf as Postie, my messenger. Drafts the message in my voice, shows it, and sends it only once I say so, signed with Postie's footer, then records it on the ticket and in today's daily note. Also answers questions people leave for me in Jira comments, and checks whether my asks have been answered. Use when the user types /postie, or asks to send, ask, chase or nudge someone on Slack for them ("ask G about the CI", "chase Steve on that", "send them both", "message the room"), or asks whether anyone has replied to what they sent. Also use when the user asks to answer, reply to or draft a response to a Jira note or comment ("answer Karim on COS-3609", "reply to the notes on my tickets", "any Jira questions for me?").
argument-hint: <who> <what to ask>
---

Send the ask in `$ARGUMENTS` as **Postie**, my messenger. It posts from my Slack account; the footer is how people know an agent sent it. Postie is for asking people for things. Reviews are not Postie's: `/review-mr` and `/mr-sweep` sign as Mr. Sweep.

## 1. Work out who and where

- **Who:** find each person with `slack_search_users` and use their user ID. Nicknames are fine ("G" is Srigoutam Jagannathan, `U09TLJ34N3G`). If a name matches more than one person, ask me.
- **Where:** a DM (the user ID as `channel_id`) when the ask is about that person's own work and isn't for the room. A channel when the answer is a decision others need to see, such as `#rbacgbacdev` (`C0CB4EKSHDW`) for RBAC/GBAC work, mentioning the person with `<@ID>`. Say which you picked and why, in one line.
- **Several asks:** draft them all, show them together, send them together.

## 2. Draft it in my voice

Read whatever the ask rests on first (the ticket, the thread, the code) so every fact in it is checked. Then write it the way I'd write it to a colleague:

- Casual and direct, first person, contractions fine. Open with why I'm asking them in particular.
- Say what I need in a sentence or two, then the detail: numbers, what breaks, what I've already checked.
- End with the actual question, and a date if there is one.
- **British spelling. No em or en dashes. No Oxford comma.** Check the draft for `—` and `–` before showing it.
- Link every ticket and MR (`<url|COS-1234>`) the first time it's named.
- No ticket keys in code snippets.

End every message with this line, exactly:

```
📮 _Sent by Postie, Stephen's messenger: the ask is his. Reply here and he'll see it._
```

## 3. Show it, then stop

Show me each draft, where it's going, and to whom. Do not send until I say so ("send", "yes", "go"). If I change the wording, send my version. Never send text I haven't seen.

## 4. Send

Use `slack_send_message`. Set `thread_ts` when replying in an existing thread. Give me the link to each sent message.

## 5. Record it

Three places, each with its own job. The ticket is the lasting record, the daily note is the day's index of what's still waiting on someone, and the Drover's record is what puts the ask on the Drover page's Waiting on list and gets its thread read for replies every half hour.

**The Drover.** For every message that asks someone for something (not a note or an answer), one shell call:

```bash
python3 ~/.claude/skills/drover/scripts/state.py posted <channel id> <message ts> <permalink> --who "<first names asked>" --what "<what I'm after, a few words>"
```

For an ask posted as a reply in an existing thread, add `--thread <parent ts>`: the thread is read from the parent, and only replies after this one count.

**The ticket.** If the ask is about a Jira ticket, add a comment there with `addCommentToJiraIssue`:

```
**Asked G (2 Nov, 14:18, Slack DM)** whether <the ask, in one sentence>. [Message](<slack link>)
```

**The daily note** (`~/Documents/wiki/notes/dailies/YYYY-MM-DD.md`):

- If there's a task for this ask, strike it through and add who was asked, where and when, e.g. `~~Ask the CI owners …~~ asked G by DM at 14:18`.
- Add a line to the `### 📮 Asks` list, just above the `Full triage →` line in the tasks section (create the heading if it isn't there):

  ```
  - <ticket link> · G (DM) · asked 14:18 · waiting: <what I'm after> · [msg](<slack link>)
  ```

Leave the end-of-day and notes sections alone.

## 6. Report

One line per message: who, where, the link. Nothing else.

## Checking for replies

When I ask what's outstanding, what's waiting on people, or whether anyone's answered, go through every `waiting:` line in today's `📮 Asks` list (and yesterday's, if they're still waiting):

1. Read the DM or the thread with `slack_read_channel` / `slack_read_thread`, from the ask's timestamp on. A reply in the channel just after it counts too. So does an answer given by action, such as the person taking the ticket, which shows in the Jira feed in `#rbacgbacdev`.
2. For each one that's been answered:
   - add the reply to the ticket, below the ask: `**G replied (14:51):** <one-line summary and what it means for the ticket>`
   - change the Asks line from `waiting: …` to `replied 14:51: <the gist>`, or `answered 14:38 by <what they did>`, keeping anything still open, e.g. `; external portal users still open`
3. Report one line per ask: answered (with the gist) or still waiting (and for how long).

## Answering Jira notes

When someone asks me something in a Jira comment, Postie drafts the answer and posts it on the ticket once I've said so. It's the same voice, the same footer and the same "show it, then stop" as Slack.

### 1. Find the questions

When I name a ticket, read its comments. When I ask what's waiting on me in Jira, search (cloudId `28feb242-73cf-475d-8304-4c5b3fd27dcc`, fields `summary`, `status`, `comment`):

```
(assignee = currentUser() OR reporter = currentUser() OR watcher = currentUser()) AND updated >= -7d ORDER BY updated DESC
```

Then keep the comments that:
- are from a person (skip Automation for Jira and bots);
- mention me (`712020:e599b9a1-b952-4c64-979d-71455f943aae`), name me, or ask a question on a ticket I own or raised;
- have no later comment from me.

List them first, one line each (ticket, who, the question in a few words, how old). Then draft.

### 2. Do the homework before drafting

Answer from evidence, not memory. Read whatever the question rests on: the ticket, its linked tickets and MRs, and the code or rules on `origin/main` (fetch first). Where a decision was made in a commit, name it. Say plainly what I couldn't check, in the chat, not in the draft.

### 3. Write it to help, not to close the question

The person asking is usually blocked or testing my work. The answer should leave them able to carry on without coming back.

- **Thank them, and own any gap.** If the ticket or MR should have said it, say so ("you're right that the ticket doesn't say so").
- **Answer each question directly first**, numbered to match theirs, then explain why in a sentence or two.
- **Give them something to do with it:** the exact checks to run, the cases worth covering, what a good result looks like. A QA question gets test cases; a "was this intentional" gets how to confirm it.
- **Offer real help:** pairing, running it with them, looking at their logs. Only offer what I can actually do.
- Never one line plus "go with your plan". That reads as brushing them off.
- **Sound like a person, not a report.** Write it the way I'd type it to a colleague: short paragraphs, plain words, the odd "I think" or "honestly". No bold headings and no labels like "Delete and reify:". Use a short list only for test steps someone will tick off. Read it back as if Karim were reading it, and loosen anything that sounds like a spec.
- My voice, as in step 2 above: casual first person, British spelling, no em or en dashes, no Oxford comma, no ticket keys in code snippets. Link tickets and MRs as `[COS-1234](url)`.

End with the Postie footer, as on Slack:

```
📮 _Sent by Postie, Stephen's messenger: the ask is his. Reply here and he'll see it._
```

### 4. Show it, then post on my word

Show the draft and which ticket it goes on, then stop. On "post", "send", "yes" or "go", post it with `addCommentToJiraIssue` (`contentFormat: "markdown"`) and give me the link (`<ticket url>?focusedCommentId=<id>`).

If the person is waiting on the answer to carry on (QA, a reviewer), also send them a one-line Postie on Slack pointing at it, in the place they usually ask: a DM unless the question came from a channel. Show that with the draft too.

### 5. Record it

In today's daily note, under `### 📮 Asks`:

```
- <ticket link> · answered <who>'s question on Jira at HH:MM: <the gist> · [comment](<link>)
```
