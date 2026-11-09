#!/usr/bin/env python3
"""Which session owns the rounds, and whether a timed round still has anything to do.

Usage:
  round.py new                    start a new muster: print a fresh token and make it the current one
  round.py gate <round> <token>   print one word for a timer that just fired:
                                    go          run the round
                                    superseded  a newer /muster owns the rounds; this session's timers are stale
                                    done        this round's output for the day is already written

Rounds: mr-sweep, drover, wee-standie, washup, plan, muster.

The last /muster to run owns the rounds, wherever it ran. Timers in any other session see a token
that isn't current and switch themselves off, so running /muster again never doubles anything.
Only washup and plan write something that a second run would duplicate, so only they answer
`done`, and only from the file itself, so a run by hand counts too.
"""
import datetime as dt, re, secrets, sys
from pathlib import Path

CURRENT = Path.home() / ".cache/muster/current"
WIKI = Path.home() / "Documents/wiki"
ROUNDS = {"mr-sweep", "drover", "wee-standie", "washup", "plan", "muster"}


def next_working_day(today):
    days = 3 if today.weekday() == 4 else 2 if today.weekday() == 5 else 1
    return today + dt.timedelta(days=days)


def washup_written(today):
    note = WIKI / f"notes/dailies/{today:%Y-%m-%d}.md"
    try:
        text = note.read_text()
    except FileNotFoundError:
        return False
    m = re.search(r"^## 📊 End of Day Summary\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return False
    # The template leaves only an HTML comment here until /washup writes the section.
    return bool(re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip())


def plan_written(today):
    return (WIKI / f"plans/{next_working_day(today):%Y-%m-%d}-day.md").exists()


def gate(name, token):
    try:
        current = CURRENT.read_text().strip()
    except FileNotFoundError:
        current = None
    if token != current:
        return "superseded"
    today = dt.date.today()
    if name == "washup" and washup_written(today):
        return "done"
    if name == "plan" and plan_written(today):
        return "done"
    return "go"


def main(argv):
    if argv == ["new"]:
        token = secrets.token_hex(4)
        CURRENT.parent.mkdir(parents=True, exist_ok=True)
        CURRENT.write_text(token)
        print(token)
        return 0
    if len(argv) == 3 and argv[0] == "gate" and argv[1] in ROUNDS:
        print(gate(argv[1], argv[2]))
        return 0
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
