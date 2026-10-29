"""Run with: python3 -m unittest discover -s skills/mr-sweep/scripts"""
import unittest
from types import SimpleNamespace

from candidates import mentions, parse, sweep

GM = "https://gitlab.com/whitedotspace/collective-os/services/graph-manager/-/merge_requests"
FE = "https://gitlab.com/whitedotspace/collective-os/frontend/-/merge_requests"

# The shapes the Slack connector returns, copied from the channel.
CHANNEL = f"""Channel: #collective-mrs (C0AKFUXG80J)

=== Message from Lee O'Connell <lee.oconnell@white.space> (U0A767CSN5P) at 2026-10-29 09:33:27 GMT ===
Message TS: 1793266407.971779
:eyes: :mr-open:  ~Need a quick sanity check <https://gitlab.com/whitedotspace/collective-os/ms-template/-/merge_requests/227|gitlab.com/whitedotspace/…/227>~

=== Message from Lee O'Connell <lee.oconnell@white.space> (U0A767CSN5P) at 2026-10-29 08:33:07 GMT ===
Message TS: 1793262787.090509
:eyes::mr-open: :bump:
- <{GM}/832|gitlab.com/whitedotspace/…/832>, gm pack bundles static files
- <{GM}/833|gitlab.com/whitedotspace/…/833>, check package files on publish
Reactions: eyes (1)

=== Message from Lee O'Connell <lee.oconnell@white.space> (U0A767CSN5P) at 2026-10-28 14:26:30 GMT ===
Message TS: 1793197590.299299
:eyes: :mr-open:  <{GM}/832|gitlab.com/whitedotspace/…/832> gm pack static files

=== Message from Review Bot <botuser-T3SDH639Q-B0BREJU62A1@slack-bots.com> (U0BSCPGPHCG) at 2026-10-28 10:14:36 GMT ===
Message TS: 1793182476.932569
:eyes: :robot_face: :mr-open: {GM}/824 :hammer_and_wrench: Update Copier Template (45149c3) (effort 3/5)
Reactions: mr-approved (1), mr-merged (1)

=== Message from Ryan Wilson <ryan.wilson@white.space> (U09T65AH85V) at 2026-10-28 09:39:59 GMT ===
Message TS: 1793180399.705979
:eyes: :partymerge: <{FE}/1622|Retire /api/graph proxy> <@U082BL09HK4|Stephen> fancy a look?
Thread: 2 replies (latest: 2026-10-28 10:00:00 GMT)

=== Message from jenkins <ross.jenkins@white.space> (U0C0P65G80H) at 2026-10-28 11:16:07 GMT ===
Message TS: 1793186167.039529
• <{FE}/1624|gitlab.com/whitedotspace/…/1624> - deprecate a component
"""


def mr(author="someone", reviewers=(), state="opened", draft=False, approved_by=()):
    return {"title": "t", "state": state, "draft": draft, "author": author, "author_name": author.title(),
            "reviewers": list(reviewers), "approved_by": list(approved_by)}


GITLAB = {
    ("whitedotspace/collective-os/ms-template", 227): mr("lee.oconnell", ["swmcc_whitespace"]),
    ("whitedotspace/collective-os/services/graph-manager", 832): mr("lee.oconnell", ["swmcc_whitespace"]),
    ("whitedotspace/collective-os/services/graph-manager", 833): mr("lee.oconnell"),
    ("whitedotspace/collective-os/services/graph-manager", 824): mr("propagate-bot"),
    ("whitedotspace/collective-os/frontend", 1622): mr("ryan.wilson4"),
    ("whitedotspace/collective-os/frontend", 1624): mr("ross.jenkins", ["swmcc_whitespace"]),
}


def run(mode="mine", author=(), repo=(), cap=6, drafts=frozenset(), gitlab=GITLAB):
    opts = SimpleNamespace(mode=mode, author=list(author), repo=list(repo), cap=cap)
    out = sweep(parse(CHANNEL), lambda p, i: gitlab.get((p, i)), set(drafts), opts)
    return out, {(r["repo"], r["iid"]): r["skip_reason"] for r in out["skipped"]}


def picked(out):
    return [(r["repo"], r["iid"]) for r in out["selected"]]


class ParseTest(unittest.TestCase):
    def test_reads_every_message_with_its_ts_and_reactions(self):
        msgs = parse(CHANNEL)
        self.assertEqual(len(msgs), 6)
        self.assertEqual(msgs[1].ts, "1793262787.090509")
        self.assertEqual(msgs[3].reactions, ["mr-approved", "mr-merged"])
        self.assertEqual(msgs[0].name, "Lee O'Connell")

    def test_a_bumped_link_counts_once_from_its_newest_post(self):
        found = {(m.path.rsplit("/", 1)[-1], m.iid): m for m in mentions(parse(CHANNEL))}
        self.assertEqual(len(found), 6)
        self.assertEqual(found[("graph-manager", 832)].posted_ts, "1793262787.090509")

    def test_a_struck_through_link_is_marked(self):
        found = {m.iid: m for m in mentions(parse(CHANNEL))}
        self.assertTrue(found[227].struck)
        self.assertFalse(found[832].struck)

    def test_a_bare_url_is_found(self):
        self.assertIn(824, {m.iid for m in mentions(parse(CHANNEL))})


class SweepTest(unittest.TestCase):
    def test_default_takes_what_i_review_or_am_mentioned_in(self):
        out, why = run()
        self.assertEqual(picked(out), [("frontend", 1622), ("frontend", 1624), ("graph-manager", 832)])
        self.assertEqual(why[("ms-template", 227)], "struck through in Slack")
        self.assertEqual(why[("graph-manager", 824)], "template update from Review Bot")
        self.assertEqual(why[("graph-manager", 833)], "not asked to review (use all)")

    def test_all_widens_to_every_open_mr(self):
        out, _ = run(mode="all")
        self.assertIn(("graph-manager", 833), picked(out))

    def test_author_filter_matches_slack_name_or_gitlab_user_by_prefix(self):
        out, why = run(mode="all", author=["lee"])
        self.assertEqual(picked(out), [("graph-manager", 832), ("graph-manager", 833)])
        self.assertEqual(why[("frontend", 1624)], "not in --author")

    def test_repo_filter_matches_the_last_path_segment(self):
        out, why = run(mode="all", repo=["frontend"])
        self.assertEqual(picked(out), [("frontend", 1622), ("frontend", 1624)])
        self.assertEqual(why[("graph-manager", 833)], "not in --repo")

    def test_an_mr_already_drafted_is_skipped(self):
        _, why = run(drafts={("frontend", 1622)})
        self.assertEqual(why[("frontend", 1622)], "already drafted")

    def test_over_the_cap_is_kept_not_dropped(self):
        out, _ = run(mode="all", cap=2)
        self.assertEqual(len(out["selected"]), 2)
        self.assertEqual(len(out["over_cap"]), 2)

    def test_closed_mine_and_approved_are_skipped(self):
        gitlab = {
            **GITLAB,
            ("whitedotspace/collective-os/frontend", 1624): mr(state="merged"),
            ("whitedotspace/collective-os/services/graph-manager", 833): mr("swmcc_whitespace"),
            ("whitedotspace/collective-os/services/graph-manager", 832): mr(approved_by=["swmcc_whitespace"]),
        }
        _, why = run(mode="all", gitlab=gitlab)
        self.assertEqual(why[("frontend", 1624)], "merged")
        self.assertEqual(why[("graph-manager", 833)], "mine")
        self.assertEqual(why[("graph-manager", 832)], "already approved by me")

    def test_newest_ts_is_the_latest_message(self):
        out, _ = run()
        self.assertEqual(out["newest_ts"], "1793266407.971779")


if __name__ == "__main__":
    unittest.main()
