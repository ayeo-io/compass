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

# The names of self-check's two aggregate steps: the whole suite's rule, in a
# merge group and on a push, and the fast rule, on a pull request.
FULL_STEP = "Every needed job succeeded and the shard counts add up"
FAST_STEP = "The fast jobs succeeded and the suite jobs skipped"


def _aggregate_steps(job: dict) -> list[dict]:
    return [s for s in job["steps"] if "ci-self-check.py aggregate" in s.get("run", "")]


def _aggregate_argv(doc: dict, counts_dir: Path, step_name: str = FULL_STEP
                    ) -> tuple[list[str], str]:
    """The aggregator's command as the self-check job runs it, with the
    runner's temporary folder replaced by counts_dir's parent."""
    job = doc["jobs"]["self-check"]
    steps = _aggregate_steps(job)
    assert [s.get("name") for s in steps] == [FULL_STEP, FAST_STEP], job["steps"]
    step = next(s for s in steps if s["name"] == step_name)
    assert step["env"]["NEEDS"] == "${{ toJSON(needs) }}", step["env"]
    text = step["run"].replace('"$RUNNER_TEMP/count"', str(counts_dir))
    argv = shlex.split(text)
    assert argv[:3] == ["python3", "scripts/ci-self-check.py", "aggregate"], argv
    return [sys.executable, str(SELF_CHECK), *argv[2:]], "NEEDS"


# The required jobs self-check needs besides the suite's own, so that its
# result carries theirs on a title or body edit, where they skip (CRT-21).
OTHER_REQUIRED = ["check-mutation", "bdd-adapter", "bdd-adapter-behave",
                  "bdd-adapter-cucumber-js", "bdd-adapter-godog", "atdd-adapter-python",
                  "atdd-adapter-typescript"]
# The jobs a pull request runs, and the ones only a merge group or a push to
# main runs (ayeo-io/compass-delivery#362).
FAST_JOBS = ["checks", "count", "fast-tests"]
SUITE_ONLY = ["shard", "serial", *OTHER_REQUIRED]
SELF_CHECK_NEEDS = {"already-tested", *FAST_JOBS, *SUITE_ONLY}


def _needs(**results) -> dict:
    """A needs record of a merge-group run: every suite job succeeded and
    fast-tests skipped."""
    base = {"already-tested": "skipped", "checks": "success",
            "count": "success", "fast-tests": "skipped", "shard": "success",
            "serial": "success", **{jid: "success" for jid in OTHER_REQUIRED}}
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


def _fast_needs(**results) -> dict:
    """A needs record of a pull-request run: the fast jobs succeeded and
    every suite job skipped."""
    record = _needs(**{"fast_tests": "success",
                       **{j.replace("-", "_"): "skipped" for j in SUITE_ONLY}})
    for job, result in results.items():
        record[job.replace("_", "-")]["result"] = result
    return record


def _aggregate(tmp_path: Path, needs: dict, counts, *, shards: int = 4,
               step_name: str = FULL_STEP):
    doc = _load("compass.yml")
    counts_dir = tmp_path / "count"
    counts_dir.mkdir(parents=True, exist_ok=True)
    for index, value in enumerate(counts):
        if value is not None:
            (counts_dir / COUNT_FILE.format(index=index, count=shards)).write_text(
                f"{value}\n")
    argv, env_name = _aggregate_argv(doc, counts_dir, step_name)
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
    ("fast-tests ran in a merge group", _needs(fast_tests="success"), GOOD_COUNTS,
     False, ["fast-tests", "not skipped"]),
    ("fast-tests failed in a merge group", _needs(fast_tests="failure"), GOOD_COUNTS,
     False, ["fast-tests", "failure"]),
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
    assert set(needs) == SELF_CHECK_NEEDS, needs
    assert "strategy" in jobs["shard"], "the shard job is not the matrix job"

    # The jobs the rule checks are exactly the ones self-check needs, less
    # the push-only job that is skipped in a merge group, and fast-tests,
    # which must skip there.
    argv, _ = _aggregate_argv(doc, tmp_path / "count")
    needed = argv[argv.index("--needed") + 1].split(",")
    assert sorted(needed) == sorted(set(needs) - {"already-tested", "fast-tests"}), needed
    assert argv[argv.index("--skipped") + 1] == "fast-tests"
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


def _without(record: dict, job: str) -> dict:
    return {k: v for k, v in record.items() if k != job}


FAST_ROWS = [
    ("the fast jobs succeeded, the suite jobs skipped", _fast_needs(), True, []),
    ("fast-tests failure", _fast_needs(fast_tests="failure"), False,
     ["fast-tests", "failure"]),
    ("fast-tests skipped", _fast_needs(fast_tests="skipped"), False,
     ["fast-tests", "skipped"]),
    ("fast-tests has no result", _without(_fast_needs(), "fast-tests"), False,
     ["fast-tests", "no result"]),
    ("the count job failure", _fast_needs(count="failure"), False, ["count", "failure"]),
    ("the checks job cancelled", _fast_needs(checks="cancelled"), False,
     ["checks", "cancelled"]),
    ("a shard ran on a pull request", _fast_needs(shard="success"), False,
     ["shard", "not skipped"]),
    ("check-mutation failed on a pull request", _fast_needs(check_mutation="failure"),
     False, ["check-mutation", "failure"]),
]


def test_mq_1_pull_request_aggregator_pass_rule(tmp_path):
    """On a pull request self-check passes only when the fast jobs
    succeeded and every suite job skipped; it reads no shard count."""
    doc = _load("compass.yml")
    argv, _ = _aggregate_argv(doc, tmp_path / "count", FAST_STEP)
    assert argv[argv.index("--needed") + 1].split(",") == FAST_JOBS
    assert sorted(argv[argv.index("--skipped") + 1].split(",")) == sorted(SUITE_ONLY)
    assert argv[argv.index("--exempt") + 1] == "already-tested"
    assert "--counts" not in argv, argv
    named = (set(FAST_JOBS) | set(SUITE_ONLY) | {"already-tested"})
    assert named == set(doc["jobs"]["self-check"]["needs"])

    wrong = []
    for i, (row, record, passes, words) in enumerate(FAST_ROWS):
        r = _aggregate(tmp_path / f"row-{i}", record, [], step_name=FAST_STEP)
        if (r.returncode == 0) != passes:
            wrong.append(f"{row}: exit {r.returncode}\n{r.stdout}{r.stderr}")
            continue
        missing = [w for w in words if w not in r.stdout]
        if missing:
            wrong.append(f"{row}: output does not name {missing}\n{r.stdout}")
        if "Shard counts: not read" not in r.stdout:
            wrong.append(f"{row}: output does not say the counts were not read\n{r.stdout}")
    assert not wrong, "\n\n".join(wrong)


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


DOCS_PATHS = ["docs/", "mkdocs.yml", ".github/workflows/docs.yml"]


def test_crt_13_docs_build_always_reports(change_repo, tmp_path):
    """Build reports on every pull request; it builds the site only
    when the site's files changed."""
    doc = _load("docs.yml")
    on = _on(doc)
    assert on["pull_request"] in (None, {}) or "paths" not in on["pull_request"], on
    assert "paths-ignore" not in (on["pull_request"] or {})
    # The merge queue waits for build too, so it reports in a merge group.
    assert on["merge_group"] == {"types": ["checks_requested"]}, on
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
    group = {"event": {"merge_group": {"base_sha": "b" * 40}}, "sha": "m" * 40}
    assert ci_expr.render(env["BASE_SHA"], github=group) == "b" * 40
    assert ci_expr.render(env["HEAD_SHA"], github=group) == "m" * 40

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
    # An empty base, the all-zero sha of a new branch and a sha the clone
    # does not hold each run the job rather than skip it.
    for missing in ["", "0" * 40, "1234567890abcdef" * 2 + "12345678"]:
        out, said = _run_changed(build, repo, missing, head, tmp_path)
        assert out == ["run=true"], (missing, out, said)

    deploy = doc["jobs"]["deploy"]
    needs = {"build": {"result": "success", "outputs": {}}}
    for event, ref, runs in [("pull_request", "refs/pull/12/merge", False),
                             ("merge_group", "refs/heads/gh-readonly-queue/main/pr-12-"
                              + "a" * 40, False),
                             ("push", "refs/heads/main", True),
                             ("push", "refs/heads/other", False)]:
        assert ci_expr.job_runs(deploy, github={"event_name": event, "ref": ref},
                                needs=needs) is runs, (event, ref)
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}


# --- triggers, jobs and conditions ------------------------------------------

def test_crt_1_triggers_and_concurrency():
    """The compass.yml workflow runs on new commits, base changes, a draft
    marked ready and merge groups, and cancels a superseded pull-request run."""
    doc = _load("compass.yml")
    on = _on(doc)
    assert set(on) == {"pull_request", "merge_group", "push"}, on
    assert on["pull_request"]["types"] == ["opened", "synchronize", "reopened",
                                           "edited", "ready_for_review"], on
    assert on["merge_group"] == {"types": ["checks_requested"]}, on
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
    group1, group2 = ctx("merge_group", sha="mg1"), ctx("merge_group", sha="mg2")
    contexts = (pr12, pr13, push, group1, group2)
    groups = [ci_expr.render(group, github=g) for g in contexts]
    assert len(set(groups)) == 5, groups
    assert groups[0].endswith("12") and groups[2].endswith("abc"), groups
    assert groups[3].endswith("mg1"), groups
    assert [ci_expr.truthy(ci_expr.evaluate(cancel, github=g))
            for g in contexts] == [True, True, False, False, False]


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
            '--durations=0 --durations-min=0 "${files[@]}"') in running, running
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
    # fast-tests runs the serial tests of its own few files on a pull request.
    assert serial == ["fast-tests", "serial"], serial
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
    assert 'python3 cli/compass ci --since "$GROUP_BASE"' in gate["run"]
    assert gate["env"]["BASE_REF"] == "${{ github.base_ref }}"
    assert gate["env"]["GROUP_BASE"] == "${{ github.event.merge_group.base_sha }}"

    rival = by_name[want[0]]
    assert rival.get("shell") == "bash"
    pr = _rival_step_calls(rival, tmp_path / "pr", {
        "EVENT_NAME": "pull_request", "BASE_SHA": "base1", "HEAD_SHA": "head1",
        "BEFORE_SHA": "", "AFTER_SHA": "merge1"})
    assert "git log --format=%B base1..head1" in pr, pr
    group = _rival_step_calls(rival, tmp_path / "group", {
        "EVENT_NAME": "merge_group", "BASE_SHA": "gbase", "HEAD_SHA": "ghead",
        "BEFORE_SHA": "", "AFTER_SHA": "ghead"})
    assert "git log --format=%B gbase..ghead" in group, group
    env = rival["env"]
    mg = {"event": {"merge_group": {"base_sha": "gbase", "head_sha": "ghead"}}}
    assert ci_expr.render(env["BASE_SHA"], github=mg) == "gbase"
    assert ci_expr.render(env["HEAD_SHA"], github=mg) == "ghead"
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
    for calls in (pr, group, push, first, gone):
        assert "python3 scripts/rival-name-gate.py --text -" in calls, calls


def test_crt_7_already_tested_job_shape():
    """The already-tested job runs on a push only, reads this workflow's
    runs and jobs, and publishes skip."""
    job = _load("compass.yml")["jobs"]["already-tested"]
    assert ci_expr.job_runs(job, github={"event_name": "push"})
    assert not ci_expr.job_runs(job, github={"event_name": "pull_request"})
    assert not ci_expr.job_runs(job, github={"event_name": "merge_group"})
    assert job["permissions"] == {"contents": "read", "actions": "read"}
    assert job["outputs"] == {"skip": "${{ steps.decide.outputs.skip }}"}
    decide = next(s for s in job["steps"] if s.get("id") == "decide")
    assert shlex.split(decide["run"]) == [
        "python3", "scripts/ci-already-tested.py", "--repo", "$REPO",
        "--commit", "$MERGED", "--this-run", "$RUN_ID", "--output", "$GITHUB_OUTPUT"]
    assert decide["env"] == {"GH_TOKEN": "${{ github.token }}",
                             "REPO": "${{ github.repository }}",
                             "MERGED": "${{ github.sha }}",
                             "RUN_ID": "${{ github.run_id }}"}


# The job-level grant of already-tested and self-check: both read the pull
# request's check runs and its timeline (issues read covers the timeline).
READ_GRANT = {"contents": "read", "pull-requests": "read", "checks": "read",
              "issues": "read"}
# self-check also reads the pull request's workflow runs and their jobs on a
# title or body edit, because the check-runs API lists no check run for a job
# still waiting on the jobs it needs (ayeo-io/compass#578, run 38849230839).
SELF_CHECK_GRANT = {**READ_GRANT, "actions": "read"}

REQUIRED = ["self-check", "check-mutation", "bdd-adapter", "bdd-adapter-behave",
            "bdd-adapter-cucumber-js", "bdd-adapter-godog", "atdd-adapter-python"]


def test_crt_8_required_jobs():
    """The required jobs keep their names. A pull request runs the fast jobs,
    a merge group and an untested push run the suite, and every job skips
    together on a tested push."""
    jobs = _load("compass.yml")["jobs"]
    for jid in REQUIRED:
        assert jid in jobs and jobs[jid].get("name", jid) == jid, jid
    for jid in REQUIRED + ["shard", "serial", "count", "checks", "fast-tests"]:
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
        for jid in ("checks", "count", "fast-tests", "shard", "serial"):
            rec[jid] = {"result": others_results.get(jid, "success"), "outputs": {}}
        return rec

    pr = {"event_name": "pull_request", "event": {"pull_request": {"draft": False}}}
    draft = {"event_name": "pull_request", "event": {"pull_request": {"draft": True}}}
    group = {"event_name": "merge_group", "event": {"merge_group": {}}}
    push = {"event_name": "push", "event": {}}
    on_pr = {"checks", "count", "fast-tests", "self-check"}
    in_group = set(others) - {"fast-tests"}
    wrong = []
    for jid in others:
        rows = [(pr, record("skipped"), jid in on_pr),
                (draft, record("skipped"), jid == "self-check"),
                (group, record("skipped"), jid in in_group),
                (push, record("success", {"skip": "true"}), False),
                (push, record("success", {"skip": "false"}), jid in in_group),
                (push, record("failure"), jid in in_group)]
        for github, needs, runs in rows:
            if ci_expr.job_runs(jobs[jid], github=github, needs=needs) is not runs:
                wrong.append(f"{jid} on {github['event_name']} {github['event']} "
                             f"with {needs['already-tested']}: expected runs={runs}")
        for github in (pr, group):
            if ci_expr.job_runs(jobs[jid], github=github, needs=record("skipped"),
                                cancelled=True):
                wrong.append(f"{jid} runs in a cancelled {github['event_name']} run")
    assert not wrong, "\n".join(wrong)
    for other in ("checks", "count", "fast-tests", "shard", "serial"):
        for result in ("failure", "cancelled", "skipped"):
            for github in (pr, group):
                assert ci_expr.job_runs(jobs["self-check"], github=github,
                                        needs=record("skipped", **{other: result})), (
                    other, result, github)


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
    edits too, and its group never cancels the suite. In a merge group,
    which has no text, the required check reports without a scan."""
    doc = _load("pr-text.yml")
    on = _on(doc)
    assert set(on) == {"pull_request", "merge_group"}, on
    assert on["pull_request"]["types"] == ["opened", "synchronize", "reopened", "edited"]
    assert on["merge_group"] == {"types": ["checks_requested"]}, on
    pr12 = {"event_name": "pull_request", "ref": "refs/pull/12/merge", "sha": "abc",
            "event": {"pull_request": {"number": 12}}}
    group = {"event_name": "merge_group", "sha": "mg1", "event": {"merge_group": {}}}
    cancel = doc["concurrency"]["cancel-in-progress"]
    assert ci_expr.truthy(ci_expr.evaluate(cancel, github=pr12))
    assert not ci_expr.truthy(ci_expr.evaluate(cancel, github=group))
    assert ci_expr.render(doc["concurrency"]["group"], github=group) == "pr-text-mg1"
    groups = {name: ci_expr.render(_load(name)["concurrency"]["group"], github=pr12)
              for name in ("pr-text.yml", "compass.yml", "docs.yml",
                           "claude-review.yml")}
    assert len(set(groups.values())) == 4, groups
    pr13 = dict(pr12, event={"pull_request": {"number": 13}})
    assert ci_expr.render(doc["concurrency"]["group"], github=pr13) != groups["pr-text.yml"]

    assert list(doc["jobs"]) == ["pr-text"]
    job = doc["jobs"]["pr-text"]
    assert "if" not in job, "a skipped job would hide the scan's absence"
    assert ('python3 scripts/rival-name-gate.py --github-event "$GITHUB_EVENT_PATH"'
            in _run_text(job))
    scan = _step_named(job, "No rival product name in the pull request title or body")
    note = _step_named(job, "A merge group has no title or body to scan")
    for github, scans in ((pr12, True), (group, False)):
        assert ci_expr.step_runs(scan, github=github, steps={}) is scans
        assert ci_expr.step_runs(note, github=github, steps={}) is not scans
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
    # 4 since 9.0.0 removed compass-run-demo.yml with `compass run` (ADR-090).
    assert len(files) >= 4, files
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
        expected = ({"already-tested": {"contents": "read", "actions": "read"},
                     "self-check": SELF_CHECK_GRANT}
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

SUITE_JOBS = ["checks", "count", "fast-tests", "shard", "serial", "check-mutation",
              "bdd-adapter", "bdd-adapter-behave",
              "bdd-adapter-cucumber-js", "bdd-adapter-godog", "atdd-adapter-python",
              "atdd-adapter-typescript"]
# The jobs a pull request runs. The others run only in a merge group or on a
# push to main.
PR_JOBS = ["checks", "count", "fast-tests"]

# (action, changes, the fast jobs run). A missing `changes` is what GitHub
# sends on every action but edited.
EDIT_ROWS = [
    ("opened", None, True),
    ("synchronize", None, True),
    ("reopened", None, True),
    ("edited", {"base": {"ref": {"from": "stack"}, "sha": {"from": "a" * 40}}}, True),
    ("edited", {"title": {"from": "old title"}}, False),
    ("edited", {"body": {"from": "old body"}}, False),
    ("ready_for_review", None, True),
]


def _pr_event(action, changes, number=12, draft=False):
    event = {"action": action, "pull_request": {"number": number, "draft": draft}}
    if changes is not None:
        event["changes"] = changes
    return {"event_name": "pull_request", "event": event, "sha": "abc"}


def _earlier_result_steps(job):
    return [s for s in job["steps"] if "ci-already-tested.py" in s.get("run", "")]


def test_crt_21_base_change_reruns_the_suite():
    """A base change runs the fast jobs again; a title or body edit runs only
    self-check, which reports the earlier result, and never cancels a run.
    A draft runs no test, and self-check says so."""
    doc = _load("compass.yml")
    jobs = doc["jobs"]
    assert set(SUITE_JOBS) | {"already-tested", "self-check"} == set(jobs), set(jobs)
    pr_needs = {"already-tested": {"result": "skipped", "outputs": {}}}
    wrong = []
    for action, changes, fast in EDIT_ROWS:
        for draft in (False, True):
            github = _pr_event(action, changes, draft=draft)
            for jid in SUITE_JOBS:
                runs = fast and not draft and jid in PR_JOBS
                if ci_expr.job_runs(jobs[jid], github=github, needs=pr_needs) is not runs:
                    wrong.append(f"{jid} on {action} {changes} draft={draft}: "
                                 f"expected runs={runs}")
    assert not wrong, "\n".join(wrong)

    self_check = jobs["self-check"]
    assert set(self_check["needs"]) == SELF_CHECK_NEEDS, self_check["needs"]
    by_name = {s.get("name"): s for s in self_check["steps"]}
    full, fast_step = by_name[FULL_STEP], by_name[FAST_STEP]
    draft_step = by_name["A draft runs no test"]
    downloads = [s for s in self_check["steps"]
                 if "download-artifact" in s.get("uses", "")]
    earlier = _earlier_result_steps(self_check)
    assert len(downloads) == 1 and len(earlier) == 1, self_check["steps"]
    deciding = [full, downloads[0], fast_step, draft_step, earlier[0]]
    for action, changes, fast in EDIT_ROWS:
        for draft in (False, True):
            github = _pr_event(action, changes, draft=draft)
            assert ci_expr.job_runs(self_check, github=github, needs=pr_needs), action
            expected = [False, False, fast and not draft, draft,
                        not fast and not draft]
            got = [ci_expr.step_runs(step, github=github, steps={}) for step in deciding]
            assert got == expected, (action, changes, draft, got)
    for event in ("merge_group", "push"):
        github = {"event_name": event, "event": {}}
        got = [ci_expr.step_runs(step, github=github, steps={}) for step in deciding]
        assert got == [True, True, False, False, False], (event, got)
    assert "--github-event" not in draft_step["run"] and "exit" not in draft_step["run"]

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
