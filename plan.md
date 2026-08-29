# Working plan: souls plumbing + runner trial phase 2

*Temporary file. Not committed. Delete when both tracks are done.*
*Written 29 Aug 2026. Tickets: #16 umbrella, #17 #18 #19 now, #20 #21 #24 later, #14/#8 trial.*

Two tracks run side by side. Claude (this session) does the serial work on
thrawn's own internals. You drive thrawn from your CLI on real tickets in
your other repos, which is exactly the phase 2 data the trial needs. The
tracks are designed not to collide: nothing Claude changes alters planner
or execution behaviour mid-trial except the one declared prerequisite (#17).

---

## Track 1: Claude does these directly (serial, same files)

Why not thrawn for these: #17 #18 #19 all touch `thrawn/bin/thrawn`,
`runners.toml` and the prompt files. It is one coherent change set wearing
three tickets' clothing; the width gate would rightly refuse it.

Order and scope:

1. **#17 run-the-checks prompt step** (small, first, benefits your runs)
   - Add a numbered rule to `prompts/executor.md` and `prompts/swarm.md`:
     run the repo's checks before committing and fix what they surface
   - Plain text so codex and pi receive it identically
   - This is the pi lint-discipline fix and a declared phase 2 prerequisite,
     so it lands BEFORE your first phase 2 run
2. **#19 souls mechanism, shipped inert**
   - `souls/` directory, `{{persona}}` slot in the prompt templates,
     `[personas]` table in runners.toml, `make setup-souls` symlink,
     thin-wrapper pattern for `~/.claude/agents`, `/soul <name>` skill
   - All persona mappings EMPTY: rendered prompts stay byte-identical,
     verified by test, so your trial runs are untouched
3. **#18 lessons loop**
   - Post-run debrief (haiku) summarises state.json + logs into
     `.thrawn/lessons.md`, injected alongside recon
   - Lands with the debrief active but the planner injection behind the
     same inert principle if there is any doubt about mid-trial effects

Each lands as its own tested, linted commit that closes its ticket.
Nothing in track 1 requires you to wait.

## Track 2: You run thrawn from your CLI (this IS phase 2 of #14)

The trial needs a fortnight of ordinary work through the planner with
codex and pi both earning their keep. Rough cadence: a few runs a week,
ending around **12 September**, then the verdict gets written on #8/#14
from the ledger.

What to run:

```bash
# once per repo, cheap and cached
thrawn recon

# ordinary tickets through the full pipeline (planner routes the runners)
thrawn 42
thrawn 42 43 45          # several issues become one run planned together

# mechanical batches through swarm, alternating runners so the ledger
# gets comparable data
thrawn swarm 51 52 --runner codex
thrawn swarm 53 54 --runner pi
```

Good hunting grounds: groomed issues on funeralsni, whatisonthe.tv,
second_breakfast, jotter or any repo with a Makefile so checks auto-detect.
rails_love_letter's backlog is done, so fresh repos are better data anyway.

Worth knowing about things that landed this week:

- `thrawn status` now shows per-task token usage; it accumulates in
  state.json and that IS the trial ledger, no bookkeeping needed
- `thrawn retry` on the same runner resumes the failed session warm
- `thrawn abort` now snapshots per-task patches into the run dir first,
  so aborting is no longer destructive
- if a pi pane looks noisy or a codex pane dies instantly, that is signal
  for the trial: note it on #14 rather than working around it silently

What to jot on #14 as you go (a comment per notable run is plenty):
which repo, planner or swarm, runner, shipped or aborted, anything odd.
The token numbers are already captured for you.

## Interlocks

- #17 lands before your first phase 2 run (Claude does it immediately)
- #19 and #18 can land any time; they are inert to trial behaviour
- #20 (skeptic), #24 (tactician) and #21 (fixer) DO change behaviour, so
  they wait until phase 2 concludes ~12 Sep
- If a track 2 run exposes a thrawn bug, Claude fixes it as its own
  ticket; bugfixes do not count as behaviour changes

## Done means

- Track 1: #17 #18 #19 closed, suite green, pushed
- Track 2: a fortnight of ledger data, verdict written on #8 and #14,
  then the post-phase-2 souls tickets unblock
- This file deleted
