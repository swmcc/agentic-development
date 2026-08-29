# Souls

One markdown file per character. A soul is the single source of truth for
who a character is, consumed three ways:

1. **Thrawn**: the `[personas]` table in `thrawn/runners.toml` maps a
   pipeline stage to a soul (`planner = "tactician"`). The file's text is
   injected at the top of that stage's prompt for whichever runner
   executes it, claude, codex, pi or local alike.
2. **Interactive agents**: files in `~/.claude/agents/` become thin
   wrappers, frontmatter for tools and model plus an instruction to read
   their soul from `~/.claude/souls/<name>.md` (a symlink to this
   directory, created by `make setup-souls`).
3. **Any session**: the `/soul <name>` skill loads a character into an
   ordinary Claude Code conversation.

## Writing a soul

- **Taste, not checklists.** Falsifiable convictions with hills to die
  on, and things the character deliberately does not care about. "Most
  Elixir bugs come from catching errors OTP wanted to crash on; I flag
  every defensive rescue until proven wrong" beats "check error
  handling".
- **Plain, harness-agnostic text.** No tool names, no thrawn-isms, no
  Claude-specific instructions. The same words must work inside a codex
  pane where none of that machinery exists. Anything mechanical belongs
  in the wrapper or the pipeline template, never in the soul.
- **Memory lives elsewhere.** Per-character memory goes in
  `~/.claude/agent-memory/<name>/` (lessons.md and journal.md); the soul
  may instruct the character to read it first and append to it last, but
  the soul file itself stays stable.
- **A name is a handle for trust.** Write in a voice distinct enough
  that a review reads differently from a debug note without the persona
  ever being announced.

The design and its reasoning: issue #16 and the vault note
`agent-souls.md`. No souls exist yet by design; the mechanism landed
inert and characters arrive one at a time, skeptic first.
