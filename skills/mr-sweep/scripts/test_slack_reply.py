import unittest

from candidates import parse
from slack_reply import replies

CE = "https://gitlab.com/whitedotspace/collective-engine/-/merge_requests"

CHANNEL = f"""=== Message from Ryan Wilson <ryan.wilson@white.space> (U09T65AH85V) at 2026-10-28 09:20:47 GMT ===
Message TS: 1793179247.558739
:eyes: :partymerge:<{CE}/998|guard empty keys>
:eyes: :partymerge:<{CE}/1005|retire graph_execute_agql>

=== Message from Ryan Wilson <ryan.wilson@white.space> (U09T65AH85V) at 2026-10-28 16:15:27 GMT ===
Message TS: 1793204127.911379
:eyes: :partymerge: <{CE}/1006|retire aql_template>
:eyes: :partymerge: <{CE}/1005|retire graph_execute_agql>
"""


def review(iid, verdict="APPROVE", comments=2, status="posted"):
    return {"url": f"{CE}/{iid}", "repo": "collective-engine", "iid": iid,
            "verdict": verdict, "comments": comments, "status": status}


class RepliesTest(unittest.TestCase):
    def setUp(self):
        self.msgs = parse(CHANNEL)

    def test_one_reply_per_post_on_the_newest_mention(self):
        out = replies(self.msgs, [review(998), review(1005, "CHANGES", 3), review(1006)])
        by_ts = {r["thread_ts"]: r["text"] for r in out["replies"]}
        self.assertEqual(set(by_ts), {"1793179247.558739", "1793204127.911379"})
        self.assertIn("collective-engine!998](https://gitlab.com/whitedotspace/collective-engine/-/merge_requests/998): ✅ approved, 2 comments", by_ts["1793179247.558739"])
        self.assertNotIn("1005", by_ts["1793179247.558739"])
        self.assertIn("!1005](https://gitlab.com/whitedotspace/collective-engine/-/merge_requests/1005): 🔁 changes requested, 3 comments", by_ts["1793204127.911379"])
        self.assertIn("!1006](https://gitlab.com/whitedotspace/collective-engine/-/merge_requests/1006): ✅ approved", by_ts["1793204127.911379"])

    def test_a_review_that_did_not_post_gets_no_reply(self):
        out = replies(self.msgs, [review(998, status="not_posted")])
        self.assertEqual(out["replies"], [])

    def test_an_mr_never_posted_in_the_channel_is_unmatched(self):
        out = replies(self.msgs, [review(4242)])
        self.assertEqual(out["unmatched"], [f"{CE}/4242"])

    def test_a_summary_only_review_has_no_comment_count(self):
        out = replies(self.msgs, [review(998, comments=0)])
        self.assertTrue(out["replies"][0]["text"].endswith("✅ approved"))


if __name__ == "__main__":
    unittest.main()
