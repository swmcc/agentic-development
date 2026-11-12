#!/usr/bin/env python3
"""What the Drover is working on, and who it has already asked to re-review what.

Usage:
  state.py claim <url>...            mark MRs as being worked, so an overlapping run skips them
  state.py release <url>...          clear those marks
  state.py claimed                   the live claims, one per line
  state.py asked <url> <sha> <reviewer>...
                                     record that these reviewers were asked to look at <url> at <sha>
  state.py was-asked <url> <sha> <reviewer>
                                     exit 0 if that reviewer was already asked at that head
  state.py posted <channel> <ts> <permalink> --who <names> --what <gist> [--thread <parent ts>]
                    [--at <unix>] [<url>...]
                                     record a Postie ask, so its thread can be read for replies.
                                     The MR links are for a re-review ask; any other ask has none.
                                     --thread is the parent of an ask sent as a thread reply
  state.py open-asks <scan.json>     JSON list of the asks worth reading: any with a reply still
                                     waiting on Stephen, any other ask not yet settled, and any
                                     re-review ask whose MRs are still waiting on review
  state.py waiting-on <scan.json>    JSON list for the page's Waiting on section
  state.py seen <ts> <reply ts>      every reply up to <reply ts> in that ask's thread has been read
  state.py replied <ts> <reply ts> <who> <permalink> <gist>
                                     someone answered; the gist shows beside the ask on the page
  state.py done <ts>                 what the ask wanted has been answered; it leaves Waiting on
  state.py pending <ts> <reply ts> <mr url or -> <who> <permalink> <gist>
                                     a reply that needs Stephen; it shows under Needs you until cleared
  state.py clear <ts> <reply ts>     Stephen has answered that reply

A claim lapses after two hours, so a run that dies part way doesn't hide an MR for good. An ask
with nothing pending is forgotten after a week.
"""
import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

STATE = Path.home() / ".cache/drover/state.json"
CLAIM_SECONDS = 2 * 3600
ASK_SECONDS = 7 * 24 * 3600


def load():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def live_claims(state, now=None):
    now = now or time.time()
    return {u: at for u, at in state.get("claims", {}).items() if now - at < CLAIM_SECONDS}


def waiting_mrs(scan_path):
    """MRs a re-review ask is still about: open, and not yet approved by everyone. An MR another
    run has claimed or whose pipeline is running is still waiting on its reviewers."""
    return {
        r["url"] for r in json.loads(Path(scan_path).read_text())["mrs"]
        if r.get("state") in ("waiting_review", "claimed", "running", "needs_work")
    }


def still_asking(ask, waiting, now):
    """A re-review ask is settled once none of its MRs waits on review; any other ask once a
    run has marked it done. Either way it stops being chased after a week."""
    if ask.get("done") or now - ask["sent_at"] >= ASK_SECONDS:
        return False
    return bool(waiting & set(ask["mrs"])) if ask["mrs"] else True


def open_asks(state, scan_path, now=None):
    """Asks whose threads are worth a read: one with a reply still waiting on Stephen, or one
    still asking. Reading nothing else keeps a quiet run with nothing outstanding to no Slack
    calls at all."""
    now = now or time.time()
    waiting = waiting_mrs(scan_path)
    return [a for a in state.get("asks", {}).values() if a.get("pending") or still_asking(a, waiting, now)]


def waiting_on(state, scan_path, now=None):
    """Every ask still out, newest first, in the shape the page shows. A settled ask drops off at
    once: next to live asks, a merged MR still listed reads as if it were waiting."""
    now = now or time.time()
    waiting = waiting_mrs(scan_path)
    rows = []
    for a in state.get("asks", {}).values():
        asking = still_asking(a, waiting, now)
        if not (asking or a.get("pending")):
            continue
        last = (a.get("replies") or [None])[-1]
        status = "needs_you" if a.get("pending") else "replied" if last else "waiting"
        rows.append({
            "who": a.get("who", ""), "what": a.get("what", ""), "link": a["permalink"],
            "sent": datetime.fromtimestamp(a["sent_at"], timezone.utc).isoformat(), "status": status,
            "reply": last and f'{last["who"]}: {last["gist"]}', "reply_link": last and last["permalink"],
        })
    return sorted(rows, key=lambda r: r["sent"], reverse=True)


def prune_asks(state, now=None):
    now = now or time.time()
    state["asks"] = {
        ts: a for ts, a in state.get("asks", {}).items()
        if a.get("pending") or now - a["sent_at"] < ASK_SECONDS
    }


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    state = load()
    if cmd == "claim":
        claims = live_claims(state)
        claims.update({u: time.time() for u in args})
        state["claims"] = claims
    elif cmd == "release":
        claims = live_claims(state)
        for u in args:
            claims.pop(u, None)
        state["claims"] = claims
    elif cmd == "claimed":
        print("\n".join(live_claims(state)))
        return 0
    elif cmd == "asked":
        url, sha, reviewers = args[0], args[1], args[2:]
        entry = state.setdefault("asked", {}).setdefault(url, {})
        for r in reviewers:
            entry[r] = sha
    elif cmd == "was-asked":
        url, sha, reviewer = args
        return 0 if state.get("asked", {}).get(url, {}).get(reviewer) == sha else 1
    elif cmd == "posted":
        channel, ts, permalink, rest = args[0], args[1], args[2], args[3:]
        opts = {}
        while rest and rest[0] in ("--who", "--what", "--at", "--thread"):
            opts[rest[0][2:]], rest = rest[1], rest[2:]
        state.setdefault("asks", {})[ts] = {
            "channel": channel, "ts": ts, "thread": opts.get("thread", ts), "permalink": permalink, "mrs": rest,
            "who": opts.get("who", ""), "what": opts.get("what", ""),
            "sent_at": float(opts.get("at", time.time())), "seen": ts, "pending": [], "replies": [],
        }
        prune_asks(state)
    elif cmd == "open-asks":
        print(json.dumps(open_asks(state, args[0]), indent=1))
        return 0
    elif cmd == "waiting-on":
        print(json.dumps(waiting_on(state, args[0]), indent=1))
        return 0
    elif cmd == "replied":
        ts, reply_ts, who, permalink, gist = args
        replies = state["asks"][ts].setdefault("replies", [])
        if not any(r["reply_ts"] == reply_ts for r in replies):
            replies.append({"reply_ts": reply_ts, "who": who, "permalink": permalink, "gist": gist})
    elif cmd == "done":
        state["asks"][args[0]].update(done=True, done_at=time.time())
    elif cmd == "seen":
        ask, reply_ts = state["asks"][args[0]], args[1]
        # Slack timestamps are fixed-width decimals, so a float compare orders them.
        if float(reply_ts) > float(ask["seen"]):
            ask["seen"] = reply_ts
    elif cmd == "pending":
        ts, reply_ts, url, who, permalink, gist = args
        ask = state["asks"][ts]
        if not any(p["reply_ts"] == reply_ts for p in ask["pending"]):
            ask["pending"].append({"reply_ts": reply_ts, "mr": None if url == "-" else url, "who": who, "permalink": permalink, "gist": gist})
    elif cmd == "clear":
        ask = state["asks"][args[0]]
        ask["pending"] = [p for p in ask["pending"] if p["reply_ts"] != args[1]]
    else:
        print(__doc__)
        return 2
    save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
