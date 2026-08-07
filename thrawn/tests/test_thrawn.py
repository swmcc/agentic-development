"""Tests for thrawn — pure functions, the ship gate, and an e2e green run.

The e2e uses fake runners defined in a throwaway repo's .thrawn.toml, with
THRAWN_NO_HERDR=1 so tasks run as plain detached processes. No real agents,
no network: the fixture repo's origin is a local bare repo.

Run with: make test   (or: python3 -m pytest thrawn/tests -q)
"""

import importlib.util
import json
import shutil
import subprocess
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

BIN = Path(__file__).resolve().parent.parent / "bin" / "thrawn"


# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------

def g(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    g("-c", "init.defaultBranch=main", "init", cwd=path)
    g("config", "user.email", "test@thrawn.local", cwd=path)
    g("config", "user.name", "thrawn tests", cwd=path)
    (path / "README.md").write_text("# fixture repo\n")
    g("add", "README.md", cwd=path)
    g("commit", "-q", "-m", "initial", cwd=path)
    return path


@pytest.fixture(scope="module")
def T():
    """The thrawn script imported as a module (it has no .py extension)."""
    loader = SourceFileLoader("thrawn", str(BIN))
    spec = importlib.util.spec_from_loader("thrawn", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture
def repo(tmp_path):
    return init_repo(tmp_path / "repo")


def base_cfg(T, **thrawn_over):
    cfg = {
        "thrawn": {
            "planner": "fable-plan",
            "integrator": "opus",
            "default_runner": "opus",
            "allowed_runners": ["opus", "haiku"],
            "max_tasks": 6,
            "integrator_attempts": 2,
            "poll_seconds": 2,
            "recon_runner": "",
            "recon_max_age_commits": 50,
            "auto_recon": True,
        },
        "checks": {"commands": []},
        "runners": {"opus": {"argv": ["x"]}, "haiku": {"argv": ["x"]}},
    }
    cfg["thrawn"].update(thrawn_over)
    return cfg


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_fenced(self, T):
        text = 'thinking…\n```json\n{"a": 1}\n```\ndone'
        assert T.extract_json(text) == {"a": 1}

    def test_bare_with_noise(self, T):
        text = 'Here is the plan:\n{"tasks": [{"id": "t1"}]}\nGood luck.'
        assert T.extract_json(text) == {"tasks": [{"id": "t1"}]}

    def test_no_json_raises(self, T):
        with pytest.raises(ValueError):
            T.extract_json("no json here { broken")


class TestRender:
    def test_replaces_keys_and_leaves_braces(self, T):
        out = T.render("hi {{name}}, json: {\"a\": 1} {{other}}", name="bob")
        assert out == 'hi bob, json: {"a": 1} {{other}}'


class TestMerge:
    def test_nested_precedence(self, T):
        base = {"a": {"x": 1, "y": 2}, "b": 1}
        over = {"a": {"y": 99, "z": 3}, "c": 4}
        assert T._merge(base, over) == {
            "a": {"x": 1, "y": 99, "z": 3}, "b": 1, "c": 4,
        }


class TestRunnerArgv:
    def test_prompt_substitution(self, T):
        cfg = {"runners": {"r": {"argv": ["cmd", "-p", "{prompt}"]}}}
        assert T.runner_argv(cfg, "r", "hello") == ["cmd", "-p", "hello"]

    def test_unknown_runner_is_none(self, T):
        assert T.runner_argv({"runners": {}}, "nope", "x") is None


class TestWrappedCmdline:
    def test_tees_log_and_writes_exit_file(self, T):
        cmd = T.wrapped_cmdline(["echo", "hi"], Path("/l og.txt"), Path("/e.exit"))
        assert "set -o pipefail" in cmd
        assert "tee '/l og.txt'" in cmd
        assert "> /e.exit" in cmd


class TestValidatePlan:
    def plan(self, **over):
        p = {
            "tasks": [
                {"id": "t1", "title": "a", "prompt": "do a", "complexity": "low",
                 "runner": "haiku", "deps": []},
                {"id": "t2", "title": "b", "prompt": "do b", "deps": ["t1"]},
            ],
        }
        p.update(over)
        return p

    def test_defaults_filled(self, T):
        plan = T.validate_plan(base_cfg(T), self.plan(), "run-1")
        assert plan["summary"] == "run-1"
        assert plan["branch"] == "thrawn/run-1"
        assert plan["pr"]["title"] == "run-1"
        assert plan["tasks"][1]["complexity"] == "medium"

    def test_unknown_runner_low_falls_to_haiku(self, T):
        p = self.plan()
        p["tasks"][0]["runner"] = "gpt-99"
        plan = T.validate_plan(base_cfg(T), p, "r")
        assert plan["tasks"][0]["runner"] == "haiku"

    def test_unknown_runner_medium_falls_to_default(self, T):
        p = self.plan()
        p["tasks"][1]["runner"] = "gpt-99"
        plan = T.validate_plan(base_cfg(T), p, "r")
        assert plan["tasks"][1]["runner"] == "opus"

    def test_duplicate_ids_die(self, T):
        p = self.plan()
        p["tasks"][1]["id"] = "t1"
        with pytest.raises(SystemExit):
            T.validate_plan(base_cfg(T), p, "r")

    def test_missing_prompt_dies(self, T):
        p = self.plan()
        p["tasks"][0]["prompt"] = "  "
        with pytest.raises(SystemExit):
            T.validate_plan(base_cfg(T), p, "r")

    def test_unknown_dep_dies(self, T):
        p = self.plan()
        p["tasks"][1]["deps"] = ["t9"]
        with pytest.raises(SystemExit):
            T.validate_plan(base_cfg(T), p, "r")

    def test_no_tasks_dies(self, T):
        with pytest.raises(SystemExit):
            T.validate_plan(base_cfg(T), {"tasks": []}, "r")

    def test_branch_sanitised(self, T):
        plan = T.validate_plan(base_cfg(T), self.plan(branch="thrawn/x y!z"), "r")
        assert plan["branch"] == "thrawn/x-y-z"

    def test_max_tasks_truncates(self, T):
        p = {"tasks": [
            {"id": f"t{i}", "title": f"t{i}", "prompt": "p", "deps": []}
            for i in range(1, 5)
        ]}
        plan = T.validate_plan(base_cfg(T, max_tasks=2), p, "r")
        assert [t["id"] for t in plan["tasks"]] == ["t1", "t2"]


class TestRunIds:
    def test_make_run_id_kinds(self, T, tmp_path):
        gh = {"kind": "github", "ref": "42", "title": "x"}
        gl = {"kind": "gitlab", "ref": "7", "title": "x"}
        brief = {"kind": "brief", "ref": "b.md", "title": "Add CSV Export!"}
        assert T.make_run_id(tmp_path, gh) == "gh-42"
        assert T.make_run_id(tmp_path, gl) == "gl-7"
        assert T.make_run_id(tmp_path, brief) == "add-csv-export"

    def test_unique_run_id_suffixes(self, T, tmp_path):
        (tmp_path / ".thrawn" / "runs" / "gh-42").mkdir(parents=True)
        assert T.unique_run_id(tmp_path, "gh-42") == "gh-42-2"


class TestRecon:
    def test_no_cache_marker(self, T, repo):
        out = T.load_recon(repo, base_cfg(T))
        assert "no cached brief" in out

    def test_fresh_recon_trusted(self, T, repo):
        md, meta = T.recon_paths(repo)
        md.parent.mkdir(parents=True)
        md.write_text("## the brief\n")
        head = g("rev-parse", "HEAD", cwd=repo).stdout.strip()
        meta.write_text(json.dumps({"commit": head}))
        out = T.load_recon(repo, base_cfg(T))
        assert "trust it for orientation" in out
        assert "## the brief" in out

    def test_stale_recon_flagged(self, T, repo):
        md, meta = T.recon_paths(repo)
        md.parent.mkdir(parents=True)
        md.write_text("## old brief\n")
        head = g("rev-parse", "HEAD", cwd=repo).stdout.strip()
        meta.write_text(json.dumps({"commit": head}))
        for i in range(2):
            (repo / f"f{i}.txt").write_text("x")
            g("add", ".", cwd=repo)
            g("commit", "-q", "-m", f"c{i}", cwd=repo)
        out = T.load_recon(repo, base_cfg(T, recon_max_age_commits=1))
        assert "STALE" in out

    def test_unknown_commit_is_stale(self, T, repo):
        assert T.recon_age_commits(repo, {"commit": "0" * 40}) is None


class TestDetectChecks:
    def test_plan_checks_win(self, T, repo):
        cfg = base_cfg(T)
        cfg["checks"]["commands"] = ["from-cfg"]
        assert T.detect_checks(repo, cfg, {"checks": ["from-plan"]}) == ["from-plan"]

    def test_makefile_check_target(self, T, repo):
        (repo / "Makefile").write_text("check:\n\ttrue\n")
        assert T.detect_checks(repo, base_cfg(T), {}) == ["make check"]

    def test_makefile_lint_and_test(self, T, repo):
        (repo / "Makefile").write_text("lint:\n\ttrue\ntest:\n\ttrue\n")
        assert T.detect_checks(repo, base_cfg(T), {}) == ["make lint", "make test"]

    def test_nothing_found(self, T, repo):
        assert T.detect_checks(repo, base_cfg(T), {}) == []


class TestSpawner:
    def test_no_herdr_falls_back_to_local(self, T, tmp_path, monkeypatch):
        monkeypatch.setenv("THRAWN_NO_HERDR", "1")
        spawner = T.make_spawner(tmp_path, {"run_id": "r1"})
        assert isinstance(spawner, T.LocalSpawner)

    def test_herdr_spawner_needs_run_id_for_tab(self, T):
        # no state/run_id → no run tab; spawn would fall through tab-less
        assert T.HerdrSpawner()._run_tab() is None


# ---------------------------------------------------------------------------
# The ship gate — guards (no git needed; guards fire before any git call)
# ---------------------------------------------------------------------------

def seed_state(T, repo, **over):
    state = {
        "run_id": "r1",
        "created": T.now_iso(),
        "phase": "green",
        "ship_code": "123456",
        "target": {"kind": "brief", "ref": "b.md", "title": "t"},
        "base_branch": "main",
        "base_commit": "0" * 40,
        "tasks": {},
        "integration": {"status": "green", "branch": "thrawn/r1", "worktree": "/nope"},
    }
    state.update(over)
    T.save_state(repo, state)
    return state


class TestShipGate:
    def test_not_green_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="working")
        with pytest.raises(SystemExit):
            T.ship(tmp_path, base_cfg(T), "r1", "123456")

    def test_missing_code_refused(self, T, tmp_path):
        seed_state(T, tmp_path)
        with pytest.raises(SystemExit):
            T.ship(tmp_path, base_cfg(T), "r1", "")

    def test_wrong_code_refused(self, T, tmp_path):
        seed_state(T, tmp_path)
        with pytest.raises(SystemExit):
            T.ship(tmp_path, base_cfg(T), "r1", "000000")
        assert T.load_state(tmp_path, "r1")["phase"] == "green"

    def test_already_shipped_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="shipped")
        with pytest.raises(SystemExit):
            T.ship(tmp_path, base_cfg(T), "r1", "123456")

    def test_unknown_run_refused(self, T, tmp_path):
        with pytest.raises(SystemExit):
            T.ship(tmp_path, base_cfg(T), "no-such-run", "123456")


# ---------------------------------------------------------------------------
# Run reuse — bare dispatch resumes an open run instead of re-planning
# ---------------------------------------------------------------------------

INTAKE = {"kind": "brief", "ref": "b.md", "title": "t"}


class TestRunReuse:
    def test_open_run_is_found(self, T, tmp_path):
        seed_state(T, tmp_path, phase="planned")
        prev = T.find_open_run(tmp_path, INTAKE)
        assert prev and prev["run_id"] == "r1"

    def test_finished_and_crashed_runs_ignored(self, T, tmp_path):
        for i, phase in enumerate(("shipped", "aborted", "planning")):
            seed_state(T, tmp_path, run_id=f"r{i}", phase=phase)
        assert T.find_open_run(tmp_path, INTAKE) is None

    def test_different_target_ignored(self, T, tmp_path):
        seed_state(T, tmp_path, target={"kind": "github", "ref": "42", "title": "x"})
        assert T.find_open_run(tmp_path, INTAKE) is None

    def test_most_recent_open_run_wins(self, T, tmp_path):
        seed_state(T, tmp_path, run_id="r1", phase="working",
                   created="2026-01-01T00:00:00")
        seed_state(T, tmp_path, run_id="r2", phase="working",
                   created="2026-02-01T00:00:00")
        assert T.find_open_run(tmp_path, INTAKE)["run_id"] == "r2"

    def test_advanced_run_beats_newer_stale_plan(self, T, tmp_path):
        # a run mid-integration must win over a later abandoned duplicate plan —
        # resuming the plan would re-spawn every agent from scratch
        seed_state(T, tmp_path, run_id="r1", phase="integrating",
                   created="2026-01-01T00:00:00")
        seed_state(T, tmp_path, run_id="r2", phase="planned",
                   created="2026-02-01T00:00:00")
        assert T.find_open_run(tmp_path, INTAKE)["run_id"] == "r1"

    def test_working_run_beats_failed_and_planned(self, T, tmp_path):
        seed_state(T, tmp_path, run_id="r1", phase="planned",
                   created="2026-03-01T00:00:00")
        seed_state(T, tmp_path, run_id="r2", phase="failed",
                   created="2026-02-01T00:00:00")
        seed_state(T, tmp_path, run_id="r3", phase="working",
                   created="2026-01-01T00:00:00")
        assert T.find_open_run(tmp_path, INTAKE)["run_id"] == "r3"

    def test_duplicate_open_runs_warn_and_suggest_abort(self, T, tmp_path, capsys):
        seed_state(T, tmp_path, run_id="r1", phase="integrating")
        seed_state(T, tmp_path, run_id="r2", phase="planned")
        best = T.find_open_run(tmp_path, INTAKE)
        assert best["run_id"] == "r1"
        out = capsys.readouterr().out
        assert "2 open runs" in out
        assert "thrawn abort r2" in out

    def test_single_open_run_does_not_warn(self, T, tmp_path, capsys):
        seed_state(T, tmp_path, run_id="r1", phase="working")
        T.find_open_run(tmp_path, INTAKE)
        assert "open runs" not in capsys.readouterr().out

    def test_green_run_points_at_ship_code(self, T, tmp_path):
        prev = seed_state(T, tmp_path, phase="green")
        with pytest.raises(SystemExit):
            T.continue_run(tmp_path, base_cfg(T), prev)

    def test_failed_run_points_at_integrate(self, T, tmp_path):
        prev = seed_state(T, tmp_path, phase="failed")
        with pytest.raises(SystemExit):
            T.continue_run(tmp_path, base_cfg(T), prev)


# ---------------------------------------------------------------------------
# retry / adopt — guards (no git needed; guards fire before any git call)
# ---------------------------------------------------------------------------

class TestRecoveryGuards:
    def test_retry_shipped_run_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="shipped")
        with pytest.raises(SystemExit):
            T.cmd_retry(tmp_path, base_cfg(T), "r1", [])

    def test_retry_green_run_refused(self, T, tmp_path):
        seed_state(T, tmp_path)  # green, nothing failed
        with pytest.raises(SystemExit):
            T.cmd_retry(tmp_path, base_cfg(T), "r1", [])

    def test_retry_unknown_task_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="failed",
                   tasks={"t1": {"status": "failed"}})
        with pytest.raises(SystemExit):
            T.cmd_retry(tmp_path, base_cfg(T), "r1", ["nope"])

    def test_retry_healthy_task_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="failed",
                   tasks={"t1": {"status": "done"}, "t2": {"status": "failed"}})
        with pytest.raises(SystemExit):
            T.cmd_retry(tmp_path, base_cfg(T), "r1", ["t1"])

    def test_retry_unknown_runner_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="failed",
                   tasks={"t1": {"status": "failed"}})
        with pytest.raises(SystemExit):
            T.cmd_retry(tmp_path, base_cfg(T), "r1", [], runner="gpt9000")

    def test_adopt_nothing_failed_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="failed")
        with pytest.raises(SystemExit):
            T.cmd_adopt(tmp_path, base_cfg(T), "r1", [])

    def test_adopt_without_worktree_refused(self, T, tmp_path):
        seed_state(T, tmp_path, phase="failed",
                   tasks={"t1": {"status": "failed"}})
        with pytest.raises(SystemExit):
            T.cmd_adopt(tmp_path, base_cfg(T), "r1", ["t1"])


# ---------------------------------------------------------------------------
# E2E — fake runners, real worktrees/merges, then ship to a local bare origin
# ---------------------------------------------------------------------------

THRAWN_TOML = """\
[thrawn]
planner = "fakeplan"
integrator = "fakework"
default_runner = "fakework"
allowed_runners = ["fakework"]
poll_seconds = 0
auto_recon = false

[runners.fakeplan]
argv = ["cat", "plan-fixture.json"]

[runners.fakework]
argv = ["bash", "-c", "f=$(git branch --show-current | tr '/' '-'); echo hi > $f.txt; git add $f.txt; git commit -q -m 'test work'"]
"""

PLAN_FIXTURE = {
    "summary": "e2e test feature",
    "branch": "thrawn/e2e",
    "tasks": [
        {"id": "t1", "title": "first piece", "complexity": "low",
         "runner": "fakework", "deps": [], "prompt": "do t1"},
        {"id": "t2", "title": "second piece", "complexity": "low",
         "runner": "fakework", "deps": ["t1"], "prompt": "do t2"},
    ],
    "checks": ["ls *.txt"],
    "pr": {"title": "e2e feature", "body": "e2e body"},
}


# ---------------------------------------------------------------------------
# Plan approval gate — the rendered plan must be approved before agents spawn
# ---------------------------------------------------------------------------

class TestPlanApproved:
    def _tty(self, T, monkeypatch):
        monkeypatch.setattr(T.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr(T.sys.stdout, "isatty", lambda: True)

    def test_non_interactive_proceeds(self, T):
        # pytest's stdin is not a tty — the gate must not block scripted runs
        assert T.plan_approved("r1") is True

    def test_auto_yes_never_prompts(self, T, monkeypatch):
        self._tty(T, monkeypatch)
        monkeypatch.setattr(T, "confirm",
                            lambda q: pytest.fail("prompted despite --yes"))
        assert T.plan_approved("r1", auto_yes=True) is True

    def test_interactive_yes_proceeds(self, T, monkeypatch):
        self._tty(T, monkeypatch)
        monkeypatch.setattr(T, "confirm", lambda q: True)
        assert T.plan_approved("r1") is True

    def test_interactive_no_declines(self, T, monkeypatch):
        self._tty(T, monkeypatch)
        monkeypatch.setattr(T, "confirm", lambda q: False)
        assert T.plan_approved("r1") is False


@pytest.fixture
def gated(T, tmp_path, monkeypatch):
    """A repo ready to dispatch with fake runners, for scripting the gate."""
    monkeypatch.setenv("THRAWN_NO_HERDR", "1")
    repo = init_repo(tmp_path / "repo")
    (repo / ".thrawn.toml").write_text(THRAWN_TOML)
    (repo / "plan-fixture.json").write_text(json.dumps(PLAN_FIXTURE))
    (repo / "THRAWN.md").write_text("# Gate test brief\n")
    cfg = T.load_config(repo)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    yield SimpleNamespace(repo=repo, cfg=cfg)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)


class TestPlanGateDispatch:
    def test_declined_plan_spawns_nothing(self, T, gated, monkeypatch):
        monkeypatch.setattr(T, "plan_approved", lambda rid, auto=False: False)
        T.dispatch(gated.repo, gated.cfg, None, plan_only=False)
        state = T.latest_run(gated.repo)
        assert state["phase"] == "planned"
        assert state["tasks"] == {}

    def test_declined_then_approved_resume_goes_green(self, T, gated,
                                                      monkeypatch):
        monkeypatch.setattr(T, "plan_approved", lambda rid, auto=False: False)
        T.dispatch(gated.repo, gated.cfg, None, plan_only=False)
        # re-dispatching the same target resumes the planned run; approving
        # the gate this time lets it execute — no second run is created
        monkeypatch.setattr(T, "plan_approved", lambda rid, auto=False: True)
        T.dispatch(gated.repo, gated.cfg, None, plan_only=False)
        state = T.latest_run(gated.repo)
        assert state["phase"] == "green"
        assert len(T.list_runs(gated.repo)) == 1


@pytest.fixture(scope="module")
def e2e(T, tmp_path_factory):
    """Dispatch a full run with fake runners; yields the green run."""
    mp = pytest.MonkeyPatch()
    mp.setenv("THRAWN_NO_HERDR", "1")
    root = tmp_path_factory.mktemp("e2e")
    repo = init_repo(root / "repo")
    origin = root / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    g("remote", "add", "origin", str(origin), cwd=repo)

    (repo / ".thrawn.toml").write_text(THRAWN_TOML)
    (repo / "plan-fixture.json").write_text(json.dumps(PLAN_FIXTURE))
    (repo / "THRAWN.md").write_text("# E2E test brief\n\nDo the fake work.\n")

    cfg = T.load_config(repo)
    # worktrees live in a cache dir keyed by repo path; with --basetemp the
    # path repeats across runs, so purge leftovers from any interrupted run
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    T.dispatch(repo, cfg, None, plan_only=False)
    state = T.latest_run(repo)
    yield SimpleNamespace(repo=repo, cfg=cfg, origin=origin, state=state)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    mp.undo()


class TestEndToEnd:
    def test_goes_green_with_ship_code(self, T, e2e):
        assert e2e.state["phase"] == "green"
        assert e2e.state["integration"]["status"] == "green"
        assert len(e2e.state["ship_code"]) == 6
        assert e2e.state["ship_code"].isdigit()

    def test_all_tasks_done_and_dep_ordering(self, e2e):
        t1, t2 = e2e.state["tasks"]["t1"], e2e.state["tasks"]["t2"]
        assert t1["status"] == "done" and t2["status"] == "done"
        # t2 depends on t1 — it must not have started before t1 finished
        assert t2["started"] >= t1["finished"]

    def test_both_branches_merged_into_integration(self, e2e):
        worktree = Path(e2e.state["integration"]["worktree"])
        files = {p.name for p in worktree.glob("*.txt")}
        assert files == {
            f"thrawn-{e2e.state['run_id']}-t1.txt",
            f"thrawn-{e2e.state['run_id']}-t2.txt",
        }

    def test_diff_of_green_run_shows_integration_change(self, T, e2e, capfd):
        T.cmd_diff(e2e.repo, e2e.state["run_id"], None)
        out = capfd.readouterr().out
        assert "integration branch" in out
        assert f"thrawn-{e2e.state['run_id']}-t1.txt" in out

    def test_redispatch_while_green_does_not_replan(self, T, e2e):
        with pytest.raises(SystemExit):
            T.dispatch(e2e.repo, e2e.cfg, None, plan_only=False)
        assert len(T.list_runs(e2e.repo)) == 1  # no second run was created

    def test_ship_wrong_code_leaves_run_green(self, T, e2e):
        with pytest.raises(SystemExit):
            T.ship(e2e.repo, e2e.cfg, e2e.state["run_id"], "999999")
        assert T.load_state(e2e.repo, e2e.state["run_id"])["phase"] == "green"

    def test_ship_correct_code_pushes_branch(self, T, e2e):
        T.ship(e2e.repo, e2e.cfg, e2e.state["run_id"], e2e.state["ship_code"])
        after = T.load_state(e2e.repo, e2e.state["run_id"])
        assert after["phase"] == "shipped"
        # branch really landed on the (local bare) origin
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "refs/heads/thrawn/e2e"],
            cwd=e2e.origin, capture_output=True, text=True,
        )
        assert proc.returncode == 0

    def test_ship_twice_refused(self, T, e2e):
        with pytest.raises(SystemExit):
            T.ship(e2e.repo, e2e.cfg, e2e.state["run_id"], e2e.state["ship_code"])

    def test_abort_cleans_worktrees_and_branches(self, T, e2e):
        T.cmd_abort(e2e.repo, e2e.state["run_id"])
        after = T.load_state(e2e.repo, e2e.state["run_id"])
        assert after["phase"] == "aborted"
        for ts in after["tasks"].values():
            assert not Path(ts["worktree"]).exists()
        branches = g("branch", "--list", "thrawn/*/*", cwd=e2e.repo).stdout
        assert branches.strip() == ""


# ---------------------------------------------------------------------------
# E2E recovery — a run with casualties, healed by adopt + retry --runner
# ---------------------------------------------------------------------------

RECOVERY_TOML = """\
[thrawn]
planner = "fakeplan"
integrator = "fakework"
default_runner = "fakework"
allowed_runners = ["fakework", "fakefail", "fakeshy"]
poll_seconds = 0
auto_recon = false

[runners.fakeplan]
argv = ["cat", "plan-fixture.json"]

[runners.fakework]
argv = ["bash", "-c", "f=$(git branch --show-current | tr '/' '-'); echo hi > $f.txt; git add $f.txt; git commit -q -m 'test work'"]

[runners.fakefail]
argv = ["bash", "-c", "exit 1"]

[runners.fakeshy]
argv = ["bash", "-c", "echo salvage me > shy.txt"]
"""

RECOVERY_PLAN = {
    "summary": "recovery e2e",
    "branch": "thrawn/recovery",
    "tasks": [
        {"id": "t1", "title": "good worker", "complexity": "low",
         "runner": "fakework", "deps": [], "prompt": "do t1"},
        {"id": "t2", "title": "hard fail", "complexity": "low",
         "runner": "fakefail", "deps": [], "prompt": "do t2"},
        {"id": "t3", "title": "works but never commits", "complexity": "low",
         "runner": "fakeshy", "deps": [], "prompt": "do t3"},
    ],
    "checks": ["true"],
    "pr": {"title": "recovery", "body": "recovery"},
}


@pytest.fixture(scope="module")
def rec(T, tmp_path_factory):
    """A failed run: t2 hard-fails, t3 does the work but never commits."""
    mp = pytest.MonkeyPatch()
    mp.setenv("THRAWN_NO_HERDR", "1")
    root = tmp_path_factory.mktemp("recovery")
    repo = init_repo(root / "repo")
    (repo / ".thrawn.toml").write_text(RECOVERY_TOML)
    (repo / "plan-fixture.json").write_text(json.dumps(RECOVERY_PLAN))
    (repo / "THRAWN.md").write_text("# Recovery test brief\n")
    cfg = T.load_config(repo)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    with pytest.raises(SystemExit):  # watch dies when failures land
        T.dispatch(repo, cfg, None, plan_only=False)
    state = T.latest_run(repo)
    # watch bails at the first failure it sees; wait for the stragglers'
    # exit files so every task has settled before tests poke at the run
    for _ in range(100):
        T.poll_tasks(repo, state)
        if all(ts["status"] != "running" for ts in state["tasks"].values()):
            break
        time.sleep(0.05)
    T.save_state(repo, state)
    yield SimpleNamespace(repo=repo, cfg=cfg, state=state)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    mp.undo()


class TestRecoveryEndToEnd:
    def test_run_failed_with_two_casualties(self, rec):
        assert rec.state["phase"] == "failed"
        assert rec.state["tasks"]["t1"]["status"] == "done"
        assert rec.state["tasks"]["t2"]["status"] == "failed"
        # exit 0 but no commits counts as failed, with the salvage note
        assert rec.state["tasks"]["t3"]["status"] == "failed"
        assert "committed nothing" in rec.state["tasks"]["t3"]["note"]

    def test_retry_refuses_to_discard_uncommitted_work(self, T, rec):
        with pytest.raises(SystemExit):
            T.cmd_retry(rec.repo, rec.cfg, rec.state["run_id"], ["t3"])
        wt = Path(rec.state["tasks"]["t3"]["worktree"])
        assert (wt / "shy.txt").exists()  # the work survived

    def test_diff_shows_blocked_note_and_unstaged_work(self, T, rec, capfd):
        wt = Path(rec.state["tasks"]["t3"]["worktree"])
        (wt / "THRAWN-BLOCKED.md").write_text("sandbox said no\n")
        T.cmd_diff(rec.repo, rec.state["run_id"], "t3")
        out = capfd.readouterr().out
        assert "sandbox said no" in out          # its own account of why
        assert "shy.txt" in out                  # the unstaged file
        assert "salvage me" in out               # ...with its content

    def test_diff_of_unintegrated_run_walks_tasks(self, T, rec, capfd):
        T.cmd_diff(rec.repo, rec.state["run_id"], None)
        out = capfd.readouterr().out
        assert "not integrated yet" in out
        assert "t1" in out and "t2" in out and "t3" in out

    def test_adopt_commits_the_leftover_work(self, T, rec):
        rid = rec.state["run_id"]
        with pytest.raises(SystemExit):  # t2 still failed → watch dies again
            T.cmd_adopt(rec.repo, rec.cfg, rid, ["t3"])
        after = T.load_state(rec.repo, rid)
        assert after["tasks"]["t3"]["status"] == "done"
        branch = after["tasks"]["t3"]["branch"]
        count = g("rev-list", "--count", f"{after['base_commit']}..{branch}",
                  cwd=rec.repo).stdout.strip()
        assert count == "1"
        # the work landed; the blocked marker (a signal, not work) did not
        files = g("ls-tree", "-r", "--name-only", branch, cwd=rec.repo).stdout
        assert "shy.txt" in files
        assert "THRAWN-BLOCKED.md" not in files

    def test_retry_reroutes_and_goes_green(self, T, rec):
        rid = rec.state["run_id"]
        T.cmd_retry(rec.repo, rec.cfg, rid, ["t2"], runner="fakework")
        after = T.load_state(rec.repo, rid)
        assert after["phase"] == "green"
        assert after["tasks"]["t2"]["status"] == "done"
        assert len(after["ship_code"]) == 6
        plan = json.loads((T.run_dir(rec.repo, rid) / "plan.json").read_text())
        t2 = next(t for t in plan["tasks"] if t["id"] == "t2")
        assert t2["runner"] == "fakework"  # reroute recorded in the plan
        # all three branches made it into the integration worktree
        wt = Path(after["integration"]["worktree"])
        assert (wt / "shy.txt").exists()
        assert (wt / f"thrawn-{rid}-t2.txt").exists()
