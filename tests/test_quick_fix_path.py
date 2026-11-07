"""`compass quick-fix start` and `finish` on the four-stage path (ADR-092).

`start` serves every size:
it writes the path manifest and `acceptance-criteria.md` with the one scenario
and the intent, and no devlog. It takes the hotfix setting as `--urgency`.
`finish` works on any delivery issue on the path. It passes the three immovable
gates, as before, and refuses with exit 1 while other evidence is owed, with one
`next:` line for each owed item.

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
    GREET_CMD, NAMED, RELEASE_NOTE, _base_greeting, _git, _manifest, _run,
    _write_greeting, repo)

SLUG = "greet-path"
STANDARD = ["scenarios", "red-before-green", "suite-green", "correctness", "governance",
            "traceability", "regression", "security", "clarity", "outer-loop", "isolation",
            "layering", "definition-of-done", "ship-approval"]
INTENT = "A greeting says hello to the person it names."
SCENARIO = ("Given the greeting template, when it is read, then it says "
            "'Hello, %s!'.")
TEST_ID = "tests/test_greeting.py::test_greeting_says_hello"


def _start(root, slug=SLUG, size="atomic - one file, one obvious change", *extra):
    return _run(root, "quick-fix", "start", slug,
                "--risk", "trivial - a one-line text change",
                "--familiarity", "brownfield-mapped - the file and its test already exist",
                "--size", size, "--intent", INTENT, "--scenario", SCENARIO,
                "--test", TEST_ID, *extra)


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
    assert manifest["evidence_required"] == STANDARD
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
    # A change that owes the Definition of Done resolves its requirement rows:
    # start leaves each concern empty, and the next step names the file.
    for concern in CONCERNS:
        assert f"| {concern} | | |" in spec, concern
    rel = specs[0].relative_to(repo).as_posix()
    assert result.stdout.splitlines()[-1] == (
        f"next: fill the Non-functional requirements rows of {rel}: the scenario ids "
        "that cover each concern, or the reason it does not apply")
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
    assert result.stdout.splitlines()[-1] == (
        "next: compass tdd-red --loop outer --scenario TRC-001 -- <acceptance test command>")


def test_start_takes_the_hotfix_setting_as_urgency(repo):
    result = _start(repo, SLUG, "small - one file",
                    "--urgency", "live-defect - the greeting is wrong in production")
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = _manifest(repo, SLUG)
    assert manifest["assessment"]["urgency"] == "live-defect"
    assert manifest["justifications"]["urgency"] == "the greeting is wrong in production"
    assert "reproduce-first" in manifest["evidence_required"]


def test_the_preview_owes_what_the_write_stores_where_s17_applies(repo):
    # `governance/routing-policy.md` ("The path writer") says `approach evaluate
    # --assessment` without `--write` shows what a write stores. Under
    # `controlled`, where `S17` applies, that includes the strategy's tokens, its
    # block and the build and ship checkpoints of its stage 2 and 3 reviews.
    (repo / "compass.yml").write_text("schema: 1\nautonomy: controlled\n")
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

def test_finish_refuses_while_a_medium_change_owes_evidence(repo):
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    owed = _next_lines(finish)
    assert owed, finish.stdout
    for gate in ("verify.regression", "verify.security", "verify.clarity"):
        assert f"next: compass gate pass {gate} --evidence <EV-id>" in owed
    assert any(line.startswith("next: compass isolation record") for line in owed)
    assert ("next: compass layering record --test-path <layering test path> "
            "-- <layering test command>") in owed
    assert any(line.startswith("next: fill the Non-functional requirements rows")
               for line in owed)
    assert any("--meets dod-" in line for line in owed)
    # Nothing was written: no gate passed, no green, no commit.
    manifest = _manifest(repo, SLUG)
    assert all(g["status"] == "pending" for g in manifest["gates"])
    assert not [e for e in manifest.get("evidence") or [] if e.get("type") == "test-run"]
    assert _git(repo, "rev-parse", "HEAD") == head


def test_finish_json_names_the_owed_commands(repo):
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG, "-m", "Say hello",
                  *RELEASE_NOTE, *NAMED, "--json", *GREET_CMD)
    assert finish.returncode == 1
    doc = json.loads(finish.stdout)
    assert "compass gate pass verify.clarity --evidence <EV-id>" in doc["owed"]


def test_finish_refuses_until_the_outer_loop_red_then_ships(repo):
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo, SLUG, "--loop", "inner")

    refused = _finish(repo)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert _next_lines(refused) == [
        "next: compass tdd-red --loop outer --scenario TRC-001 "
        "-- <acceptance test command>"]

    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")
    shipped = _finish(repo)
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
    # Nothing is staged, and `compass ship-commit` lands what is staged, so the
    # line names the traced files to stage first.
    assert last.startswith("next: compass check, then git add -- "), last
    assert "data/greeting.txt" in last, last
    assert last.endswith(', then compass ship-commit -m "<message>"'), last


def test_the_finish_next_line_names_the_candidate_and_client_it_needs(repo):
    # A light-row change where `S17` applies records its green on the outer loop,
    # and `finish` refuses an outer-loop green with no candidate and client
    # (ADR-085). The `next:` line that sends the session to `finish` must name
    # both, so the command run as printed is not refused.
    import shlex
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    green = _run(repo, "tdd-green", "--issue", SLUG, "--loop", "outer",
                 "--scenario", "TRC-001", *NAMED, *GREET_CMD)
    assert green.returncode == 0, green.stdout + green.stderr
    line = _next_lines(green)[-1][len("next: "):]
    assert line.startswith("compass quick-fix finish "), line
    assert "--candidate <build id>|local" in line and "--client api|web|cli" in line, line

    filled = (line.replace('"<commit message>"', '"Say hello properly"')
              .replace("<build id>|local", "local").replace("api|web|cli", "cli")
              .replace("<test command>", " ".join(GREET_CMD[1:])))
    argv = shlex.split(filled)[1:]          # drop the leading `compass`
    finish = _run(repo, *argv[:2], "--issue", SLUG, *argv[2:])
    assert finish.returncode != 2, finish.stdout + finish.stderr
    assert finish.returncode == 0, finish.stdout + finish.stderr


# --- the whole path, by the `next:` lines alone --------------------------------------

LAYERING_TEST = "tests/test_layering.py"
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]


def _next_of(result):
    """The command of the `next:` line a verb printed last, or of `compass next`."""
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    last = lines[-1] if lines else ""
    if last.startswith("next: "):
        return last[len("next: "):]
    part = next((p for p in last.split(" | ") if p.startswith("next: ")), None)
    return part[len("next: "):] if part else None


def _step(root, command, done):
    """Run the command a `next:` line names, with the angle-bracket words filled in
    with real values. A line this does not know fails the test: the walk must not
    need a step no `next:` line named."""
    test = PYTEST + [TEST_ID]
    work = root / ".compass" / "work" / SLUG
    evidence = work / "evidence"
    if command.startswith("fill the Non-functional requirements rows of "):
        spec = root / command[len("fill the Non-functional requirements rows of "):].split(":")[0]
        text = re.sub(r"^\| (\w+) \| \| \|$", r"| \1 | | a greeting has no \1 effect |",
                      spec.read_text(), flags=re.M)
        spec.write_text(text)
        return _run(root, "next", "--issue", SLUG)
    if command.startswith("write the layering test at <layering test path> and git add it, "
                          "then "):
        # The line names the test to write and stage before the outer-loop red,
        # so the records bound to the tree after it do not go stale.
        (root / LAYERING_TEST).write_text("def test_layers_are_separate():\n"
                                          "    assert True\n")
        _git(root, "add", LAYERING_TEST)
        command = command.split(", then ", 1)[1]
    if command.startswith("compass tdd-red "):
        loop = ["--loop", "outer"] if "--loop outer" in command else []
        return _run(root, "tdd-red", "--issue", SLUG, *loop, "--scenario", "TRC-001",
                    "--", *test)
    if command.startswith("compass tdd-green --loop outer "):
        _write_greeting(root, "Hello, %s!")         # the fix, written after the red
        return _run(root, "tdd-green", "--issue", SLUG, "--loop", "outer",
                    "--scenario", "TRC-001", "--candidate", "local", "--client", "cli",
                    "--", *test)
    if command.startswith("compass isolation record "):
        named = re.search(r"--candidate (\S+) --client (\S+)", command)
        assert named and "<" not in named.group(1), command
        return _run(root, "isolation", "record", "--issue", SLUG,
                    "--candidate", named.group(1), "--client", named.group(2),
                    "--parallel", " ".join(PYTEST + ["tests"]),
                    "--repeat", " ".join(PYTEST) + " {tests}")
    if command.startswith("compass layering record "):
        return _run(root, "layering", "record", "--issue", SLUG,
                    "--test-path", LAYERING_TEST, "--", *PYTEST, LAYERING_TEST)
    if command.startswith("compass evidence add <EV-id> ") and "--meets " in command:
        item = command.split("--meets ", 1)[1].split()[0]
        evidence.mkdir(exist_ok=True)
        (evidence / "suite.txt").write_text("2 passed\n")
        done["dod"] += 1
        return _run(root, "evidence", "add", f"EV-DOD-{done['dod']}", "--issue", SLUG,
                    "--type", "command-output", "--path", "evidence/suite.txt",
                    "--meets", item)
    if command.startswith("compass gate pass "):
        gate = command.split()[3]
        if gate == "verify.regression":
            proof = next(e["id"] for e in _manifest(root, SLUG)["evidence"]
                         if e["type"] == "test-run")
        else:
            kind = {"verify.security": "security-review",
                    "verify.clarity": "manual-review"}[gate]
            proof = f"EV-{kind.upper()}"
            (evidence / f"{kind}.md").write_text(f"Reviewed for {gate}: no finding.\n")
            added = _run(root, "evidence", "add", proof, "--issue", SLUG, "--type", kind,
                         "--path", f"evidence/{kind}.md")
            assert added.returncode == 0, added.stdout + added.stderr
        return _run(root, "gate", "pass", gate, "--issue", SLUG, "--evidence", proof)
    if command.startswith("compass quick-fix finish "):
        # The person asked for the commit, so `--no-commit` is left out.
        done["finished"] = True
        return _run(root, "quick-fix", "finish", "--issue", SLUG, "-m", "Say hello properly",
                    *RELEASE_NOTE, "--", *test)
    raise AssertionError(f"no step is known for the next: line {command!r}")


def test_a_medium_change_reaches_the_commit_by_the_next_lines_alone(repo):
    _base_greeting(repo)
    head = _git(repo, "rev-parse", "HEAD")

    result = _start(repo, SLUG, "medium - several files and a design choice")
    done, walked = {"dod": 0, "finished": False}, []
    for _ in range(40):
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
    # The order the `next:` lines gave, one kind of step each.
    kinds = [c.split(" -- ")[0].split(" --")[0] for c in walked]
    assert kinds[0].startswith("fill the Non-functional requirements rows")
    assert kinds[1] == ("write the layering test at <layering test path> and git add it, "
                        "then compass tdd-red")
    assert [k for k in kinds if k.startswith("compass")][:4] == [
        "compass tdd-green", "compass isolation record",
        "compass layering record", "compass evidence add <EV-id>"]
    assert (repo / LAYERING_TEST).is_file()
    assert walked[-1].startswith("compass quick-fix finish")
