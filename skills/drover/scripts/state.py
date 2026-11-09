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

A claim lapses after two hours, so a run that dies part way doesn't hide an MR for good.
"""
import json, sys, time
from pathlib import Path

STATE = Path.home() / ".cache/drover/state.json"
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
    return {u: at for u, at in state.get("claims", {}).items() if now - at < CLAIM_SECONDS}


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
    else:
        print(__doc__)
        return 2
    save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
