---
name: test-plan
description: Write the "QA by tests" test plan on a Jira ticket from its merged MR, in the shape the RBAC/GBAC epic uses for native tests - a numbered check table mapping each acceptance criterion to the test that covers it, with real local counts on main, revert proof, CI links and what isn't covered - then label it needs-native-tests. Use when the user types /test-plan, asks for a test plan, a "QA by tests" note or the native-tests write-up on a ticket, or when the Drover merges an MR on the epic.
---

🧪 Every ticket on the RBAC/GBAC epic (parent `COS-3789` or label `rbac-gbac`) that leaves Peer Review by merge gets a test plan on the ticket, labelled `needs-native-tests`. Karim's native-test work starts from these, and QA reads them to decide whether the ticket can leave QA on tests alone.

Arguments: one or more ticket keys, or merged MR links. `--post` posts without showing first (the Drover passes it). `--dry-run` writes the draft only.

The exemplar is COS-2916's 18 Nov comment ("**QA, 18 Nov.**"). Read it with `getJiraIssue` (fields `comment`) the first time in a session, and match it.

## 1. Gather

For each ticket:

1. `getJiraIssue` (cloudId `28feb242-73cf-475d-8304-4c5b3fd27dcc`, fields `summary`, `description`, `status`, `labels`, `comment`). Take the acceptance criteria or "Done when" from the description, and read every comment: earlier plans, review points and known gaps all belong in the plan.
2. Find its merged MRs: `glab api "groups/whitedotspace/merge_requests?state=merged&search=<KEY>"`, plus any linked from the comments. For each, note the merge commit (`merge_commit_sha`, else `squash_commit_sha`), the MR description's "What we did and what we assumed" section, and main's pipeline for that merge commit (`projects/<p>/pipelines?sha=<merge sha>`), with its status and link.
3. If nothing has merged, stop for that ticket and say so: a plan is written from merged code, never from an open MR.

## 2. Run the tests on main

In the repo's local clone, `git fetch origin main`, then a throwaway detached worktree at `origin/main`: `git worktree add --detach <clone>/.claude/worktrees/testplan-<key> origin/main`. Never stash, commit or push.

- Run every test file the MR added or changed (from `git diff --name-only <merge>^1 <merge>`), and the suite around them. Python: `uv sync --offline --frozen --all-extras`, then `uv run --offline --frozen pytest -q -p no:cacheprovider <files>`. JS: the package's own test script.
- **Revert proof:** in the same worktree, put the MR's non-test files back to their pre-merge state (`git checkout <merge sha>^1 -- <non-test paths>`), run the new tests again and record how many fail. Then `git checkout origin/main -- .` and confirm `git status` is clean. A test-only MR has nothing to revert: say so.
- Remove the worktree.

If the env can't be built offline, say so in the plan and cite the merged pipeline instead. Never claim a run you didn't do.

## 3. Write the plan

One check per acceptance criterion or behaviour the fix promises, numbered with a two-letter prefix from the ticket's area (`RC-` register code, `SS-` sessions, `EB-` event bus, `PR-` preferences, and so on). Each row names where it's covered and the result:

- ✅ the test exists, asserts the behaviour, and passed locally and in CI;
- ⚠️ covered only partly: a mocked collaborator, an assertion that doesn't pin the thing, or a test that also passes with the fix reverted. Say which;
- ❌ not covered by any test.

Format, exactly:

```
**QA, <d Mon>.** <Unit tests only, no live environment run | or what ran live>. <Moving to QA | Staying in QA for ... | Done on tests>. <repo> [!<iid>](<mr url>) (merge <short sha>), CI [pipeline <id>](<url>) <status>. Local run at <short sha> (main containing it): `<files>`, <n> passed, <n> failed.

| # | Check | Where | Result |
| --- | --- | --- | --- |
| XX-01 | <behaviour in plain words> | Unit (!<iid>, `<path>::<test name>`) | ✅ <what it asserts, in a sentence>. CI success, local pass |

**Notes**

* Not covered: <each gap, and what would close it>
* No live run. <what that leaves unverified>
* <revert proof: reverting !<iid>'s change on <sha> fails <n> of the <n> tests>
```

When an earlier plan exists on the ticket, don't edit it: write a new one that says which earlier checks changed (e.g. RC-06 ⚠️ to ✅) and why.

Voice: plain, British spelling, no em or en dashes, no Oxford comma. Run `grep -n '—\|–'` on the draft. Test names and paths appear as they are in code; never add a ticket key to code.

## 4. Show it, then post

Save each draft to `<scratchpad>/test-plan/<KEY>.md`. Without `--post`, show a short summary per ticket (checks, how many ✅ ⚠️ ❌, counts, revert proof) and stop until I say post.

To post: `addCommentToJiraIssue` with `contentFormat: "markdown"`. Then add the label: read `labels` first and `editJiraIssue` with the full list plus `needs-native-tests` (the field replaces the list).

**Don't move the ticket.** The merge already moved it per the MR's On merge line. If the plan has a ❌ or a ⚠️ on a core behaviour and the ticket is Done, say so in the report; I'll decide whether it goes back to QA.

## 5. Report

One line per ticket: the comment link (`<ticket url>?focusedCommentId=<id>`), counts, ✅/⚠️/❌, and any gap worth a ticket.
