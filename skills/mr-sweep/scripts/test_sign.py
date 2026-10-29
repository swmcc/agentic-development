import unittest

from sign import FOOTER, sign

DRAFT = """# Review: graph-manager!836 (not posted)

Verdict: APPROVE

---

## Summary note

Nice one.

---

## Inline: `CHANGELOG.md:12`, chat-app entry

**Changelog version (NAB)**
"""


class SignTest(unittest.TestCase):
    def test_footer_closes_the_summary_note_not_the_inline_comment(self):
        signed = sign(DRAFT)
        summary, inline = signed.split("## Inline:")
        self.assertIn(f"Nice one.\n\n{FOOTER}\n", summary)
        self.assertNotIn(FOOTER, inline)

    def test_signing_twice_leaves_one_footer(self):
        self.assertEqual(sign(sign(DRAFT)).count(FOOTER), 1)

    def test_a_summary_only_review_is_signed_at_the_end(self):
        summary_only = DRAFT.split("\n---\n\n## Inline:")[0] + "\n"
        self.assertTrue(sign(summary_only).rstrip().endswith(FOOTER))


if __name__ == "__main__":
    unittest.main()
