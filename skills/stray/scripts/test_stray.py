import json
import random

import pytest

import stray


def mr(**over):
    base = {
        "iid": 534,
        "title": "🔒️ (ABC-12) Let an environment turn off the inbound fallback",
        "source_branch": "fix/ABC-12-fallback-flag",
        "target_branch": "main",
        "draft": False,
        "web_url": "https://gitlab.com/whitedotspace/collective-os/services/collective-engine-api/-/merge_requests/534",
        "references": {"full": "whitedotspace/collective-os/services/collective-engine-api!534"},
        "project_id": 1,
        "author": {"username": stray.ME_GITLAB},
    }
    return {**base, **over}


def test_key_comes_from_the_branch_before_the_title():
    assert stray.ticket_key(mr(title="XYZ-9: something")) == "ABC-12"


def test_key_falls_back_to_the_title_then_to_noticket():
    assert stray.ticket_key(mr(source_branch="tidy-up", title="XYZ-9: something")) == "XYZ-9"
    assert stray.ticket_key(mr(source_branch="tidy-up", title="Tidy the README")) == "NoTicket"


@pytest.mark.parametrize(
    "title, want",
    [
        ("🔒️ (ABC-12) Let an environment turn off the fallback", "Let an environment turn off the fallback"),
        ("🔒️ ABC-12: Call engine-api with eval's credential", "Call engine-api with eval's credential"),
        (":bug: ABC-3: Fix the thing", "Fix the thing"),
        ("Draft: ✨ Add the thing", "Add the thing"),
        ("Plain title", "Plain title"),
    ],
)
def test_short_title_drops_gitmoji_drafts_and_keys(title, want):
    assert stray.short_title(title) == want


def test_notes_say_draft_and_name_the_mr_it_is_stacked_on():
    below = mr(iid=1042, source_branch="feat/ABC-1-base")
    above = mr(iid=1043, target_branch="feat/ABC-1-base", draft=True)
    assert stray.notes_for(above, [below, above]) == ["draft", "stacked on !1042"]


def test_notes_name_the_branch_when_the_mr_below_is_not_mine():
    assert stray.notes_for(mr(target_branch="release/1.2"), []) == ["stacked on release/1.2"]


def test_render_puts_the_cow_on_top_then_a_blank_line_then_the_mrs():
    row = stray.row(mr(), [])
    cow = {"name": "Joe Graze", "emoji": ":ear_of_rice:", "line": "found grazing the backlog"}
    lines = stray.render([row], cow).split("\n")
    assert lines[0] == ":ear_of_rice: **Joe Graze has wandered in with 1 MR for review**, found grazing the backlog"
    assert lines[1] == ""
    assert lines[2] == (
        ":eyes: :partymerge: ABC-12 - [collective-engine-api!534]"
        "(https://gitlab.com/whitedotspace/collective-os/services/collective-engine-api/-/merge_requests/534)"
        " - Let an environment turn off the inbound fallback"
    )
    assert lines[-1] == stray.FOOTER
    assert "<http" not in "\n".join(lines)


def test_heading_counts_more_than_one_mr():
    cow = {"name": "Joe Graze", "emoji": ":ear_of_rice:", "line": "x"}
    assert "with 3 MRs for review" in stray.heading(cow, 3)


def test_the_footer_emoji_is_not_a_cow_in_the_herd():
    assert not any(c["emoji"] in stray.FOOTER for c in stray.herd())


@pytest.fixture
def state(tmp_path, monkeypatch):
    path = tmp_path / "used.json"
    monkeypatch.setattr(stray, "STATE", path)
    return path


def test_every_cow_gets_a_turn_before_any_repeats(state):
    names = [c["name"] for c in stray.herd()]
    seen = []
    rng = random.Random(1)
    for _ in names:
        cow = stray.next_cow(rng)
        seen.append(cow["name"])
        stray.mark_used(cow["name"])
    assert sorted(seen) == sorted(names)


def test_the_herd_starts_again_once_everyone_has_been(state):
    for c in stray.herd():
        stray.mark_used(c["name"])
    assert len(json.loads(state.read_text())) == 1


def test_herd_has_no_repeated_names_or_emoji():
    cows = stray.herd()
    assert len({c["name"] for c in cows}) == len(cows)
    assert len({c["emoji"] for c in cows}) == len(cows)


def test_marking_an_unknown_cow_refuses(state):
    with pytest.raises(SystemExit):
        stray.mark_used("Daisy")
