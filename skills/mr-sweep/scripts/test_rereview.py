"""Run with: python3 -m unittest discover -s skills/mr-sweep/scripts"""
import unittest
from types import SimpleNamespace

from rereview import assess, changes

OPTS = SimpleNamespace(author=[], repo=[])
ME = "swmcc_whitespace"


def mr(author="paddy.mcdermott", draft=False):
    return {"iid": 1045, "project_id": 1, "title": "t", "draft": draft,
            "web_url": "https://gitlab.com/whitedotspace/collective-engine/-/merge_requests/1045",
            "references": {"full": "whitedotspace/collective-engine!1045"},
            "author": {"username": author, "name": "Paddy McDermott"}}


def version(vid, at, base="b1", head="h1"):
    return {"id": vid, "created_at": at, "base_commit_sha": base, "head_commit_sha": head}


def diff(body, path="a.py"):
    return [{"old_path": path, "new_path": path, "diff": body}]


class Fake:
    def __init__(self, versions, diffs, approved=(), commented="2026-11-02T12:00:00Z"):
        self.versions, self.diffs, self.approved, self.commented = versions, diffs, approved, commented

    def mr_state(self, _):
        return list(self.approved), self.commented, self.versions

    def version_diffs(self, _, vid):
        return self.diffs[vid]


REVIEWED = version(1, "2026-11-02T10:00:00Z", base="b1", head="h1")
LATER = version(2, "2026-11-03T09:00:00Z", base="b2", head="h2")


class Rereview(unittest.TestCase):
    def reason(self, fake, **kw):
        return assess(mr(**kw), fake, set(), OPTS)[0]

    def test_a_rebase_with_the_same_changes_is_left_alone(self):
        fake = Fake([REVIEWED, LATER], {1: diff("@@ -10,2 +10,3 @@\n+x = 1\n"),
                                        2: diff("@@ -14,2 +14,3 @@\n+x = 1\n")})
        self.assertEqual(self.reason(fake), "rebased only, same changes")

    def test_changed_code_comes_back_even_with_no_new_commit(self):
        fake = Fake([REVIEWED, LATER], {1: diff("@@ -10 +10 @@\n+x = 1\n"),
                                        2: diff("@@ -10 +10 @@\n+x = 2\n")})
        why, row = assess(mr(), fake, set(), OPTS)
        self.assertIsNone(why)
        self.assertEqual((row["reviewed"]["id"], row["current"]["id"]), (1, 2))

    def test_nothing_pushed_since_my_comment(self):
        fake = Fake([REVIEWED], {}, commented="2026-11-03T12:00:00Z")
        self.assertEqual(self.reason(fake), "nothing pushed since")

    def test_the_version_reviewed_is_the_one_before_my_comment(self):
        fake = Fake([REVIEWED, LATER], {}, commented="2026-11-03T12:00:00Z")
        self.assertEqual(self.reason(fake), "nothing pushed since")

    def test_approved_is_left_alone(self):
        self.assertEqual(self.reason(Fake([REVIEWED, LATER], {}, approved=[ME])), "approved")

    def test_never_commented_is_left_alone(self):
        self.assertEqual(self.reason(Fake([REVIEWED], {}, commented=None)), "never commented")

    def test_a_draft_mr_is_left_alone(self):
        self.assertEqual(self.reason(Fake([], {}), draft=True), "draft MR")

    def test_the_author_filter_applies(self):
        opts = SimpleNamespace(author=["lee"], repo=[])
        self.assertEqual(assess(mr(), Fake([], {}), set(), opts)[0], "not in --author")

    def test_hunk_headers_do_not_count_as_a_change(self):
        self.assertEqual(changes(diff("@@ -1,2 +1,2 @@ def f():\n-a\n+b\n")),
                         changes(diff("@@ -40,2 +40,2 @@ def f():\n-a\n+b\n")))


if __name__ == "__main__":
    unittest.main()
