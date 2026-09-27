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
min_width = 1.0  # the e2e plan is a width-1 chain; gate is tested separately

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


# ---------------------------------------------------------------------------
# Width gate — sequential plans are handed off, not executed
# ---------------------------------------------------------------------------

def mkplan(*deps_by_task):
    """Plan with tasks t1..tN and the given deps lists."""
    return {"tasks": [
        {"id": f"t{i + 1}", "deps": list(deps)}
        for i, deps in enumerate(deps_by_task)
    ]}


class TestPlanMetrics:
    def test_chain_is_width_one(self, T):
        m = T.plan_metrics(mkplan([], ["t1"], ["t2"]))
        assert m == {"tasks": 3, "critical_path": 3, "width": 1.0}

    def test_independent_tasks_are_full_width(self, T):
        m = T.plan_metrics(mkplan([], [], []))
        assert m == {"tasks": 3, "critical_path": 1, "width": 3.0}

    def test_mixed_graph(self, T):
        # t1, t2 parallel; t3 after t1 → 3 tasks over a chain of 2
        m = T.plan_metrics(mkplan([], [], ["t1"]))
        assert m == {"tasks": 3, "critical_path": 2, "width": 1.5}

    def test_single_task(self, T):
        assert T.plan_metrics(mkplan([]))["width"] == 1.0

    def test_empty_and_cyclic_do_not_crash(self, T):
        assert T.plan_metrics({"tasks": []})["width"] == 0.0
        T.plan_metrics(mkplan(["t2"], ["t1"]))  # cycle: just don't recurse forever


class TestWidthGate:
    def test_wide_plan_passes(self, T):
        cfg = base_cfg(T, min_width=2.0)
        assert T.width_gate(cfg, "r1", mkplan([], [], [])) is True

    def test_narrow_plan_refused(self, T, capfd):
        cfg = base_cfg(T, min_width=2.0)
        assert T.width_gate(cfg, "r1", mkplan([], ["t1"])) is False
        out = capfd.readouterr().out
        assert "thrawn watch r1" in out  # the escape hatch is advertised

    def test_threshold_is_inclusive_and_tunable(self, T):
        cfg = base_cfg(T, min_width=1.0)
        assert T.width_gate(cfg, "r1", mkplan([], ["t1"])) is True


class TestWidthGateDispatch:
    def test_narrow_plan_stops_with_verdict_recorded(self, T, gated):
        gated.cfg["thrawn"]["min_width"] = 2.0  # PLAN_FIXTURE is width 1.0
        T.dispatch(gated.repo, gated.cfg, None, plan_only=False)
        state = T.latest_run(gated.repo)
        assert state["phase"] == "planned"
        assert state["tasks"] == {}
        assert state["verdict"] == {"tasks": 2, "critical_path": 2, "width": 1.0}

    def test_watch_executes_a_width_refused_plan(self, T, gated):
        gated.cfg["thrawn"]["min_width"] = 2.0
        T.dispatch(gated.repo, gated.cfg, None, plan_only=False)
        state = T.latest_run(gated.repo)
        state["phase"] = "working"  # what `thrawn watch <run>` does
        T.watch(gated.repo, gated.cfg, state)
        assert T.latest_run(gated.repo)["phase"] == "green"


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


# ---------------------------------------------------------------------------
# Swarm — automated environment setup, manual orchestration
# ---------------------------------------------------------------------------

class TestSwarmIntake:
    def test_jira_style_key_becomes_label(self, T, repo):
        intake = T.swarm_intake(repo, "COS-2101")
        assert intake["kind"] == "label"
        assert intake["ref"] == "COS-2101"
        assert "COS-2101" in intake["text"]

    def test_issue_number_without_remote_becomes_label(self, T, repo):
        # resolve_target would die here; swarm intake must not
        assert T.swarm_intake(repo, "42")["kind"] == "label"

    def test_markdown_brief_is_read(self, T, repo):
        brief = repo / "b.md"
        brief.write_text("# Fix the flux capacitor\n\ndetails\n")
        intake = T.swarm_intake(repo, str(brief))
        assert intake["kind"] == "brief"
        assert intake["title"] == "Fix the flux capacitor"


def fake_herdr(responses):
    """A try_run stand-in keyed on the herdr subcommand ('pane current',
    'tab list', 'tab create'); None means the command fails."""
    def _run(argv, **kw):
        key = " ".join(argv[1:3])
        if key not in responses or responses[key] is None:
            return None
        return SimpleNamespace(returncode=0, stdout=responses[key], stderr="")
    return _run


class TestSwarmSpawner:
    def test_fixed_tab_is_used_verbatim(self, T):
        spawner = T.HerdrSpawner(tab="w1:t5")
        assert spawner._run_tab() == "w1:t5"
        # splitting, not root-taking, and no run-tab bookkeeping
        assert spawner._fresh is False
        assert "herdr_tab" not in spawner.state

    def test_fresh_tab_gives_first_agent_the_root_pane(self, T):
        assert T.HerdrSpawner(tab="w1:t5", tab_fresh=True)._fresh is True
        # tab_fresh without a tab is meaningless and must not stick
        assert T.HerdrSpawner(tab_fresh=True)._fresh is False

    def test_labeled_tab_found_by_label(self, T, monkeypatch):
        monkeypatch.setattr(T, "try_run", fake_herdr({
            "pane current": '{"pane":{"tab_id":"w2:t1","workspace_id":"w2"}}',
            "tab list": '{"result":{"tabs":['
                        '{"label":"Git","tab_id":"w2:t2"},'
                        '{"label":"agents","tab_id":"w2:t7"}]}}',
        }))
        assert T.herdr_labeled_tab("agents") == ("w2:t7", False)

    def test_labeled_tab_created_when_missing(self, T, monkeypatch):
        monkeypatch.setattr(T, "try_run", fake_herdr({
            "pane current": '{"pane":{"workspace_id":"w2"}}',
            "tab list": '{"result":{"tabs":[{"label":"Git","tab_id":"w2:t2"}]}}',
            "tab create": '{"result":{"tab_id":"w2:t9"}}',
        }))
        assert T.herdr_labeled_tab("agents") == ("w2:t9", True)

    def test_labeled_tab_none_outside_herdr(self, T, monkeypatch):
        monkeypatch.setattr(T, "try_run", fake_herdr({}))
        assert T.herdr_labeled_tab("agents") == (None, False)

    def test_labeled_tab_resolved_from_pane_cwds_outside_herdr(
            self, T, monkeypatch):
        # no "pane current" response: launched from a plain terminal, but
        # the workspace is still found by matching the repo against pane cwds
        monkeypatch.setattr(T, "try_run", fake_herdr({
            "pane list": '{"result":{"panes":['
                         '{"workspace_id":"w1","cwd":"/code/other"},'
                         '{"workspace_id":"w2","cwd":"/code/repo"}]}}',
            "tab list": '{"result":{"tabs":['
                        '{"label":"agents","tab_id":"w2:t7"}]}}',
        }))
        assert T.herdr_labeled_tab("agents", "/code/repo") == ("w2:t7", False)


class TestWorkspaceForPath:
    """Pure workspace resolution from `herdr pane list` pane dicts —
    workspaces carry no cwd in the herdr API, so panes stand in."""

    PANES = [
        {"workspace_id": "w1", "cwd": "/code/alpha"},
        {"workspace_id": "w2", "cwd": "/code/beta",
         "foreground_cwd": "/code/beta/src"},
    ]

    def test_exact_match(self, T):
        assert T.workspace_for_path(self.PANES, "/code/beta") == "w2"

    def test_trailing_slash_normalised(self, T):
        assert T.workspace_for_path(self.PANES, "/code/beta/") == "w2"

    def test_pane_inside_the_repo_matches(self, T):
        # a pane cd'ed into a subdirectory still identifies the workspace
        panes = [{"workspace_id": "w3", "cwd": "/code/gamma/lib/deep"}]
        assert T.workspace_for_path(panes, "/code/gamma") == "w3"

    def test_repo_inside_the_pane_cwd_matches(self, T):
        # workspace rooted above the repo (e.g. a parent directory)
        panes = [{"workspace_id": "w4", "cwd": "/code"}]
        assert T.workspace_for_path(panes, "/code/delta") == "w4"

    def test_foreground_cwd_is_consulted(self, T):
        assert T.workspace_for_path(self.PANES, "/code/beta/src") == "w2"

    def test_prefix_is_path_aware_not_string_aware(self, T):
        # /code/alpha must not match /code/alphabet
        assert T.workspace_for_path(self.PANES, "/code/alphabet") is None

    def test_no_match_returns_none(self, T):
        assert T.workspace_for_path(self.PANES, "/somewhere/else") is None

    def test_ambiguous_match_returns_none(self, T):
        panes = [{"workspace_id": "w1", "cwd": "/code/repo"},
                 {"workspace_id": "w2", "cwd": "/code/repo"}]
        assert T.workspace_for_path(panes, "/code/repo") is None

    def test_same_workspace_twice_is_not_ambiguous(self, T):
        panes = [{"workspace_id": "w1", "cwd": "/code/repo"},
                 {"workspace_id": "w1", "cwd": "/code/repo/sub"}]
        assert T.workspace_for_path(panes, "/code/repo") == "w1"

    def test_empty_inputs(self, T):
        assert T.workspace_for_path([], "/code/repo") is None
        assert T.workspace_for_path(self.PANES, "") is None


class TestSpawnFallback:
    """Newer herdr dropped `agent start --cwd/--tab/--split`; spawn must
    fall back to `pane split` + `pane run` before going headless."""

    PANES = ('{"result":{"panes":['
             '{"pane_id":"w1:p1","tab_id":"w1:t5"},'
             '{"pane_id":"w1:p2","tab_id":"w1:t5"},'
             '{"pane_id":"w1:p9","tab_id":"w1:t1"}]}}')

    def _recording(self, T, monkeypatch, responses):
        calls = []
        stub = fake_herdr(responses)

        def _run(argv, **kw):
            calls.append([str(a) for a in argv])
            return stub(argv, **kw)

        monkeypatch.setattr(T, "try_run", _run)
        return calls

    def test_old_agent_start_form_still_wins(self, T, monkeypatch):
        self._recording(T, monkeypatch, {
            "agent start": '{"pane_id":"w1:p7"}',
            "pane rename": "{}",
        })
        h = T.HerdrSpawner(tab="w1:t5").spawn("n", "l", "/tmp", "true")
        assert h == {"via": "herdr", "pane": "w1:p7", "tab": "w1:t5"}

    def test_falls_back_to_pane_split_plus_run(self, T, monkeypatch):
        calls = self._recording(T, monkeypatch, {
            "agent start": None,  # unknown option: --cwd
            "pane list": self.PANES,
            "pane split": '{"result":{"pane_id":"w1:p3"}}',
            "pane run": "{}",
            "pane rename": "{}",
        })
        h = T.HerdrSpawner(tab="w1:t5").spawn("n", "⚔ COS-1", "/tmp", "true")
        assert h["via"] == "herdr"
        assert h["pane"] == "w1:p3"
        split = next(a for a in calls if a[1:3] == ["pane", "split"])
        assert split[3] == "w1:p2"  # bottom-most pane of the RIGHT tab
        assert "--cwd" in split
        run_cmd = next(a for a in calls if a[1:3] == ["pane", "run"])
        assert run_cmd[3] == "w1:p3"
        rename = next(a for a in calls if a[1:3] == ["pane", "rename"])
        assert rename[3:] == ["w1:p3", "⚔ COS-1"]

    def test_fresh_tab_root_pane_takes_the_command(self, T, monkeypatch):
        calls = self._recording(T, monkeypatch, {
            "agent start": None,
            "pane list": '{"result":{"panes":'
                         '[{"pane_id":"w1:p1","tab_id":"w1:t5"}]}}',
            "pane run": "{}",
            "pane rename": "{}",
        })
        h = T.HerdrSpawner(tab="w1:t5", tab_fresh=True).spawn(
            "n", "l", "/w t", "true")
        assert h["pane"] == "w1:p1"
        assert not any(a[1:3] == ["pane", "split"] for a in calls)
        run_cmd = next(a for a in calls if a[1:3] == ["pane", "run"])
        assert "cd '/w t'" in run_cmd[-1]  # cwd honoured, quoted

    def test_total_failure_goes_headless(self, T, monkeypatch):
        monkeypatch.setattr(T, "try_run", fake_herdr({}))
        monkeypatch.setattr(T.time, "sleep", lambda s: None)
        h = T.HerdrSpawner(tab="w1:t5").spawn("n", "l", "/tmp", "true")
        assert h["via"] == "local"


class TestSwarmGuards:
    def seed_swarm(self, T, repo, **over):
        return seed_state(
            T, repo, phase="swarm", mode="swarm",
            target={"kind": "swarm", "ref": "COS-1", "title": "swarm: COS-1"},
            tasks={"COS-1": {"status": "failed"}},
            integration={},
        )

    def test_watch_refuses_swarm(self, T, tmp_path):
        state = self.seed_swarm(T, tmp_path)
        with pytest.raises(SystemExit):
            T.watch(tmp_path, base_cfg(T), state)

    def test_integrate_refuses_swarm(self, T, tmp_path):
        state = self.seed_swarm(T, tmp_path)
        with pytest.raises(SystemExit):
            T.integrate(tmp_path, base_cfg(T), state)

    def test_retry_refuses_swarm(self, T, tmp_path):
        self.seed_swarm(T, tmp_path)
        with pytest.raises(SystemExit):
            T.cmd_retry(tmp_path, base_cfg(T), "r1", [])

    def test_adopt_refuses_swarm(self, T, tmp_path):
        self.seed_swarm(T, tmp_path)
        with pytest.raises(SystemExit):
            T.cmd_adopt(tmp_path, base_cfg(T), "r1", ["COS-1"])


class TestSwarmValidation:
    def test_unknown_runner_refused(self, T, repo):
        cfg = base_cfg(T)
        with pytest.raises(SystemExit):
            T.cmd_swarm(repo, cfg, ["COS-1"], runner="gpt9000")

    def test_duplicate_issues_refused(self, T, repo):
        cfg = base_cfg(T)
        cfg["runners"]["opus"] = {"argv": ["true"]}
        with pytest.raises(SystemExit):
            T.cmd_swarm(repo, cfg, ["COS-1", "COS-1"])

    def test_id_sanitised_to_empty_refused(self, T, repo):
        cfg = base_cfg(T)
        cfg["runners"]["opus"] = {"argv": ["true"]}
        with pytest.raises(SystemExit):
            T.cmd_swarm(repo, cfg, ["///"])


@pytest.fixture(scope="module")
def swarm(T, tmp_path_factory):
    """A two-issue swarm with fake runners, settled to completion."""
    mp = pytest.MonkeyPatch()
    mp.setenv("THRAWN_NO_HERDR", "1")
    root = tmp_path_factory.mktemp("swarm")
    repo = init_repo(root / "repo")
    (repo / ".thrawn.toml").write_text(THRAWN_TOML)
    cfg = T.load_config(repo)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    T.cmd_swarm(repo, cfg, ["COS-2101", "COS-2102"])  # default runner: fakework
    state = T.latest_run(repo)
    for _ in range(100):
        T.poll_tasks(repo, state)
        if all(ts["status"] != "running" for ts in state["tasks"].values()):
            break
        time.sleep(0.05)
    T.save_state(repo, state)
    yield SimpleNamespace(repo=repo, cfg=cfg, state=state)
    shutil.rmtree(T.worktree_base(repo), ignore_errors=True)
    mp.undo()


class TestSwarmEndToEnd:
    def test_state_is_a_swarm_run(self, swarm):
        assert swarm.state["run_id"] == "swarm"
        assert swarm.state["mode"] == "swarm"
        assert swarm.state["phase"] == "swarm"

    def test_one_worktree_and_branch_per_issue(self, swarm):
        for tid in ("COS-2101", "COS-2102"):
            ts = swarm.state["tasks"][tid]
            assert ts["branch"] == f"thrawn/swarm/{tid}"
            assert Path(ts["worktree"]).exists()

    def test_agents_ran_and_committed(self, swarm):
        for tid in ("COS-2101", "COS-2102"):
            ts = swarm.state["tasks"][tid]
            assert ts["status"] == "done"
            count = g("rev-list", "--count",
                      f"{swarm.state['base_commit']}..{ts['branch']}",
                      cwd=swarm.repo).stdout.strip()
            assert count == "1"

    def test_plan_json_written_for_status_and_diff(self, T, swarm):
        plan = json.loads(
            (T.run_dir(swarm.repo, "swarm") / "plan.json").read_text())
        assert [t["id"] for t in plan["tasks"]] == ["COS-2101", "COS-2102"]
        assert plan["tasks"][0]["runner"] == "fakework"

    def test_status_board_renders_swarm(self, T, swarm, capfd):
        T.cmd_status(swarm.repo, "swarm")
        out = capfd.readouterr().out
        assert "COS-2101" in out and "COS-2102" in out
        assert "you are the orchestrator" in out

    def test_second_swarm_gets_unique_run_id(self, T, swarm):
        assert T.unique_run_id(swarm.repo, "swarm") == "swarm-2"

    def test_abort_cleans_swarm(self, T, swarm):
        T.cmd_abort(swarm.repo, "swarm")
        after = T.load_state(swarm.repo, "swarm")
        assert after["phase"] == "aborted"
        for ts in after["tasks"].values():
            assert not Path(ts["worktree"]).exists()
        branches = g("branch", "--list", "thrawn/swarm/*",
                     cwd=swarm.repo).stdout
        assert branches.strip() == ""


# ---------------------------------------------------------------------------
# Runner event parsing (claude stream-json + pi --mode json)
# ---------------------------------------------------------------------------

class TestDescribeEvent:
    def test_claude_tool_use(self, T):
        evt = {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": "make test"}}]}}
        assert T._describe_event(evt) == "Bash: make test"

    def test_pi_tool_execution_start(self, T):
        evt = {"type": "tool_execution_start", "toolName": "bash",
               "args": {"command": "echo hi"}}
        assert T._describe_event(evt) == "bash: echo hi"

    def test_pi_tool_path_hint(self, T):
        evt = {"type": "tool_execution_start", "toolName": "write",
               "args": {"path": "sample.txt", "content": "hi"}}
        assert T._describe_event(evt) == "write: sample.txt"

    def test_pi_turn_end_text(self, T):
        evt = {"type": "turn_end", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "first line\nsecond"}]}}
        assert T._describe_event(evt) == "first line"

    def test_pi_turn_end_tool_call(self, T):
        evt = {"type": "turn_end", "message": {"role": "assistant", "content": [
            {"type": "toolCall", "name": "bash", "arguments": {"command": "ls"}}]}}
        assert T._describe_event(evt) == "bash: ls"

    def test_pi_text_delta_partial(self, T):
        evt = {"type": "message_update", "assistantMessageEvent": {
            "type": "text_delta", "partial": {"role": "assistant", "content": [
                {"type": "text", "text": "working on it"}]}}}
        assert T._describe_event(evt) == "working on it"

    def test_pi_lifecycle_events(self, T):
        assert T._describe_event({"type": "session", "id": "x"}) == "session started"
        assert T._describe_event({"type": "agent_end"}) == "wrapping up"

    def test_pi_user_message_ignored(self, T):
        evt = {"type": "message_end", "message": {"role": "user", "content": [
            {"type": "text", "text": "the prompt"}]}}
        assert T._describe_event(evt) is None

    def test_unknown_event_is_none(self, T):
        assert T._describe_event({"type": "turn_start"}) is None


class TestExtractUsage:
    def test_claude_result_event(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text(json.dumps({
            "type": "result", "subtype": "success", "total_cost_usd": 0.12,
            "usage": {"input_tokens": 100, "output_tokens": 50,
                      "cache_read_input_tokens": 900,
                      "cache_creation_input_tokens": 200}}) + "\n")
        u = T.extract_usage(log)
        assert u["input"] == 100 and u["output"] == 50
        assert u["cache_read"] == 900 and u["cache_write"] == 200
        assert u["total"] == 1250 and u["cost_usd"] == 0.12

    def test_pi_turn_end_sums_across_turns(self, T, tmp_path):
        log = tmp_path / "t.log"
        turn = {"type": "turn_end", "message": {"role": "assistant", "usage": {
            "input": 1000, "output": 20, "cacheRead": 0, "cacheWrite": 0,
            "cost": {"total": 0.005}}}}
        log.write_text(json.dumps(turn) + "\n" + json.dumps(turn) + "\n")
        u = T.extract_usage(log)
        assert u["input"] == 2000 and u["output"] == 40
        assert u["total"] == 2040 and u["cost_usd"] == 0.01

    def test_no_usage_is_none(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text("plain runner output\n{\"type\": \"turn_start\"}\nnot json {\n")
        assert T.extract_usage(log) is None

    def test_missing_log_is_none(self, T, tmp_path):
        assert T.extract_usage(tmp_path / "absent.log") is None


class TestRateLimit:
    def test_marker_in_tail(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text("working\nError: usage limit reached for this window\n")
        assert T.hit_rate_limit(log)

    def test_clean_log(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text("all fine\ndone\n")
        assert not T.hit_rate_limit(log)


class TestFmtTokens:
    def test_ranges(self, T):
        assert T.fmt_tokens(980) == "980"
        assert T.fmt_tokens(2040) == "2.0k"
        assert T.fmt_tokens(1_250_000) == "1.2M"


class TestFmtPaneOutput:
    """`thrawn _fmt` renders pi JSONL as readable pane lines, no JSON soup."""

    def run_fmt(self, lines):
        proc = subprocess.run([str(BIN), "_fmt"], input="\n".join(lines) + "\n",
                              capture_output=True, text=True)
        return proc.stdout

    def test_pi_events_render(self, T):
        out = self.run_fmt([
            json.dumps({"type": "session", "id": "x"}),
            json.dumps({"type": "tool_execution_start", "toolName": "bash",
                        "args": {"command": "echo hi"}}),
            json.dumps({"type": "message_update", "assistantMessageEvent":
                        {"type": "text_end", "content": "DONE"}}),
            json.dumps({"type": "agent_end"}),
        ])
        assert "session started (pi)" in out
        assert "▸ bash: echo hi" in out
        assert "DONE" in out
        assert "■ result: done" in out
        assert "{" not in out

    def test_pi_noise_suppressed_and_plain_passthrough(self, T):
        out = self.run_fmt([
            json.dumps({"type": "turn_start"}),
            json.dumps({"type": "tool_execution_update", "partialResult": {}}),
            "codex plain text line",
        ])
        assert out.strip() == "codex plain text line"

    def test_pi_tool_error(self, T):
        out = self.run_fmt([
            json.dumps({"type": "tool_execution_end", "toolName": "bash",
                        "isError": True, "result": {}}),
        ])
        assert "✗ bash failed" in out


# ---------------------------------------------------------------------------
# Batch dispatch, warm retries and abort evidence
# ---------------------------------------------------------------------------

class TestResolveTargets:
    def _brief(self, repo, name, title):
        p = repo / name
        p.write_text(f"# {title}\n\nbody of {title}\n")
        return str(p)

    def test_single_target_unchanged(self, T, repo):
        b = self._brief(repo, "one.md", "First")
        intake = T.resolve_targets(repo, [b])
        assert intake["kind"] != "multi"
        assert "First" in intake["title"]

    def test_multiple_targets_combined(self, T, repo):
        a = self._brief(repo, "a.md", "First")
        b = self._brief(repo, "b.md", "Second")
        intake = T.resolve_targets(repo, [a, b])
        assert intake["kind"] == "multi"
        assert "+" in str(intake["ref"])
        assert "First" in intake["text"] and "Second" in intake["text"]
        assert "body of First" in intake["text"]

    def test_multi_run_id(self, T, repo):
        rid = T.make_run_id(repo, {"kind": "multi", "ref": "42+43",
                                   "title": "x"})
        assert rid.startswith("multi-42-43")


class TestSessionResume:
    def test_extract_claude_session(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text(json.dumps({"type": "system", "subtype": "init",
                                   "session_id": "abc-123"}) + "\n")
        assert T.extract_session_id(log) == "abc-123"

    def test_extract_pi_session(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text(json.dumps({"type": "session", "id": "def-456"}) + "\n")
        assert T.extract_session_id(log) == "def-456"

    def test_extract_none(self, T, tmp_path):
        log = tmp_path / "t.log"
        log.write_text("plain output\n")
        assert T.extract_session_id(log) is None

    def test_resume_claude_appends(self, T):
        argv = ["claude", "--model", "opus", "-p", "x"]
        out = T.resume_argv(argv, "sid")
        assert out[-2:] == ["--resume", "sid"]

    def test_resume_pi_swaps_no_session(self, T):
        argv = ["pi", "--no-session", "--mode", "json", "-p", "x"]
        out = T.resume_argv(argv, "sid")
        assert "--no-session" not in out
        assert out[-2:] == ["--session", "sid"]

    def test_resume_codex_cold(self, T):
        argv = ["codex", "exec", "x"]
        assert T.resume_argv(argv, "sid") == argv


class TestAbortEvidence:
    def test_abort_snapshots_patch_and_head(self, T, repo, monkeypatch):
        monkeypatch.setenv("THRAWN_NO_HERDR", "1")
        base = g("rev-parse", "HEAD", cwd=repo).stdout.strip()
        g("checkout", "-b", "thrawn/x/t1", cwd=repo)
        (repo / "new.txt").write_text("hello\n")
        g("add", "new.txt", cwd=repo)
        g("commit", "-q", "-m", "work", cwd=repo)
        g("checkout", "main", cwd=repo)
        state = {"run_id": "x", "created": "2026-01-01T00:00:00Z",
                 "phase": "working", "base_commit": base,
                 "tasks": {"t1": {"status": "done",
                                  "branch": "thrawn/x/t1"}}}
        T.save_state(repo, state)
        T.cmd_abort(repo, "x")
        after = T.load_state(repo, "x")
        patch = T.run_dir(repo, "x") / "abort-t1.patch"
        assert patch.exists() and "hello" in patch.read_text()
        assert after["tasks"]["t1"]["head_commit"]
        branches = g("branch", "--list", "thrawn/x/*", cwd=repo).stdout
        assert branches.strip() == ""


# ---------------------------------------------------------------------------
# Souls (persona slot — must be inert when unmapped)
# ---------------------------------------------------------------------------

class TestSouls:
    def test_unmapped_stage_is_empty(self, T):
        assert T.load_soul({"personas": {}}, "planner") == ""
        assert T.load_soul({}, "planner") == ""
        assert T.load_soul({"personas": {"planner": ""}}, "planner") == ""

    def test_mapped_soul_is_loaded(self, T, tmp_path, monkeypatch):
        inst = tmp_path / "inst"
        (tmp_path / "souls").mkdir()
        (tmp_path / "souls" / "tester.md").write_text("I am the tester.\n")
        monkeypatch.setattr(T, "install_root", lambda: inst)
        out = T.load_soul({"personas": {"executor": "tester"}}, "executor")
        assert out == "I am the tester.\n\n"

    def test_missing_soul_falls_back_to_plain(self, T, tmp_path, monkeypatch):
        monkeypatch.setattr(T, "install_root", lambda: tmp_path / "inst")
        monkeypatch.setattr(T.Path, "home", classmethod(lambda cls: tmp_path))
        out = T.load_soul({"personas": {"swarm": "ghost"}}, "swarm")
        assert out == ""

    def test_templates_carry_the_slot(self, T):
        for name in ("planner.md", "executor.md", "integrator.md", "swarm.md"):
            assert T.load_prompt(name).startswith("{{persona}}# Role"), name

    def test_empty_persona_renders_byte_identical(self, T):
        tpl = T.load_prompt("swarm.md")
        rendered = T.render(tpl, persona="")
        assert rendered.startswith("# Role")
        assert "{{persona}}" not in rendered
        assert rendered == tpl.replace("{{persona}}", "")

    def test_filled_persona_leads_the_prompt(self, T):
        rendered = T.render(T.load_prompt("executor.md"),
                            persona="I am the builder.\n\n")
        assert rendered.startswith("I am the builder.\n\n# Role")


# ---------------------------------------------------------------------------
# Lessons loop
# ---------------------------------------------------------------------------

class TestLessons:
    def test_no_file_is_empty(self, T, repo):
        assert T.load_lessons(repo) == ""

    def test_bullets_filtered_and_capped(self, T):
        out = ("Here are my thoughts:\n"
               "- schema tasks always conflict, never split them\n"
               "- haiku botched the LiveView work twice\n"
               "not a bullet\n"
               "- three\n"
               "- four\n")
        lessons = T.lessons_from_output(out)
        assert len(lessons) == 3
        assert lessons[0].startswith("- schema tasks")

    def test_nothing_yields_no_lessons(self, T):
        assert T.lessons_from_output("NOTHING\n") == []

    def test_debrief_disabled_without_model(self, T, repo, monkeypatch):
        def boom(*a, **kw):
            raise AssertionError("debrief ran without a model configured")
        monkeypatch.setattr(T, "try_run", boom)
        T.run_debrief(repo, {"thrawn": {}}, {"run_id": "x", "phase": "green"})

    def test_debrief_appends_lessons(self, T, repo, monkeypatch):
        monkeypatch.setattr(
            T, "try_run",
            lambda *a, **kw: SimpleNamespace(
                returncode=0, stdout="- always run bundle install first\n"))
        state = {"run_id": "gh-1", "phase": "green", "tasks": {}}
        T.run_debrief(repo, {"thrawn": {"debrief_model": "haiku"}}, state)
        text = T.load_lessons(repo)
        assert "bundle install" in text and "gh-1" in text

    def test_planner_template_has_lessons_slot(self, T):
        assert "{{lessons}}" in T.load_prompt("planner.md")
