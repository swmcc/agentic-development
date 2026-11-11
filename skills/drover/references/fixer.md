# Fixer brief: one MR, every note answered, pipeline green

Paste this to each fixer agent with the MR's scan row (url, project, iid, branch, sha, failing_jobs, threads, conflicts) filled in below it.

---

You're finishing one of Stephen McCullough's merge requests so it can be re-reviewed. Work only on this MR.

1. **Worktree.** Find the repo under `~/Documents/Code` whose `origin` matches the project. Use or create the worktree `<repo>/.claude/worktrees/<short-name>` on the MR's source branch: `git -C <repo> worktree add <path> <branch>` if it isn't there, then `git pull --ff-only`. Read the repo's AGENTS.md or CLAUDE.md first. Other people (Ryan, for one) sometimes push to these branches: always build on top of what's there, never discard their commits.
2. **Read every open note.** Fetch all discussions: `glab api "projects/<url-encoded project>/merge_requests/<iid>/discussions?per_page=100"`. Ignore Review Bot, Wiz and system notes. Act on every thread whose last word is from a human reviewer and isn't just a confirmation: Required, MAJOR, MINOR, Consider, NIT and QUESTION alike. **If the MR already has an approval on its current head, a push clears it, so on an approved MR fix only real bugs and blocking points (Required, MAJOR, a reviewer who won't approve) and leave MINOR, NIT, Consider and QUESTION points unfixed: list them in your report under `TICKET THESE:` with the reviewer and a link to each thread, and reply on those threads that they're going to a follow-up. An MR with no approvals yet takes every fix in one push.** Fix it in code. If you genuinely disagree, have file-and-line evidence and say so politely in the reply instead. A reviewer's summary note ("Review: Request changes" / "Approve, with comments") is answered by fixing what it lists.
3. **Fix the pipeline.** For each job in `failing_jobs`, read its log (`glab api projects/<id>/jobs/<job id>/trace`) and fix the cause in this MR. If a job failed on infrastructure (a 429, a runner or network error), retry it with `glab api -X POST projects/<id>/jobs/<job id>/retry` instead of changing code. Jobs that also fail on main aren't this MR's to fix.
4. **Conflicts.** If the MR conflicts with its target, merge the target into the branch (`git merge origin/<target>`). Never rebase and never force-push.
5. **Description.** If the change makes the MR description wrong (the mechanism, the QA steps, the test counts), update it with `glab mr update <iid> --description "$(cat file)"`. Keep its first line, the `> **On merge:** move ...` line.
6. **Test, then push once.** Run the tests for what you touched (use `~/Documents/Code/<repo>/.venv/bin/python -m pytest` if the worktree has no venv) and pre-commit on changed files. A new test must fail without the fix. Commit with a gitmoji title `<emoji> <TICKET>: <what changed>`, a body saying why, ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push once with a plain `git push`. Each push clears the reviewers' approvals, so batch everything into it.
7. **Watch the pipeline** to the end (poll every 60s, up to 25 min). If it fails because of this MR, fix and push again.
8. **Reply on every thread you acted on**, in one or two casual first-person sentences: what changed and the commit. British English, no em or en dashes, no Oxford comma. Never resolve a thread; that's the reviewer's click.

Never write an internal ticket key (`COS-1234`, `SE-495`, `OL-…`, `WK-…`) in code, comments, docstrings, test names or fixtures; keys go in commit messages only. The pre-commit hook enforces it: fix the lines, never use `--no-verify`. Never git stash, never push to main, never merge or approve the MR, never touch Jira.

**Stop and report instead of guessing** if a note needs a decision from Stephen (a design choice, a scope question, a disagreement between reviewers), or if the work is more than about two hours.

Report in under 150 words: for each thread, what you did; the commit sha; the final pipeline status; and anything that needs Stephen, starting with `NEEDS STEPHEN:`.

---

## Follow-up: NITs left on an MR that merged approved

Use this section instead of steps 1 to 5 above when the Drover hands you a merged MR, its `nits` and a new ticket key (`<NEW>`). The Drover has already raised that ticket and moves it in Jira; you don't touch Jira. Every reviewer approved, so the original MR merged as it was. Your job is to clear the NITs in one small MR.

1. **Branch.** In the repo, create the worktree `<repo>/.claude/worktrees/<short-name>-nits` on a new branch `fix/<NEW>-nits-from-<iid>`, from `origin/main` (which now holds the merge). Use `git worktree add -b <branch> <path> origin/main`, then `git branch --unset-upstream` so the branch never tracks main.
2. **Fix every NIT** in the list. If one would mean reworking the change rather than tidying it, leave it and say so in your report under `NEEDS STEPHEN:`.
3. **Test** what you touched and run pre-commit on changed files. Commit `🎨 <NEW>: NITs from !<iid>`, with a body that names the reviewers' points, ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
4. **Open the MR.** Use the repo's `.gitlab/merge_request_templates/default.md` and write it in Stephen's voice: British spelling, no em or en dashes, no Oxford comma. Its first line is `> **On merge:** move <NEW> to **Done**.` Under JIRA Tickets, link `<NEW>`, and mention the original MR and its ticket in the text. Run `git push -u origin <branch>`, then `glab mr create --source-branch <branch> --target-branch main --assignee @me --reviewer <NIT authors' usernames> --yes`.
5. **Reply on each NIT thread** of the original MR: "Merged as approved; this one's in !<new iid>." Never resolve it.

Report the new MR's link, which NITs went in, the pipeline status and any `NEEDS STEPHEN:` line.
