"""The shape of this repository's own CI workflows, read as data.

No workflow can run here, so these tests read each file under
`.github/workflows/` as YAML and check its triggers, jobs, conditions and
commands. Job conditions and concurrency groups are evaluated for a stated
event by `tests/ci_expr.py`, which refuses any construct it does not model.
The commands that hold a job's decision (`scripts/ci-self-check.py` and
`scripts/ci-changed.py`) run here as the job runs them, against temporary
folders and git repositories.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_expr  # noqa: E402

WORKFLOWS = ROOT / ".github" / "workflows"
SELF_CHECK = ROOT / "scripts" / "ci-self-check.py"
# The name each shard gives its count file. The aggregator reads the shard
# count from these names, so the number of shards is set in one place: the
# shard job's matrix.
COUNT_FILE = "shard-{index}-of-{count}"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _on(doc: dict) -> dict:
    # PyYAML reads the bare key `on` as the boolean True.
    return doc.get("on", doc.get(True))


def _run_text(job: dict) -> str:
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


def _step_named(job: dict, words: str) -> dict:
    found = [s for s in job.get("steps", []) if words in s.get("name", "")]
    assert len(found) == 1, (words, [s.get("name") for s in job["steps"]])
    return found[0]


# --- the aggregator --------------------------------------------------------

def _aggregate_argv(doc: dict, counts_dir: Path) -> tuple[list[str], str]:
    """The aggregator's command as the self-check job runs it, with the
    runner's temporary folder replaced by counts_dir's parent."""
    job = doc["jobs"]["self-check"]
    steps = [s for s in job["steps"] if "ci-self-check.py aggregate" in s.get("run", "")]
    assert len(steps) == 1, job["steps"]
    step = steps[0]
    assert step["env"]["NEEDS"] == "${{ toJSON(needs) }}", step["env"]
    text = step["run"].replace('"$RUNNER_TEMP/count"', str(counts_dir))
    argv = shlex.split(text)
    assert argv[:3] == ["python3", "scripts/ci-self-check.py", "aggregate"], argv
    return [sys.executable, str(SELF_CHECK), *argv[2:]], "NEEDS"


# The required jobs self-check needs besides the suite's own, so that its
# result carries theirs on a title or body edit, where they skip (CRT-21).
OTHER_REQUIRED = ["check-mutation", "bdd-adapter", "bdd-adapter-behave",
                  "bdd-adapter-cucumber-js", "bdd-adapter-godog"]


def _needs(**results) -> dict:
    base = {"already-tested": "skipped", "checks": "success",
            "count": "success", "shard": "success", "serial": "success",
            **{jid: "success" for jid in OTHER_REQUIRED}}
    base.update({k.replace("_", "-"): v for k, v in results.items()})
    record = {}
    for job, result in base.items():
        if result is None:
            continue
        outputs = {}
        if job == "count" and result == "success":
            outputs = {"total": "8389"}
        record[job] = {"result": result, "outputs": outputs}
    return record


def _aggregate(tmp_path: Path, needs: dict, counts, *, shards: int = 4):
    doc = _load("compass.yml")
    counts_dir = tmp_path / "count"
    counts_dir.mkdir(parents=True, exist_ok=True)
    for index, value in enumerate(counts):
        if value is not None:
            (counts_dir / COUNT_FILE.format(index=index, count=shards)).write_text(
                f"{value}\n")
    argv, env_name = _aggregate_argv(doc, counts_dir)
    env = dict(os.environ, **{env_name: json.dumps(needs)})
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                          env=env, timeout=60)


GOOD_COUNTS = [2100, 2090, 2105, 2094]

AGGREGATOR_ROWS = [
    ("every needed job success, already-tested skipped", _needs(), GOOD_COUNTS, True, []),
    ("the matrix job failure", _needs(shard="failure"), GOOD_COUNTS, False, ["shard", "failure"]),
    ("the matrix job cancelled", _needs(shard="cancelled"), GOOD_COUNTS, False, ["shard", "cancelled"]),
    ("the matrix job skipped", _needs(shard="skipped"), GOOD_COUNTS, False, ["shard", "skipped"]),
    ("the matrix job success, one count missing", _needs(),
     [2100, 2090, 2105, None], False, ["shard 3"]),
    ("the serial job failure", _needs(serial="failure"), GOOD_COUNTS, False, ["serial", "failure"]),
    ("the serial job skipped", _needs(serial="skipped"), GOOD_COUNTS, False, ["serial", "skipped"]),
    ("the count job skipped", _needs(count="skipped"), GOOD_COUNTS, False, ["count", "skipped"]),
    ("the checks job cancelled", _needs(checks="cancelled"), GOOD_COUNTS, False, ["checks", "cancelled"]),
    ("the matrix job's result missing", _needs(shard=None), GOOD_COUNTS, False, ["shard", "no result"]),
    ("already-tested failure, every other job success",
     _needs(already_tested="failure"), GOOD_COUNTS, True, []),
]


def test_crt_5_aggregator_pass_rule(tmp_path):
    """The self-check job passes only when every job it needs succeeded."""
    doc = _load("compass.yml")
    jobs = doc["jobs"]
    reporting = [jid for jid, job in jobs.items()
                 if job.get("name", jid) == "self-check"]
    assert reporting == ["self-check"], reporting
    job = jobs["self-check"]
    needs = job["needs"]
    assert set(needs) == {"already-tested", "checks", "count", "shard", "serial",
                          *OTHER_REQUIRED}, needs
    assert "strategy" in jobs["shard"], "the shard job is not the matrix job"

    # The jobs the rule checks are exactly the ones self-check needs,
    # less the push-only job that is skipped on every pull request.
    argv, _ = _aggregate_argv(doc, tmp_path / "count")
    needed = argv[argv.index("--needed") + 1].split(",")
    assert sorted(needed) == sorted(set(needs) - {"already-tested"}), needed
    assert argv[argv.index("--exempt") + 1] == "already-tested"

    # It runs unless the run was cancelled, and skips on a tested push.
    pr = {"event_name": "pull_request"}
    assert ci_expr.job_runs(job, github=pr, needs=_needs(), cancelled=False)
    assert not ci_expr.job_runs(job, github=pr, needs=_needs(), cancelled=True)
    tested = _needs(already_tested="success")
    tested["already-tested"]["outputs"] = {"skip": "true"}
    assert not ci_expr.job_runs(job, github={"event_name": "push"},
                                needs=tested, cancelled=False)

    wrong = []
    for i, (row, record, counts, passes, named) in enumerate(AGGREGATOR_ROWS):
        r = _aggregate(tmp_path / f"row-{i}", record, counts)
        if (r.returncode == 0) != passes:
            wrong.append(f"{row}: exit {r.returncode}\n{r.stdout}{r.stderr}")
            continue
        if not passes:
            missing = [word for word in named if word not in r.stdout]
            if missing:
                wrong.append(f"{row}: output does not name {missing}\n{r.stdout}")
        # Every run prints every job and its result, on success too.
        for jid, entry in record.items():
            if f"{jid}: {entry['result']}" not in r.stdout:
                wrong.append(f"{row}: does not print {jid}'s result\n{r.stdout}")
    assert not wrong, "\n\n".join(wrong)

    # A skipped shard fails twice over: its result and its missing count.
    r = _aggregate(tmp_path / "twice", _needs(shard="skipped"),
                   [2100, 2090, 2105, None])
    assert r.returncode != 0
    assert "shard: skipped" in r.stdout and "shard 3" in r.stdout, r.stdout


COUNT_ROWS = [
    ([2100, 2090, 2105, 2094], True),
    ([2100, 2090, 2105, 2093], False),
    ([2100, 2090, 2105, 2095], False),
    ([2100, 2090, 2105, None], False),
    ([2100, 2090, 2105, "abc"], False),
]


def test_crt_6_count_check(tmp_path):
    """The shards' counts must add up to the count job's total."""
    doc = _load("compass.yml")
    job = doc["jobs"]["count"]
    run = _run_text(job)
    assert 'python3 -m pytest --collect-only -q -m "not serial" tests/' in run, run
    assert "scripts/ci-self-check.py count" in run, run
    assert job["outputs"]["total"] == "${{ steps.count.outputs.total }}", job["outputs"]
    assert 'echo "total=$total" >> "$GITHUB_OUTPUT"' in run, run

    wrong = []
    for i, (counts, passes) in enumerate(COUNT_ROWS):
        r = _aggregate(tmp_path / f"row-{i}", _needs(), counts)
        if (r.returncode == 0) != passes:
            wrong.append(f"{counts}: exit {r.returncode}\n{r.stdout}{r.stderr}")
            continue
        shown = ", ".join("missing" if c is None else str(c) for c in counts)
        readable = sum(c for c in counts if isinstance(c, int))
        for text in (f"Shard counts: {shown}", f"Sum of shard counts: {readable}",
                     "Total from the count job: 8389"):
            if text not in r.stdout:
                wrong.append(f"{counts}: output lacks {text!r}\n{r.stdout}")
    assert not wrong, "\n\n".join(wrong)

    # The count each shard is checked against can be any number of shards:
    # three shards that add up pass, and a fourth file from a stale count
    # setting fails.
    r = _aggregate(tmp_path / "three", _needs(), [2800, 2800, 2789], shards=3)
    assert r.returncode == 0, r.stdout + r.stderr
    mixed = tmp_path / "mixed"
    _aggregate(mixed, _needs(), [2800, 2800, 2789], shards=3)
    r = _aggregate(mixed, _needs(), [2100, 2090, 2105, 2094], shards=4)
    assert r.returncode != 0 and "disagree" in r.stdout, r.stdout


def test_crt_6_count_reads_pytest_per_file_lines(tmp_path):
    """The count command sums pytest's "<path>: <n>" lines, and fails on
    output that holds none."""
    collected = tmp_path / "collected.txt"
    collected.write_text("tests/test_a.py: 3\ntests/sub/test_b.py: 12\n\n")
    r = subprocess.run([sys.executable, str(SELF_CHECK), "count", str(collected)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "15", r.stdout + r.stderr

    collected.write_text("no tests ran in 0.01s\n")
    r = subprocess.run([sys.executable, str(SELF_CHECK), "count", str(collected)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1 and r.stdout == "", r.stdout + r.stderr


# --- the change test --------------------------------------------------------

CHANGED = ROOT / "scripts" / "ci-changed.py"


def _git(cwd: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, env=env, check=True).stdout.strip()


@pytest.fixture
def change_repo(tmp_path):
    """A repository with a base commit, and a helper that makes a head
    commit on it changing the given paths."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")

    def change(*paths: str) -> str:
        _git(repo, "checkout", "-q", "--detach", base)
        for rel in paths:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(f"changed {rel}\n")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", "change")
        return _git(repo, "rev-parse", "HEAD")

    return repo, base, change


def _changed_argv(job: dict) -> list[str]:
    steps = [s for s in job["steps"] if s.get("id") == "changed"]
    assert len(steps) == 1, [s.get("name") for s in job["steps"]]
    argv = shlex.split(steps[0]["run"])
    assert argv[:2] == ["python3", "scripts/ci-changed.py"], argv
    return argv[2:]


def _run_changed(job: dict, repo: Path, base: str, head: str, tmp: Path):
    argv = _changed_argv(job)
    values = {"$BASE_SHA": base, "$HEAD_SHA": head,
              "$GITHUB_OUTPUT": str(tmp / "out")}
    argv = [values.get(a, a) for a in argv]
    (tmp / "out").write_text("")
    r = subprocess.run([sys.executable, str(CHANGED), *argv], cwd=repo,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return (tmp / "out").read_text().splitlines(), r.stdout


def _gated_steps(job: dict) -> None:
    """Every step after the change test runs only when it said run=true."""
    seen = False
    for step in job["steps"]:
        if step.get("id") == "changed":
            seen = True
            continue
        if seen:
            assert step.get("if") == "steps.changed.outputs.run == 'true'", step
    assert seen


HARNESS_PATHS = ["evals/", "tests/test_harness_root_real.py",
                 "tests/test_eval_harness.py",
                 ".github/requirements/self-check.txt",
                 ".github/workflows/compass.yml"]


def test_crt_9_harness_root_path_gate(change_repo, tmp_path):
    """The real-root harness runs only when its inputs change."""
    job = _load("compass.yml")["jobs"]["harness-root"]
    argv = _changed_argv(job)
    assert argv[argv.index("--output") + 2:] == HARNESS_PATHS, argv
    assert job["steps"][0]["with"]["fetch-depth"] == 0
    _gated_steps(job)
    env = next(s for s in job["steps"] if s.get("id") == "changed")["env"]
    pr = {"event": {"pull_request": {"base": {"sha": "b" * 40}, "head": {"sha": "h" * 40}},
                    "before": None}, "sha": "m" * 40}
    push = {"event": {"before": "p" * 40}, "sha": "a" * 40}
    assert ci_expr.render(env["BASE_SHA"], github=pr) == "b" * 40
    assert ci_expr.render(env["HEAD_SHA"], github=pr) == "h" * 40
    assert ci_expr.render(env["BASE_SHA"], github=push) == "p" * 40
    assert ci_expr.render(env["HEAD_SHA"], github=push) == "a" * 40

    repo, base, change = change_repo
    for i, path in enumerate(["evals/runner.py", *HARNESS_PATHS[1:]]):
        out, said = _run_changed(job, repo, base, change(path), tmp_path)
        assert out == ["run=true"], (path, out, said)
        assert path in said, said
    out, said = _run_changed(job, repo, base,
                             change("cli/compass_pkg/next_cmd.py", "docs/README.md"),
                             tmp_path)
    assert out == ["run=false"], (out, said)
    head = change("cli/compass_pkg/next_cmd.py")
    for missing in ["", "0" * 40, "1234567890abcdef" * 2 + "12345678"]:
        out, said = _run_changed(job, repo, missing, head, tmp_path)
        assert out == ["run=true"], (missing, out, said)


DOCS_PATHS = ["docs/", "mkdocs.yml", ".github/workflows/docs.yml"]


def test_crt_13_docs_build_always_reports(change_repo, tmp_path):
    """Build reports on every pull request; it builds the site only
    when the site's files changed."""
    doc = _load("docs.yml")
    on = _on(doc)
    assert on["pull_request"] in (None, {}) or "paths" not in on["pull_request"], on
    assert "paths-ignore" not in (on["pull_request"] or {})
    assert on["push"]["paths"] == ["docs/**", "mkdocs.yml", ".github/workflows/docs.yml"]
    group = doc["concurrency"]["group"]
    a = ci_expr.render(group, github={"ref": "refs/pull/12/merge"})
    b = ci_expr.render(group, github={"ref": "refs/pull/13/merge"})
    assert a != b and "refs/pull/12/merge" in a, (a, b)

    build = doc["jobs"]["build"]
    assert "if" not in build, build.get("if")
    assert ci_expr.job_runs(build, github={"event_name": "pull_request"})
    argv = _changed_argv(build)
    assert argv[argv.index("--output") + 2:] == DOCS_PATHS, argv
    assert build["steps"][0]["with"]["fetch-depth"] == 0
    _gated_steps(build)
    env = next(s for s in build["steps"] if s.get("id") == "changed")["env"]
    push = {"event": {}, "sha": "a" * 40}
    assert ci_expr.render(env["BASE_SHA"], github=push) == ""

    # With run=false every step after the change test skips, so the job
    # ends in success having built nothing.
    skipped = {"changed": {"outputs": {"run": "false"}, "outcome": "success"}}
    running = [s.get("name") or s.get("uses") for s in build["steps"]
               if ci_expr.step_runs(s, github={"event_name": "pull_request"},
                                    steps=skipped)]
    assert running == [build["steps"][0]["uses"], build["steps"][1]["uses"],
                       build["steps"][2]["name"]], running
    assert "setup-python" in build["steps"][1]["uses"], build["steps"][1]
    assert not any("continue-on-error" in s for s in build["steps"])

    repo, base, change = change_repo
    for path in ["docs/README.md", "mkdocs.yml", ".github/workflows/docs.yml"]:
        out, said = _run_changed(build, repo, base, change(path), tmp_path)
        assert out == ["run=true"], (path, out, said)
    head = change("cli/compass_pkg/next_cmd.py")
    out, said = _run_changed(build, repo, base, head, tmp_path)
    assert out == ["run=false"], (out, said)
    for missing in ["", "0" * 40]:
        out, said = _run_changed(build, repo, missing, head, tmp_path)
        assert out == ["run=true"], (missing, out, said)

    deploy = doc["jobs"]["deploy"]
    needs = {"build": {"result": "success", "outputs": {}}}
    for event, ref, runs in [("pull_request", "refs/pull/12/merge", False),
                             ("push", "refs/heads/main", True),
                             ("push", "refs/heads/other", False)]:
        assert ci_expr.job_runs(deploy, github={"event_name": event, "ref": ref},
                                needs=needs) is runs, (event, ref)
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}


# --- triggers, jobs and conditions ------------------------------------------

def test_crt_1_triggers_and_concurrency():
    """The compass.yml workflow runs on new commits and base changes, and
    cancels a superseded pull-request run."""
    doc = _load("compass.yml")
    on = _on(doc)
    assert set(on) == {"pull_request", "push"}, on
    assert on["pull_request"]["types"] == ["opened", "synchronize", "reopened",
                                           "edited"], on
    assert on["push"]["branches"] == ["main"], on
    for trigger, spec in on.items():
        for key in ("paths", "paths-ignore"):
            assert key not in (spec or {}), (trigger, key)
    group = doc["concurrency"]["group"]
    cancel = doc["concurrency"]["cancel-in-progress"]

    def ctx(event, number=None, sha="abc"):
        ev = {"pull_request": {"number": number}} if number else {}
        return {"event_name": event, "event": ev, "sha": sha}

    pr12, pr13, push = ctx("pull_request", 12), ctx("pull_request", 13), ctx("push")
    groups = [ci_expr.render(group, github=g) for g in (pr12, pr13, push)]
    assert len(set(groups)) == 3, groups
    assert groups[0].endswith("12") and groups[2].endswith("abc"), groups
    assert [ci_expr.truthy(ci_expr.evaluate(cancel, github=g))
            for g in (pr12, pr13, push)] == [True, True, False]


def _shard_job(doc):
    matrix_jobs = [jid for jid, job in doc["jobs"].items()
                   if "shard" in ((job.get("strategy") or {}).get("matrix") or {})]
    assert len(matrix_jobs) == 1, matrix_jobs
    return matrix_jobs[0], doc["jobs"][matrix_jobs[0]]


# The number of shards. It is set by the shard job's matrix alone: the
# shard command takes the count from strategy.job-total, and each shard's
# count file carries it to the aggregator. This constant is the number the
# spec fixes today.
SHARD_COUNT = 4


def test_crt_2_shard_matrix():
    """The parallel pass runs as shards that print their slowest
    tests and publish their counts under their own names."""
    doc = _load("compass.yml")
    jid, job = _shard_job(doc)
    assert jid != "self-check" and job.get("name", jid) != "self-check"
    strategy = job["strategy"]
    assert strategy["matrix"]["shard"] == list(range(SHARD_COUNT)), strategy
    assert strategy["fail-fast"] is False
    assert job["steps"][0]["with"]["fetch-depth"] == 0
    assert job["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert job["env"]["SHARD"] == "${{ matrix.shard }}"
    total = ci_expr.render(job["env"]["SHARDS"],
                           strategy={"job-total": len(strategy["matrix"]["shard"])})
    assert total == str(SHARD_COUNT), total

    listing = _step_named(job, "List this shard's test files")["run"]
    assert listing.startswith('python3 scripts/ci-shard.py "$SHARD" "$SHARDS" >'), listing
    counting = _step_named(job, "Count this shard's tests")["run"]
    assert 'python3 -m pytest --collect-only -q -m "not serial" "${files[@]}"' in counting
    assert 'count/shard-$SHARD-of-$SHARDS' in counting, counting
    running = _step_named(job, "Run this shard's tests")["run"]
    assert ('python3 -m pytest -p xdist.plugin -n auto -m "not serial" '
            '--durations=0 "${files[@]}"') in running, running
    assert " -q" not in running, "pytest.ini already sets -q"

    uploads = [s for s in job["steps"] if "upload-artifact" in s.get("uses", "")]
    assert len(uploads) == 1, uploads
    names, paths = set(), set()
    for index in range(SHARD_COUNT):
        names.add(ci_expr.render(uploads[0]["with"]["name"], matrix={"shard": index}))
        paths.add(ci_expr.render(uploads[0]["with"]["path"], matrix={"shard": index},
                                 runner={"temp": "/t"},
                                 strategy={"job-total": SHARD_COUNT}))
    assert names == {f"shard-count-{i}" for i in range(SHARD_COUNT)}, names
    assert paths == {f"/t/count/{COUNT_FILE.format(index=i, count=SHARD_COUNT)}"
                     for i in range(SHARD_COUNT)}, paths
    assert uploads[0]["with"]["if-no-files-found"] == "error"
    assert job["steps"][-1] is uploads[0], "the count is published before the tests pass"


def test_crt_3_serial_job():
    """The serial pass runs in its own job."""
    doc = _load("compass.yml")
    serial = [jid for jid, job in doc["jobs"].items()
              if "-m serial" in _run_text(job).replace('"not serial"', "")]
    assert serial == ["serial"], serial
    job = doc["jobs"]["serial"]
    assert "python3 -m pytest tests/ -m serial --durations=20" in _run_text(job)
    assert job["timeout-minutes"] == 20
    assert job["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    _, shard = _shard_job(doc)
    for line in _run_text(shard).splitlines():
        if "pytest" in line:
            assert '-m "not serial"' in line, line


class _Stub:
    """Stand-in git and python3 that log their arguments."""

    def __init__(self, tmp: Path, before_exists: bool):
        self.bin = tmp / "bin"
        self.bin.mkdir(parents=True)
        self.log = tmp / "calls.txt"
        for name in ("git", "python3"):
            path = self.bin / name
            path.write_text(
                "#!/bin/sh\n"
                f'echo "{name} $*" >> "{self.log}"\n'
                'case "$1" in cat-file) exit '
                f'{0 if before_exists else 1};; esac\n'
                "cat >/dev/null 2>&1 || true\n"
                "exit 0\n")
            path.chmod(0o755)


def _rival_step_calls(step: dict, tmp: Path, env: dict, before_exists=True):
    stub = _Stub(tmp, before_exists)
    full = dict(os.environ, PATH=f"{stub.bin}{os.pathsep}{os.environ['PATH']}", **env)
    r = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", step["run"]],
                       env=full, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return stub.log.read_text().splitlines()


def test_crt_4_old_self_check_steps_still_run(tmp_path):
    """Every check the old self-check job ran still runs, in order,
    in a job self-check needs."""
    doc = _load("compass.yml")
    assert "checks" in doc["jobs"]["self-check"]["needs"]
    job = doc["jobs"]["checks"]
    assert job["steps"][0]["with"]["fetch-depth"] == 0
    names = [s.get("name", "") for s in job["steps"]]
    want = ["No rival product name in commit messages",
            "Install the test runner and the optional JSON Schema validator",
            "Repo structure check", "CLI syntax", "Compass gate suite"]
    found = [n for n in names if n in want]
    assert found == want, names
    by_name = {s.get("name"): s for s in job["steps"]}
    assert by_name[want[1]]["run"] == "pip install -r .github/requirements/self-check.txt"
    assert by_name[want[2]]["run"] == "bash scripts/validate.sh"
    assert "ast.parse(open('cli/compass').read())" in by_name[want[3]]["run"]
    gate = by_name[want[4]]
    assert 'python3 cli/compass ci --since "origin/$BASE_REF"' in gate["run"]
    assert gate["env"]["BASE_REF"] == "${{ github.base_ref }}"

    rival = by_name[want[0]]
    assert rival.get("shell") == "bash"
    pr = _rival_step_calls(rival, tmp_path / "pr", {
        "EVENT_NAME": "pull_request", "BASE_SHA": "base1", "HEAD_SHA": "head1",
        "BEFORE_SHA": "", "AFTER_SHA": "merge1"})
    assert "git log --format=%B base1..head1" in pr, pr
    push = _rival_step_calls(rival, tmp_path / "push", {
        "EVENT_NAME": "push", "BASE_SHA": "", "HEAD_SHA": "",
        "BEFORE_SHA": "before1", "AFTER_SHA": "after1"})
    assert "git log --format=%B before1..after1" in push, push
    first = _rival_step_calls(rival, tmp_path / "first", {
        "EVENT_NAME": "push", "BASE_SHA": "", "HEAD_SHA": "",
        "BEFORE_SHA": "0" * 40, "AFTER_SHA": "after1"})
    assert "git log -1 --format=%B after1" in first, first
    gone = _rival_step_calls(rival, tmp_path / "gone", {
        "EVENT_NAME": "push", "BASE_SHA": "", "HEAD_SHA": "",
        "BEFORE_SHA": "before1", "AFTER_SHA": "after1"}, before_exists=False)
    assert "git log -1 --format=%B after1" in gone, gone
    for calls in (pr, push, first, gone):
        assert "python3 scripts/rival-name-gate.py --text -" in calls, calls


def test_crt_7_already_tested_job_shape():
    """The already-tested job runs on a push only, with four read
    permissions, and publishes skip."""
    job = _load("compass.yml")["jobs"]["already-tested"]
    assert ci_expr.job_runs(job, github={"event_name": "push"})
    assert not ci_expr.job_runs(job, github={"event_name": "pull_request"})
    assert job["permissions"] == READ_GRANT
    assert job["outputs"] == {"skip": "${{ steps.decide.outputs.skip }}"}
    assert job["steps"][0]["with"]["fetch-depth"] == 0
    decide = next(s for s in job["steps"] if s.get("id") == "decide")
    assert shlex.split(decide["run"]) == [
        "python3", "scripts/ci-already-tested.py", "--repo", "$REPO",
        "--commit", "$MERGED", "--output", "$GITHUB_OUTPUT"]
    assert decide["env"] == {"GH_TOKEN": "${{ github.token }}",
                             "REPO": "${{ github.repository }}",
                             "MERGED": "${{ github.sha }}"}


# The job-level grant of already-tested and self-check: both read the pull
# request's check runs and its timeline (issues read covers the timeline).
READ_GRANT = {"contents": "read", "pull-requests": "read", "checks": "read",
              "issues": "read"}
# self-check also reads the pull request's workflow runs and their jobs on a
# title or body edit, because the check-runs API lists no check run for a job
# still waiting on the jobs it needs (ayeo-io/compass#578, run 38849230839).
SELF_CHECK_GRANT = {**READ_GRANT, "actions": "read"}

REQUIRED = ["self-check", "check-mutation", "bdd-adapter", "bdd-adapter-behave",
            "bdd-adapter-cucumber-js", "bdd-adapter-godog"]


def test_crt_8_required_jobs():
    """The required jobs keep their names, run on every pull request,
    and skip together on a tested push."""
    jobs = _load("compass.yml")["jobs"]
    for jid in REQUIRED:
        assert jid in jobs and jobs[jid].get("name", jid) == jid, jid
    for jid in REQUIRED + ["shard", "serial", "count", "checks"]:
        texts = [str(jobs[jid].get("if", ""))] + [
            str(s.get("if", "")) for s in jobs[jid].get("steps", [])]
        assert not any("changed" in t or "paths" in t for t in texts), (jid, texts)

    others = [jid for jid in jobs if jid != "already-tested"]
    for jid in others:
        needs = jobs[jid].get("needs")
        needs = [needs] if isinstance(needs, str) else needs
        assert "already-tested" in needs, jid

    def record(at_result, at_outputs=None, **others_results):
        rec = {"already-tested": {"result": at_result, "outputs": at_outputs or {}}}
        for jid in ("checks", "count", "shard", "serial"):
            rec[jid] = {"result": others_results.get(jid, "success"), "outputs": {}}
        return rec

    pr = {"event_name": "pull_request"}
    push = {"event_name": "push"}
    for jid in others:
        assert ci_expr.job_runs(jobs[jid], github=pr, needs=record("skipped")), jid
        assert not ci_expr.job_runs(jobs[jid], github=push,
                                    needs=record("success", {"skip": "true"})), jid
        assert ci_expr.job_runs(jobs[jid], github=push,
                                needs=record("success", {"skip": "false"})), jid
        assert ci_expr.job_runs(jobs[jid], github=push, needs=record("failure")), jid
        assert not ci_expr.job_runs(jobs[jid], github=pr, needs=record("skipped"),
                                    cancelled=True), jid
    for other in ("checks", "count", "shard", "serial"):
        for result in ("failure", "cancelled", "skipped"):
            assert ci_expr.job_runs(jobs["self-check"], github=pr,
                                    needs=record("skipped", **{other: result})), (
                other, result)


@pytest.mark.parametrize("text", [
    "always()", "failure()", "contains(github.ref, 'main')",
    "github.event.commits[0]", "1 < 2", "secrets.TOKEN == ''", "env.X",
    "toJSON(needs)", "github.ref ~ 'x'", "'a' + 'b'",
])
def test_crt_8_evaluator_refuses_what_it_does_not_know(text):
    """A construct the evaluator does not model raises, so a test of a new
    condition fails rather than reading it as something else."""
    with pytest.raises(ci_expr.ExprError):
        ci_expr.evaluate(text, github={"ref": "refs/heads/main", "event": {}},
                         needs={})


def test_crt_8_evaluator_follows_github_rules():
    """The rules the conditions depend on: a missing property is null,
    null compared with a string is unequal, && and || return an operand,
    and strings compare without regard to case."""
    ev = lambda text, **c: ci_expr.evaluate(text, **c)  # noqa: E731
    needs = {"already-tested": {"result": "skipped", "outputs": {}}}
    assert ev("needs.already-tested.outputs.skip != 'true'", needs=needs) is True
    assert ev("needs.already-tested.outputs.skip == 'true'", needs=needs) is False
    assert ev("github.x || 'fallback'", github={}) == "fallback"
    assert ev("'a' && 'b'", github={}) == "b"
    assert ev("'ABC' == 'abc'") is True
    assert ev("!cancelled()", status={"cancelled": False}) is True
    assert ci_expr.condition("github.event_name == 'push'",
                             needs={"x": {"result": "failure"}},
                             github={"event_name": "push"}) is False


def test_crt_12_pr_text_workflow():
    """The pull-request text is scanned in its own workflow, on
    edits too, and its group never cancels the suite."""
    doc = _load("pr-text.yml")
    on = _on(doc)
    assert set(on) == {"pull_request"}, on
    assert on["pull_request"]["types"] == ["opened", "synchronize", "reopened", "edited"]
    assert ci_expr.truthy(ci_expr.evaluate(doc["concurrency"]["cancel-in-progress"]))
    pr12 = {"event_name": "pull_request", "ref": "refs/pull/12/merge", "sha": "abc",
            "event": {"pull_request": {"number": 12}}}
    groups = {name: ci_expr.render(_load(name)["concurrency"]["group"], github=pr12)
              for name in ("pr-text.yml", "compass.yml", "docs.yml",
                           "claude-review.yml")}
    assert len(set(groups.values())) == 4, groups
    pr13 = dict(pr12, event={"pull_request": {"number": 13}})
    assert ci_expr.render(doc["concurrency"]["group"], github=pr13) != groups["pr-text.yml"]

    assert list(doc["jobs"]) == ["pr-text"]
    job = doc["jobs"]["pr-text"]
    assert ('python3 scripts/rival-name-gate.py --github-event "$GITHUB_EVENT_PATH"'
            in _run_text(job))
    compass = (WORKFLOWS / "compass.yml").read_text(encoding="utf-8")
    assert "--github-event" not in compass
    for name in ("pr-text.yml", "compass.yml"):
        for jid, j in _load(name)["jobs"].items():
            for step in j.get("steps", []):
                text = json.dumps(step)
                for field in ("pull_request.title", "pull_request.body"):
                    assert field not in text, (name, jid, field)
    assert "secrets" not in (WORKFLOWS / "pr-text.yml").read_text(encoding="utf-8")


# The one job allowed more than 45 minutes: on a title or body edit,
# compass.yml's self-check waits up to 55 minutes for the head's suite run,
# whose shards alone may take 45.
LONGER_TIMEOUTS = {("compass.yml", "self-check"): 60}


def _timeout_problems(paths) -> list[str]:
    problems = []
    for path in paths:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for jid, job in (doc.get("jobs") or {}).items():
            value = job.get("timeout-minutes")
            most = LONGER_TIMEOUTS.get((Path(path).name, jid), 45)
            if not (isinstance(value, int) and not isinstance(value, bool)
                    and 5 <= value <= most):
                problems.append(f"{Path(path).name}: job {jid} has timeout-minutes "
                                f"{value!r}, not a whole number from 5 to {most}")
    return problems


def test_crt_14_every_job_has_a_timeout(tmp_path):
    """Every job in every workflow ends at its own timeout."""
    files = sorted(WORKFLOWS.glob("*.yml"))
    assert len(files) >= 5, files
    assert _timeout_problems(files) == []
    assert _load("compass.yml")["jobs"]["serial"]["timeout-minutes"] == 20

    # The same check fails on a copy with one timeout removed, and names it.
    text = (WORKFLOWS / "compass.yml").read_text(encoding="utf-8")
    marker = "  count:\n"
    head, tail = text.split(marker, 1)
    first, rest = tail.split("    timeout-minutes: 5\n", 1)
    copy = tmp_path / "compass.yml"
    copy.write_text(head + marker + first + rest, encoding="utf-8")
    assert _timeout_problems([copy]) == [
        "compass.yml: job count has timeout-minutes None, not a whole number from 5 to 45"]


def test_crt_22_shard_timeout_is_45():
    """A shard ends at 45 minutes, so one slow shard fails clearly rather
    than at the margin of its usual run time (decision BD-4)."""
    job = _load("compass.yml")["jobs"]["shard"]
    assert job["timeout-minutes"] == 45
    # Every test's duration reaches the log, so scripts/ci-durations.py can
    # weigh every file rather than only those holding the slowest tests.
    running = _step_named(job, "Run this shard's tests")["run"]
    assert " --durations=0 " in running, running


def test_crt_15_token_stays_read_only():
    """The workflow token stays read-only, with two job-level read grants."""
    for name in ("compass.yml", "pr-text.yml", "docs.yml"):
        assert _load(name)["permissions"] == {"contents": "read"}, name
    for name in ("compass.yml", "pr-text.yml"):
        jobs = _load(name)["jobs"]
        granted = {jid: job["permissions"] for jid, job in jobs.items()
                   if "permissions" in job}
        expected = ({"already-tested": READ_GRANT, "self-check": SELF_CHECK_GRANT}
                    if name == "compass.yml" else {})
        assert granted == expected, (name, granted)
        for jid, job in jobs.items():
            assert "write" not in json.dumps(job.get("permissions", {})), (name, jid)
    assert _load("docs.yml")["jobs"]["deploy"]["permissions"] == {
        "pages": "write", "id-token": "write"}

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ci_permissions_posture", ROOT / "tests" / "test_ci_permissions_posture.py")
    posture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(posture)
    assert WORKFLOWS / "pr-text.yml" in posture._workflow_files()
    assert posture._declares_permissions(WORKFLOWS / "pr-text.yml")


# --- a base change (CRT-21) -------------------------------------------------

SUITE_JOBS = ["checks", "count", "shard", "serial", "check-mutation", "harness-root",
              "bdd-adapter", "bdd-adapter-behave", "bdd-adapter-cucumber-js",
              "bdd-adapter-godog"]

# (action, changes, the suite runs). A missing `changes` is what GitHub
# sends on every action but edited.
EDIT_ROWS = [
    ("opened", None, True),
    ("synchronize", None, True),
    ("reopened", None, True),
    ("edited", {"base": {"ref": {"from": "stack"}, "sha": {"from": "a" * 40}}}, True),
    ("edited", {"title": {"from": "old title"}}, False),
    ("edited", {"body": {"from": "old body"}}, False),
]


def _pr_event(action, changes, number=12):
    event = {"action": action, "pull_request": {"number": number}}
    if changes is not None:
        event["changes"] = changes
    return {"event_name": "pull_request", "event": event, "sha": "abc"}


def _earlier_result_steps(job):
    return [s for s in job["steps"] if "ci-already-tested.py" in s.get("run", "")]


def test_crt_21_base_change_reruns_the_suite():
    """A base change runs the suite again; a title or body edit runs only
    self-check, which reports the earlier suite result, and never cancels a
    suite run."""
    doc = _load("compass.yml")
    jobs = doc["jobs"]
    assert set(SUITE_JOBS) | {"already-tested", "self-check"} == set(jobs), set(jobs)
    pr_needs = {"already-tested": {"result": "skipped", "outputs": {}}}
    wrong = []
    for action, changes, suite in EDIT_ROWS:
        github = _pr_event(action, changes)
        for jid in SUITE_JOBS:
            if ci_expr.job_runs(jobs[jid], github=github, needs=pr_needs) is not suite:
                wrong.append(f"{jid} on {action} {changes}: expected runs={suite}")
    assert not wrong, "\n".join(wrong)

    self_check = jobs["self-check"]
    assert set(self_check["needs"]) == {"already-tested", "checks", "count", "shard",
                                        "serial", *OTHER_REQUIRED}, self_check["needs"]
    aggregate = [s for s in self_check["steps"]
                 if "ci-self-check.py aggregate" in s.get("run", "")]
    downloads = [s for s in self_check["steps"]
                 if "download-artifact" in s.get("uses", "")]
    earlier = _earlier_result_steps(self_check)
    assert len(aggregate) == 1 and len(downloads) == 1 and len(earlier) == 1, (
        self_check["steps"])
    for action, changes, suite in EDIT_ROWS:
        github = _pr_event(action, changes)
        skipped_needs = {jid: {"result": "success" if suite else "skipped",
                               "outputs": {}} for jid in self_check["needs"]}
        skipped_needs["already-tested"] = {"result": "skipped", "outputs": {}}
        assert ci_expr.job_runs(self_check, github=github, needs=skipped_needs), action
        for step in aggregate + downloads:
            assert ci_expr.step_runs(step, github=github, steps={}) is suite, (
                action, changes, step)
        assert ci_expr.step_runs(earlier[0], github=github, steps={}) is (not suite), (
            action, changes)

    # The earlier-result command, as the step runs it.
    step = earlier[0]
    assert shlex.split(step["run"]) == [
        "python3", "scripts/ci-already-tested.py", "--repo", "$REPO",
        "--pull-request", "$NUMBER", "--head", "$HEAD", "--this-run", "$RUN_ID",
        "--wait-minutes", "55"]
    assert step["env"] == {"GH_TOKEN": "${{ github.token }}",
                           "REPO": "${{ github.repository }}",
                           "NUMBER": "${{ github.event.pull_request.number }}",
                           "HEAD": "${{ github.event.pull_request.head.sha }}",
                           "RUN_ID": "${{ github.run_id }}"}
    assert self_check["permissions"] == SELF_CHECK_GRANT
    # The text-edit step waits up to 55 minutes for the head's suite run, so
    # the job may run 60; the aggregate step keeps a 5-minute limit.
    assert self_check["timeout-minutes"] == 60
    for step in self_check["steps"]:
        if step not in earlier:
            assert step.get("timeout-minutes") == 5, step

    # A title edit has a group of its own; a base change shares the push's.
    group = doc["concurrency"]["group"]
    cancel = doc["concurrency"]["cancel-in-progress"]
    push_group = ci_expr.render(group, github=_pr_event("synchronize", None))
    base_group = ci_expr.render(group, github=_pr_event(*EDIT_ROWS[3][:2]))
    title_group = ci_expr.render(group, github=_pr_event(*EDIT_ROWS[4][:2]))
    body_group = ci_expr.render(group, github=_pr_event(*EDIT_ROWS[5][:2]))
    other_title = ci_expr.render(group, github=_pr_event(*EDIT_ROWS[4][:2], number=13))
    assert base_group == push_group, (base_group, push_group)
    assert title_group == body_group != push_group, (title_group, push_group)
    assert other_title != title_group, other_title
    assert ci_expr.truthy(ci_expr.evaluate(cancel, github=_pr_event(*EDIT_ROWS[4][:2])))
