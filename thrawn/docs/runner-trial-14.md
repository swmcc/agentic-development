# Runner trial: pi vs codex on the same task batch (issue #14)

Why: both pi and codex bill to the same ChatGPT subscription, so the question
is which harness earns the mechanical traffic on that pool (and whether either
beats haiku on the Claude pool). The ledger decides, not enthusiasm. See
agentic-development#8 for the full economics analysis.

## Method

- Target repo: swmcc/rails_love_letter (Rails 8, RSpec, RuboCop)
- Batch: five unblocked agent-ready size:S issues — #36 (typo bugfix),
  #37 (schema hardening migration), #38 (GitHub Actions CI), #39 (card
  catalogue value object), #56 (stale-game cleanup task)
- One swarm leg per runner, sequential: codex first, review and snapshot,
  abort, then pi on the same five issues
- Baseline before either leg: `make lint` clean (33 files), `make test`
  green (2 examples). Note the suite is thin — "checks pass" is a weak
  signal here; branch quality is judged by review.
- codex emits no usage events, so its quota burn is only visible on the
  ChatGPT usage page — leg start/end timestamps below are for
  cross-referencing that. pi usage comes from thrawn's per-task capture
  (state.json, recorded by poll_tasks).

## Scoring per branch

adopt (mergeable as-is) / adopt-with-nits / reject; checks pass; needed
intervention; tokens (pi only); wall clock.

Wrinkle discovered during setup: a Rails-default `ci.yml` already exists
(brakeman, importmap audit, rubocop — no RSpec), so #38 is really "extend
the existing workflow". Left in the batch deliberately: it tests whether a
runner notices the existing file and extends it or blindly creates a
duplicate.

## Leg 1: codex

- false start 02:32:48Z: all five panes crashed in ~14s. Installed
  codex-cli was 0.7.0 and choked on a `[tui]` config section written by a
  newer codex (`missing field disable_mouse_capture`). Four tasks still
  wrote exit 0 — thrawn's zero-commit salvage check is what would have
  caught this on an automated run. Upgraded codex to 0.150.1 and verified
  auth against the ChatGPT subscription. Counts as an environment
  intervention, not a harness failure, but it is exactly the class of
  breakage a runner trial should surface.
- observation: codex 0.150.1's exec output includes a `tokens used` line,
  so codex usage capture may be feasible after all (follow-up for #12).
- started (real): 2026-08-28T02:35:12Z as run `swarm-2` (base main @ 172749e1)
- finished: 2026-08-28T02:37:39Z (~2.5 min wall clock, all five parallel)
- tokens (from codex `tokens used` lines): 36,431 + 38,885 + 29,078 +
  29,057 + 37,290 = 170,741 total

| issue | result | checks | notes |
|-------|--------|--------|-------|
| 36 | adopt | lint ok, 4 ex 0 fail | Typo fixed at both call sites plus request specs added. Log shows one odd `find /Users/swm` excursion outside the worktree before settling. |
| 37 | adopt | lint ok, 8 ex 0 fail | Textbook: bulk change_table migration, unique indexes on games.code and participants (game_id, session_id), model validations, code auto-generation, specs. Schema.rb updated. |
| 38 | adopt-with-nits | lint ok, 2 ex 0 fail | Passed the judgement test: extended the existing ci.yml rather than duplicating. Restructured into test (postgres 17 service, db:prepare, rspec), lint (rubocop) and security (brakeman) jobs. Nit: dropped the importmap audit job. |
| 39 | adopt | lint ok, 7 ex 0 fail | Frozen card catalogue value object with specs, 127 lines added. |
| 56 | adopt | lint ok, 3 ex 0 fail | Rake task plus model scope and specs. |

Leg summary: 5/5 committed, 5/5 checks green, 4 adopt + 1 adopt-with-nits,
zero interventions after the CLI upgrade. Commit subjects even follow the
repo's emoji convention.

## Leg 2: pi

- started: 2026-08-28T02:39:35Z as run `swarm-3` (base main @ 172749e1)
- finished: 2026-08-28T02:43:47Z (~4.2 min wall clock, all five parallel)
- usage from thrawn's own capture (state.json), total incl cache reads
  1,691,260 — but 1,443,328 of that is cache_read; fresh input 225,910 +
  output 22,022 = 247,932. API-rate cost equivalent $2.51 (informational,
  billed to subscription quota in reality). No task flagged rate limited.

| issue | result | checks | tokens (fresh/total) | notes |
|-------|--------|--------|----------------------|-------|
| 36 | adopt | lint ok, 4 ex 0 fail | 59k / 431k | Same shape as codex: typo fixed, request specs added. |
| 37 | adopt | lint ok, 9 ex 0 fail | 84k / 821k | Equivalent hardening to codex plus one extra spec file, 129 insertions. |
| 38 | adopt | lint ok, 2 ex 0 fail | 16k / 36k | Also extended the existing ci.yml, and did it better: added an RSpec job with a postgres 16 service while KEEPING brakeman and the importmap audit. Best branch of the ten. |
| 39 | adopt-with-nits | LINT FAILS, 9 ex 0 fail | 20k / 45k | Good catalogue and specs but six rubocop offences (class length, parameter list, layout) — pi never ran the linter before committing. |
| 56 | adopt-with-nits | LINT FAILS, 6 ex 0 fail | 70k / 358k | Working rake task and specs but rubocop offences (block length, update_columns in specs). Same failure: no lint pass. |

Leg summary: 5/5 committed, 3/5 checks green, 3 adopt + 2 adopt-with-nits.

## Raw data

Snapshots under `runner-trial-14/`: per-leg state.json (pi usage captured
by thrawn), `git diff` per branch as .patch (any branch can be recreated
with `git apply`), task logs gzipped. Both swarms aborted after snapshot;
the five issues stay open for a real dispatched run.

## Verdict (phase 1)

- Substance: even. Both runners shipped credible, spec-covered work on all
  five issues; both passed the extend-don't-duplicate judgement test on the
  CI file. pi produced the single best branch (#38); codex produced no
  failing branch.
- Discipline: codex. It ran the checks before committing (5/5 green); pi
  skipped linting and failed checks on 2/5. Mechanical to fix, but "adopt
  as-is" is the metric, and unattended operation is the point.
- Speed: codex, 2.5 min vs 4.2 min for the batch.
- Quota: codex self-reported 171k; pi's fresh tokens 248k with zero cache
  writes recorded and heavy cache reads (the provider caches server-side).
  Semantics of codex's "tokens used" line are unknown, so treat this as
  indicative only. Neither leg came close to a rate limit.
- Telemetry: pi, decisively. thrawn captured normalised per-task usage
  automatically; codex needed its log line scraped by hand.

Provisional call: codex stays the default subscription-backed worker for
mechanical tasks; pi earns a seat where usage accounting matters, and its
lint discipline is a prompt fix (make the executor prompt's check step
explicit) rather than a harness flaw. Phase 2 (a fortnight of planner
routing with both in rotation) decides the split properly.

Environment findings worth keeping regardless of runner choice: the
codex-cli 0.7.0 config crash (silent exit 0 on four of five tasks) and
codex 0.150.1's `tokens used` line as a future #12 data source.
