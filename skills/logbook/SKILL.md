---
name: logbook
description: Record commits, pull requests and issues in my Commit Logbook, the shared page every herdr workspace writes to. Use when the user types /logbook, asks to log what was committed, or after committing and pushing work in any repo. Also use when a workspace finds an issue or something to do that nobody is acting on yet, or when a logged PR is merged or an issue is finished.
argument-hint: [what to log, or nothing to log the latest commits]
---

Record the work in `$ARGUMENTS`, or the commits this session has just made, in the Commit Logbook:

https://claude.ai/artifact/ShBvWRL1NJcuWo4AP1EwHK

Log facts you have checked. Never log a commit that is not in the repo, and never use a link you have not built from real values.

## 1. Gather the facts

For a commit, run these in the repo:

```bash
git log -1 --format='%H%n%cI%n%s' <sha>
git rev-parse --abbrev-ref HEAD
git remote get-url origin
git branch -r --contains <sha>
```

Turn the remote into `owner/repo`. The workspace is `$HERDR_WORKSPACE_ID`'s label from `herdr workspace get`, or the repo's folder name outside herdr.

## 2. Write the entry

Use the Artifact tool with `action: "write_db"`, the URL above, `collection: "entries"` and `db_op: "set"`. Several entries go in one `db_op: "batch"`. The tool's data is shared state, so keep secrets, customer names and anything private out of it.

| Field | Value |
|---|---|
| `kind` | `commit`, `pr` or `issue` |
| `repo` | `owner/repo` |
| `title` | The commit subject, or the PR or issue title |
| `why` | One line on why, only if the title does not say. Optional |
| `sha` | Full commit hash, commits only |
| `branch` | The branch |
| `url` | `https://github.com/<repo>/commit/<sha>`, or the PR or issue URL |
| `pr_url` | The PR, or `https://github.com/<repo>/pull/new/<branch>` until one exists |
| `status` | See below |
| `at` | ISO 8601 time: the commit time, or now for anything else |
| `workspace` | The herdr workspace |
| `machine` | `hostname -s`, capitalised |

Use `<repo-name>-<short sha>` as the `doc_id` for a commit, `<repo-name>-pr-<number>` for a PR and `<repo-name>-issue-<slug>` for an issue with no number. Logging the same thing twice then overwrites rather than duplicates.

| `status` | Meaning |
|---|---|
| `local` | Committed, not pushed |
| `pushed` | Pushed to a branch, no PR yet |
| `pr-open` | In a PR that is open |
| `merged` | On the default branch |
| `closed-unmerged` | The PR was closed without merging |
| `open` | An issue nobody has finished |
| `done` | The issue is finished |

## 3. Keep it current

When a logged PR merges or an issue is finished, use `db_op: "update"` on the same `doc_id` to change `status`, and add `pr_url` if the PR now exists.

## 4. Say what was logged

Reply with one line naming the entries, and the logbook link. If the write fails, say so. The commit stands either way.

Codex and pi panes cannot reach the logbook. Log their work from a Claude pane.
