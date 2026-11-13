"""`compass quick-fix start` and `finish` on the four-stage path (ADR-092, ADR-099).

`start` serves every size:
it writes the path manifest and `acceptance-criteria.md` with the one scenario
and the intent, and no devlog. It takes the hotfix setting as `--urgency`.
`finish` works on any delivery issue on the path. It passes the three immovable
gates and, once a person has approved, commits. It refuses with exit 1 while
evidence a project setting adds is owed, with one `next:` line for each owed
item. The records of the four-layer acceptance strategy and the reviews are
owed only where the project's `compass.yml` adds them (`require_evidence`).

Issue: ayeo-io/compass-delivery#351 [Replace the approaches and eight stages
with one four-stage path].
"""
from __future__ import annotations

import json
import re
import sys

from compass_pkg.path_writer import NFR_REASON
from compass_pkg.section_checks import CONCERNS

from test_quick_fix_verbs import (  # noqa: F401  (`repo` is a fixture)
    GREET_CMD, NAMED, RELEASE_NOTE, _base_greeting, _git, _land, _manifest, _run,
    _write_greeting, e2e, repo)

SLUG = "greet-path"
#: What every change owes (ADR-099 decision 4), whatever its size.
COMMON = ["request", "scenarios", "red-before-green", "suite-green", "correctness",
          "governance", "traceability", "ship-approval"]
WRITE = ('write the tests and the code, then compass quick-fix finish -m '
         '"<commit message>" -- <test command>')
#: A project that asks for the old standard row, one `require_evidence` rule.
STANDARD_SETTING = (
    "require_evidence:\n"
    "  - when: {size: [medium, large, product]}\n"
    "    add: [regression, security, clarity, outer-loop, isolation, layering,\n"
    "          definition-of-done]\n")
INTENT = "A greeting says hello to the person it names."
SCENARIO = ("Given the greeting template, when it is read, then it says "
            "'Hello, %s!'.")
TEST_ID = "tests/test_greeting.py::test_greeting_says_hello"


#: Assess records who asked and the link to the request (#356).
REQUEST = ("--request", "https://example.com/requests/greet", "--requester", "Test fixture")


def _start(root, slug=SLUG, size="atomic - one file, one obvious change", *extra,
           request=True):
    return _run(root, "quick-fix", "start", slug,
                "--risk", "trivial - a one-line text change",
                "--familiarity", "brownfield-mapped - the file and its test already exist",
                "--size", size, "--intent", INTENT, "--scenario", SCENARIO,
                "--test", TEST_ID, *extra, *(REQUEST if request else ()))


def _red(root, slug=SLUG, *extra):
    red = _run(root, "tdd-red", "--issue", slug, "--scenario", "TRC-001", *extra,
               *GREET_CMD)
    assert red.returncode == 0, red.stdout + red.stderr
    return red


def _finish(root, slug=SLUG, *extra):
    return _run(root, "quick-fix", "finish", "--issue", slug, "-m", "Say hello properly",
                *RELEASE_NOTE, *NAMED, *extra, *GREET_CMD)


def _spec(root, slug=SLUG):
    specs = list((root / "docs" / "compass").glob(f"*-{slug}/acceptance-criteria.md"))
    assert len(specs) == 1, specs
    return specs[0]


def _next_lines(result):
    return [ln for ln in result.stdout.splitlines() if ln.startswith("next: ")]


# --- start ---------------------------------------------------------------------------

def test_start_records_a_medium_change_on_the_path(repo):
    result = _start(repo, SLUG, "medium - several files and a design choice")
    assert result.returncode == 0, result.stdout + result.stderr

    manifest = _manifest(repo, SLUG)
    assert manifest["delivery_approach"] == "delivery"
    assert manifest["evidence_required"] == COMMON
    assert "stages" not in manifest and "subtask_ceiling" not in manifest
    assert [s["id"] for s in manifest["scenarios"]] == ["TRC-001"]
    assert (repo / ".compass" / "current-task").read_text().strip() == SLUG

    # The acceptance criteria hold the intent and the one scenario; no devlog.
    work = repo / ".compass" / "work" / SLUG
    assert not (work / "devlog.md").exists()
    specs = list((repo / "docs" / "compass").glob(f"*-{SLUG}/acceptance-criteria.md"))
    assert len(specs) == 1, specs
    spec = specs[0].read_text()
    assert f"INT-1 | quick-fix start | {INTENT}" in spec
    assert "traceability id: TRC-001" in spec and "serves: INT-1" in spec
    assert "Given the greeting template" in spec
    assert "## Non-functional requirements" in spec
    assert "{{" not in spec
    # No Definition of Done is owed, so `start` resolves each requirement row
    # itself and the next step is to write the tests and the code.
    for concern in CONCERNS:
        assert f"| {concern} | | {NFR_REASON} |" in spec, concern
    assert result.stdout.splitlines()[-1] == f"next: {WRITE}"


def test_a_project_setting_leaves_the_requirement_rows_empty_for_a_medium_change(repo):
    """Where the project's `compass.yml` adds the Definition of Done, `start`
    leaves each concern empty. `finish` names the file when it is the turn of the
    rows (see the finish tests); the `next:` line of `start` is still to write."""
    (repo / "compass.yml").write_text(STANDARD_SETTING)
    result = _start(repo, SLUG, "medium - several files and a design choice")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "definition-of-done" in _manifest(repo, SLUG)["evidence_required"]
    spec = _spec(repo).read_text()
    for concern in CONCERNS:
        assert f"| {concern} | | |" in spec, concern
    # The setting adds the outer loop too, so the line names the loop and the
    # candidate and client an outer-loop green needs (ADR-085).
    assert result.stdout.splitlines()[-1] == "next: " + WRITE.replace(
        " -- ", " --loop outer --candidate <build id>|local --client api|web|cli -- ")
    checked = _run(repo, "check", "--issue", SLUG, "--verbose")
    assert checked.returncode != 0
    assert '"performance" has neither a scenario nor a reason' in checked.stdout


def test_start_resolves_the_requirement_rows_of_a_small_change(repo):
    result = _start(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "definition-of-done" not in _manifest(repo, SLUG)["evidence_required"]
    spec = _spec(repo).read_text()
    for concern in CONCERNS:
        assert f"| {concern} | | {NFR_REASON} |" in spec, concern
    assert result.stdout.splitlines()[-1] == f"next: {WRITE}"


def test_start_takes_the_hotfix_setting_as_urgency(repo):
    result = _start(repo, SLUG, "small - one file",
                    "--urgency", "live-defect - the greeting is wrong in production")
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = _manifest(repo, SLUG)
    assert manifest["assessment"]["urgency"] == "live-defect"
    assert manifest["justifications"]["urgency"] == "the greeting is wrong in production"
    # Urgency adds no record by default (ADR-099 decision 9).
    assert "reproduce-first" not in manifest["evidence_required"]


def test_a_project_setting_owes_the_reproduction_for_a_live_defect(repo):
    (repo / "compass.yml").write_text(
        "require_evidence:\n  - when: {urgency: live-defect}\n    add: [reproduce-first]\n")
    result = _start(repo, SLUG, "small - one file",
                    "--urgency", "live-defect - the greeting is wrong in production")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "reproduce-first" in _manifest(repo, SLUG)["evidence_required"]


def test_the_preview_owes_what_the_write_stores_where_s17_applies(repo):
    # `governance/routing-policy.md` ("The path writer") says `approach evaluate
    # --assessment` without `--write` shows what a write stores. Under
    # `controlled`, where a setting adds the tokens of `S17`, that includes the
    # strategy's tokens, its block and the build and ship checkpoints of its
    # stage 2 and 3 reviews.
    (repo / "compass.yml").write_text("schema: 1\nautonomy: controlled\n" + STANDARD_SETTING)
    medium = "medium - several files and a design choice"
    preview = _run(repo, "approach", "evaluate", "--json",
                   "--assessment", "risk=trivial",
                   "--assessment", "familiarity=brownfield-mapped",
                   "--assessment", "size=medium")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    shown = json.loads(preview.stdout)
    assert _start(repo, SLUG, medium).returncode == 0
    stored = _manifest(repo, SLUG)
    assert "outer-loop" in stored["evidence_required"]
    assert stored["checkpoints"] == ["assess", "specify", "build", "ship"]
    for key in ("evidence_required", "checkpoints", "acceptance_strategy"):
        assert shown[key] == stored[key], (key, shown[key], stored[key])
    assert shown["gates"] == [g["id"] for g in stored["gates"]]


def test_start_refuses_a_spike_and_says_why(repo):
    # A spike is not lighter or heavier than the path: it ships nothing, so the
    # refusal gives that reason. "computes to" is the phrase contract 4 pins.
    result = _start(repo, SLUG, "small - one file",
                    "--goal", "exploration - we do not know yet what to build")
    out = result.stdout + result.stderr
    assert result.returncode == 1, out
    assert "computes to spike, which cannot start as a quick fix" in out
    assert "a spike explores and ships nothing" in out
    assert "heavier" not in out
    assert "/compass:assess" in out


def test_start_refuses_an_urgency_with_no_reason(repo):
    result = _start(repo, SLUG, "small - one file", "--urgency", "live-defect")
    assert result.returncode != 0
    assert "--urgency needs a reason" in result.stdout + result.stderr
    assert not (repo / ".compass" / "work" / SLUG).exists()


# --- finish --------------------------------------------------------------------------

REVIEWS_SETTING = ("require_evidence:\n  - when: {}\n"
                   "    add: [regression, security, clarity]\n")


def test_finish_refuses_while_a_project_setting_owes_the_reviews(repo):
    (repo / "compass.yml").write_text(REVIEWS_SETTING)
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG)
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    assert "owes 3 item(s) that the project's settings add" in finish.stdout, finish.stdout
    owed = _next_lines(finish)
    for gate in ("verify.regression", "verify.security", "verify.clarity"):
        assert f"next: compass gate pass {gate} --evidence <EV-id>" in owed
    # The three gates `finish` owns passed, the added ones did not, and nothing
    # was committed.
    status = {g["id"]: g["status"] for g in _manifest(repo, SLUG)["gates"]}
    assert status["verify.correctness"] == "pass"
    assert all(status[g] == "pending" for g in
               ("verify.regression", "verify.security", "verify.clarity"))
    assert _git(repo, "rev-parse", "HEAD") == head


def test_finish_refuses_while_the_s17_and_definition_of_done_records_are_owed(repo):
    (repo / "compass.yml").write_text(STANDARD_SETTING)
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    assert "`compass check` fails" in finish.stdout, finish.stdout
    assert "FAIL nfr-rows-resolved" in finish.stdout, finish.stdout
    assert _next_lines(finish) == [
        "next: fix what the lines above name, then run the same finish again"]
    assert _git(repo, "rev-parse", "HEAD") == head


def test_finish_json_names_the_owed_commands(repo):
    (repo / "compass.yml").write_text(REVIEWS_SETTING)
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG)
    _write_greeting(repo, "Hello, %s!")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG, "-m", "Say hello",
                  *RELEASE_NOTE, "--json", *GREET_CMD)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    doc = json.loads(finish.stdout)
    assert "compass gate pass verify.clarity --evidence <EV-id>" in doc["owed"]


def test_finish_with_the_outer_loop_added_waits_for_the_approval_then_commits(repo):
    """Where the project's settings add the outer loop, the green is recorded on
    the outer loop, and `finish` commits once a person has approved."""
    (repo / "compass.yml").write_text(
        "require_evidence:\n  - when: {}\n    add: [outer-loop]\n")
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")

    first = _finish(repo, SLUG, "--loop", "outer")
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Nothing is committed" in first.stdout
    assert _git(repo, "rev-parse", "HEAD") == head
    shipped = _land(repo, SLUG, "--loop", "outer")
    assert shipped.returncode == 0, shipped.stdout + shipped.stderr
    assert _git(repo, "rev-parse", "HEAD") != head

    manifest = _manifest(repo, SLUG)
    assert manifest["status"] == "done"
    assert {g["id"]: g["status"] for g in manifest["gates"]} == {
        "verify.correctness": "pass", "verify.governance": "pass",
        "verify.traceability": "pass"}
    assert not (repo / ".compass" / "work" / SLUG / "devlog.md").exists()
    # The issue is closed, so no command comes next.
    assert not _next_lines(shipped)


def test_finish_no_commit_ends_with_the_next_command(repo):
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo)
    _write_greeting(repo, "Hello, %s!")
    finish = _finish(repo, SLUG, "--no-commit")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    last = finish.stdout.splitlines()[-1]
    # Nothing is committed and the ship approval is still owed, so the line asks
    # for the approval first (ADR-099).
    assert last.startswith("next: stop and ask the person to type /compass:approve 1"), last


def test_finish_no_commit_after_the_approval_names_ship_commit(repo):
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo)
    _write_greeting(repo, "Hello, %s!")
    assert _finish(repo, SLUG, "--no-commit").returncode == 0
    assert e2e.person_approves(repo)
    finish = _finish(repo, SLUG, "--no-commit")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert finish.stdout.splitlines()[-1] == (
        "next: when the person asks for a commit, run compass ship-commit")


def _next_of(result):
    """The command of the `next:` line a verb printed last, or of `compass next`."""
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if last.startswith("next: "):
        return last[len("next: "):]
    part = next((p for p in last.split(" | ") if p.startswith("next: ")), None)
    return part[len("next: "):] if part else None


def test_the_finish_next_line_names_the_candidate_and_client_it_needs(repo):
    # Where a project setting adds the outer loop, `S17` applies and `finish`
    # refuses an outer-loop green with no candidate and client (ADR-085). The
    # `next:` line that sends the session to `finish` must name the loop, the
    # candidate and the client, so the command run as printed is not refused.
    import shlex
    (repo / "compass.yml").write_text(
        "require_evidence:\n  - when: {}\n    add: [outer-loop]\n")
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    line = _next_of(_run(repo, "next", "--issue", SLUG))
    assert line.startswith("write the tests and the code, then compass quick-fix finish "), line
    assert "--loop outer" in line, line
    assert "--candidate <build id>|local" in line and "--client api|web|cli" in line, line

    filled = (line.split(", then ", 1)[1].replace('"<commit message>"', '"Say hello properly"')
              .replace("<build id>|local", "local").replace("api|web|cli", "cli")
              .replace("<test command>", " ".join(GREET_CMD[1:])))
    argv = shlex.split(filled)[1:]          # drop the leading `compass`
    finish = _run(repo, *argv[:2], "--issue", SLUG, *argv[2:])
    assert finish.returncode != 2, finish.stdout + finish.stderr
    assert finish.returncode == 0, finish.stdout + finish.stderr


# --- the whole path, by the `next:` lines alone --------------------------------------

def _step(root, command, done):
    """Run the command a `next:` line names, with the angle-bracket words filled in
    with real values. A line this does not know fails the test: the walk must not
    need a step no `next:` line named."""
    test = GREET_CMD[1:]
    if command.startswith("compass issue link set ") and "--request <url>" in command:
        linked = _run(root, "issue", "link", "set", "--issue", SLUG, *REQUEST)
        assert linked.returncode == 0, linked.stdout + linked.stderr
        return _run(root, "next", "--issue", SLUG)
    if command.startswith("write the tests and the code, then compass quick-fix finish "):
        _write_greeting(root, "Hello, %s!")         # the fix; the test is committed
        return _run(root, "quick-fix", "finish", "--issue", SLUG, "-m", "Say hello properly",
                    *RELEASE_NOTE, "--", *test)
    if command.startswith("stop and ask the person to type /compass:approve "):
        # The person answers in the terminal, then the same finish runs again.
        assert e2e.person_approves(root)
        done["finished"] = True
        return _run(root, "quick-fix", "finish", "--issue", SLUG, "-m", "Say hello properly",
                    *RELEASE_NOTE, "--", *test)
    raise AssertionError(f"no step is known for the next: line {command!r}")


def test_a_medium_change_reaches_the_commit_by_the_next_lines_alone(repo):
    _base_greeting(repo)
    head = _git(repo, "rev-parse", "HEAD")

    # Started with no request, so the first next: line asks for it (#356).
    result = _start(repo, SLUG, "medium - several files and a design choice", request=False)
    done, walked = {"finished": False}, []
    for _ in range(10):
        assert result.returncode == 0, (walked, result.stdout + result.stderr)
        if done["finished"]:
            break
        command = _next_of(result)
        assert command, (walked, result.stdout)
        walked.append(command)
        result = _step(repo, command, done)
    else:
        raise AssertionError(f"the walk did not end: {walked}")

    manifest = _manifest(repo, SLUG)
    assert manifest["status"] == "done", walked
    assert _git(repo, "rev-parse", "HEAD") != head
    assert all(g["status"] == "pass" for g in manifest["gates"])
    # The order the `next:` lines gave: the request, the work and `finish`, then the
    # person's approval, after which the same `finish` commits.
    kinds = [c.split(" -- ")[0].split(" --")[0] for c in walked]
    assert kinds[0] == "compass issue link set"
    assert kinds[1].startswith("write the tests and the code, then compass quick-fix finish")
    assert kinds[2].startswith("stop and ask the person to type /compass:approve")
    assert len(kinds) == 3, walked
    assert result.stdout.splitlines()[-1].startswith("done: nothing more to run")
