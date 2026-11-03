#!/usr/bin/env python3
"""Where the next sweep of #collective-mrs starts from, and what is being reviewed right now.

Usage:
  state.py oldest [--days N] [--channel ID]
                               the Slack timestamp to read from: N days back if given, else the
                               last sweep, else the start of today (a first run looks at today only)
  state.py set <ts> [--channel ID]
                               remember <ts> as where the next sweep starts

Without --channel these mean #collective-mrs. Any other room swept first gets its own
place under --channel, so reading one room never moves the other on.
  state.py claim <url>...      mark these MRs as being reviewed, so an overlapping sweep skips them
  state.py release <url>...    clear those marks once their reviews are posted or abandoned
  state.py claimed             the MRs currently claimed, one per line

A claim lapses after two hours, so a sweep that dies part way doesn't hide an MR for good.
"""
import json, sys, time
from datetime import datetime
from pathlib import Path

STATE = Path.home() / ".cache/mr-sweep/state.json"
CLAIM_SECONDS = 2 * 3600


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
    return {url: at for url, at in state.get("claims", {}).items() if now - at < CLAIM_SECONDS}


def split_channel(args):
    if "--channel" not in args:
        return args, None
    i = args.index("--channel")
    return args[:i] + args[i + 2:], args[i + 1]


def place(state, channel):
    # #collective-mrs keeps the top-level keys it always had, so existing state still reads.
    return state if channel is None else state.setdefault("channels", {}).setdefault(channel, {})


def oldest(args):
    args, channel = split_channel(args)
    if args[:1] == ["--days"]:
        return f"{time.time() - float(args[1]) * 86400:.6f}"
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return place(load(), channel).get("last_ts") or f"{start_of_today.timestamp():.6f}"


def set_ts(args):
    args, channel = split_channel(args)
    state = load()
    place(state, channel).update(last_ts=args[0], swept_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    save(state)
    return f"next sweep{f' of {channel}' if channel else ''} starts after {args[0]}"


def claim(urls):
    state = load()
    state["claims"] = {**live_claims(state), **{u: time.time() for u in urls}}
    save(state)
    return f"claimed {len(urls)}"


def release(urls):
    state = load()
    state["claims"] = {u: at for u, at in live_claims(state).items() if u not in urls}
    save(state)
    return f"released {len(urls)}"


def claimed(_args):
    return "\n".join(live_claims(load()))


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["oldest"]
    print({"oldest": oldest, "set": set_ts, "claim": claim, "release": release, "claimed": claimed}[cmd](rest))
