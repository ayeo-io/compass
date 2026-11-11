"""A change takes two commands and Compass keeps the record (ADR-099).

`compass quick-fix start` opens the issue and `compass quick-fix finish`
writes the record: the scenarios, the changed files from git, the red on a
copy of the base commit, the green, the check and the approval requests. These
tests play the agent and the person with no model. The person answers a
request as a person at a terminal does, on a pseudo-terminal, with the helper
of `scripts/two-command-e2e.py`.

Decision record:
`architecture/decisions/ADR-099-compass-keeps-the-record-itself-and-a-change-takes-two-commands.md`.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "two_command_e2e", ROOT / "scripts" / "two-command-e2e.py")
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import approval_records, lean, ship_approval  # noqa: E402
from compass_pkg.checks import _check_human_approval  # noqa: E402

PYTEST = [sys.executable, "-m", "pytest", "-q"]
REQUEST = "https://github.com/acme/shop/issues/7"
MESSAGE = "Add a percentage discount to the total (#7)"
#: The most lines one `finish` may print. Each line is context the session
#: pays for on every later call.
FINISH_LINES = 8


def compass(repo, *args, env=None):
    return subprocess.run([e2e.COMPASS, *args], cwd=repo, env=dict(e2e.ENV, **(env or {})),
                          capture_output=True, text=True)


def start(repo, slug="discount", *extra):
    done = compass(repo, "quick-fix", "start", slug,
                   "--intent", "An order total can take a percentage discount",
                   "--request", REQUEST, "--requester", "Sam Taylor", *extra)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def finish(repo, message=MESSAGE, *extra):
    return compass(repo, "quick-fix", "finish", "-m", message, *extra, "--", *PYTEST)


def manifest(repo, slug="discount"):
    return yaml.safe_load(
        (repo / ".compass" / "work" / slug / "manifest.yml").read_text(encoding="utf-8"))


def check(repo, slug="discount"):
    done = compass(repo, "check", "--issue", slug)
    failed = [line.split()[1].rstrip(":") for line in done.stdout.splitlines()
              if line.startswith("FAIL ") and not line.startswith("FAIL - ")]
    return done.returncode, failed


def head(repo):
    return e2e.sh(["git", "rev-parse", "HEAD"], repo).stdout.strip()


def change_again(repo, number=10):
    """A round of feedback: the code and the same test file change."""
    with (repo / "shop" / "orders.py").open("a") as fh:
        fh.write(f"\n\ndef discounted_{number}(prices):\n"
                 f"    return discounted(prices, {number})\n")
    with (repo / "tests" / "test_discount.py").open("a") as fh:
        fh.write(f"\n\ndef test_round_{number}():\n"
                 f"    from shop.orders import discounted_{number}\n"
                 f"    assert discounted_{number}([100]) == {100 - number}\n")


@pytest.fixture
def repo(tmp_path):
    return e2e.make_repo(tmp_path)


@pytest.fixture
def approved(repo):
    """A change with its first approval, committed by the second `finish`."""
    start(repo)
    e2e.write_discount(repo)
    assert finish(repo).returncode == 0
    assert e2e.person_approves(repo) == [1]
    done = finish(repo)
    assert "checked and committed" in done.stdout, done.stdout + done.stderr
    return repo


# --- the red on a copy of the base commit (decision 2) ------------------------------------

def test_finish_proves_the_red_on_the_base_copy_and_the_green_on_the_tree(repo):
    start(repo)
    base = head(repo)
    e2e.write_discount(repo)
    done = finish(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    assert f"the tests fail on the base commit {base[:8]}" in done.stdout
    assert "the tests pass on the working tree" in done.stdout
    evidence = repo / ".compass" / "work" / "discount" / "evidence"
    red = json.loads((evidence / "red-TRC-001.json").read_text(encoding="utf-8"))
    green = json.loads((evidence / "green-TRC-001.json").read_text(encoding="utf-8"))
    assert red["proved_on"] == "base-copy" and red["base_commit"] == base
    assert red["passed"] is False and red["exit_code"] != 0
    assert red["test_files"] == ["tests/test_discount.py"]
    assert green["passed"] is True and red["timestamp"] < green["timestamp"]
    assert check(repo) == (0, [])


def test_finish_refuses_a_test_that_passes_on_the_base_commit(repo):
    """A test that does not need the change proves nothing; the refusal names
    the likely causes in one line."""
    start(repo)
    with (repo / "shop" / "orders.py").open("a") as fh:
        fh.write("\n\ndef discounted(prices, percent):\n    return 0\n")
    (repo / "tests" / "test_discount.py").write_text(
        "from shop.orders import total\n\n\ndef test_total_again():\n"
        "    assert total([1]) == 1\n")
    done = finish(repo)
    assert done.returncode == 1
    lines = done.stdout.splitlines()
    assert len(lines) == 2, done.stdout
    assert "the tests pass on the base commit without the change" in lines[0]
    assert "does not exercise the change" in lines[0]
    assert "editable install" in lines[0] and "docs/base-copy.md" in lines[0]
    assert lines[1].startswith("next: ")
    assert not (repo / ".compass" / "work" / "discount" / "evidence" / "red-TRC-001.json").exists()


def test_a_change_with_no_test_file_is_refused(repo):
    start(repo)
    with (repo / "shop" / "orders.py").open("a") as fh:
        fh.write("\n\ndef discounted(prices, percent):\n    return 0\n")
    done = finish(repo)
    assert done.returncode == 1
    assert "the change holds no test file" in done.stdout


def test_the_base_copy_links_the_paths_the_project_names(repo):
    """`project.base_copy_links` names untracked paths the tests need. Without
    the link the base copy lacks the file, so the test cannot tell a missing
    build from a missing change."""
    (repo / "compass.yml").write_text(
        f"owner: {e2e.APPROVER}\nproject:\n  base_copy_links: [build]\n")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\nbuild/\n")
    e2e.sh(["git", "commit", "-qam", "Name the build output"], repo)
    (repo / "build").mkdir()
    (repo / "build" / "rates.txt").write_text("10\n")
    start(repo)
    e2e.write_discount(repo)
    (repo / "tests" / "test_discount.py").write_text(
        "import pathlib\n\nfrom shop import orders\n\n\n"
        "def test_the_built_rate_is_applied():\n"
        "    rate = int(pathlib.Path('build/rates.txt').read_text())\n"
        "    assert orders.discounted([100], rate) == 90\n")
    done = finish(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    red = json.loads((repo / ".compass" / "work" / "discount" / "evidence"
                      / "red-TRC-001.json").read_text(encoding="utf-8"))
    # The red is the missing function, not the missing build file.
    assert "FileNotFoundError" not in red["log_excerpt"], red["log_excerpt"]
    assert "discounted" in red["log_excerpt"]


@pytest.mark.parametrize("value, said", [
    ("../outside", "not a path inside the project"),
    ("/etc", "not a path inside the project"),
])
def test_a_base_copy_link_outside_the_project_is_refused(tmp_path, value, said):
    (tmp_path / "compass.yml").write_text(f"project:\n  base_copy_links: ['{value}']\n")
    with pytest.raises(Exception) as caught:
        lean.base_copy_links(str(tmp_path))
    assert said in str(caught.value)


def test_no_setting_links_nothing_more(tmp_path):
    assert lean.base_copy_links(str(tmp_path)) == ()


# --- the changed files come from git (decision 3) -----------------------------------------

def test_finish_reads_the_changed_files_from_git_without_run_output(repo):
    start(repo)
    e2e.write_discount(repo)
    for leftover in (".coverage", "coverage.xml", "htmlcov/index.html"):
        path = repo / leftover
        path.parent.mkdir(exist_ok=True)
        path.write_text("run data\n")
    assert finish(repo).returncode == 0
    held = manifest(repo)
    assert sorted(f["path"] for f in held["changed_files"] if not f["path"].startswith(
        "docs/compass/")) == ["shop/orders.py", "tests/test_discount.py"]
    assert all(f["scenarios"] == ["TRC-001"] for f in held["changed_files"])
    assert held["scenarios"][0]["tests"] == ["tests/test_discount.py"]


def test_a_path_changed_before_start_is_left_out_and_named(repo):
    (repo / "notes.txt").write_text("a local note\n")
    start(repo)
    e2e.write_discount(repo)
    done = finish(repo)
    assert done.returncode == 0, done.stdout
    assert "left out : notes.txt" in done.stdout
    assert "notes.txt" not in [f["path"] for f in manifest(repo)["changed_files"]]


def test_the_change_digest_names_the_files_and_not_the_run(repo):
    """Decision 6: the digest covers the code and test files of the change. A
    test run, the record and a second `finish` do not move it; an edit does."""
    start(repo)
    e2e.write_discount(repo)
    assert finish(repo).returncode == 0
    first = manifest(repo)[approval_records.CHANGE_KEY]
    assert first == lean.change_digest(str(repo), ["shop/orders.py", "tests/test_discount.py"])
    (repo / ".coverage").write_text("run data\n")
    assert finish(repo).returncode == 0
    assert manifest(repo)[approval_records.CHANGE_KEY] == first
    change_again(repo)
    assert finish(repo).returncode == 0
    assert manifest(repo)[approval_records.CHANGE_KEY] != first


def test_the_digest_of_no_file_is_the_no_change_digest(tmp_path):
    assert lean.change_digest(str(tmp_path), []) == approval_records.NO_CHANGE
    (tmp_path / "a.py").write_text("x = 1\n")
    with_file = lean.change_digest(str(tmp_path), ["a.py"])
    assert with_file != approval_records.NO_CHANGE
    assert lean.change_digest(str(tmp_path), ["a.py", "gone.py"]) != with_file


# --- one request is one issue (decision 8) ------------------------------------------------

def test_a_second_start_for_the_same_request_makes_no_issue(approved):
    repo = approved
    done = compass(repo, "quick-fix", "start", "discount-follow-up",
                   "--intent", "A fixed discount", "--request", "acme/shop#7")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "this request already has the issue 'discount'" in done.stdout
    assert "No new issue was made" in done.stdout
    assert sorted(p.name for p in (repo / ".compass" / "work").iterdir() if p.is_dir()) \
        == ["discount"]
    assert (repo / ".compass" / "current-task").read_text().strip() == "discount"


# --- finish commits after the approval and not before (decision 7) ------------------------

def test_finish_commits_after_the_first_approval_and_not_before(repo):
    start(repo)
    base = head(repo)
    e2e.write_discount(repo)
    first = finish(repo)
    assert first.returncode == 0
    assert "Nothing is committed" in first.stdout and head(repo) == base
    assert first.stdout.splitlines()[-1].startswith(
        "next: stop and ask the person to type /compass:approve 1 (the ship approval).")
    # The same finish with no approval asks again and still commits nothing.
    again = finish(repo)
    assert "/compass:approve 1 (the ship approval)" in again.stdout and head(repo) == base
    assert e2e.person_approves(repo) == [1]
    done = finish(repo)
    assert "checked and committed" in done.stdout, done.stdout
    assert done.stdout.splitlines()[-1].startswith("done: nothing more to run")
    assert head(repo) != base
    # On the default branch, finish makes a branch named after the issue first.
    assert e2e.sh(["git", "symbolic-ref", "--short", "HEAD"], repo).stdout.strip() == "discount"
    assert e2e.sh(["git", "rev-parse", "main"], repo).stdout.strip() == base
    assert check(repo) == (0, [])


def test_finish_prints_few_lines(repo):
    start(repo)
    e2e.write_discount(repo)
    outputs = [finish(repo).stdout]
    e2e.person_approves(repo)
    outputs.append(finish(repo).stdout)
    change_again(repo)
    outputs.append(finish(repo).stdout)
    for out in outputs:
        assert len(out.strip().splitlines()) <= FINISH_LINES, out


# --- an approval covers the change the person saw (decision 6) ----------------------------

def test_the_approval_records_the_digest_of_the_change(approved):
    held = manifest(approved)
    record = next(e for e in held["evidence"] if e.get("ship") == "discount")
    assert record[approval_records.CHANGE_KEY] == held[approval_records.CHANGE_KEY]


def test_a_change_after_the_approval_is_committed_and_asks_for_a_new_approval(approved):
    """The feedback round is one command: `finish` proves the red again,
    commits on the branch, asks for the new approval and says nothing else is
    to run. `compass check` fails on the ship approval until a person gives it."""
    repo = approved
    before = head(repo)
    change_again(repo)
    done = finish(repo, "Add a fixed ten percent discount (#7)")
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert "checked and committed" in lines[0]
    assert any("the tests fail on the base commit" in line for line in lines)
    assert lines[-1] == ("next: stop: the change differs from the one approved. Ask the person "
                         "to type /compass:approve 2 (the ship approval). Nothing else to run "
                         "now.")
    assert head(repo) != before
    assert e2e.sh(["git", "log", "-1", "--format=%s"], repo).stdout.strip() \
        == "Add a fixed ten percent discount (#7)"
    code, failed = check(repo)
    assert code != 0 and failed == ["ship-approval-present"]
    out = compass(repo, "check", "--issue", "discount").stdout
    assert "was given for an earlier state of the change" in out
    # `compass next` says the same, and names no command to run.
    assert "Nothing else to run now" in compass(repo, "next").stdout
    # The first request closed as replaced; the new one names the new state.
    pending = sorted((repo / ".compass" / "work" / "discount" / "approval-requests"
                      / "pending").glob("*.yml"))
    assert [p.name for p in pending] == ["2.yml"]
    request = yaml.safe_load(pending[0].read_text(encoding="utf-8"))
    assert request[approval_records.CHANGE_KEY] == manifest(repo)[approval_records.CHANGE_KEY]

    assert e2e.person_approves(repo) == [2]
    assert check(repo) == (0, [])
    ships = [e for e in manifest(repo)["evidence"] if e.get("ship") == "discount"]
    # The earlier approval stays on record, as given.
    assert [e["id"] for e in ships] == ["EV-SHIP-APPROVAL-1", "EV-SHIP-APPROVAL-2"]
    assert ships[0]["decision"] == ships[1]["decision"] == "approved"
    assert ships[0][approval_records.CHANGE_KEY] != ships[1][approval_records.CHANGE_KEY]
    # A finish on the approved state asks for nothing.
    last = finish(repo, "Add a fixed ten percent discount (#7)")
    assert last.stdout.splitlines()[-1].startswith("done: nothing more to run"), last.stdout


def test_an_approval_before_the_first_finish_covers_no_code(repo):
    start(repo)
    assert compass(repo, "evidence", "request", "--ship").returncode == 0
    assert e2e.person_approves(repo) == [1]
    record = next(e for e in manifest(repo)["evidence"] if e.get("ship") == "discount")
    assert record[approval_records.CHANGE_KEY] == approval_records.NO_CHANGE
    e2e.write_discount(repo)
    done = finish(repo)
    assert "Nothing is committed" in done.stdout, done.stdout
    assert "/compass:approve 2 (the ship approval)" in done.stdout, done.stdout


def _task(change, *evidence, **more):
    task = {"issue": "discount", "generation": 1, "status": "in-progress",
            "evidence_required": ["ship-approval", "human-approval"],
            "evidence": list(evidence)}
    if change:
        task[approval_records.CHANGE_KEY] = change
    task.update(more)
    return task


def _ship(change=None, number=1):
    record = {"id": f"EV-SHIP-APPROVAL-{number}", "type": "human-approval", "ship": "discount",
              "approver": "Sam", "role": "owner", "scope": "the change", "decision": "approved",
              "timestamp": "2026-11-10T10:00:00Z", "issue": "discount", "generation": 1}
    if change:
        record[approval_records.CHANGE_KEY] = change
    return record


def _g5(change=None, number=1):
    record = {"id": f"EV-APPROVAL-G5-{number}", "type": "human-approval", "guardrail": "G5",
              "approver": "Sam", "role": "owner", "scope": "the change", "decision": "approved",
              "timestamp": "2026-11-10T10:00:00Z", "issue": "discount", "generation": 1}
    if change:
        record[approval_records.CHANGE_KEY] = change
    return record


TASK_DIR = "/nowhere/.compass/work/discount"


def test_the_ship_approval_check_reads_the_digests():
    verdict = ship_approval._check_ship_approval_present
    assert verdict(_task("b" * 64, _ship("b" * 64)), TASK_DIR)[0] is True
    passed, detail = verdict(_task("b" * 64, _ship("a" * 64)), TASK_DIR)
    assert passed is False
    assert "EV-SHIP-APPROVAL-1 was given for an earlier state of the change" in detail
    assert "/compass:approve" in detail
    # A later approval of the state as it is passes.
    assert verdict(_task("b" * 64, _ship("a" * 64), _ship("b" * 64, 2)), TASK_DIR)[0] is True


def test_an_approval_with_no_digest_keeps_its_old_meaning():
    """A record from before the digest, and a manifest with none, are not
    compared: no existing record changes its result."""
    verdict = ship_approval._check_ship_approval_present
    assert verdict(_task("b" * 64, _ship()), TASK_DIR)[0] is True
    assert verdict(_task(None, _ship("a" * 64)), TASK_DIR)[0] is True
    assert _check_human_approval(_task("b" * 64, _g5()), TASK_DIR)[0] is True
    assert _check_human_approval(_task(None, _g5("a" * 64)), TASK_DIR)[0] is True


def test_the_approving_review_of_the_pull_request_covers_the_new_state():
    """ADR-095: the review is read from the merged pull request, after the
    change stopped moving, so it passes where the typed approval is for an
    earlier state."""
    review = {"id": "EV-PR-APPROVAL-1", "type": "pr-approval", "approver": "sam",
              "decision": "approved", "timestamp": "2026-11-10T11:00:00Z",
              "pull_request": {"repo": "acme/shop", "number": 8}}
    task = _task("b" * 64, _ship("a" * 64), review,
                 pull_request={"repo": "acme/shop", "number": 8,
                               "merged_at": "2026-11-10T12:00:00Z"})
    passed, detail = ship_approval._check_ship_approval_present(task, TASK_DIR)
    assert passed is True and "approved pull request acme/shop#8" in detail


@pytest.mark.parametrize("status", ["in-progress", "landed"])
def test_the_g5_check_fails_on_a_sign_off_of_an_earlier_state(status):
    task = _task("b" * 64, _g5("a" * 64), status=status)
    passed, detail = _check_human_approval(task, TASK_DIR)
    assert passed is False
    assert "EV-APPROVAL-G5-1 was given for an earlier state of the change" in detail
    task["evidence"].append(_g5("b" * 64, 2))
    assert _check_human_approval(task, TASK_DIR)[0] is True


def test_a_labeled_change_asks_for_both_approvals_again(repo):
    start(repo, "forget-user", "--labels", "personal-data")
    assert compass(repo, "evidence", "request", "--checkpoint", "specify").returncode == 0
    assert e2e.person_approves(repo) == [1]
    e2e.write_forget_user(repo)
    message = "Let a user be forgotten (#7)"
    first = finish(repo, message)
    assert "/compass:approve 2 (the `G5` sign-off) and /compass:approve 3 (the ship approval)" \
        in first.stdout, first.stdout
    assert "Nothing is committed" in first.stdout
    assert e2e.person_approves(repo) == [2, 3]
    assert "checked and committed" in finish(repo, message).stdout
    with (repo / "shop" / "users.py").open("a") as fh:
        fh.write("\n\ndef forget_all():\n    USERS.clear()\n")
    with (repo / "tests" / "test_forget_user.py").open("a") as fh:
        fh.write("\n\ndef test_forget_all_leaves_no_row():\n"
                 "    users.add_user('bo', 'bo@example.com')\n"
                 "    users.forget_all()\n    assert users.USERS == {}\n")
    done = finish(repo, message)
    assert done.stdout.splitlines()[-1] == (
        "next: stop: the change differs from the one approved. Ask the person to type "
        "/compass:approve 4 (the `G5` sign-off) and /compass:approve 5 (the ship approval). "
        "Nothing else to run now.")
    assert check(repo, "forget-user")[1] == ["human-approval-present", "ship-approval-present"]
    assert e2e.person_approves(repo) == [4, 5]
    assert check(repo, "forget-user") == (0, [])


# --- a person's approval before code (decision 5) -----------------------------------------

@pytest.mark.parametrize("settings, extra", [
    ("", ("--labels", "personal-data")),
    ("", ("--risk", "critical - it moves money")),
    ("signoff_labels: [billing]\n", ("--labels", "billing")),
])
def test_the_hook_refuses_code_until_a_person_approves_the_scenarios(repo, settings, extra):
    (repo / "compass.yml").write_text(f"owner: {e2e.APPROVER}\n{settings}")
    out = start(repo, "discount", *extra)
    held = manifest(repo)
    assert "scenario-approval" in held["evidence_required"]
    assert held["checkpoints"] == ["specify"]
    assert "scenarios: docs/compass/" in out
    assert "next: write the scenarios in acceptance-criteria.md" in out
    code, why = e2e.hook_verdict(repo, "shop/orders.py")
    assert code == 2 and "need a person's approval before code" in why, why
    # Finish refuses too, and writes no record.
    e2e.write_discount(repo)
    refused = finish(repo)
    assert refused.returncode == 1
    assert "a person has not approved its scenarios" in refused.stdout
    assert compass(repo, "evidence", "request", "--checkpoint", "specify").returncode == 0
    assert e2e.hook_verdict(repo, "shop/orders.py")[0] == 2
    assert e2e.person_approves(repo) == [1]
    assert e2e.hook_verdict(repo, "shop/orders.py")[0] == 0
    assert finish(repo).returncode == 0


def test_critical_risk_owes_the_scenario_approval_and_no_sign_off(repo):
    start(repo, "discount", "--risk", "critical - it moves money")
    owed = manifest(repo)["evidence_required"]
    assert "scenario-approval" in owed and "human-approval" not in owed


def test_an_ordinary_change_edits_code_with_no_red_and_no_approval(repo):
    start(repo)
    assert manifest(repo)["evidence_required"] == [
        "request", "scenarios", "red-before-green", "suite-green", "correctness",
        "governance", "traceability", "ship-approval"]
    assert e2e.hook_verdict(repo, "shop/orders.py")[0] == 0


def test_a_project_setting_adds_evidence_on_top_of_the_common_set(repo):
    (repo / "compass.yml").write_text(
        f"owner: {e2e.APPROVER}\nrequire_evidence:\n"
        "  - when: {risk: [cross-cutting, critical]}\n    add: [security]\n")
    start(repo, "discount", "--risk", "cross-cutting - it touches every order")
    held = manifest(repo)
    assert "security" in held["evidence_required"]
    assert "verify.security" in [g["id"] for g in held["gates"]]
    e2e.write_discount(repo)
    done = finish(repo)
    # The project asked for the review, so the issue owes it.
    assert done.returncode == 1, done.stdout
    assert "owes 1 item(s) that the project's settings add" in done.stdout
    assert "next: compass gate pass verify.security --evidence <EV-id>" in done.stdout
    assert not list((repo / ".compass" / "work" / "discount").glob(
        "approval-requests/pending/*.yml"))


# --- a change with no natural red -----------------------------------------------------------

def test_a_declared_refactor_acceptance_stands_in_place_of_the_red(repo):
    """A refactor changes no behavior, so no test can fail without it. The
    acceptance declared before the change is recorded by `finish` on the tree
    that lands, and the check passes."""
    start(repo, "discount", "--expected-acceptance", "refactor",
          "--test", "tests/test_orders.py::test_total")
    declared = compass(repo, "acceptance", "start", "--kind", "refactor", "--", *PYTEST)
    assert declared.returncode == 0, declared.stdout + declared.stderr
    (repo / "shop" / "orders.py").write_text(
        "def total(prices):\n    result = 0\n    for price in prices:\n"
        "        result += price\n    return result\n")
    done = finish(repo, "Spell out the total loop (#7)")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "accepted : the declared refactor acceptance passes" in done.stdout
    assert "red      :" not in done.stdout
    assert check(repo) == (0, [])


# --- a red recorded before the code (decision 2) --------------------------------------------

def test_a_red_recorded_with_tdd_red_is_kept_by_finish(repo):
    """`compass tdd-red` is the only record that the test came before the code.
    `finish` keeps that red and adds the green; it does not replace the red
    with one proved on the base copy."""
    start(repo)
    e2e.write_discount(repo)
    code = (repo / "shop" / "orders.py").read_text()
    e2e.sh(["git", "checkout", "--", "shop/orders.py"], repo)   # the test alone, first
    red = compass(repo, "tdd-red", "--scenario", "TRC-001", "--", *PYTEST)
    assert red.returncode == 0, red.stdout + red.stderr
    (repo / "shop" / "orders.py").write_text(code)
    done = finish(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "red      : recorded earlier with compass tdd-red; it stays" in done.stdout
    record = json.loads((repo / ".compass" / "work" / "discount" / "evidence"
                         / "red-TRC-001.json").read_text())
    assert "proved_on" not in record
    assert check(repo)[1] == []


def test_a_red_recorded_with_no_scenario_is_not_deleted_by_finish(repo):
    """Every 8.x quick fix ran `compass tdd-red` with no `--scenario`, which writes
    `red.json`. A green cannot pair with an unbound red, so `finish` proves the red
    on the base copy as well; it must not delete the older record, the only one
    that shows the test came before the code."""
    start(repo)
    e2e.write_discount(repo)
    code = (repo / "shop" / "orders.py").read_text()
    e2e.sh(["git", "checkout", "--", "shop/orders.py"], repo)   # the test alone, first
    red = compass(repo, "tdd-red", "--", *PYTEST)
    assert red.returncode == 0, red.stdout + red.stderr
    evidence = repo / ".compass" / "work" / "discount" / "evidence"
    before = (evidence / "red.json").read_bytes()
    (repo / "shop" / "orders.py").write_text(code)
    done = finish(repo)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (evidence / "red.json").read_bytes() == before
    assert json.loads((evidence / "red-TRC-001.json").read_text())["proved_on"] == "base-copy"
    assert check(repo)[1] == []
