#!/usr/bin/env python3
"""Render the fused state as a terminal board.

Three rules the layout exists to serve:

1. **Blank means nothing is waiting, never "I could not look."** Every section
   that has no data says which of the two it is. A dashboard that renders an
   empty box over a failed collector is worse than no dashboard, because it
   reports good news it has not earned.
2. **Age is the signal.** A review raised an hour ago and one sitting for three
   days are different objects. Nothing here shows a count without an age.
3. **Quiet things are absent.** A repo on main with a clean tree earns no line.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import unicodedata

STATE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")

TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
W = max(58, min(shutil.get_terminal_size((88, 24)).columns - 2, 100))


def c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if TTY else s


DIM, BOLD = lambda s: c("2", s), lambda s: c("1", s)
RED, AMBER, GREEN = (lambda s: c("31", s)), (lambda s: c("33", s)), (lambda s: c("32", s))
CYAN = lambda s: c("36", s)


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
    """Printable width — ANSI codes take no columns."""
    out, i = 0, 0
    while i < len(s):
        if s[i] == "\033":
            i = s.find("m", i) + 1 or len(s)
            continue
        out += cwidth(s[i])
        i += 1
    return out


def fit(s: str, n: int) -> str:
    """Left-align to n *visible* columns.

    Python's own `:<n` pads by byte length, which counts the colour escapes and
    silently shears every coloured column out of alignment.
    """
    return s + " " * max(n - vlen(s), 0)


def load(source: str) -> dict | None:
    try:
        with open(os.path.join(STATE, f"{source}.json")) as fh:
            return json.load(fh)
    except Exception:
        return None


def age_of(env: dict | None) -> float | None:
    if not env:
        return None
    try:
        at = dt.datetime.strptime(env["collected_at"], "%Y-%m-%dT%H:%M:%SZ") \
               .replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None
    return (dt.datetime.now(dt.timezone.utc) - at).total_seconds()


def freshness(env: dict | None, warn_after: float) -> str:
    """A short right-aligned marker saying how much to trust this block."""
    if env is None:
        return DIM("not collected")
    if not env.get("ok"):
        return RED("failed")
    age = age_of(env)
    if age is None:
        return DIM("?")
    if age < warn_after:
        return ""
    mins = int(age // 60)
    return DIM(f"{mins}m old" if mins < 90 else f"{mins // 60}h old")


# ---------------------------------------------------------------- box drawing
LINES: list[str] = []


def rule(title: str = "", right: str = "") -> None:
    if not title:
        LINES.append(DIM("├" + "─" * (W - 2) + "┤"))
        return
    left = f"├─ {BOLD(title)} "
    pad = W - 2 - vlen(left[1:]) - vlen(right) - (1 if right else 0)
    LINES.append(DIM("├─ ") + BOLD(title) + " " + DIM("─" * max(pad, 1)) +
                 (f" {right}" if right else "") + DIM("┤"))


def row(text: str = "", indent: int = 1) -> None:
    body = " " * indent + text
    pad = W - 2 - vlen(body)
    if pad < 0:  # trim on overflow rather than wrapping — one line, one fact
        while vlen(body) > W - 5 and body:
            body = body[:-1]
        body += DIM("…")
        pad = W - 2 - vlen(body)
    LINES.append(DIM("│") + body + " " * max(pad, 0) + DIM("│"))


def empty(source_env: dict | None, good: str) -> None:
    """The distinction that rule 1 exists for."""
    if source_env is None:
        row(DIM("— not collected yet"))
    elif not source_env.get("ok"):
        row(RED("— unavailable: ") + DIM(str(source_env.get("error"))[:W - 20]))
    else:
        row(GREEN(f"— {good}"))


# ------------------------------------------------------------------- sections
jira, mrs, repos = load("jira"), load("mrs"), load("repos")
cal, mail = load("calendar"), load("mail")

now = dt.datetime.now().strftime("%H:%M")
head = DIM("┌─ ") + BOLD("C2") + " "
pad = W - 2 - vlen(head[1:]) - len(now) - 1
LINES.append(head + DIM("─" * max(pad, 1)) + f" {DIM(now)}" + DIM("┐"))

# --- NEXT ------------------------------------------------------------------
rule("NEXT", freshness(cal, 900))


def upcoming(events: list) -> list:
    """What is still ahead of you, soonest first.

    "Still ahead" is computed here rather than stored, so an hour-old calendar
    pull is still correct about what is next — only about three fields fewer
    than a live one. A declined event is free time and is dropped outright; the
    schedule you agreed to is not the same as the schedule you were sent.
    """
    out = []
    now = dt.datetime.now(dt.timezone.utc)
    for e in events:
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


if cal and cal.get("ok") and (cal.get("data") or {}).get("events") is not None:
    ahead = upcoming(cal["data"]["events"])
    if not ahead:
        row(GREEN("— nothing left today"))
    for i, e in enumerate(ahead[:3]):
        when = (GREEN("now") if e["_now"] else
                AMBER(f"in {e['_in']}m") if e["_in"] <= 15 else
                DIM(f"in {e['_in']}m" if e["_in"] < 90 else f"in {e['_in'] // 60}h{e['_in'] % 60:02d}"))
        label = e["_start"].astimezone().strftime("%H:%M")
        name = e.get("summary") or ""
        row((BOLD(label) if i == 0 else DIM(label)) + "  " +
            fit(name if i == 0 else DIM(name), 44) + when)
else:
    empty(cal, "nothing left today")

# --- ON YOU ----------------------------------------------------------------
rule("ON YOU", freshness(mrs, 300))
anything = False
if mrs and mrs.get("ok"):
    for m in (mrs["data"] or {}).get("on_you", []):
        anything = True
        d = m.get("created_age_days")
        agec = RED if (d or 0) >= 3 else (AMBER if (d or 0) >= 1 else DIM)
        flag = RED(" conflicts") if m.get("conflicts") else ""
        row(fit(CYAN("!" + str(m["iid"])), 7) + fit(m.get("project") or "", 19)
            + fit(agec(f"{d}d"), 5) + DIM(m.get("author") or "") + flag)
        row(DIM("   " + (m.get("title") or "")), indent=1)
if mail and mail.get("ok"):
    for t in (mail["data"] or {}).get("needs_reply", [])[:4]:
        anything = True
        h = t.get("age_hours")
        agec = RED if (h or 0) >= 48 else (AMBER if (h or 0) >= 12 else DIM)
        row(fit(CYAN("✉"), 7) + fit((t.get("from") or "")[:18], 19)
            + fit(agec(f"{int(h or 0)}h"), 5) + DIM((t.get("subject") or "")[:34]))
elif mail is None:
    row(DIM("✉  mail not collected — /sitrep pulls it"))
if not anything:
    empty(mrs, "nothing blocked on you")

# --- IN FLIGHT -------------------------------------------------------------
rule("IN FLIGHT", freshness(mrs, 300))
flight = False
if mrs and mrs.get("ok"):
    for m in (mrs["data"] or {}).get("yours", []):
        flight = True
        d = m.get("created_age_days")
        state = GREEN("approved") if m.get("approved") else (
            DIM(f"{m.get('approvals', 0)} approvals") if m.get("approvals")
            else AMBER("no approvals"))
        draft = DIM(" draft") if m.get("draft") else ""
        row(fit(CYAN("!" + str(m["iid"])), 7) + fit(m.get("project") or "", 19)
            + fit(DIM(f"{d}d"), 5) + state + draft)
if jira and jira.get("ok"):
    for i in (jira["data"] or {}).get("issues", []):
        if i.get("status") not in ("In Progress", "Peer Review"):
            continue
        flight = True
        idle = i.get("idle_days") or 0
        idlec = AMBER(f"{idle}d idle") if idle >= 3 else DIM(f"{idle}d")
        row(fit(CYAN(i["key"]), 11) + fit(DIM(i.get("status") or ""), 15) + idlec)
        row(DIM("   " + (i.get("summary") or "")), indent=1)
if not flight:
    empty(jira, "nothing in flight")

# --- WORKSPACE -------------------------------------------------------------
rule("WORKSPACE", freshness(repos, 120))
if repos and repos.get("ok"):
    noisy = [r for r in (repos["data"] or {}).get("repos", []) if not r["quiet"]]
    for r in noisy:
        bits = []
        if r["dirty"]:
            bits.append(AMBER(f"{r['dirty']} dirty"))
        if r["stashes"]:
            bits.append(RED(f"{r['stashes']} stash"))
        if r["worktrees"]:
            bits.append(DIM(f"{r['worktrees']} wt"))
        if r["ahead"]:
            bits.append(DIM(f"↑{r['ahead']}"))
        if r["behind"]:
            bits.append(DIM(f"↓{r['behind']}"))
        branch = r["branch"] if r["branch"] in ("main", "master") else CYAN(r["branch"])
        row(fit(r["name"], 21) + fit(branch, 34) + DIM("·").join(f" {b} " for b in bits))
    if not noisy:
        row(GREEN("— every repo clean and on main"))
else:
    empty(repos, "every repo clean and on main")

# --- QUEUE -----------------------------------------------------------------
rule("QUEUE", freshness(jira, 300))
if jira and jira.get("ok"):
    d = jira["data"] or {}
    counts = d.get("counts") or {}
    order = ["In Progress", "Peer Review", "QA", "To Do"]
    parts = [f"{BOLD(str(counts[k]))} {DIM(k.lower())}"
             for k in order if counts.get(k)]
    parts += [f"{BOLD(str(v))} {DIM(k.lower())}"
              for k, v in counts.items() if k not in order]
    row("  ".join(parts) + DIM(f"   ({d.get('total', 0)} assigned)"))
else:
    empty(jira, "queue empty")

LINES.append(DIM("└" + "─" * (W - 2) + "┘"))
print("\n".join(LINES))
