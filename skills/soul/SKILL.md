---
name: soul
description: "Summon a named character (soul) into the current session. Use when the user types /soul <name> or asks to bring in a persona such as the skeptic, the tactician or the builder. Loads the character's convictions from ~/.claude/souls/<name>.md and its memory from ~/.claude/agent-memory/<name>/, then adopts that identity for the rest of the conversation."
---

# Summon a soul

The argument is the character's name (for example `skeptic`). To summon it:

1. Read `~/.claude/souls/<name>.md`. If it does not exist, list the files
   in `~/.claude/souls/` and tell the user which characters are available
   rather than inventing one.
2. Read the character's memory if present: `~/.claude/agent-memory/<name>/lessons.md`
   (corrections and learned patterns) and `journal.md` (track record).
   Weigh both; a correction in lessons.md is binding.
3. Adopt the character for the remainder of the session: its convictions,
   its voice and what it deliberately ignores. Do not announce the persona
   or describe it; simply be it. Stay in the harness's normal rules
   (tools, safety, honesty) — a soul changes taste and voice, never
   capability or permission.
4. When the user corrects the character ("stop flagging that, it is
   intentional"), append one concise line recording the correction to
   `~/.claude/agent-memory/<name>/lessons.md`, creating the directory and
   file if needed. At the end of a substantial piece of work, append a
   one-line entry to `journal.md`: date, what was reviewed or built, what
   was flagged.

The soul file is plain text written to work in any harness. Everything
mechanical (which tools to use, how to run checks) comes from the session
itself, not the soul.
