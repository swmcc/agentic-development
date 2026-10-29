#!/usr/bin/env python3
"""Turn a read of #collective-mrs into the MRs worth reviewing.

Usage:
  candidates.py <channel.txt> [--mode mine|all] [--author a,b] [--repo r,s] [--cap 6]

<channel.txt> is the text the Slack connector's slack_read_channel returns in its detailed
format, saved as is. Prints JSON: `selected` (oldest post first, at most --cap), `over_cap`,
`skipped` (each with a reason) and `newest_ts`, the timestamp to save as the next sweep's start.

Slack can't be read from a shell, so a Claude session fetches the channel and this does the rest.
"""
import argparse, json, os, re, subprocess, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ME_GITLAB = "swmcc_whitespace"
ME_SLACK = "U082BL09HK4"
REVIEWS_DIR = Path(os.environ.get("COLLIE_REVIEWS_DIR", Path.home() / "Documents/wiki/reviews"))

HEADER = re.compile(r"^=== Message from (?P<who>.+?) \((?P<uid>[A-Z0-9]+)\) at (?P<when>.+?) ===\s*$")
MR_URL = re.compile(r"https://gitlab\.com/(?P<path>[\w.\-/]+?)/-/merge_requests/(?P<iid>\d+)")
STRUCK = re.compile(r"~[^~\n]+~")
# The name /review-mr gives a draft, the same pattern collie reads drafts with.
DRAFT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+?)-(\d+)(?:-[A-Z][A-Z0-9]*-\d+)*\.md$")


@dataclass
class Message:
    who: str
    uid: str
    ts: str = ""
    body: list = field(default_factory=list)
    reactions: list = field(default_factory=list)

    @property
    def name(self):
        return self.who.split(" <", 1)[0].strip()

    @property
    def text(self):
        return "\n".join(self.body)


@dataclass
class Mention:
    url: str
    path: str
    iid: int
    posted_by: str
    posted_ts: str
    struck: bool
    mentions_me: bool
    bot_template: bool
    reactions: list


def parse(text):
    """Split the connector's text into messages, keeping the body lines and the reactions."""
    messages, current = [], None
    for line in text.splitlines():
        if m := HEADER.match(line):
            current = Message(m["who"], m["uid"])
            messages.append(current)
        elif current is None:
            continue
        elif line.startswith("Message TS: "):
            current.ts = line.removeprefix("Message TS: ").strip()
        elif line.startswith("Reactions: "):
            current.reactions = re.findall(r"([\w+\-]+) \(\d+\)", line)
        elif line.startswith("Thread: "):
            continue
        else:
            current.body.append(line)
    return messages


def mentions(messages):
    """One Mention per MR, taken from its newest post, so a bump of ten links counts each once."""
    found = {}
    for msg in sorted(messages, key=lambda m: float(m.ts or 0)):
        struck = {u.group(0) for s in STRUCK.findall(msg.text) for u in MR_URL.finditer(s)}
        for u in MR_URL.finditer(msg.text):
            url = u.group(0)
            found[url] = Mention(
                url=url, path=u["path"], iid=int(u["iid"]), posted_by=msg.name, posted_ts=msg.ts,
                struck=url in struck, mentions_me=ME_SLACK in msg.text,
                bot_template=msg.name.startswith("Review Bot") and "Copier Template" in msg.text,
                reactions=msg.reactions,
            )
    return list(found.values())


def existing_drafts(directory=REVIEWS_DIR):
    """(repo, iid) for every draft I've written, posted or not."""
    try:
        names = os.listdir(directory)
    except FileNotFoundError:
        return set()
    return {(m[1], int(m[2])) for n in names if (m := DRAFT_NAME.match(n))}


def glab_json(endpoint):
    out = subprocess.run(["glab", "api", endpoint], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else None


def gitlab_lookup(path, iid):
    """The MR as GitLab sees it, or None if it can't be read."""
    base = f"projects/{urllib.parse.quote(path, safe='')}/merge_requests/{iid}"
    mr = glab_json(base)
    if mr is None:
        return None
    approvals = glab_json(f"{base}/approvals") or {}
    return {
        "title": mr["title"],
        "state": mr["state"],
        "draft": mr.get("draft", False),
        "author": mr["author"]["username"],
        "author_name": mr["author"]["name"],
        "reviewers": [r["username"] for r in mr.get("reviewers", [])],
        "approved_by": [a["user"]["username"] for a in approvals.get("approved_by", [])],
    }


def _matches(wanted, names):
    names = [n.lower() for n in names if n]
    return any(n.startswith(w) for w in wanted for n in names)


def skip_reason(m, mr, drafts, opts):
    """Why this MR stays out of the sweep, or None if it goes forward. First reason wins."""
    repo = m.path.rsplit("/", 1)[-1]
    checks = [
        (m.bot_template, "template update from Review Bot"),
        (m.struck, "struck through in Slack"),
        (mr is None, "couldn't read it from GitLab"),
        (mr and mr["state"] != "opened", f"{mr and mr['state']}"),
        (mr and mr["draft"], "draft MR"),
        (mr and mr["author"] == ME_GITLAB, "mine"),
        (mr and ME_GITLAB in mr["approved_by"], "already approved by me"),
        ((repo, m.iid) in drafts, "already drafted"),
        (opts.repo and repo.lower() not in opts.repo, "not in --repo"),
        (opts.author and mr and not _matches(opts.author, [m.posted_by, mr["author"], mr["author_name"]]),
         "not in --author"),
        (opts.mode == "mine" and mr and ME_GITLAB not in mr["reviewers"] and not m.mentions_me,
         "not asked to review (use all)"),
    ]
    return next((why for hit, why in checks if hit), None)


def sweep(messages, lookup, drafts, opts):
    found = mentions(messages)
    with ThreadPoolExecutor(max_workers=8) as pool:
        mrs = list(pool.map(lambda m: lookup(m.path, m.iid), found))
    keep, skipped = [], []
    for m, mr in zip(found, mrs):
        row = {
            "url": m.url, "repo": m.path.rsplit("/", 1)[-1], "iid": m.iid,
            "title": mr and mr["title"], "author": mr and mr["author"],
            "posted_by": m.posted_by, "posted_ts": m.posted_ts,
            "i_am_reviewer": bool(mr and ME_GITLAB in mr["reviewers"]),
            "approvals": mr["approved_by"] if mr else [],
        }
        why = skip_reason(m, mr, drafts, opts)
        (skipped if why else keep).append({**row, "skip_reason": why})
    keep.sort(key=lambda r: float(r["posted_ts"] or 0))
    newest = max((float(m.ts) for m in messages if m.ts), default=None)
    return {
        "selected": keep[: opts.cap],
        "over_cap": keep[opts.cap :],
        "skipped": skipped,
        "newest_ts": f"{newest:.6f}" if newest is not None else None,
    }


def options(argv):
    p = argparse.ArgumentParser()
    p.add_argument("channel")
    p.add_argument("--mode", choices=["mine", "all"], default="mine")
    p.add_argument("--author", default="")
    p.add_argument("--repo", default="")
    p.add_argument("--cap", type=int, default=6)
    o = p.parse_args(argv)
    o.author = [a.strip().lower() for a in o.author.split(",") if a.strip()]
    o.repo = [r.strip().lower() for r in o.repo.split(",") if r.strip()]
    return o


def main(argv):
    opts = options(argv)
    messages = parse(Path(opts.channel).read_text())
    print(json.dumps(sweep(messages, gitlab_lookup, existing_drafts(), opts), indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])
