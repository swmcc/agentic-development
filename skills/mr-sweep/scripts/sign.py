#!/usr/bin/env python3
"""Sign a review draft as Mr. Sweep's, so the author knows an agent wrote it.

Usage: sign.py <draft.md>

Adds the footer as the last paragraph of the draft's summary note, which posts once per MR.
Running it twice leaves one footer.
"""
import sys
from pathlib import Path

FOOTER = (
    "🧑‍🌾 *Reviewed by Mr. Sweep, collie's shepherd: Stephen's review agent, "
    "working to his review standards. Reply here and he'll see it.*"
)
SUMMARY = "## Summary note"
SEPARATOR = "\n---\n"


def sign(text):
    if FOOTER in text:
        return text
    start = text.index(SUMMARY)
    end = text.find(SEPARATOR, start)
    end = len(text) if end == -1 else end
    body = text[start:end].rstrip("\n")
    return text[:start] + f"{body}\n\n{FOOTER}\n" + text[end:]


if __name__ == "__main__":
    path = Path(sys.argv[1])
    path.write_text(sign(path.read_text()))
    print(f"signed {path.name}")
