---
name: muster
description: Start Stephen's background rounds in this session, Mr. Sweep (reviews other people's MRs, hourly in working hours), the Drover (drives his own MRs home, hourly in working hours), Wee Standie (posts his standup, weekdays at 08:47), the washup (writes his end of day, weekdays at 16:02) and tomorrow's plan (weekdays at 16:32). Safe to run any time, in any session; the newest muster takes the rounds over and older sessions' timers switch themselves off. Use when the user types /muster, or asks to start, restart or kick off the sweep and the drover, or his loops, rounds or standup.
argument-hint: "[--renew <token>]"
---

📯 **Muster** puts the rounds on their timers in this session, and takes them over from any other session.

`R=~/.claude/skills/muster/scripts/round.py`

## Who owns the rounds

The last `/muster` to run owns them. It makes a fresh token, and every timer it sets carries that token as `--round <token>`. When a timer fires, the round's first step is `python3 $R gate <round> <token>`:
- `go`: run it.
- `superseded`: a newer `/muster` ran somewhere else. Delete every job in this session whose prompt carries this token (`CronList`, then `CronDelete`), reply with the single line `📯 superseded by a newer /muster: timers here removed`, and stop. Post nothing.
- `done`: today's is already written (washup and plan only). Reply with one line saying so, and stop.

So running `/muster` again, here or in a fresh session, never doubles a post: the old session's timers go quiet the next time they fire. A round typed by hand, with no `--round`, skips the gate and always runs.

## Steps

0. **A renewal checks first.** If this run is `/muster --renew <token>` (the timer from step 4), run `python3 $R gate muster <token>`. On `superseded`, do as above and stop. On `go`, carry on.
1. Make the token: `T=$(python3 $R new)`.
2. Run `CronList`. Delete with `CronDelete` every job in this session whose prompt starts with one of the rounds below (`/mr-sweep`, `/drover`, `/wee-standie`, `/washup`, `/workplan day for the next working day`) or with `/muster`. Muster always rebuilds them fresh, so their 7-day expiry starts again.
3. Run `CronCreate` with `recurring: true` for each round, with `<T>` replaced by the token:

   | Round | cron | prompt |
   |---|---|---|
   | Mr. Sweep | `7 9-17 * * 1-5` | `/mr-sweep --round <T>` |
   | The Drover | `37 9-17 * * 1-5` | `/drover --round <T>` |
   | Wee Standie | `47 8 * * 1-5` | `/wee-standie --post --round <T>` |
   | Washup | `2 16 * * 1-5` | `/washup --round <T>` |
   | Tomorrow's plan | `32 16 * * 1-5` | `/workplan day for the next working day --round <T> (tomorrow, or Monday when today is Friday): use that day's calendar, carry over what today's washup put under Carried into tomorrow, and keep building against the M1 label on COS-3789` |

   The minutes are off the hour so none of them fire together. Sweep and Drover run weekdays 09:00 to 17:59 only: overnight and weekend runs were nearly all quiet, and still cost a full read of the session each time.
   A hand-made `/loop` of Mr. Sweep or the Drover carries no token, so nothing switches it off. If one is running in another session, say so and ask Stephen to stop it there.
4. **Book the renewal.** One `CronCreate` with `recurring: false`, prompt `/muster --renew <T>`, pinned to 6 days from now at 08:23 (`23 8 <dom> <month> *`). It rebuilds everything a day before anything expires and books the next one, as long as this session still owns the rounds.
5. Report in five lines: what was started and when each next fires. Add one line saying when the renewal fires, and that everything stops if the session closes, so run `/muster` again in a new session.

Don't run any round now; the timers fire them.

Keep this session for the rounds only, and start it fresh each morning (open a new one and `/muster`; yesterday's switches itself off). Every round re-reads the whole session, so one left open all week makes each run several times dearer than the same run in a fresh one.
