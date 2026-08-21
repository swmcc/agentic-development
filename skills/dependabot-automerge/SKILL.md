---
name: dependabot-automerge
description: "Set up, audit, or fix Dependabot auto-merge for a GitHub repo so patch and minor updates merge only after tests pass, and major updates never merge automatically. Use when asked to enable Dependabot auto-merge, automerge dependency PRs, stop Dependabot PR noise, require status checks before merging dependency updates, or check whether an existing auto-merge setup is actually safe."
---

# Dependabot auto-merge

Set up a repo so Dependabot **patch and minor** PRs merge automatically once the
existing tests pass, and **major** PRs never do.

Audit before you change anything. Most repos that look ready are not, and the
common failure mode is automation that reads as safety while merging untested
code.

## The one thing to get right

**Auto-merge with no required status check merges immediately.** `gh pr merge --auto`
means "merge as soon as requirements are satisfied". If the branch has no required
checks, there is nothing to wait for, so the PR merges straight away — untested.

Enabling `allow_auto_merge` on an unprotected branch is therefore *worse* than
doing nothing: it looks like a test gate and is the opposite of one. Never enable
auto-merge for a repo where you cannot also require checks.

## Step 1 — audit

Run `audit.sh <owner/repo>` (beside this file), or gather the same facts by hand.
Five things decide whether the repo is eligible:

| Fact | How | Blocks setup if |
|---|---|---|
| Admin permission | `gh api repos/O/R --jq .permissions.admin` | false |
| Dependabot enabled | `gh api repos/O/R/contents/.github/dependabot.yml` | absent — no PRs to merge |
| Real test checks | see below | none, or only linters/scanners |
| Branch protection available | `gh api repos/O/R/branches/M/protection` | `Upgrade to GitHub Pro` |
| Existing auto-merge workflow | list `.github/workflows/` | must be fixed, not duplicated |

### Getting check names right

Required status checks match the **check-run name**, which is the *job id*, not the
workflow name. A workflow called `CI` with jobs `test` and `lint` produces checks
named `test` and `lint`. Requiring `CI` would wait forever.

```bash
sha=$(gh api "repos/O/R/commits?per_page=1" --jq '.[0].sha')
gh api "repos/O/R/commits/$sha/check-runs" --jq '.check_runs[].name' | sort -u
```

Cross-check against the workflow source, because a check only appears here if it
ran on that commit. A `pull_request`-only workflow shows nothing on a default-branch
commit but is still a valid required check:

```bash
gh api repos/O/R/contents/.github/workflows/ci.yml --jq .content | base64 -d
```

**Requiring a job that does not exist deadlocks every PR in the repo, permanently.**
Only require names you have confirmed in the workflow source.

Judge the checks, don't just count them. Lint and vulnerability scanners passing
tells you nothing about whether an upgraded dependency still works. If a repo has
`lint` and `scan_*` but no `test` job, say so — the honest recommendation is usually
to add tests first, not to automate merging on the strength of a linter.

## Step 2 — report, and stop if ineligible

Show the audit before changing anything, and state plainly which repos are not
eligible and why. Do not enable auto-merge to be helpful when the gate cannot be
enforced. Common outcomes:

- **No CI** → not eligible. Nothing to gate on.
- **No `dependabot.yml`** → nothing to auto-merge. Offer to add it as a separate step.
- **Private repo, free plan** → branch protection unavailable. Either leave it alone,
  or use the workflow's own CI gate (Step 3 variant B) and be explicit that it is
  weaker: anyone editing the workflow bypasses it.
- **Only linters/scanners** → say the gate is nominal, and recommend tests.

## Step 3 — apply

Three pieces are required. All three, or the policy is not enforced.

### a. Repo setting

```bash
gh api -X PATCH "repos/O/R" -F allow_auto_merge=true
```

### b. Branch protection with the confirmed check names

Read the current protection first and preserve it — this endpoint is a full
replacement, so any field you omit is silently dropped.

```bash
gh api "repos/O/R/branches/main/protection" > /tmp/before.json   # keep for rollback

gh api -X PUT "repos/O/R/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": { "strict": true, "contexts": ["test", "lint"] },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

`required_pull_request_reviews: null` matters. Dependabot cannot approve its own
PR, so requiring a human review means auto-merge never fires.

### c. The workflow — this is what enforces patch/minor

**No `gh` setting distinguishes a patch from a major.** That distinction exists only
in `dependabot/fetch-metadata`. Without this file, "never auto-merge major" is not
enforced, no matter what the branch protection says. Copy
`dependabot-auto-merge.yml` from beside this file into `.github/workflows/`.

Note it needs `pull_request_target`, not `pull_request` — Dependabot PRs run with a
read-only token otherwise, and `gh pr merge` fails with a permissions error.

## Step 4 — show what changed

Report per repo: the setting flipped, the exact contexts now required, the workflow
added, and anything deliberately skipped with the reason. Keep the pre-change
protection JSON so it can be restored.

## Fixing an existing setup

Two failure modes are common in workflows written before this skill:

- **No semver gate** — `if: github.actor == 'dependabot[bot]'` merges *everything*,
  majors included. Add the `fetch-metadata` condition.
- **No CI gate** — calling `gh pr merge --auto` on an unprotected branch merges
  immediately. Add branch protection, or trigger on `workflow_run` completion.

Fix in place rather than adding a second workflow; two auto-merge workflows race.

## Gotchas

- `jq '.allow_auto_merge // "?"'` prints `"?"` when the value is `false` — `//`
  treats `false` as empty. Use `| tostring`.
- The default shell here is zsh, which does **not** word-split unquoted variables.
  `for r in $repos` iterates once with the whole string. Use an array.
- Auto-merge is cancelled if anyone pushes to the PR branch; Dependabot rebases
  land as force-pushes, which is fine, but a manual push silently disables it.
