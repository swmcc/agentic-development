#!/usr/bin/env python3
"""Find Stephen's open MRs and say what each one needs next.

Usage: scan.py [--only <url>...]

Prints JSON: {"me": ..., "mrs": [...]} with one row per open, non-draft MR he authored
across GitLab. Each row carries a `state`:

  running         a pipeline is running; leave it for the next run
  claimed         another Drover run is working on it
  needs_work      a blocking job failed because of this MR, there are merge conflicts, or a
                  human left a note nobody has answered
  ready_to_merge  every human reviewer approved, the pipeline passed, GitLab says mergeable
                  and nothing is waiting on a reply
  waiting_review  answered and green, but some reviewer hasn't approved this head yet
  parked          its ticket is in parked.txt

`ask` lists the reviewers of a waiting_review MR not yet asked at this head (state.py).
`on_merge` is "QA" or "Done" from the description's "On merge" line, or null.
"""
import json, re, subprocess, sys, time
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import state as drover_state  # noqa: E402

BOTS = re.compile(r"review bot|wiz connector|renovate|propagate|gitlab", re.I)
RUNNING = {"running", "pending", "created", "preparing", "waiting_for_resource", "scheduled"}
# A reviewer's note that only confirms or closes the loop needs no reply.
CLOSING = re.compile(
    r"^\s*(\*\*)?(hold lifted|my comments are up|fixed in|fixed at|fixed:|confirmed fixed|checked at|"
    r"(the )?fix(es)? look(s)? good|look(s)? good( to me)?|lgtm|all good|"
    r"re-review at [0-9a-f]+: (still )?approve\.?\*\*\s*$)",
    re.I,
)
APPROVAL_SUMMARY = re.compile(r"^\s*\**\s*(re-review at [0-9a-f]+: |review: )approve\b", re.I)
HOLD_NOTE = re.compile(r"\s*I'm reviewing this now, so I've put a hold on merging", re.I)
STILL_OPEN = re.compile(r"\b(required|consider|nit|major|minor|question|blocking)\b", re.I)
# The label a reviewer opens a note with: **NIT**, **Required:**, **Consider:** and so on.
LABEL = re.compile(r"^\s*\*\*\s*(nit|nitpick|required|consider|minor|major|question|fyi|blocking)\b", re.I)
KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
ON_MERGE = re.compile(r"On merge:\*\*.*?to \*\*(QA|Done)\*\*", re.I)


def api(path):
    out = subprocess.run(["glab", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"glab api {path}: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout or "null")


def api_all(path):
    rows, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        batch = api(f"{path}{sep}per_page=100&page={page}")
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        page += 1


def parked_keys():
    f = HERE.parent / "parked.txt"
    if not f.exists():
        return set()
    return {l.strip() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")}


def failed_blocking_jobs(pid, pipeline_id):
    jobs = api_all(f"projects/{pid}/pipelines/{pipeline_id}/jobs?scope[]=failed")
    return sorted({j["name"] for j in jobs if not j.get("allow_failure")})


def main_failing_jobs(pid, cache):
    if pid in cache:
        return cache[pid]
    names = set()
    try:
        latest = api(f"projects/{pid}/pipelines?ref=main&per_page=1")
        if latest:
            names = set(failed_blocking_jobs(pid, latest[0]["id"]))
    except RuntimeError:
        pass
    cache[pid] = names
    return names


def open_threads(pid, iid, me):
    threads = []
    for d in api_all(f"projects/{pid}/merge_requests/{iid}/discussions"):
        notes = [n for n in d.get("notes", []) if not n.get("system")]
        if not notes or BOTS.search(notes[0]["author"]["name"]):
            continue
        if notes[0].get("resolvable") and all(n.get("resolved") for n in notes if n.get("resolvable")):
            continue
        last = notes[-1]
        if last["author"]["username"] == me or BOTS.search(last["author"]["name"]):
            continue
        body = last.get("body", "")
        if CLOSING.search(body) and not STILL_OPEN.search(body.split("\n", 1)[-1] if "\n" in body else ""):
            continue
        # An approval summary points at its inline threads, which are checked on their own.
        if APPROVAL_SUMMARY.match(body):
            continue
        # A reviewer's "reviewing now" hold is a status note: it asks for nothing and comes off with their review.
        if HOLD_NOTE.match(body):
            continue
        pos = notes[0].get("position") or {}
        label = LABEL.match(notes[0].get("body", ""))
        threads.append({
            "label": label.group(1).lower().replace("nitpick", "nit") if label else None,
            "discussion_id": d["id"],
            "author": last["author"]["name"],
            "at": last.get("created_at"),
            "where": f'{pos.get("new_path")}:{pos.get("new_line")}' if pos.get("new_path") else "general",
            "excerpt": re.sub(r"\s+", " ", body)[:300],
        })
    return threads


def row_for(mr, me, claims, main_cache, parked):
    pid, iid = mr["project_id"], mr["iid"]
    url = mr["web_url"]
    keys = sorted(set(KEY.findall(mr["source_branch"] + " " + mr["title"])))
    row = {
        "url": url, "project": mr["references"]["full"].split("!")[0], "project_id": pid, "iid": iid,
        "title": mr["title"], "branch": mr["source_branch"], "tickets": keys, "sha": mr["sha"],
        "target": mr["target_branch"],
    }
    if parked & set(keys):
        return {**row, "state": "parked"}
    if url in claims:
        return {**row, "state": "claimed"}

    full = api(f"projects/{pid}/merge_requests/{iid}")
    pipeline = full.get("head_pipeline") or {}
    pstatus = pipeline.get("status")
    m = ON_MERGE.search(full.get("description") or "")
    row.update({
        "pipeline": pstatus, "pipeline_url": pipeline.get("web_url"),
        "merge_status": full.get("detailed_merge_status"), "conflicts": full.get("has_conflicts"),
        "on_merge": {"qa": "QA", "done": "Done"}[m.group(1).lower()] if m else None,
        "stacked_on": full["target_branch"] if full["target_branch"] not in ("main", "master") else None,
    })
    if pstatus in RUNNING:
        return {**row, "state": "running"}

    reviewers = [r for r in api(f"projects/{pid}/merge_requests/{iid}/reviewers")
                 if not BOTS.search(r["user"]["name"])]
    row["reviewers"] = [{"name": r["user"]["name"], "username": r["user"]["username"], "state": r["state"]}
                        for r in reviewers]

    failing = []
    if pstatus == "failed":
        mine = set(failed_blocking_jobs(pid, pipeline["id"]))
        failing = sorted(mine - main_failing_jobs(pid, main_cache))
        row["failing_on_main_too"] = sorted(mine & main_failing_jobs(pid, main_cache))
    row["failing_jobs"] = failing
    row["threads"] = open_threads(pid, iid, me)

    approved = [r for r in row["reviewers"] if r["state"] == "approved"]
    mergeable = (row["reviewers"] and len(approved) == len(row["reviewers"]) and pstatus == "success"
                 and row["merge_status"] == "mergeable" and not row["stacked_on"])
    # Approved with only NITs left: merge now and take the NITs to a follow-up, rather than
    # spend another push, pipeline and re-review round on them.
    nits = [t for t in row["threads"] if t["label"] == "nit"]
    if mergeable and not failing and not row["conflicts"] and len(nits) == len(row["threads"]):
        return {**row, "nits": nits, "state": "ready_to_merge"}
    if failing or row["threads"] or row["conflicts"]:
        return {**row, "state": "needs_work"}
    st = drover_state.load()
    asked = st.get("asked", {}).get(url, {})
    row["ask"] = [r for r in row["reviewers"] if r["state"] != "approved" and asked.get(r["username"]) != mr["sha"]]
    return {**row, "state": "waiting_review"}


def main(argv):
    only = set(argv[argv.index("--only") + 1:]) if "--only" in argv else None
    me = api("user")["username"]
    mrs = api_all("merge_requests?scope=created_by_me&state=opened")
    claims = drover_state.live_claims(drover_state.load())
    parked, main_cache, rows = parked_keys(), {}, []
    for mr in mrs:
        if mr.get("draft") or mr.get("work_in_progress"):
            continue
        if only and mr["web_url"] not in only:
            continue
        if mr["web_url"] in parked:
            continue  # a forgotten MR: no row, no page entry
        try:
            rows.append(row_for(mr, me, claims, main_cache, parked))
        except RuntimeError as e:
            rows.append({"url": mr["web_url"], "title": mr["title"], "state": "error", "error": str(e)})
    print(json.dumps({"me": me, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "mrs": rows}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
