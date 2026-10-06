"""Loading and width maths shared by both renderers.

`board.py` draws the static box, `tui.py` the tabbed one. Both read the same
envelopes and both have to measure the same gitmoji, so that logic lives here
rather than in two copies that drift.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import unicodedata

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")

# Shell collectors first, then the ones a Claude session has to fetch.
SOURCES = ("repos", "jira", "mrs", "calendar", "mail", "rovo")


def cwidth(ch: str) -> int:
    """Terminal columns one character occupies.

    MR titles here start with a gitmoji, and most of those are double-width.
    Counting them as one shears the right-hand border off every row that has
    one. `east_asian_width` catches most, but not all — U+1F3D7 🏗 reports N and
    still renders wide — so the emoji planes are treated as wide outright, and
    combining marks (the variation selector that follows many of them) as zero.
    """
    o = ord(ch)
    if unicodedata.combining(ch) or unicodedata.category(ch) == "Mn" or o == 0x200D:
        return 0
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return 2
    if 0x1F300 <= o <= 0x1FAFF:
        return 2
    return 1


def vlen(s: str) -> int:
    """Printable width, skipping ANSI escapes."""
    out, i = 0, 0
    while i < len(s):
        if s[i] == "\033":
            i = s.find("m", i) + 1 or len(s)
            continue
        out += cwidth(s[i])
        i += 1
    return out


def fit(s: str, n: int) -> str:
    """Left-align to n *visible* columns — Python's `:<n` pads by byte length."""
    return s + " " * max(n - vlen(s), 0)


def clip(s: str, n: int) -> str:
    """Trim to n visible columns, with an ellipsis if anything was lost."""
    if vlen(s) <= n:
        return s
    out, w = "", 0
    for ch in s:
        cw = cwidth(ch)
        if w + cw > n - 1:
            break
        out += ch
        w += cw
    return out + "…"


def load(source: str, state_dir: str = None) -> dict | None:
    try:
        with open(os.path.join(state_dir or STATE_DIR, f"{source}.json")) as fh:
            return json.load(fh)
    except Exception:
        return None


def load_all(state_dir: str = None) -> dict:
    return {s: load(s, state_dir) for s in SOURCES}


def age_seconds(env: dict | None) -> float | None:
    if not env:
        return None
    try:
        at = dt.datetime.strptime(env["collected_at"], "%Y-%m-%dT%H:%M:%SZ") \
               .replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None
    return (dt.datetime.now(dt.timezone.utc) - at).total_seconds()


def age_label(env: dict | None) -> str:
    """How old, in the shortest honest form."""
    if env is None:
        return "—"
    if not env.get("ok"):
        return "failed"
    age = age_seconds(env)
    if age is None:
        return "?"
    if age < 90:
        return "now"
    mins = int(age // 60)
    return f"{mins}m" if mins < 90 else f"{mins // 60}h"


def data(env: dict | None) -> dict:
    """The payload, or an empty dict — callers should check `ok` separately."""
    return (env or {}).get("data") or {}


def upcoming(events: list) -> list:
    """What is still ahead of you, soonest first.

    Computed at render time rather than stored, so an hour-old calendar pull is
    still correct about what is next. A declined event is free time and is
    dropped: the schedule you agreed to is not the schedule you were sent.
    """
    out = []
    now = dt.datetime.now(dt.timezone.utc)
    for e in events or []:
        if e.get("response_status") == "declined":
            continue
        try:
            start = dt.datetime.fromisoformat(e["start"])
            end = dt.datetime.fromisoformat(e.get("end") or e["start"])
        except Exception:
            continue
        if end <= now:
            continue
        e = dict(e, _start=start, _in=int((start - now).total_seconds() // 60))
        e["_now"] = start <= now < end
        out.append(e)
    return sorted(out, key=lambda e: e["_start"])


def when_label(e: dict) -> str:
    if e["_now"]:
        return "now"
    m = e["_in"]
    return f"in {m}m" if m < 90 else f"in {m // 60}h{m % 60:02d}"
