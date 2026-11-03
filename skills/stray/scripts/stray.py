#!/usr/bin/env python3
"""Let my open MRs into #collective-mrs the way the team posts them, signed by a stray cow.

Usage:
  stray.py find [URL ...] [--drafts]      my open MRs (or the ones given) as JSON rows
  stray.py cow                            the next cow from the herd, as JSON (records nothing)
  stray.py used NAME                      mark a cow as having had its turn, once the post is sent
  stray.py render ROWS.json --cow NAME    the Slack message for those rows

The message copies the shape most of the team uses, one line per MR:

  :eyes: :partymerge: COS-1234 - [repo!iid](url) - what it does (notes)

Links are markdown, never Slack's <url|label>, because slack_send_message takes markdown.
"""
import argparse, json, os, random, re, subprocess, sys, urllib.parse
from pathlib import Path

ME_GITLAB = "swmcc_whitespace"
GROUP = "whitedotspace"
HERD = Path(__file__).resolve().parent.parent / "herd.json"
STATE = Path(os.environ.get("STRAY_STATE", Path.home() / ".local/state/stray/used.json"))

KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
MR_URL = re.compile(r"https://gitlab\.com/(.+?)/-/merge_requests/(\d+)")
# Leading noise people put on titles: Draft markers, gitmoji (as characters or :codes:), and the key.
TITLE_NOISE = re.compile(
    r"^(?:\s*(?:draft:|\[draft\]|:[a-z0-9_+-]+:|[^\w\s(\[]+|\(?[A-Z][A-Z0-9]+-\d+\)?:?)\s*)+",
    re.I,
)


def glab_json(endpoint):
    out = subprocess.run(["glab", "api", endpoint], capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else None


def ticket_key(mr):
    """The ticket the MR is for: the branch name first, since that's where keys are meant to live."""
    for text in (mr.get("source_branch", ""), mr.get("title", "")):
        m = KEY.search(text)
        if m:
            return m.group(1)
    return "NoTicket"


def short_title(title):
    cleaned = TITLE_NOISE.sub("", title).strip()
    return cleaned or title.strip()


def repo_of(mr):
    return mr["references"]["full"].split("!")[0].rsplit("/", 1)[-1]


def notes_for(mr, siblings):
    """What a reviewer needs before opening it: draft, or stacked on another MR."""
    notes = []
    if mr.get("draft"):
        notes.append("draft")
    target = mr.get("target_branch")
    if target and target not in ("main", "master"):
        below = next((s for s in siblings if s.get("source_branch") == target), None)
        notes.append(f"stacked on !{below['iid']}" if below else f"stacked on {target}")
    return notes


def row(mr, siblings):
    return {
        "url": mr["web_url"],
        "repo": repo_of(mr),
        "iid": mr["iid"],
        "key": ticket_key(mr),
        "title": short_title(mr["title"]),
        "notes": notes_for(mr, siblings),
        "draft": bool(mr.get("draft")),
    }


def find(urls, drafts):
    if urls:
        mrs = []
        for url in urls:
            m = MR_URL.search(url)
            if not m:
                sys.exit(f"not a GitLab MR link: {url}")
            mr = glab_json(f"projects/{urllib.parse.quote(m.group(1), safe='')}/merge_requests/{m.group(2)}")
            if mr is None:
                sys.exit(f"couldn't read {url} from GitLab")
            mrs.append(mr)
    else:
        mrs = glab_json(
            f"groups/{GROUP}/merge_requests?author_username={ME_GITLAB}&state=opened&per_page=100"
        ) or []
        if not drafts:
            mrs = [m for m in mrs if not m.get("draft")]
    mine = [m for m in mrs if m.get("author", {}).get("username") == ME_GITLAB]
    by_project = {}
    for m in mrs:
        by_project.setdefault(m["project_id"], []).append(m)
    rows = [row(m, by_project[m["project_id"]]) for m in mine]
    return sorted(rows, key=lambda r: (r["key"], r["repo"], r["iid"]))


def herd():
    return json.loads(HERD.read_text())


def load_used():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return []


def next_cow(rng=random):
    """A cow that hasn't had a turn yet; once the whole herd has, everyone's back in."""
    cows = herd()
    used = set(load_used())
    fresh = [c for c in cows if c["name"] not in used] or cows
    return rng.choice(fresh)


def mark_used(name):
    names = {c["name"] for c in herd()}
    if name not in names:
        sys.exit(f"no cow called {name!r} in the herd")
    used = [n for n in load_used() if n in names]
    if name not in used:
        used.append(name)
    if set(used) >= names:
        used = [name]
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(used))


def heading(cow, count):
    """The cow's line on top, so the post stands out in a busy channel."""
    mrs = "1 MR" if count == 1 else f"{count} MRs"
    return f"{cow['emoji']} **{cow['name']} has wandered in with {mrs} for review**, {cow['line']}"


FOOTER = (
    ":cowboy_approved: _Let in by the Stray Herd, Stephen's cattle: the MRs are his. "
    "Somebody herd them home, or reply here and he'll see it._"
)


def render(rows, cow, header=None):
    """Cow's heading, a blank line, any extra header, one line per MR, then the herd's footer."""
    lines = [heading(cow, len(rows)), ""]
    if header:
        lines.append(header)
    for r in rows:
        note = f" ({', '.join(r['notes'])})" if r["notes"] else ""
        lines.append(f":eyes: :partymerge: {r['key']} - [{r['repo']}!{r['iid']}]({r['url']}) - {r['title']}{note}")
    return "\n".join(lines) + "\n\n" + FOOTER


def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find")
    f.add_argument("urls", nargs="*")
    f.add_argument("--drafts", action="store_true")
    sub.add_parser("cow")
    u = sub.add_parser("used")
    u.add_argument("name")
    r = sub.add_parser("render")
    r.add_argument("rows")
    r.add_argument("--cow", required=True)
    r.add_argument("--header")
    a = p.parse_args(argv)

    if a.cmd == "find":
        print(json.dumps(find(a.urls, a.drafts), indent=2))
    elif a.cmd == "cow":
        print(json.dumps(next_cow()))
    elif a.cmd == "used":
        mark_used(a.name)
    elif a.cmd == "render":
        cow = next((c for c in herd() if c["name"] == a.cow), None)
        if cow is None:
            sys.exit(f"no cow called {a.cow!r} in the herd")
        print(render(json.loads(Path(a.rows).read_text()), cow, a.header))


if __name__ == "__main__":
    main()
