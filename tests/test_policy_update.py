"""`compass policy update` for the shipped default (ADR-039, ADR-043).

The shipped default has one major today, so the end-to-end tests build a
fixture framework root that holds `default@6` (a copy of the real default,
kept as a retired major) and `default` at major 7 with one changed field.
`policy_update` reads any kept major, so the code that runs on the fixture is
the code that runs when a real next major ships.

Scenario ids: `UP-1` to `UP-16` (issue `policy-update-default`). Each test
name starts with its scenario id.
"""
from __future__ import annotations

import copy
import datetime
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

TODAY = datetime.date(2026, 10, 8)


def _module(name):
    assert importlib.util.find_spec(f"compass_pkg.{name}") is not None, \
        f"cli/compass_pkg/{name}.py does not exist"
    return importlib.import_module(f"compass_pkg.{name}")


def _has(module, name):
    got = _module(module)
    assert hasattr(got, name), f"{module}.{name} does not exist"
    return getattr(got, name)


# --- the shared pieces: the extends spelling and the move re-check ---------------------

def test_up_9_extends_is_read_and_written_by_one_pair_of_functions():
    parse, write = _has("layers", "parse_extends"), _has("layers", "default_extends")
    assert parse("compass:default@6") == ("default", 6)
    assert write(7) == "compass:default@7"
    assert parse(write(12)) == ("default", 12)
    from compass_pkg.core import CompassError
    for bad in ("compass:default@6.0.0", "compass:default", "default@6", "compass:default@x",
                "github:a/b@main#abc", None, 6):
        with pytest.raises(CompassError):
            parse(bad)


def _configs():
    import classifier_fixtures
    old = classifier_fixtures.base()
    new = copy.deepcopy(old)
    return old, new


def _loose_layer(check="tests-pass", **waiver):
    import waiver_fixtures as fx
    return fx.severity_layer(fx.project_waiver(**waiver), check=check)


def _found(layer):
    from compass_pkg import waivers
    found, faults = waivers.find(layer, "project")
    assert not faults
    return found


def test_up_9_a_move_keeps_a_waiver_whose_waived_field_did_not_change():
    import waiver_fixtures as fx
    recheck_move = _has("waivers", "recheck_move")
    old, new = _configs()
    new["checks"]["tests-pass"]["statement"] = "Changed wording, not the waived field."
    layer = _loose_layer()
    child = fx.resolve(old, layer)
    assert recheck_move(_found(layer), old, child, new) == []


def test_up_4_a_move_invalidates_a_waiver_whose_waived_field_changed():
    import waiver_fixtures as fx
    recheck_move = _has("waivers", "recheck_move")
    old, new = _configs()
    new["checks"]["tests-pass"]["severity"] = "advisory"
    layer = _loose_layer()
    child = fx.resolve(old, layer)
    got = recheck_move(_found(layer), old, child, new)
    assert [(i.waiver_id, i.entry, i.field) for i in got] == [
        ("project:checks.tests-pass", "checks.tests-pass", "severity")]
    assert got[0].old == "blocking" and got[0].new == "advisory"
    assert got[0].project == "advisory"


def test_up_10_a_move_invalidates_a_waiver_on_an_entry_the_new_parent_dropped():
    import waiver_fixtures as fx
    recheck_move = _has("waivers", "recheck_move")
    old, new = _configs()
    del new["checks"]["tests-pass"]
    layer = _loose_layer()
    child = fx.resolve(old, layer)
    got = recheck_move(_found(layer), old, child, new)
    assert [i.waiver_id for i in got] == ["project:checks.tests-pass"]
    assert got[0].field is None and "no longer defines" in got[0].reason


# --- the plan: majors, errors, waivers, classification -----------------------------------

import policy_update_fixtures as fixtures  # noqa: E402


@pytest.fixture(scope="session")
def frameworks(tmp_path_factory):
    """The fixture framework roots, one for each change, built once."""
    built = {}

    def get(change="ceiling"):
        if change not in built:
            built[change] = fixtures.framework_root(
                tmp_path_factory.mktemp(f"framework-{change}"), change)
        return built[change]
    return get


def _plan(root, frameworks, to=None, change="ceiling", **kw):
    make = _has("policy_update", "plan")
    return make(root, to, framework_root=frameworks(change), **kw)


def _waiver(plan, waiver_id):
    return next(w for w in plan.waivers if w.id == waiver_id)


CEILING_ID = "project:approaches.regular"


def test_trc_013_the_live_default_wins_for_its_own_major_beside_a_kept_folder(tmp_path):
    """Scenario id: `TRC-013` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base = fixtures.framework_root(tmp_path / "fw", change="none", version="6.0.0")
    found = _has("policy_update", "available_defaults")(base)
    assert list(found) == [6]
    assert Path(found[6]) == base / "governance" / "presets" / "default"


def test_up_1_a_project_on_the_target_major_has_nothing_to_do(tmp_path, frameworks):
    root = fixtures.project(tmp_path, fixtures.PROJECT.replace("@6", "@7"))
    plan = _plan(root, frameworks)
    assert plan.current == 7 and plan.target == 7 and plan.nothing_to_do
    assert plan.waivers == []


def test_up_1_the_real_framework_ships_three_majors_so_update_plans_the_move_to_the_live_one(
        tmp_path):
    make = _has("policy_update", "plan")
    root = fixtures.project(tmp_path)
    plan = make(root, None)
    assert plan.current == 6 and plan.target == 8 and not plan.nothing_to_do


def test_up_3_an_unusable_request_is_an_error_that_names_the_cause(tmp_path, frameworks):
    from compass_pkg.core import CompassError
    cases = [
        (fixtures.PROJECT, 9, "default@9 is not available"),
        (fixtures.PROJECT, 5, "default@5 is not available"),
        (fixtures.PROJECT.replace("@6", "@7"), 6, "older"),
        (fixtures.PROJECT.replace("compass:default@6", "github:o/r@main#abc"), None,
         "L-PARENT-FORM"),
        (fixtures.PROJECT.replace("@6", "@5"), None, "default@5 is not kept"),
        (fixtures.NO_WAIVER.replace("extends: compass:default@6   # the shipped default\n", ""),
         7, "no extends"),
        (fixtures.PROJECT.replace("compass:default@6", "compass:team@6"), None,
         "only the shipped default"),
    ]
    for n, (text, to, words) in enumerate(cases):
        root = fixtures.project(tmp_path / f"case-{n}", text)
        with pytest.raises(CompassError) as caught:
            _plan(root, frameworks, to)
        assert words in str(caught.value), (n, str(caught.value))
    empty = tmp_path / "empty"
    (empty / ".compass").mkdir(parents=True)
    with pytest.raises(CompassError) as caught:
        _plan(empty, frameworks, 7)
    assert "no compass.yml" in str(caught.value)


def test_up_4_a_waiver_whose_waived_field_changed_is_affected(tmp_path, frameworks):
    plan = _plan(fixtures.project(tmp_path), frameworks)
    assert (plan.current, plan.target) == (6, 7)
    assert plan.versions == {"from": "6.0.0", "to": "7.0.0"}
    waiver = _waiver(plan, CEILING_ID)
    assert waiver.status == "invalidated"
    [change] = waiver.invalidations
    assert (change.entry, change.field) == ("approaches.regular", "subtask_ceiling")
    assert (change.old, change.new, change.project) == (2, 3, 5)
    assert waiver.allowed == ["jed72"]


def test_up_9_a_waiver_whose_field_did_not_change_stays_valid(tmp_path, frameworks):
    plan = _plan(fixtures.project(tmp_path), frameworks, change="unrelated")
    assert _waiver(plan, CEILING_ID).status == "kept"
    assert _waiver(plan, CEILING_ID).invalidations == []


def test_up_10_a_dropped_entry_invalidates_the_waiver_and_the_file_does_not_resolve(
        tmp_path, frameworks):
    root = fixtures.project(tmp_path, fixtures.DROPPED_PROJECT)
    plan = _plan(root, frameworks, change="drop-entry")
    waiver = _waiver(plan, "project:checks.backfills-paid")
    assert waiver.status == "invalidated" and "no longer defines" in waiver.invalidations[0].reason
    assert plan.merge_errors and "backfills-paid" in plan.merge_errors[0][1]
    assert plan.classification is None and plan.replay is None


def test_up_12_the_plan_classifies_the_two_defaults_with_the_projects_layer(
        tmp_path, frameworks):
    plan = _plan(fixtures.project(tmp_path), frameworks)
    c = plan.classification
    assert c["result"] in ("tightening", "loosening", "incomparable", "equivalent")
    assert c["result"] == "loosening" or c["first_looser"] is None
    assert c["reason"]
    names = [s["name"] for s in plan.replay["sets"]]
    assert names == ["grid", "labels", "archive"]
    assert plan.replay["changed"] >= 1


def test_up_12_an_unrelated_change_classifies_equivalent_and_replays_no_change(
        tmp_path, frameworks):
    plan = _plan(fixtures.project(tmp_path), frameworks, change="unrelated")
    assert plan.classification["result"] == "equivalent" and plan.replay["changed"] == 0


# --- the text edit ---------------------------------------------------------------------

def _rewrite(text, target=7, approvals=()):
    return _has("policy_update", "rewrite_text")(text, target, list(approvals))


def test_up_2_a_move_changes_only_the_integer_in_extends():
    assert _rewrite(fixtures.NO_WAIVER) == fixtures.NO_WAIVER.replace("@6", "@7")
    assert _rewrite(fixtures.PROJECT) == fixtures.PROJECT.replace("@6", "@7")


def test_up_2_the_map_form_changes_only_the_integer_in_from():
    assert _rewrite(fixtures.MAP_FORM) == fixtures.MAP_FORM.replace("@6", "@7")


def test_up_2_a_comment_that_names_another_major_is_left_alone():
    text = fixtures.NO_WAIVER.replace("# the shipped default", "# was compass:default@5")
    assert _rewrite(text) == text.replace("default@6 ", "default@7 ")


def test_up_6_a_re_approval_rewrites_the_approver_and_the_date_of_that_waiver_only():
    second = fixtures.PROJECT + (
        "  hotfix:\n    set:\n      subtask_ceiling: 3\n" + fixtures.CEILING_WAIVER.replace(
            "jed72", "morgan").replace("2026-10-05", "2026-09-01"))
    got = _rewrite(second, 7, [("approaches", "regular", "alex", datetime.date(2026, 10, 8))])
    want = second.replace("@6", "@7").replace("approved_by: jed72", "approved_by: alex", 1) \
        .replace("approved_on: 2026-10-05", "approved_on: 2026-10-08")
    assert got == want
    assert "approved_by: morgan" in got and "approved_on: 2026-09-01" in got


def test_up_6_a_missing_approved_on_is_added_below_approved_by():
    text = fixtures.PROJECT.replace("approved_by: jed72\n      approved_on: 2026-10-05\n",
                                    "approved_by: LEGACY\n")
    got = _rewrite(text, 7, [("approaches", "regular", "jed72", TODAY)])
    assert got.endswith("      approved_by: jed72\n      approved_on: 2026-10-08\n")


def test_up_6_a_name_that_needs_quotes_is_quoted_and_a_trailing_comment_is_replaced():
    text = fixtures.PROJECT.replace("approved_on: 2026-10-05", "approved_on: 2026-10-05  # old")
    got = _rewrite(text, 7, [("approaches", "regular", "Alex Q", TODAY)])
    assert 'approved_by: "Alex Q"\n' in got and "approved_on: 2026-10-08\n" in got
    assert "# old" not in got


def test_up_15_a_waiver_the_edit_cannot_reach_in_place_is_an_error():
    from compass_pkg.core import CompassError
    flow = fixtures.PROJECT.replace(
        fixtures.CEILING_WAIVER,
        "    waiver: {reason: A reason., approved_by: jed72, approved_on: 2026-10-05}\n")
    with pytest.raises(CompassError) as caught:
        _rewrite(flow, 7, [("approaches", "regular", "jed72", TODAY)])
    assert "cannot be edited in place" in str(caught.value)
    assert "approaches.regular" in str(caught.value)
    missing = fixtures.PROJECT
    with pytest.raises(CompassError) as caught:
        _rewrite(missing, 7, [("approaches", "no-such-entry", "jed72", TODAY)])
    assert "cannot be edited in place" in str(caught.value)


def test_up_15_an_edit_that_changes_more_than_the_integer_and_the_approvals_is_refused(
        monkeypatch):
    from compass_pkg import policy_update
    from compass_pkg.core import CompassError
    real = policy_update._set_approval

    def greedy(lines, *args):
        real(lines, *args)
        lines[1] = lines[1].replace("schema: 1", "schema: 2")

    monkeypatch.setattr(policy_update, "_set_approval", greedy)
    with pytest.raises(CompassError) as caught:
        _rewrite(fixtures.PROJECT, 7, [("approaches", "regular", "jed72", TODAY)])
    assert "more than" in str(caught.value)


# --- the decision, the prompt and the one write -------------------------------------------

import dataclasses  # noqa: E402


@pytest.fixture(scope="session")
def plans(frameworks, tmp_path_factory):
    """Plans built once, because classifying the two defaults takes seconds."""
    cache = {}

    def get(change="ceiling", text=fixtures.PROJECT, to=None):
        key = (change, text, to)
        if key not in cache:
            root = fixtures.project(tmp_path_factory.mktemp("plan"), text)
            cache[key] = _plan(root, frameworks, to, change=change)
        return cache[key]
    return get


class Terminal:
    """A stand-in for the person at the keyboard: it answers each question
    in turn and fails the test if asked more than it was told."""

    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, prompt):
        self.asked.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)


def _copy(plan, tmp_path):
    root = fixtures.project(tmp_path, plan.text)
    return dataclasses.replace(plan, path=str(root / "compass.yml"))


def _execute(plan, tmp_path, *, yes=False, interactive=False, term=None, write=None):
    run = _has("policy_update", "execute")
    mine = _copy(plan, tmp_path)
    term = term if term is not None else Terminal()
    kw = {} if write is None else {"write": write}
    out = run(mine, yes=yes, interactive=interactive, ask=term, say=lambda line: None,
              today=TODAY, **kw)
    return out, mine, term


def _file(plan):
    return Path(plan.path).read_text(encoding="utf-8")


def test_up_1_nothing_to_do_writes_and_asks_nothing(tmp_path, plans):
    plan = plans(text=fixtures.PROJECT.replace("@6", "@7"))
    out, mine, term = _execute(plan, tmp_path, yes=True)
    assert (out.status, out.written, out.refusal) == ("nothing-to-do", False, None)
    assert _file(mine) == plan.text and term.asked == []


def test_up_4_without_a_terminal_an_affected_waiver_refuses_and_is_listed(tmp_path, plans):
    plan = plans()
    out, mine, term = _execute(plan, tmp_path, interactive=False)
    assert out.status == "refused" and out.refusal[0] == "no-terminal"
    assert "approaches.regular" in out.refusal[1]
    assert _file(mine) == plan.text and term.asked == [] and not out.written


def test_up_5_yes_never_re_approves_a_waiver_even_on_a_terminal(tmp_path, plans):
    plan = plans()
    for interactive in (False, True):
        out, mine, term = _execute(plan, tmp_path / str(interactive), yes=True,
                                   interactive=interactive,
                                   term=Terminal("y", "jed72", "y"))
        assert out.status == "refused" and out.refusal[0] == "yes-cannot-reapprove"
        assert "approaches.regular" in out.refusal[1]
        assert term.asked == [] and _file(mine) == plan.text


def test_up_6_a_re_approval_writes_the_move_and_the_approval_in_one_write(tmp_path, plans):
    plan = plans()
    writes = []

    def write(path, text):
        writes.append((path, text))
        Path(path).write_text(text, encoding="utf-8")

    out, mine, term = _execute(plan, tmp_path, interactive=True,
                               term=Terminal("y", "jed72", "y"), write=write)
    assert out.status == "applied" and out.written and out.refusal is None
    assert len(writes) == 1 and writes[0][0] == mine.path
    want = fixtures.PROJECT.replace("@6", "@7").replace("approved_on: 2026-10-05",
                                                         "approved_on: 2026-10-08")
    assert _file(mine) == want
    assert [w.status for w in out.waivers] == ["reapproved"]
    assert (out.waivers[0].approved_by, out.waivers[0].approved_on) == ("jed72", TODAY)
    assert len(term.asked) == 3
    assert plan.waivers[0].status == "invalidated"   # the plan itself is not changed


def test_up_6_the_only_allowed_approver_is_taken_on_an_empty_answer(tmp_path, plans):
    out, mine, _ = _execute(plans(), tmp_path, interactive=True, term=Terminal("y", "", "y"))
    assert out.status == "applied" and "approved_by: jed72" in _file(mine)


def test_up_7_a_name_outside_the_allowed_list_is_refused_after_three_tries(tmp_path, plans):
    plan = plans()
    out, mine, term = _execute(plan, tmp_path, interactive=True,
                               term=Terminal("y", "mallory", "eve", "trent", "y"))
    assert out.status == "refused" and out.refusal[0] == "declined"
    assert "mallory" not in _file(mine) and _file(mine) == plan.text
    assert len(term.asked) == 4 and term.answers == ["y"]


def test_up_7_with_no_owner_nobody_may_approve_and_nothing_is_asked(tmp_path, plans):
    text = fixtures.PROJECT.replace("owner: jed72\n", "")
    plan = plans(text=text)
    out, mine, term = _execute(plan, tmp_path, interactive=True, term=Terminal("y", "x", "y"))
    assert out.status == "refused" and out.refusal[0] == "nobody-may-approve"
    assert "owner" in out.refusal[1] and term.asked == [] and _file(mine) == text


def test_up_8_declining_the_waiver_or_the_move_writes_nothing(tmp_path, plans):
    plan = plans()
    for n, answers in enumerate((("n",), ("", ), ("y", "jed72", "n"), ("y", "jed72", ""))):
        out, mine, _ = _execute(plan, tmp_path / str(n), interactive=True,
                                term=Terminal(*answers))
        assert out.status == "refused" and out.refusal[0] == "declined", answers
        assert _file(mine) == plan.text and not out.written
    out, mine, _ = _execute(plan, tmp_path / "eof", interactive=True)
    assert out.status == "refused" and out.refusal[0] == "declined"


def test_up_9_a_waiver_whose_field_is_unchanged_lets_yes_apply_the_move(tmp_path, plans):
    plan = plans(change="unrelated")
    out, mine, term = _execute(plan, tmp_path, yes=True)
    assert out.status == "applied" and term.asked == []
    assert _file(mine) == fixtures.PROJECT.replace("@6", "@7")
    assert [w.status for w in out.waivers] == ["kept"]


def test_up_10_a_file_that_does_not_resolve_over_the_new_default_is_refused(tmp_path, plans):
    plan = plans(change="drop-entry", text=fixtures.DROPPED_PROJECT)
    out, mine, term = _execute(plan, tmp_path, yes=True)
    assert out.status == "refused" and out.refusal[0] == "does-not-resolve"
    assert "backfills-paid" in out.refusal[1] and _file(mine) == plan.text


def test_up_13_without_a_waiver_the_move_still_needs_a_confirmation(tmp_path, plans):
    plan = plans(text=fixtures.NO_WAIVER)
    out, mine, term = _execute(plan, tmp_path / "a", interactive=False)
    assert out.status == "refused" and out.refusal[0] == "needs-confirmation"
    assert _file(mine) == plan.text and term.asked == []
    out, mine, term = _execute(plan, tmp_path / "b", interactive=True, term=Terminal("y"))
    assert out.status == "applied" and _file(mine) == fixtures.NO_WAIVER.replace("@6", "@7")
    out, mine, term = _execute(plan, tmp_path / "c", interactive=True, term=Terminal("n"))
    assert out.refusal[0] == "declined" and _file(mine) == plan.text


def test_up_11_a_failed_write_leaves_the_file_and_the_folder_as_they_were(
        tmp_path, plans, monkeypatch):
    from compass_pkg.core import CompassError
    plan = plans()
    mine = _copy(plan, tmp_path)
    before = sorted(os.listdir(tmp_path))
    real = os.replace

    def broken(src, dst, *a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(CompassError) as caught:
        _has("policy_update", "execute")(mine, yes=False, interactive=True,
                                         ask=Terminal("y", "jed72", "y"),
                                         say=lambda line: None, today=TODAY)
    monkeypatch.setattr(os, "replace", real)
    assert "disk full" in str(caught.value)
    assert _file(mine) == plan.text and sorted(os.listdir(tmp_path)) == before


# --- the verb: text, JSON, exit codes -------------------------------------------------------

import subprocess  # noqa: E402

CLI = ROOT / "cli" / "compass"
EXAMPLE = ROOT / "tests" / "fixtures" / "policy-update-json-example.json"


def _entry():
    from importlib.machinery import SourceFileLoader
    spec = importlib.util.spec_from_loader("compass_entry_pu", SourceFileLoader(
        "compass_entry_pu", str(CLI)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(capsys, monkeypatch, root, frameworks, *argv, change="ceiling", terminal=False,
          answers=()):
    """Run `compass policy update` in-process over the fixture framework,
    with the terminal and its answers stood in for."""
    from compass_pkg import policy_cmd, policy_update
    monkeypatch.chdir(root)
    monkeypatch.setattr(policy_update, "FRAMEWORK_ROOT", frameworks(change))
    monkeypatch.setattr(policy_cmd, "_terminal_attached", lambda: terminal)
    term = Terminal(*answers)
    monkeypatch.setattr("builtins.input", term)
    code = _entry().main(["policy", "update", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err, term


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                          capture_output=True, text=True, timeout=300)
    return done.returncode, done.stdout, done.stderr


def test_up_1_the_real_cli_moves_to_the_live_major_only_when_confirmed_and_to_the_kept_one_is_nothing(
        tmp_path):
    root = fixtures.project(tmp_path, fixtures.NO_WAIVER)
    before = (root / "compass.yml").read_text(encoding="utf-8")
    code, out, _ = _run(root, "policy", "update")
    assert code == 1 and "compass:default@6 -> compass:default@8" in out
    assert "needs-confirmation" in out
    assert (root / "compass.yml").read_text(encoding="utf-8") == before
    code, out, _ = _run(root, "policy", "update", "--to", "6")
    assert code == 0 and "nothing to do" in out and "compass:default@6" in out
    code, out, _ = _run(root, "policy", "update", "--to", "6", "--json")
    assert code == 0
    doc = json.loads(out)
    assert (doc["status"], doc["written"], doc["refusal"]) == ("nothing-to-do", False, None)
    assert doc["from"] == {"ref": "compass:default@6", "major": 6, "version": None}
    assert doc["to"] == doc["from"] and doc["waivers"] == []
    assert (root / "compass.yml").read_text(encoding="utf-8") == before


def test_up_3_the_real_cli_exits_2_for_a_major_it_does_not_keep(tmp_path):
    root = fixtures.project(tmp_path)
    for argv in (["--to", "9"], ["--to", "five"], ["--to", "5"]):
        code, out, err = _run(root, "policy", "update", *argv)
        assert code == 2 and err.startswith("compass: "), (argv, err)
    assert "default@9 is not available" in _run(root, "policy", "update", "--to", "9")[2]
    empty = tmp_path / "bare"
    (empty / ".compass").mkdir(parents=True)
    code, _, err = _run(empty, "policy", "update")
    assert code == 2 and "no compass.yml" in err


def test_up_14_the_json_equals_the_pinned_example_and_never_prompts(
        tmp_path, capsys, monkeypatch, frameworks):
    root = fixtures.project(tmp_path)
    code, out, err, term = _call(capsys, monkeypatch, root, frameworks, "--json",
                                 terminal=True, answers=("y", "jed72", "y"))
    assert code == 1 and err == "" and term.asked == []
    assert EXAMPLE.is_file(), f"{EXAMPLE} does not exist"
    pinned = EXAMPLE.read_text(encoding="utf-8")
    assert json.loads(out) == json.loads(pinned)
    assert list(json.loads(out)) == list(json.loads(pinned))      # the key order
    assert out.strip() == pinned.strip()
    assert (root / "compass.yml").read_text(encoding="utf-8") == fixtures.PROJECT


def test_up_14_the_json_keys_are_the_documented_ones_in_order(
        tmp_path, capsys, monkeypatch, frameworks):
    root = fixtures.project(tmp_path)
    _, out, _, _ = _call(capsys, monkeypatch, root, frameworks, "--json")
    doc = json.loads(out)
    assert list(doc) == ["schema", "status", "written", "from", "to", "refusal",
                         "classification", "replay", "waivers"]
    assert list(doc["from"]) == ["ref", "major", "version"]
    assert list(doc["refusal"]) == ["code", "message"]
    assert list(doc["replay"]) == ["sets", "changed"]
    [waiver] = doc["waivers"]
    assert list(waiver) == ["id", "entry", "status", "reason", "approved_by", "approved_on",
                            "fields"]
    assert list(waiver["fields"][0]) == ["field", "old", "new", "project", "message"]
    from compass_pkg import classify
    assert classify.json_shape_errors(doc["classification"]) == []


def test_up_12_the_text_shows_the_classification_the_replay_and_the_waiver(
        tmp_path, capsys, monkeypatch, frameworks):
    root = fixtures.project(tmp_path)
    code, out, _, _ = _call(capsys, monkeypatch, root, frameworks)
    assert code == 1
    assert out.startswith("compass policy update: compass:default@6 -> compass:default@7")
    assert "classification: loosening" in out and "replay: grid " in out
    assert "approaches.regular" in out and "subtask_ceiling" in out
    assert "not applied (no-terminal)" in out


def test_up_6_the_verb_re_approves_on_a_terminal_and_writes_once(
        tmp_path, capsys, monkeypatch, frameworks):
    root = fixtures.project(tmp_path)
    code, out, _, term = _call(capsys, monkeypatch, root, frameworks, terminal=True,
                               answers=("y", "jed72", "y"))
    assert code == 0 and "applied" in out and "needs re-approval" in out
    assert (root / "compass.yml").read_text(encoding="utf-8") == fixtures.PROJECT.replace(
        "@6", "@7").replace("approved_on: 2026-10-05", f"approved_on: {datetime.date.today()}")


def test_up_5_the_verb_with_yes_never_re_approves(tmp_path, capsys, monkeypatch, frameworks):
    root = fixtures.project(tmp_path)
    code, out, _, term = _call(capsys, monkeypatch, root, frameworks, "--yes", terminal=True,
                               answers=("y", "jed72", "y"))
    assert code == 1 and term.asked == [] and "yes-cannot-reapprove" in out
    assert (root / "compass.yml").read_text(encoding="utf-8") == fixtures.PROJECT


def test_up_9_the_verb_with_yes_applies_a_move_that_affects_no_waiver(
        tmp_path, capsys, monkeypatch, frameworks):
    root = fixtures.project(tmp_path)
    code, out, _, term = _call(capsys, monkeypatch, root, frameworks, "--yes", "--to", "7",
                               change="unrelated")
    assert code == 0 and "applied" in out
    assert (root / "compass.yml").read_text(encoding="utf-8") == fixtures.PROJECT.replace(
        "@6", "@7")


# --- help, owning doc, corpus ---------------------------------------------------------------

DOC = ROOT / "docs" / "policy-update.md"
CORPUS = ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml"


def test_up_16_the_help_states_the_options_and_the_exit_codes(tmp_path):
    root = fixtures.project(tmp_path)
    code, out, _ = _run(root, "policy", "update", "--help")
    assert code == 0
    flat = " ".join(out.split())
    for words in ("--to MAJOR", "--yes", "--json", "never re-approves", "one atomic write",
                  "Exit 0 applied or nothing to do, 1 refused, 2 error"):
        assert words in flat, words
    from compass_pkg import verb_help
    assert "policy update" in verb_help.VERB_DESCRIPTIONS


def test_up_16_the_owning_doc_states_the_behaviour_and_its_example_is_the_pinned_one():
    import re
    assert DOC.is_file(), f"{DOC} does not exist"
    text = DOC.read_text(encoding="utf-8")
    flat = " ".join(text.split()).lower()
    assert "one atomic write" in flat and "never re-approves a waiver" in flat
    for words in ("compass policy update", "--to", "--yes", "default@<major>", "| 0 |", "| 1 |", "| 2 |",
                  "policy-update-json-example.json", "no-terminal", "yes-cannot-reapprove",
                  "needs-confirmation", "does-not-resolve", "nobody-may-approve", "declined"):
        assert words in text, words
    blocks = re.findall(r"```json\n(.*?)```", text, re.S)
    pinned = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert blocks and json.loads(blocks[0]) == pinned
    assert list(json.loads(blocks[0])) == list(pinned)
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "[policy-update.md](policy-update.md)" in readme
    rows = [line for line in readme.splitlines()
            if line.startswith("|") and "cli/compass_pkg/policy_update.py" in line]
    assert len(rows) == 1 and "docs/policy-update.md" in rows[0]


def test_up_16_the_command_corpus_holds_entries_with_true_reasons():
    text = CORPUS.read_text(encoding="utf-8")
    entries = yaml.safe_load(text)["entries"]
    mine = [e for e in entries if e["argv"][:2] == ["policy", "update"]]
    assert {e["id"] for e in mine} == {
        "policy-update-nothing-to-do", "policy-update-json-nothing-to-do",
        "policy-update-major-not-kept", "policy-update-no-extends",
        "policy-update-no-project-file"}
    assert {e["exit"] for e in mine} == {0, 2}
    lines = text.splitlines()
    for e in mine:
        at = lines.index(f"- id: {e['id']}")
        above = []
        while at > 0 and lines[at - 1].startswith("#"):
            at -= 1
            above.insert(0, lines[at])
        assert above and above[0].startswith("# Added on purpose by policy-update"), e["id"]
        assert "5.6.0" in " ".join(above), e["id"]
    states = _has_states()
    assert "with-default-extends" in states


def _has_states():
    import compat_commands
    return compat_commands.STATES


# --- review round: bytes, a file edited while waiting, kept majors, planted faults -----------

def _bytes(plan):
    return Path(plan.path).read_bytes()


def test_up_2_crlf_line_endings_survive_a_move_byte_for_byte(tmp_path, plans):
    crlf = fixtures.NO_WAIVER.replace("\n", "\r\n")
    plan = plans(change="unrelated", text=crlf)
    assert "\r\n" in plan.text
    out, mine, _ = _execute(plan, tmp_path / "plain", yes=True)
    assert out.status == "applied"
    assert _bytes(mine) == crlf.replace("@6", "@7").encode()
    with_waiver = fixtures.PROJECT.replace("\n", "\r\n")
    plan = plans(text=with_waiver)
    out, mine, _ = _execute(plan, tmp_path / "waiver", interactive=True,
                            term=Terminal("y", "jed72", "y"))
    want = with_waiver.replace("@6", "@7").replace("approved_on: 2026-10-05",
                                                   "approved_on: 2026-10-08")
    assert out.status == "applied" and _bytes(mine) == want.encode()


def test_up_2_rewrite_text_keeps_crlf_when_it_adds_an_approved_on_line():
    text = fixtures.PROJECT.replace("approved_by: jed72\n      approved_on: 2026-10-05\n",
                                    "approved_by: LEGACY\n").replace("\n", "\r\n")
    got = _rewrite(text, 7, [("approaches", "regular", "jed72", TODAY)])
    assert got.endswith("      approved_by: jed72\r\n      approved_on: 2026-10-08\r\n")
    assert "\n" not in got.replace("\r\n", "")


def test_up_11_a_file_edited_while_the_prompts_wait_is_not_overwritten(tmp_path, plans):
    from compass_pkg.core import CompassError
    plan = plans()
    mine = _copy(plan, tmp_path)
    answers = ["y", "jed72"]

    def ask(prompt):
        if answers:
            return answers.pop(0)
        Path(mine.path).write_text(plan.text + "# a note saved while the prompt waited\n",
                                   encoding="utf-8")
        return "y"

    with pytest.raises(CompassError) as caught:
        _has("policy_update", "execute")(mine, yes=False, interactive=True, ask=ask,
                                         say=lambda line: None, today=TODAY)
    assert "changed since" in str(caught.value) and "nothing was written" in str(caught.value)
    assert "line" in str(caught.value)
    kept = _file(mine)
    assert kept.endswith("# a note saved while the prompt waited\n") and "@7" not in kept


def test_up_3_a_kept_folder_whose_preset_names_another_major_is_a_framework_fault(tmp_path):
    from compass_pkg.core import CompassError
    base = fixtures.framework_root(tmp_path / "fw", change="none")
    meta_path = base / "governance" / "presets" / "default@6" / "preset.yml"
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
    meta["version"] = "7.1.0"
    meta_path.write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _has("policy_update", "available_defaults")(base)
    assert "default@6" in str(caught.value) and "7.1.0" in str(caught.value)


def test_up_3_a_project_on_a_newer_major_than_the_cli_keeps_gets_a_plain_error(
        tmp_path, frameworks):
    from compass_pkg.core import CompassError
    root = fixtures.project(tmp_path, fixtures.PROJECT.replace("@6", "@9"))
    with pytest.raises(CompassError) as caught:
        _plan(root, frameworks)
    message = str(caught.value)
    assert "default@9" in message and "newer" in message and "default@7" in message
    assert "older" not in message and "forward" not in message


def test_up_7_the_approvers_come_from_the_new_default_not_the_old_one(tmp_path, plans):
    plan = plans(change="approvers")
    assert plan.waivers[0].allowed == ["morgan"]
    out, mine, term = _execute(plan, tmp_path / "a", interactive=True,
                               term=Terminal("y", "alex", "alex", "alex"))
    assert out.refusal[0] == "declined" and _file(mine) == plan.text
    out, mine, term = _execute(plan, tmp_path / "b", interactive=True,
                               term=Terminal("y", "morgan", "y"))
    assert out.status == "applied" and "approved_by: morgan" in _file(mine)


def test_up_8_end_of_input_at_a_question_is_a_no_never_a_yes(tmp_path, plans):
    plan = plans(text=fixtures.NO_WAIVER)
    out, mine, _ = _execute(plan, tmp_path / "move", interactive=True)
    assert out.refusal[0] == "declined" and _file(mine) == plan.text
    plan = plans()
    out, mine, _ = _execute(plan, tmp_path / "final", interactive=True,
                            term=Terminal("y", "jed72"))
    assert out.refusal[0] == "declined" and _file(mine) == plan.text
    out, mine, _ = _execute(plan, tmp_path / "waiver", interactive=True)
    assert out.refusal[0] == "declined" and _file(mine) == plan.text


def test_up_15_a_nested_key_with_the_name_of_an_entry_is_not_mistaken_for_it():
    text = (
        "schema: 1\nextends: compass:default@6\nowner: jed72\n\napproaches:\n"
        "  other:\n    set:\n      regular: 1\n      waiver: nested\n"
        "  regular:\n    set:\n      subtask_ceiling: 5\n"
        "    waiver:\n      reason: A reason.\n      approved_by: jed72\n"
        "      approved_on: 2026-10-05\n")
    got = _rewrite(text, 7, [("approaches", "regular", "alex", TODAY)])
    assert got == text.replace("@6", "@7").replace("approved_by: jed72", "approved_by: alex") \
        .replace("2026-10-05", "2026-10-08")


# The previous major stays as `default@<n>` (docs/releasing.md). These checks
# fail when a kept folder is not the last preset that major shipped, or when
# the live major has moved on and a pinned earlier major is not kept.

def _digest_problems(folder, key, pins):
    """One line for each way the preset files in `folder` differ from the digests
    pinned under `key`: the file set, each file, then the whole preset. A file
    line names the file. Digests are over parsed content, so a comment-only edit
    gives no line; `_byte_problems` finds that."""
    import tempfile
    from compass_pkg import legacy_views
    folder, pin = Path(folder), pins[key]
    with tempfile.TemporaryDirectory() as scratch:
        shutil.copytree(folder, Path(scratch) / "governance/presets/default")
        got_key, got = legacy_views.preset_digests(scratch)
    problems = []
    if got_key != key:
        problems.append(f"{folder.name}/preset.yml reads {got_key}, not {key}")
    for name in sorted(set(got["files"]) | set(pin["files"])):
        if name not in pin["files"]:
            problems.append(f"{folder.name}/{name} is in the folder but not pinned for {key}")
        elif name not in got["files"]:
            problems.append(f"{folder.name}/{name} is pinned for {key} but missing from the folder")
        elif got["files"][name] != pin["files"][name]:
            problems.append(f"{folder.name}/{name} differs from the digest pinned for {key}")
    if got_key != key or got["preset"] != pin["preset"]:
        major = key.split("@", 1)[1].split(".")[0]
        problems.append(f"{folder.name} is not the last preset shipped for major {major} ({key})")
    return problems


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True)


def _require_tag(repo, tag):
    """Return when `tag` is a release tag of `repo`. Skip when the checkout has no
    `v*` tag (a shallow clone) or git cannot read it. Fail when release tags
    exist and `tag` is not one of them, so a missing tag is never a silent pass."""
    try:
        done = _git(repo, "tag", "--list", "v*")
    except OSError as exc:
        pytest.skip(f"git cannot read {repo}: {exc}")
    if done.returncode != 0:
        pytest.skip(f"git cannot read {repo}: {done.stderr.decode(errors='replace').strip()}")
    tags = done.stdout.decode().split()
    if not tags:
        pytest.skip("no v* release tags in this checkout (a shallow clone?); "
                    f"fetch the tags to compare with {tag}")
    if tag not in tags:
        pytest.fail(f"release tags exist but {tag} is not one of them: {', '.join(tags)}")


def _byte_problems(folder, tag, repo=ROOT):
    """One line for each file of `folder` whose bytes, or whose name, differ from
    `governance/presets/default` at `tag` in `repo`."""
    folder = Path(folder)
    listed = _git(repo, "ls-tree", "-r", "--name-only", tag, "--", "governance/presets/default")
    if listed.returncode != 0:
        return [f"git cannot list governance/presets/default at {tag}: "
                f"{listed.stderr.decode(errors='replace').strip()}"]
    paths = {Path(line).name: line for line in listed.stdout.decode().splitlines()}
    here = {p.name for p in folder.iterdir() if p.is_file()}
    problems = [f"{folder.name}/{p.name} is a directory; {tag} has only files"
                for p in sorted(folder.iterdir()) if p.is_dir()]
    for name in sorted(set(paths) | here):
        if name not in here:
            problems.append(f"{folder.name}/{name} is missing but {tag} has it")
        elif name not in paths:
            problems.append(f"{folder.name}/{name} is not in {tag}")
        elif _git(repo, "show", f"{tag}:{paths[name]}").stdout != (folder / name).read_bytes():
            problems.append(f"{folder.name}/{name} differs byte for byte from {tag}")
    return problems


def _kept_problems(root):
    root = Path(root)
    pins = yaml.safe_load((ROOT / "tests" / "fixtures" / "preset-digests.yml")
                          .read_text(encoding="utf-8"))
    last = {}
    for key in pins:
        version = key.split("@", 1)[1]
        major = int(version.split(".")[0])
        if major not in last or tuple(map(int, version.split("."))) > last[major][0]:
            last[major] = (tuple(map(int, version.split("."))), key)
    live = yaml.safe_load((root / "governance/presets/default/preset.yml")
                          .read_text(encoding="utf-8"))["version"]
    live_major = int(str(live).split(".")[0])
    problems = []
    for major, (_, key) in sorted(last.items()):
        folder = root / "governance" / "presets" / f"default@{major}"
        if major >= live_major:
            continue
        if not folder.is_dir():
            problems.append(f"default@{major} was shipped and the live major is {live_major}, "
                            f"but {folder.name} is not kept")
            continue
        problems.extend(_digest_problems(folder, key, pins))
    for folder in sorted((root / "governance" / "presets").glob("default@*")):
        if int(folder.name.split("@")[1]) not in last:
            problems.append(f"{folder.name} is kept but no shipped version of it is pinned")
    return problems


def test_up_3_the_framework_keeps_every_earlier_major_it_has_shipped():
    assert _kept_problems(ROOT) == []


def test_up_3_the_kept_major_guard_fails_for_a_missing_or_changed_folder(tmp_path):
    base = fixtures.framework_root(tmp_path / "ok", change="none")
    assert _kept_problems(base) == []
    changed = fixtures.framework_root(tmp_path / "changed", change="none")
    path = changed / "governance/presets/default@6/approaches.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("subtask_ceiling: 2",
                                                            "subtask_ceiling: 9", 1),
                    encoding="utf-8")
    assert any("not the last preset" in p for p in _kept_problems(changed))
    missing = fixtures.framework_root(tmp_path / "missing", change="none")
    shutil.rmtree(missing / "governance/presets/default@6")
    assert any("is not kept" in p for p in _kept_problems(missing))


def test_up_16_the_docs_cover_kept_majors_stepping_open_issues_and_exit_codes():
    flat = " ".join(DOC.read_text(encoding="utf-8").split())
    for words in ("two majors behind", "one major at a time", "policy diff --open",
                  "differs from `policy migrate`", "prints only a line on standard error"):
        assert words in flat, words
    releasing = " ".join((ROOT / "docs" / "releasing.md").read_text(encoding="utf-8").split())
    assert "governance/presets/default@<major>" in releasing
    assert "policy update" in releasing


# --- the kept default@6 folder (issue default-6-preset-for-7-0-0) ------------------------
# `governance/presets/default@6` is a byte copy of the files tag v6.1.0 shipped
# in `governance/presets/default`. It keeps `version: 6.0.0`, the version line
# that tag shipped.

KEPT_6 = ROOT / "governance" / "presets" / "default@6"
KEPT_TAG = "v6.1.0"
KEPT_KEY = "default@6.0.0"
SPEC = "default-6-preset-for-7-0-0/acceptance-criteria.md"


def _pins():
    return yaml.safe_load((ROOT / "tests" / "fixtures" / "preset-digests.yml")
                          .read_text(encoding="utf-8"))


def _fixture_kept(tmp_path):
    """A fixture framework (live default at 7.0.0) and its `default@6` folder."""
    base = fixtures.framework_root(tmp_path / "fw", change="none")
    return base, base / "governance" / "presets" / "default@6"


def test_trc_001_the_kept_default_6_folder_is_byte_identical_to_the_v6_1_0_tag():
    """Scenario id: `TRC-001` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    _require_tag(ROOT, KEPT_TAG)
    assert _byte_problems(KEPT_6, KEPT_TAG, ROOT) == []
    names = sorted(p.name for p in KEPT_6.iterdir())
    assert len(names) == 11 and "preset.yml" in names
    lines = (KEPT_6 / "preset.yml").read_text(encoding="utf-8").splitlines()
    assert "version: 6.0.0" in lines


def test_trc_002_the_kept_default_6_folder_matches_every_pinned_digest():
    """Scenario id: `TRC-002` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    pins = _pins()
    assert len(pins[KEPT_KEY]["files"]) == 11
    # Holds whatever major the live default has: the real folder, the real pins.
    assert _digest_problems(KEPT_6, KEPT_KEY, pins) == []


def test_trc_003_a_changed_value_in_the_kept_folder_is_reported_by_file(tmp_path):
    """Scenario id: `TRC-003` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    path = kept / "approaches.yml"
    text = path.read_text(encoding="utf-8")
    assert "subtask_ceiling: 2" in text
    path.write_text(text.replace("subtask_ceiling: 2", "subtask_ceiling: 9", 1),
                    encoding="utf-8")
    joined = "\n".join(_kept_problems(base))
    assert "approaches.yml" in joined and KEPT_KEY in joined
    for other in sorted(p.name for p in KEPT_6.iterdir()):
        if other != "approaches.yml":
            assert other not in joined, other


def test_trc_004_a_missing_file_in_the_kept_folder_is_reported(tmp_path):
    """Scenario id: `TRC-004` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    (kept / "vocabulary.yml").unlink()
    problems = _kept_problems(base)
    assert any("vocabulary.yml" in p for p in problems)
    assert any("not the last preset" in p and "vocabulary.yml" not in p for p in problems)


def test_trc_005_an_extra_file_in_the_kept_folder_is_reported(tmp_path):
    """Scenario id: `TRC-005` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    (kept / "extra.yml").write_text("schema: 1\n", encoding="utf-8")
    assert any("extra.yml" in p for p in _kept_problems(base))


def test_trc_006_a_comment_only_edit_passes_the_digest_check_and_fails_the_byte_check(
        tmp_path):
    """Scenario id: `TRC-006` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    _require_tag(ROOT, KEPT_TAG)
    copy_ = tmp_path / "default@6"
    shutil.copytree(KEPT_6, copy_)
    rules = copy_ / "rules.yml"
    rules.write_text("# a comment added later\n" + rules.read_text(encoding="utf-8"),
                     encoding="utf-8")
    assert _digest_problems(copy_, KEPT_KEY, _pins()) == []
    problems = _byte_problems(copy_, KEPT_TAG, ROOT)
    assert problems and all("rules.yml" in p for p in problems)


def test_trc_001_a_subdirectory_in_the_kept_folder_is_reported_by_name(tmp_path):
    """Scenario id: `TRC-001` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    _require_tag(ROOT, KEPT_TAG)
    copy_ = tmp_path / "default@6"
    shutil.copytree(KEPT_6, copy_)
    (copy_ / "sub").mkdir()
    (copy_ / "sub" / "x.yml").write_text("schema: 1\n", encoding="utf-8")
    problems = _byte_problems(copy_, KEPT_TAG, ROOT)
    assert any("sub" in p for p in problems), problems


def _git_repo(path, monkeypatch):
    """An empty git repository at `path`, with no user or system git settings."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_trc_007_the_byte_check_skips_when_no_release_tags_exist(tmp_path, monkeypatch):
    """Scenario id: `TRC-007` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    bare = _git_repo(tmp_path / "no-tags", monkeypatch)
    with pytest.raises(pytest.skip.Exception) as skipped:
        _require_tag(bare, KEPT_TAG)
    assert "v*" in str(skipped.value) and "tags" in str(skipped.value)
    # Not a git repository: git cannot read it, so the check skips too.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(pytest.skip.Exception):
        _require_tag(plain, KEPT_TAG)
    # Tags exist but the one the guard needs is missing: a failure, never a skip.
    other = _git_repo(tmp_path / "other-tag", monkeypatch)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit",
                    "-q", "--allow-empty", "-m", "x"], cwd=other, check=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=other, check=True)
    with pytest.raises(pytest.fail.Exception) as failed:
        _require_tag(other, KEPT_TAG)
    assert KEPT_TAG in str(failed.value)
    subprocess.run(["git", "tag", KEPT_TAG], cwd=other, check=True)
    assert _require_tag(other, KEPT_TAG) is None


def test_trc_008_update_in_the_real_framework_names_both_majors_while_both_folders_exist(
        tmp_path):
    """Scenario id: `TRC-008` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    for folder, major in ((ROOT / "governance/presets/default", "8"), (KEPT_7, "7"),
                          (KEPT_6, "6")):
        assert folder.is_dir(), f"{folder.relative_to(ROOT)} does not exist"
        meta = yaml.safe_load((folder / "preset.yml").read_text(encoding="utf-8"))
        assert str(meta["version"]).split(".")[0] == major, folder
    root = fixtures.project(tmp_path)
    before = (root / "compass.yml").read_bytes()
    code, out, err = _run(root, "policy", "update", "--to", "6")
    assert code == 0 and "nothing to do" in out, (out, err)
    code, out, err = _run(root, "policy", "update")
    assert code == 1 and "compass:default@6 -> compass:default@8" in out, (out, err)
    assert "not kept" not in err and "twice" not in err
    assert (root / "compass.yml").read_bytes() == before


def test_trc_009_a_major_the_framework_does_not_ship_still_exits_2(tmp_path):
    """Scenario id: `TRC-009` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    for folder in (ROOT / "governance/presets/default", KEPT_7, KEPT_6):
        assert folder.is_dir(), f"{folder.relative_to(ROOT)} does not exist"
    root = fixtures.project(tmp_path)
    code, _, err = _run(root, "policy", "update", "--to", "9")
    assert code == 2
    assert "default@9 is not available: this CLI keeps default@6, default@7, default@8" in err
    code, _, err = _run(root, "policy", "update", "--to", "5")
    assert code == 2 and "default@5 is not available" in err


def test_trc_010_with_the_live_default_at_major_7_a_faithful_kept_folder_raises_no_problem(
        tmp_path):
    """Scenario id: `TRC-010` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    assert _digest_problems(kept, KEPT_KEY, _pins()) == []
    assert _kept_problems(base) == []
    root = fixtures.project(tmp_path / "project")
    made = _has("policy_update", "plan")(root, None, framework_root=base)
    assert made.current == 6 and made.target == 7 and not made.nothing_to_do


# --- the kept default@7 folder (issue acceptance-strategy-core) ---------------------------
# The live default moved to 8.0.0 with the four-layer acceptance strategy, so
# `governance/presets/default@7` is a byte copy of the files the last release of
# major 7, v8.0.4, shipped in `governance/presets/default`, version line 7.0.0.

KEPT_7 = ROOT / "governance" / "presets" / "default@7"
KEPT_7_TAG = "v8.0.4"
KEPT_7_KEY = "default@7.0.0"


def test_the_kept_default_7_folder_is_byte_identical_to_the_v8_0_4_tag():
    assert KEPT_7.is_dir(), "governance/presets/default@7 does not exist"
    _require_tag(ROOT, KEPT_7_TAG)
    assert _byte_problems(KEPT_7, KEPT_7_TAG, ROOT) == []
    lines = (KEPT_7 / "preset.yml").read_text(encoding="utf-8").splitlines()
    assert "version: 7.0.0" in lines


def test_the_kept_default_7_folder_matches_every_pinned_digest():
    assert KEPT_7.is_dir(), "governance/presets/default@7 does not exist"
    pins = _pins()
    assert len(pins[KEPT_7_KEY]["files"]) == 11
    assert _digest_problems(KEPT_7, KEPT_7_KEY, pins) == []


def test_a_changed_value_in_the_kept_default_7_folder_is_reported(tmp_path):
    copy_ = tmp_path / "default@7"
    shutil.copytree(KEPT_7, copy_)
    path = copy_ / "checks.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("severity: blocking",
                                                            "severity: advisory", 1),
                    encoding="utf-8")
    joined = "\n".join(_digest_problems(copy_, KEPT_7_KEY, _pins()))
    assert "checks.yml differs" in joined and KEPT_7_KEY in joined


def test_trc_012_the_docs_state_that_the_kept_copy_keeps_the_last_shipped_version_line():
    """Scenario id: `TRC-012` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    for path in (ROOT / "docs" / "releasing.md", DOC):
        flat = " ".join(path.read_text(encoding="utf-8").split())
        for words in ("keeps the version line", "can be older than the release",
                      "do not edit", KEPT_TAG, "version: 6.0.0"):
            assert words in flat, (path.name, words)
    flat = " ".join(DOC.read_text(encoding="utf-8").split()).lower()
    assert "only default@6 ships today" not in flat
