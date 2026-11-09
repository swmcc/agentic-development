#!/usr/bin/env python3
"""Open MRs I reviewed without approving whose changes have moved on since: worth a second look.

Usage:
  rereview.py [--author a,b] [--repo r,s] [--out <dir>]

Asks GitLab, not my review files. It takes the group's open MRs that list me as a reviewer and
that I haven't approved, and for each finds the diff version I last commented on. If the
MR's changes are still the same, it was only rebased and is left alone. If they differ (new
commits, an amend, a force-push, a rebase that resolved a conflict), it comes back for a
re-review.

A rebase moves the head without changing what the MR does, which is why this compares each
version's changes against its own base rather than looking for new commits.

Prints JSON: `selected` (with the reviewed and current versions, so the re-review reads only
what changed) and `skipped` (each with a reason). With --out, writes the two versions'
diffs for each selected MR to <dir>/<repo>-<iid>/reviewed.diff and current.diff.
"""
import argparse, json, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from candidates import ME_GITLAB, _matches, glab_json
from state import live_claims, load as load_state

GROUP = "whitedotspace"
# Line numbers shift whenever main moves under a rebase, so hunk headers are left out of
# the comparison; the lines each hunk adds and removes are what the MR actually changes.
HUNK = re.compile(r"^@@[^@]*@@", re.M)


PAGE = 20  # GitLab answers 500 on this group-wide query at 100 a page


def my_open_reviews():
    """The group's open MRs that list me as a reviewer, all pages.

    A page GitLab fails to answer stops the run, so a failed read never looks like
    "nothing to re-review".
    """
    found, page = [], 1
    while True:
        batch = glab_json(f"groups/{GROUP}/merge_requests?state=opened"
                          f"&reviewer_username={ME_GITLAB}&per_page={PAGE}&page={page}")
        if batch is None:
            sys.exit(f"rereview: GitLab didn't answer page {page} of my reviews; try again")
        found += batch
        if len(batch) < PAGE:
            return found
        page += 1


def changes(version_diffs):
    """What a diff version changes, independent of where its base sits on main."""
    return sorted((d["new_path"], HUNK.sub("@@", d["diff"])) for d in version_diffs)


def last_comment_at(base):
    """When I last commented on the MR, a review summary or an inline note."""
    notes = glab_json(f"{base}/notes?sort=desc&order_by=created_at&per_page=100") or []
    mine = [n["created_at"] for n in notes if n["author"]["username"] == ME_GITLAB and not n["system"]]
    return max(mine, default=None)


class GitLab:
    def mr_state(self, mr):
        base = f"projects/{mr['project_id']}/merge_requests/{mr['iid']}"
        approvals = glab_json(f"{base}/approvals") or {}
        approved = [a["user"]["username"] for a in approvals.get("approved_by", [])]
        commented = last_comment_at(base)
        versions = glab_json(f"{base}/versions") or []
        return approved, commented, versions

    def version_diffs(self, mr, version_id):
        base = f"projects/{mr['project_id']}/merge_requests/{mr['iid']}"
        return (glab_json(f"{base}/versions/{version_id}") or {}).get("diffs", [])


def reviewed_version(versions, commented):
    """The newest version that existed when I last commented: the one my review was about."""
    before = [v for v in versions if v["created_at"] <= commented]
    return max(before, key=lambda v: v["created_at"]) if before else None


def assess(mr, gl, claimed, opts):
    """(skip reason or None, row) for one MR."""
    repo = mr["references"]["full"].split("!")[0].rsplit("/", 1)[-1]
    row = {"repo": repo, "iid": mr["iid"], "url": mr["web_url"], "title": mr["title"],
           "project": mr["references"]["full"].split("!")[0], "author": mr["author"]["username"]}
    early = [
        (mr["draft"], "draft MR"),
        (mr["author"]["username"] == ME_GITLAB, "mine"),
        (mr["web_url"] in claimed, "review in progress"),
        (opts.repo and repo.lower() not in opts.repo, "not in --repo"),
        (opts.author and not _matches(opts.author, [mr["author"]["username"], mr["author"]["name"]]),
         "not in --author"),
    ]
    if why := next((w for hit, w in early if hit), None):
        return why, row
    approved, commented, versions = gl.mr_state(mr)
    if ME_GITLAB in approved:
        return "approved", row
    if commented is None:
        return "never commented", row
    if not versions:
        return "no diff versions", row
    current = max(versions, key=lambda v: v["created_at"])
    reviewed = reviewed_version(versions, commented)
    if reviewed is None:
        return "commented before the first version", row
    row.update(reviewed={k: reviewed[k] for k in ("id", "base_commit_sha", "head_commit_sha")},
               current={k: current[k] for k in ("id", "base_commit_sha", "head_commit_sha")},
               last_comment_at=commented)
    if current["id"] == reviewed["id"]:
        return "nothing pushed since", row
    old, new = gl.version_diffs(mr, reviewed["id"]), gl.version_diffs(mr, current["id"])
    if changes(old) == changes(new):
        return "rebased only, same changes", row
    row["_diffs"] = (old, new)
    return None, row


def rereviews(mrs, gl, claimed, opts):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda m: assess(m, gl, claimed, opts), mrs))
    selected = [r for why, r in results if why is None]
    skipped = [{**{k: v for k, v in r.items() if k != "_diffs"}, "skip_reason": why}
               for why, r in results if why]
    return selected, skipped


def write_diffs(row, out):
    folder = Path(out) / f"{row['repo']}-{row['iid']}"
    folder.mkdir(parents=True, exist_ok=True)
    old, new = row.pop("_diffs")
    for name, diffs in (("reviewed.diff", old), ("current.diff", new)):
        (folder / name).write_text("".join(
            f"--- a/{d['old_path']}\n+++ b/{d['new_path']}\n{d['diff']}" for d in diffs))
    row["diffs"] = str(folder)


def options(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--author", default="")
    p.add_argument("--repo", default="")
    p.add_argument("--out")
    o = p.parse_args(argv)
    o.author = [a.strip().lower() for a in o.author.split(",") if a.strip()]
    o.repo = [r.strip().lower() for r in o.repo.split(",") if r.strip()]
    return o


def main(argv):
    opts = options(argv)
    claimed = set(live_claims(load_state()))
    selected, skipped = rereviews(my_open_reviews(), GitLab(), claimed, opts)
    for row in selected:
        if opts.out:
            write_diffs(row, opts.out)
        else:
            row.pop("_diffs")
    print(json.dumps({"selected": selected, "skipped": skipped}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
