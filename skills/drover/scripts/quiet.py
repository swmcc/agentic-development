#!/usr/bin/env python3
"""Tell a quiet run from one with work in it, before the model does anything with the scan.

Usage:
  quiet.py check <scan.json>   exit 0 and print "quiet" if every MR is exactly as the last
                               finished run left it; exit 1 otherwise
  quiet.py save <scan.json>    record this scan as what the finished run left

Only a finished run saves, so a run that dies part way is never mistaken for one that handled
everything. The scan's own timestamp is left out of the comparison; everything in each MR's row
(head sha, pipeline, threads, approvals, who's still to ask) is in it.
"""
import hashlib, json, sys
from pathlib import Path

LAST = Path.home() / ".cache/drover/last-scan"


def fingerprint(path):
    rows = json.loads(Path(path).read_text())["mrs"]
    rows = sorted(rows, key=lambda r: r.get("url", ""))
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def main(argv):
    if len(argv) != 2 or argv[0] not in ("check", "save"):
        sys.exit(__doc__)
    cmd, path = argv
    fp = fingerprint(path)
    if cmd == "save":
        LAST.parent.mkdir(parents=True, exist_ok=True)
        LAST.write_text(fp)
        return 0
    try:
        same = LAST.read_text().strip() == fp
    except FileNotFoundError:
        same = False
    if same:
        print("quiet")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
