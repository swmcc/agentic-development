---
name: mr-sweep
description: Pick up the merge requests people have posted in the #collective-mrs Slack channel since the last sweep, review them with /review-mr, and post each review with its verdict, without opening collie and without holding anyone's merge. Filters by author and repo. Use when the user types /mr-sweep, or asks to review what's been posted in collective-mrs, sweep the MR channel, or pick up new MRs from Slack.
argument-hint: "[all] [--author a,b] [--repo r,s] [--days N] [--cap N] [--no-post] [MR link...]"
---

🧑‍🌾 **Mr. Sweep**: *Collie rounds them up. Mr. Sweep sees them through.* `mr-sweep` reads as Mr. Sweep, the shepherd who directs collie, the sheepdog.

People post their MRs in **#collective-mrs** (`C0AKFUXG80J`, private). This reads what's new there, keeps what's worth my review, reviews it with `/review-mr` and **posts each review as me**. The verdict is applied as graded:
- **APPROVE** approves the MR.
- **CHANGES** requests changes, which blocks the merge until they're addressed.
- **COMMENTS** leaves it free to merge.

There is **never a review hold**. Nobody's merge is blocked while a review is in progress, only by a CHANGES verdict once it's posted.

Collie can't do this part itself, because only a Claude session can read Slack. Shell does the filtering; you do the choosing and the reviewing.

## Arguments

| Argument | Effect |
|---|---|
| *(none)* | MRs where I'm a requested reviewer, or where the post mentions me |
| `all` | every open MR that survives the filters, whether or not I'm a reviewer |
| `--author lee,ryan` | only MRs by these people: a case-insensitive prefix of the Slack poster's name or the GitLab author |
| `--repo graph-manager,frontend` | only MRs in these repos (the project's last path segment) |
| `--days N` | read N days back instead of only what's new since the last sweep |
| `--cap N` | at most N reviews this run (default 6); the rest are listed, not dropped |
| `--no-post` | write the drafts but don't post them; they show as `P` in collie for me to post |
| MR links | skip Slack and review exactly these links: go straight to step 4 |

They combine: `/mr-sweep all --author lee --repo graph-manager` takes every new graph-manager MR from Lee.

## 1. Read the channel

```bash
S=~/.claude/skills/mr-sweep/scripts
python3 $S/state.py oldest              # or: state.py oldest --days N
```

That prints the Slack timestamp to read from. By default it's the last sweep, or the start of today on a first run. Never go further back unless `--days` was given.

Read `#collective-mrs` with `slack_read_channel` (`channel_id: C0AKFUXG80J`, `oldest: <that ts>`, `limit: 100`, `response_format: detailed`). Follow `cursor` until there are no more pages. Save every page's `messages` text, concatenated and unchanged, to `<scratchpad>/mr-sweep/channel.txt`. If nothing is new, say so in one line and stop. Don't save state.

## 2. Pick out the candidates

```bash
python3 $S/candidates.py <scratchpad>/mr-sweep/channel.txt [--mode all] [--author ...] [--repo ...] [--cap N] > <scratchpad>/mr-sweep/candidates.json
```

Pass `--mode all` only when the argument `all` was given. The script removes duplicate links, so a bump counts once. It checks each MR against GitLab and against my existing drafts, and drops anything that is:
- struck through in Slack
- a Review Bot template update
- not open
- a draft MR
- mine
- already approved by me
- already drafted
- outside the filters

## 3. Show the shortlist

Show the `selected` rows, one line each: `repo!iid`, the title, who posted it, and whether I'm a reviewer. Then list `over_cap` the same way, and give a count of `skipped` grouped by reason. If `selected` is empty, say so, save state (step 6) and stop.

## 4. Review, without holds

Run `/review-mr --no-hold <url> <url> ...` with the selected links (or the links given as arguments). For more than one link it follows its own "Several MRs at once" flow: overlap groups, one agent per group in parallel, a draft per MR. Take its report, then carry on here instead of waiting for me to say "post". For this sweep, the request to post has already been given.

## 5. Post each review

Unless `--no-post` was given, post the drafts one MR at a time, in the order the reviews finished. Sign each draft first, so the author knows an agent wrote it:

```bash
python3 $S/sign.py <draft.md>
bash ~/.claude/skills/review-mr/scripts/post-and-finish.sh <group/project> <iid> <draft.md>
```

`sign.py` adds one line to the end of the summary note, which posts once per MR: *🧑‍🌾 Reviewed by Mr. Sweep, collie's shepherd: Stephen's review agent, working to his review standards. Reply here and he'll see it.* It's safe to run twice. With `--no-post`, don't sign: I'll be posting those myself.

`<group/project>` is the MR's full project path, e.g. `whitedotspace/collective-os/services/graph-manager`. The script refuses to post if:
- the draft's `Verdict:` line disagrees with its `(blocking` marks
- the verdict is APPROVE on a draft MR

It publishes all or nothing, checks every inline comment landed on its line, and only then applies the verdict. A failure on one MR leaves that draft unposted, so collie shows it as `P` with nothing half-published. Carry on with the rest. Never retry a failed post by hand in this run. Say what it printed.

## 5b. Reply in the Slack threads

Once every review is posted, tell the authors where they asked. Write the run's `reviews` list (the same rows logged in step 7) to `<scratchpad>/mr-sweep/reviews.json`, then:

```bash
python3 $S/slack_reply.py <scratchpad>/mr-sweep/channel.txt <scratchpad>/mr-sweep/reviews.json
```

It groups the posted reviews by the newest channel post that links each MR, so a bump gets the reply, and there's one reply per post, never one per MR. Send each with `slack_send_message` (`channel_id: C0AKFUXG80J`, `thread_ts`, `message: text`). It covers every posted verdict: approved, changes requested and comments. A review that failed to post gets no reply.

For a run given MR links, read the channel with `--days 3` first, so the script can find the posts. Any MR it lists as `unmatched` was never posted in the channel, and gets no reply. With `--no-post`, skip this step.

## 6. Save state and report

```bash
python3 $S/state.py set <newest_ts from candidates.json>
```

Save it after posting, so a run that fails part way reads the same messages again next time. Don't save it for a run made with only MR links, since that run never read Slack.

Open the report with `🧑‍🌾 Mr. Sweep` and one line on what this run did, e.g. "🧑‍🌾 Mr. Sweep: 3 reviewed, 2 approved, 1 changes requested". Then report one line per MR: `repo!iid` with its link, the verdict, the number of comments, and **posted**, **not posted** (with the reason), or **draft only** (with `--no-post`). After that, list what's still over the cap, which the next run picks up.

## 7. Log it to the sweep page

Every run that read new messages writes one document, even if nothing in them was worth reviewing, to the **MR Sweep** page (https://claude.ai/artifact/GnAtN8G71nMrdui5DqjUex). That page is how I see what happened when I'm away from the terminal. Use `ArtifactData` `set` with `collection: "sweeps"`, `doc_id: "s<newest_ts with the dot removed>"` (or `s<unix seconds now>` for a links-only run), and no `if_version`, since it's always a new document:

```json
{
  "at": "<ISO 8601 time of this run, with offset>",
  "args": "<the arguments as typed, e.g. all --author lee>",
  "reviews": [
    {"repo": "graph-manager", "iid": 836, "url": "<MR link>", "title": "<title>", "author": "<gitlab username>",
     "verdict": "APPROVE|CHANGES|COMMENTS", "comments": 2, "status": "posted|not_posted|draft_only",
     "note": "<what post-and-finish.sh printed, only when not_posted>"}
  ],
  "over_cap": [{"repo": "...", "iid": 0, "url": "..."}],
  "skipped": {"merged": 5, "struck through in Slack": 1}
}
```

`skipped` counts `candidates.json`'s skipped rows by `skip_reason`. **Write the document as soon as the first review is posted, and update it after each one after that**, using `update` with `if_version` from the previous write and the whole `reviews` list. That way the page shows each MR as it lands, rather than only when the slowest review finishes. A failed post is recorded as `not_posted` with its reason. The page lists those under "Needs you". Once I've posted one from collie, set its `status` to `posted` in that sweep's document, so it drops off the list.

## On a timer

`/loop 1h /mr-sweep` sweeps hourly in a session left open. Each run only sees what's new, and the cap keeps a big bump from turning into twenty reviews at once.
