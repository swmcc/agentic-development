---
name: sweep
description: Pick who reviews an MR and run it - Mr. Sweep (default) or Dr. Sweep (core repos) leads, Sergeant Sweep (security) and Prof. Sweep (tests) are called in as consults when the diff needs them, and Granny Sweep signs for the juniors - then hand over to the lead's skill. Also the routing table Mr. Sweep's rounds use. Use when the user types /sweep with MR links or a ticket key, or asks "who should review this", "sweep this", or "send the right Sweep".
---

🧹 **The Sweep family**: one review per MR. Mr. or Dr. Sweep leads every review; Sergeant and Prof. Sweep are called in when needed; Granny signs for the juniors.

Arguments: MR links or a ticket key, plus anything the persona skills take (a tone note, `--no-hold`, `--no-slack`). Naming a persona (`/sweep <link> as prof`) skips the table.

## 1. Look at each MR

```bash
glab api "projects/<url-encoded project>/merge_requests/<iid>" ; glab api "projects/<p>/merge_requests/<iid>/changes"
```

Note the repo, the author's username, `draft`, the changed paths and line counts, and the ticket key from the branch or title. Read the ticket's labels (`getJiraIssue`, fields `labels`).

## 2. The lead: Mr. or Dr.

Every review has one lead, who writes and signs it:

| When | Lead |
|---|---|
| The MR is a draft | 🧑‍🌾 Mr. Sweep, comments only |
| Repo is collective-engine, collective-engine-api or graph-manager | 🧑‍⚕️ Dr. Sweep |
| Anything else (frontend, logto, consistency-agent, the collective-vue apps, tooling) | 🧑‍🌾 Mr. Sweep |

Over 800 changed lines in a core repo still gets Dr. Sweep, who reviews it in parts and says it should have been smaller.

## 3. Call in the specialists, if needed

Sergeant and Prof. Sweep never review on their own. The lead calls them in for a consult, and their findings go into the lead's one review:

| Called in when | Specialist | What they add |
|---|---|---|
| The diff touches access control, in any repo: permission rules or `permission_rules_rows.json`, `scope_role_map`, the write gate, `access_control`, `policy_builder`, `required_permissions` or `SERVER_SIDE_SCOPES`, audit or `rbac_denied` code | 👮 Sergeant Sweep | his step 1 extras: the surface map and the caller-to-gate-to-audit trace |
| Mostly tests (over 70% of changed lines under `testing/` or `tests/`), or the ticket is labelled `needs-native-tests`, or the lead is Dr. Sweep on an RBAC/GBAC ticket | 🧑‍🏫 Prof. Sweep | his step 1 extras: criteria mapped to tests, the revert proof, the "QA by tests" table |

Both can be called in on one MR. In the draft, each consult is a short section in the summary, opened with one line in their voice (`👮 **Sergeant Sweep was called in** and rattled the doors: ...`, `🧑‍🏫 **Prof. Sweep was asked to mark the tests**: ...`). Their findings are inline comments like any other, graded by the same rules, and count toward the review's six-comment limit. The verdict, the sign-off and the Slack reply are the lead's.

## 4. The voice: Granny for the juniors

- **The juniors get Granny.** If the author is in the list below, 👵 Granny Sweep signs the review in place of the lead: her intro, her "why" line on every comment, her "what was good" close and her biscuit count. The lead's method (and any consults) still run; the findings and grades don't change.
- **Everyone needs a school day.** For anyone else, roll 1 in 5: on a hit, Granny signs it the same way. Say "school day" in the report so I know it was the dice.

**Juniors** (Granny by default) are listed in `juniors.md` beside this file, one GitLab username per line. It's kept out of git; add new joiners there, and to every persona's notes file.

The tone line comes from the signing persona's notes file; a consult's opening line uses the specialist's own notes file.

## 5. Hand over

Say in one line per MR who got it and why (`engine!1420 → 🧑‍⚕️ Dr. (core repo) + 👮 Sergeant (touches scopes), 👵 Granny voice (junior)`), then follow the lead's SKILL.md (`dr-sweep`, or `review-mr` for Mr. Sweep), with the consults' extras added to step 1 and, when she's the voice, Granny's frame from `granny-sweep/SKILL.md` in place of the lead's. Everything else, show first, post on my word, the Slack reply, the report, is the lead's skill's.

## In Mr. Sweep's rounds

The rounds run this table on every MR they pick, priority authors and the 1-in-5 sample alike. A Dr. Sweep lead or a Prof. consult runs tests, so a round does at most **three** of those; the rest wait for the next round, oldest first. Mr. Sweep's own reviews aren't capped.
