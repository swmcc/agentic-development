#!/usr/bin/env python3
"""Where the next sweep of #collective-mrs starts from.

Usage:
  state.py oldest [--days N]   the Slack timestamp to read from: N days back if given, else the
                               last sweep, else the start of today (a first run looks at today only)
  state.py set <ts>            remember <ts> as the newest message swept
"""
import json, sys, time
from datetime import datetime
from pathlib import Path

STATE = Path.home() / ".cache/mr-sweep/state.json"


def saved():
    try:
        return json.loads(STATE.read_text()).get("last_ts")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def oldest(args):
    if args[:1] == ["--days"]:
        return f"{time.time() - float(args[1]) * 86400:.6f}"
    start_of_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return saved() or f"{start_of_today.timestamp():.6f}"


def set_ts(args):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_ts": args[0], "swept_at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    return f"next sweep starts after {args[0]}"


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["oldest"]
    print({"oldest": oldest, "set": set_ts}[cmd](rest))
