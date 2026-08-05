# ⚔ thrawn — User Guide

A single scenario, start to finish. Commands on the left, what's actually
happening on the right.

## The scenario

You maintain a web app. Issue **#42** is sitting in the tracker:

> **Add CSV export to reports**
>
> Users want to download any report as CSV. Needs a download button on the
> report page, an export endpoint, and the actual CSV generation. Should
> respect the current report filters.

One feature, but it's really three or four pieces of work that don't overlap
much — which is exactly the shape thrawn likes.

---

## Step 0 — one-time repo setup

First time using thrawn in a repo, cache a codebase brief:

```bash
cd ~/code/your-app
thrawn recon
```

```
thrawn surveying the terrain with fable-plan …
thrawn recon saved → .thrawn/recon.md (112 lines, pinned to 3f9a21c8)
```

The planner and every worker will now start every run already knowing the
stack, layout, conventions, and test commands. Re-run it occasionally —
thrawn tells you when it's gone stale (default: 50 commits behind).

(You can skip this step entirely: if a repo has no recon cache, dispatch
runs it for you first. So `thrawn 42` on a fresh repo is genuinely
steps 0–4 in one command — everything except `ship`, which is *always*
manual.)

## Step 1 — see the plan before committing to it

You *can* just run `thrawn 42` and let it fly. First few times, look at the
plan first:

```bash
thrawn plan 42
```

```
thrawn run gh-42: Add CSV export to reports
thrawn deep thinking with fable-plan … (this is the slow part)
thrawn plan: 3 task(s) → t1[opus], t2[haiku], t3[codex]
{
  "summary": "Add filtered CSV export to reports",
  "branch": "thrawn/gh-42-csv-export",
  "tasks": [
    { "id": "t1", "title": "Export endpoint + CSV serializer",
      "complexity": "high", "runner": "opus", "deps": [] },
    { "id": "t2", "title": "Download button on report page",
      "complexity": "low", "runner": "haiku", "deps": [] },
    { "id": "t3", "title": "Endpoint tests incl. filter passthrough",
      "complexity": "medium", "runner": "codex", "deps": ["t1"] }
  ],
  ...
}
thrawn planned only — execute with: thrawn watch gh-42
```

Read the task prompts with `thrawn plan gh-42 --full` (or open
`.thrawn/runs/gh-42/plan.json`). Sanity checks worth doing:

- Do any two tasks touch the same files? (They'll conflict at merge.)
- Are the routings sensible? (A `high` task on `local` would be a bad sign.)
- Is anything in the plan that the ticket didn't ask for?

Plan looks wrong? Cheap to fix: edit the ticket to be clearer (or add
constraints), then `thrawn plan 42` again — it creates a fresh run.

## Step 2 — execute

```bash
thrawn watch gh-42
```

Your pane becomes the board:

```
⚔ thrawn — gh-42  Add filtered CSV export to reports
phase: working   base: main @ 3f9a21c8

  ◐ t1   Export endpoint + CSV serializer   opus    running
  ◐ t2   Download button on report page     haiku   running
  ○ t3   Endpoint tests incl. filters       codex   pending (after t1)

  watching … ctrl-c is safe; resume with `thrawn watch gh-42`
```

What just happened:

- Each task got its own **git worktree** branched from the same commit
  (`.thrawn/worktrees/gh-42/t1`, `…/t2`), so agents can't tread on each
  other or on your working copy
- The run got one **herdr tab** (`⚔ gh-42`) with a stacked pane per agent
  (`t1 Export endpoint…`) streaming output live — click in if you're
  curious, herdr's working/idle dots track each pane
- t1 and t2 run **in parallel**; t3 waits for t1 because the plan said so

Meanwhile you keep working in your own pane on whatever you like — the run
doesn't touch your checkout.

## Step 3 — integration happens by itself

When the last task finishes, thrawn merges the task branches into
`thrawn/gh-42-csv-export`, then runs your checks (auto-detected from the
Makefile: `make check`, or `make lint` + `make test`).

Two things can interrupt the cruise:

- **Merge conflict** → an integrator agent is dispatched into the
  integration worktree to combine both sides (it knows both branches were
  parts of the same feature). You'll see it as another pane in the run tab.
- **Checks fail** → the integrator gets the failing output and fixes the
  root cause, then re-runs the checks. Two strikes and thrawn stops and
  hands it to you instead of thrashing.

## Step 4 — the green board

```
⚔ thrawn — gh-42  Add filtered CSV export to reports
phase: green   base: main @ 3f9a21c8

  ● t1   Export endpoint + CSV serializer   opus    done
  ● t2   Download button on report page     haiku   done
  ● t3   Endpoint tests incl. filters       codex   done (after t1)

  integration: green

  ALL GREEN  ship code: 482913
  → thrawn ship gh-42 --code 482913
```

You also get a herdr notification. Nothing has been pushed. Nothing will
be, until you act. This is the moment to review if you want to:

```bash
cd .thrawn/worktrees/gh-42/_integration
git log --oneline main..    # what's going in
git diff main               # the whole change
```

## Step 5 — ship it

The 6-digit code only exists on the board — typing it back proves you've
seen green:

```bash
thrawn ship gh-42 --code 482913
```

```
thrawn pushed thrawn/gh-42-csv-export
thrawn opened: https://github.com/you/your-app/pull/117
```

Branch pushed, PR opened with the plan's title/body plus `Closes #42`, and
a comment dropped on the issue. On a GitLab remote the same step runs
`glab mr create` instead. Review the PR like any other.

---

## The other timeline — when things go wrong

**A task fails** (agent exited non-zero):

```bash
cat .thrawn/runs/gh-42/task-t2.log     # what happened
cat .thrawn/worktrees/gh-42/t2/THRAWN-BLOCKED.md   # if it declared itself blocked
```

Fix the cause (often: the task prompt was ambiguous, or the ticket lied),
then either patch the worktree yourself and `thrawn integrate gh-42`, or
`thrawn abort gh-42` and start over with a better ticket.

**Integration stuck red:**

```bash
cd .thrawn/worktrees/gh-42/_integration   # poke at it yourself
thrawn integrate gh-42                    # then retry merge + checks
```

**You closed the laptop mid-run:** agents in herdr panes kept going.

```bash
thrawn status          # where things stand
thrawn watch gh-42     # resume orchestration
```

**Burn it down:**

```bash
thrawn abort gh-42     # kills agents, removes worktrees, deletes task branches
```

Your repo is untouched — everything thrawn does lives in `.thrawn/` and on
`thrawn/*` branches until the moment you ship.

---

## Variant: no ticket, just an idea

Write a brief instead — same pipeline, different intake:

```bash
cp ~/path/to/agentic-development/thrawn/templates/THRAWN.md .
$EDITOR THRAWN.md      # goal, context, constraints, routing hints
thrawn                 # bare = picks up ./THRAWN.md
```

Briefs beat tickets when you know things the tracker doesn't: which modules
are involved, what's out of scope, "the CSS is trivial, route it to haiku".

## Cheat sheet

| Moment | Command |
|--------|---------|
| New repo | `thrawn recon` |
| Cautious dispatch | `thrawn plan 42` → review → `thrawn watch gh-42` |
| Confident dispatch | `thrawn 42` |
| Re-run `thrawn 42` | resumes the open run — never re-plans (`--new` forces fresh) |
| See a saved plan | `thrawn plan gh-42 --full` |
| Where are things? | `thrawn status` / `thrawn runs` |
| It's green | `thrawn ship gh-42 --code NNNNNN` |
| Retry integration | `thrawn integrate gh-42` |
| Resume after ctrl-c | `thrawn watch gh-42` |
| Give up | `thrawn abort gh-42` |
