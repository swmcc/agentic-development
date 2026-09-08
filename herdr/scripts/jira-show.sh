#!/usr/bin/env bash
# Render a Jira issue as markdown on stdout — status, people, description, comments.
#
# Built for the prefix+j popup, so it talks to the Jira REST API directly rather
# than going through an agent: a headless `claude -p` round trip measured 20-30s
# per lookup, which is fine for a slash command and useless for a keybinding.
#
# Auth comes from the macOS Keychain, so no token sits in the repo or in a
# dotfile. Store it once with:
#
#   security add-generic-password -s jira-api-token \
#     -a stephen.mccullough@white.space -w '<token>' -U
#
# Token from: https://id.atlassian.com/manage-profile/security/api-tokens
#
# Usage: jira-show.sh COS-7656      # or a bare 7656, which assumes COS-

set -uo pipefail

JIRA_SITE="${JIRA_SITE:-https://whitespaceventures.atlassian.net}"
JIRA_EMAIL="${JIRA_EMAIL:-stephen.mccullough@white.space}"
JIRA_DEFAULT_PROJECT="${JIRA_DEFAULT_PROJECT:-COS}"
KEYCHAIN_SERVICE="${JIRA_KEYCHAIN_SERVICE:-jira-api-token}"

die() { printf '\n**%s**\n\n%s\n' "Error" "$1"; exit 1; }

RAW="${1:-}"
[ -n "$RAW" ] || die "No ticket given. Usage: \`jira-show COS-7656\` (or just \`7656\`)."

# A bare number means the default project; anything else is upper-cased as-is.
if [[ "$RAW" =~ ^[0-9]+$ ]]; then
  KEY="${JIRA_DEFAULT_PROJECT}-${RAW}"
else
  KEY="$(printf '%s' "$RAW" | tr '[:lower:]' '[:upper:]')"
fi

command -v curl >/dev/null 2>&1 || die "\`curl\` not found."
command -v python3 >/dev/null 2>&1 || die "\`python3\` not found."

TOKEN="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -a "$JIRA_EMAIL" -w 2>/dev/null)"
if [ -z "$TOKEN" ]; then
  die "No Jira token in the Keychain (service \`$KEYCHAIN_SERVICE\`, account \`$JIRA_EMAIL\`).

Create one at https://id.atlassian.com/manage-profile/security/api-tokens then run:

    security add-generic-password -s $KEYCHAIN_SERVICE \\
      -a $JIRA_EMAIL -w '<token>' -U"
fi

FIELDS='summary,status,assignee,reporter,priority,issuetype,parent,labels,components,resolution,created,updated,duedate,description,subtasks,issuelinks'

fetch() { # fetch <path>
  curl -sS --max-time 20 -u "$JIRA_EMAIL:$TOKEN" \
    -H 'Accept: application/json' "$JIRA_SITE/rest/api/3/$1"
}

ISSUE_JSON="$(fetch "issue/${KEY}?fields=${FIELDS}")" || die "Could not reach $JIRA_SITE."
[ -n "$ISSUE_JSON" ] || die "Empty response for \`$KEY\`."

# Comments come from their own endpoint so ordering and paging are predictable.
COMMENTS_JSON="$(fetch "issue/${KEY}/comment?orderBy=created&maxResults=50")"

ISSUE_JSON="$ISSUE_JSON" COMMENTS_JSON="${COMMENTS_JSON:-}" KEY="$KEY" SITE="$JIRA_SITE" \
python3 <<'PY'
import json, os, re, sys, textwrap

key   = os.environ["KEY"]
site  = os.environ["SITE"]
issue = json.loads(os.environ["ISSUE_JSON"])

if "errorMessages" in issue or "errors" in issue:
    msgs = issue.get("errorMessages") or []
    errs = issue.get("errors") or {}
    detail = "; ".join(msgs) or "; ".join(f"{k}: {v}" for k, v in errs.items()) or "unknown error"
    print(f"\n**Error**\n\n`{key}`: {detail}\n")
    sys.exit(0)

F = issue.get("fields") or {}

def person(v):
    return (v or {}).get("displayName") or "Unassigned"

def named(v, default="—"):
    return (v or {}).get("name") or default

def day(s):
    return (s or "")[:10] or "—"

# ---------------------------------------------------------------- ADF rendering
#
# Jira Cloud stores rich text as Atlassian Document Format. Only the node types
# that actually turn up in these tickets are handled; anything unknown falls
# through to its children so text is never silently dropped.

def marks(text, node):
    for m in node.get("marks") or []:
        t = m.get("type")
        if t == "strong":                 text = f"**{text}**"
        elif t in ("em", "emphasis"):     text = f"*{text}*"
        elif t == "code":                 text = f"`{text}`"
        elif t == "strike":               text = f"~~{text}~~"
        elif t == "link":
            href = (m.get("attrs") or {}).get("href", "")
            if href:                      text = f"[{text}]({href})"
    return text

def inline(nodes):
    out = []
    for n in nodes or []:
        t = n.get("type")
        if t == "text":
            out.append(marks(n.get("text", ""), n))
        elif t == "hardBreak":
            out.append("  \n")
        elif t in ("emoji", "status"):
            a = n.get("attrs") or {}
            out.append(a.get("shortName") or a.get("text") or "")
        elif t == "mention":
            out.append("@" + ((n.get("attrs") or {}).get("text", "").lstrip("@")))
        elif t == "inlineCard":
            out.append((n.get("attrs") or {}).get("url", ""))
        else:
            out.append(inline(n.get("content")))
    return "".join(out)

def block(nodes, depth=0):
    lines = []
    for n in nodes or []:
        t = n.get("type")
        a = n.get("attrs") or {}
        c = n.get("content")

        if t == "paragraph":
            txt = inline(c).strip()
            if txt:
                lines.append(txt)
                lines.append("")
        elif t == "heading":
            lines.append("#" * min(a.get("level", 2) + 1, 6) + " " + inline(c).strip())
            lines.append("")
        elif t in ("bulletList", "orderedList"):
            for i, item in enumerate(c or [], 1):
                bullet = f"{i}." if t == "orderedList" else "-"
                body = block(item.get("content"), depth + 1).strip().splitlines()
                pad = "  " * depth
                if body:
                    lines.append(f"{pad}{bullet} {body[0]}")
                    lines.extend(f"{pad}  {b}" for b in body[1:] if b.strip())
            lines.append("")
        elif t == "codeBlock":
            lines.append("```" + (a.get("language") or ""))
            lines.append(inline(c))
            lines.append("```")
            lines.append("")
        elif t == "blockquote":
            for b in block(c, depth).strip().splitlines():
                lines.append("> " + b)
            lines.append("")
        elif t == "rule":
            lines.append("---")
            lines.append("")
        elif t == "panel":
            kind = (a.get("panelType") or "info").upper()
            lines.append(f"> **{kind}**")
            for b in block(c, depth).strip().splitlines():
                lines.append("> " + b)
            lines.append("")
        elif t == "table":
            rows = []
            for row in c or []:
                cells = [inline_cell(cell) for cell in (row.get("content") or [])]
                rows.append(cells)
            if rows:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("|" + "---|" * width)
                for r in rows[1:]:
                    lines.append("| " + " | ".join(r) + " |")
                lines.append("")
        elif t in ("mediaSingle", "mediaGroup", "media"):
            lines.append("*(attachment)*")
            lines.append("")
        else:
            nested = block(c, depth)
            if nested.strip():
                lines.append(nested.rstrip())
                lines.append("")
    return "\n".join(lines)

def inline_cell(cell):
    # Table cells hold blocks; flatten to one line and protect the pipes.
    txt = block(cell.get("content")).strip().replace("\n", " ")
    return re.sub(r"\s+", " ", txt).replace("|", r"\|")

def adf(doc):
    if not doc:
        return "*No description.*"
    if isinstance(doc, str):
        return doc.strip() or "*No description.*"
    out = block(doc.get("content")).strip()
    return out or "*No description.*"

# ------------------------------------------------------------------- the output
parent = F.get("parent") or {}
parent_line = ""
if parent:
    pf = parent.get("fields") or {}
    parent_line = f"{parent.get('key')} — {pf.get('summary', '')}"

print(f"# {key} — {F.get('summary', '(no summary)')}")
print()
print(
    f"**{named(F.get('status'), 'Unknown')}**"
    f" · {person(F.get('assignee'))}"
    f" · {named(F.get('priority'))}"
    f" · {named(F.get('issuetype'))}"
)
print()

meta = []
if parent_line:                  meta.append(f"**Epic:** {parent_line}")
if F.get("resolution"):          meta.append(f"**Resolution:** {named(F.get('resolution'))}")
if F.get("labels"):              meta.append("**Labels:** " + ", ".join(F["labels"]))
comps = [c.get("name") for c in (F.get("components") or []) if c.get("name")]
if comps:                        meta.append("**Components:** " + ", ".join(comps))
meta.append(f"**Reporter:** {person(F.get('reporter'))}")
meta.append(f"**Created:** {day(F.get('created'))} · **Updated:** {day(F.get('updated'))}")
if F.get("duedate"):             meta.append(f"**Due:** {day(F.get('duedate'))}")
meta.append(f"**Link:** {site}/browse/{key}")
for m in meta:
    print(m)
    print()

links = []
for l in F.get("issuelinks") or []:
    lt = l.get("type") or {}
    for side, label in (("outwardIssue", lt.get("outward")), ("inwardIssue", lt.get("inward"))):
        t = l.get(side)
        if t:
            tf = t.get("fields") or {}
            links.append(f"- {label} **{t.get('key')}** — {tf.get('summary','')} "
                         f"({named(tf.get('status'), '?')})")
subs = [f"- **{s.get('key')}** — {(s.get('fields') or {}).get('summary','')}"
        for s in (F.get("subtasks") or [])]

if links:
    print("## Links")
    print()
    print("\n".join(links))
    print()
if subs:
    print("## Subtasks")
    print()
    print("\n".join(subs))
    print()

print("## Description")
print()
print(adf(F.get("description")))
print()

print("## Comments")
print()
craw = os.environ.get("COMMENTS_JSON") or ""
try:
    cdata = json.loads(craw) if craw else {}
except Exception:
    cdata = {}
comments = cdata.get("comments") or []
if not comments:
    print("*None.*")
else:
    for c in comments:
        who = person(c.get("author"))
        print(f"**{who}** · {day(c.get('created'))}")
        print()
        print(adf(c.get("body")))
        print()
    total = cdata.get("total", len(comments))
    if total > len(comments):
        print(f"*Showing {len(comments)} of {total} comments.*")
        print()
PY
