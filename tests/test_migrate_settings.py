"""`compass migrate` rewrites an 8.x `compass.yml` for 9.0.0 (#359, ADR-098 decision 6).

Each key `removed_parts.REPLACEMENTS` marks as migrated is deleted, with the
setting that replaces it written where one does; each key it marks as not
migrated is left in the file with a line naming the edit. The edit keeps the
file's comments, and the settings lint must pass on the result before
anything is written.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
import compass_pkg  # noqa: E402,F401  - resolves the bundled yaml first
import yaml  # noqa: E402

from compass_pkg import (acceptance_strategy, check_set, migrate_settings,  # noqa: E402
                         removed_parts, settings_lint)

KEPT = "# A comment no key owns, which the edit keeps."


@pytest.fixture(scope="module")
def base():
    return check_set.resolved()


def _run(root, *args):
    done = subprocess.run([sys.executable, str(CLI), "migrate", *args], cwd=root,
                          capture_output=True, text=True, timeout=120)
    assert "Traceback" not in done.stderr, done.stderr
    return done


def _project(tmp_path, text):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(text, encoding="utf-8")
    return root


def _migrate(text, base):
    """`(plan, new text)` for the `compass.yml` text, with the checks a write makes."""
    doc = yaml.safe_load(text)
    plan = migrate_settings.build(doc, base)
    new = migrate_settings.edit(text, plan) if plan.has_change else text
    assert migrate_settings._problems(new, plan, base) == [], new
    return plan, new


def _removed(text):
    return {f.path for f in settings_lint.lint(yaml.safe_load(text))
            if f.code == "L-SETTING-REMOVED"}


# --- every row of the table -----------------------------------------------------------

LEAVES = {
    "project": "make",
    "capabilities": True,
    "github_labels": True,
    "approvers": ["sam"],
    "governance_drift": "advisory",
}
EFFECT_VALUES = {"force_minimum_approach": "full", "forbid_approach": ["quick-fix"],
                 "never_skip": ["ship"], "require_phase": "define"}


def fixture(key):
    """A `compass.yml` mapping that holds the removed key `key`, and nothing
    else the lint refuses."""
    if key == "extends":
        return {"schema": 1, "extends": "./team.yml"}
    if key.startswith("extends@"):
        return {"schema": 1, "extends": f"compass:default@{key.split('@', 1)[1]}"}
    path = key.replace("*", "mine.rules.RP-MINE-1.then").split(".")
    effect = path[-1]
    leaf = EFFECT_VALUES.get(effect, LEAVES.get(path[0], {}) if len(path) > 1 else
                             LEAVES.get(key, {}))
    doc = node = {"schema": 1}
    for part in path[:-1]:
        node[part] = {}
        node = node[part]
    node[path[-1]] = leaf
    return doc


ROWS = sorted(removed_parts.REPLACEMENTS)


@pytest.mark.parametrize("key", ROWS)
def test_each_row_is_rewritten_or_left_as_its_flag_says(key, base):
    _settings, migrated = removed_parts.REPLACEMENTS[key]
    doc = fixture(key)
    top = next(k for k in doc if k != "schema")
    text = KEPT + "\n" + yaml.safe_dump(doc, sort_keys=False)
    assert _removed(text), f"the fixture of {key} holds no removed key"
    plan, new = _migrate(text, base)
    left = {item["key"] for item in plan.left}
    if migrated:
        assert plan.has_change, key
        assert not left, (key, plan.left)
        assert _removed(new) == set(), (key, new)
        assert KEPT in new
    else:
        assert left & {key, top}, (key, plan.left)
        item = next(i for i in plan.left if i["key"] in (key, top))
        assert "compass migrate" in item["edit"] or "delete" in item["edit"], item
        assert top in yaml.safe_load(new), (key, new)
        assert _removed(new), key


def test_the_rows_name_every_top_level_key_migrate_deletes():
    """migrate reads its list of removed keys from the table, so a row a later
    change adds is migrated with no change to migrate."""
    tops = set(migrate_settings.removed_top_keys())
    assert tops == {k for k in removed_parts.REPLACEMENTS
                    if "." not in k and "@" not in k and "*" not in k}
    assert {"extends", "rules", "checks", "gates", "models", "readiness"} <= tops


# --- the conversions ------------------------------------------------------------------

@pytest.mark.parametrize("major", [6, 7])
def test_a_pin_below_8_becomes_acceptance_strategy_off(major, base):
    plan, new = _migrate(f"schema: 1\nextends: compass:default@{major}\n", base)
    doc = yaml.safe_load(new)
    assert "extends" not in doc
    assert acceptance_strategy.problem(doc["acceptance_strategy"]) is None
    assert acceptance_strategy._state(doc["acceptance_strategy"]["state"]) == "off"
    assert f"compass:default@{major}" in doc["acceptance_strategy"]["reason"]
    assert migrate_settings.ADDED_COMMENT in new


def test_a_pin_of_8_is_deleted_with_nothing_added(base):
    _plan, new = _migrate("schema: 1\nextends: compass:default@8\n", base)
    assert yaml.safe_load(new) == {"schema": 1}


def test_a_set_acceptance_strategy_is_kept(base):
    text = ("schema: 1\nextends: compass:default@6\n"
            "acceptance_strategy: {state: on}\n")
    _plan, new = _migrate(text, base)
    # YAML 1.1 reads an unquoted `on` as true; the line is kept as written.
    assert yaml.safe_load(new) == {"schema": 1, "acceptance_strategy": {"state": True}}
    assert "acceptance_strategy: {state: on}" in new


def test_the_labels_g5_adds_become_signoff_labels(base):
    text = ("schema: 1\ngates:\n  G5:\n    set:\n      when:\n"
            "        labels_any: {add: [billing, gdpr]}\n")
    _plan, new = _migrate(text, base)
    assert yaml.safe_load(new) == {"schema": 1, "signoff_labels": ["billing", "gdpr"]}


def test_signoff_labels_already_set_are_kept_and_added_to(base):
    text = ("schema: 1\nsignoff_labels: [legal]\ngates:\n  G5:\n    set:\n      when:\n"
            "        labels_any: [auth, payments, personal-data, migrations, billing]\n")
    _plan, new = _migrate(text, base)
    assert yaml.safe_load(new)["signoff_labels"] == ["legal", "billing"]


def test_an_add_gate_floor_with_a_token_becomes_require_evidence(base):
    text = ("schema: 1\nrules:\n  floors:\n    set:\n      rules:\n        add:\n"
            "          RP-MINE-1:\n            when: {risk: critical}\n"
            "            then: {add_gate: verify.security}\n")
    plan, new = _migrate(text, base)
    assert yaml.safe_load(new) == {"schema": 1, "require_evidence": [
        {"when": {"risk": "critical"}, "add": ["security"]}]}
    assert plan.dropped == []


def test_an_add_gate_with_no_token_and_a_forced_approach_are_named(base):
    text = ("schema: 1\nrules:\n  mine:\n    rules:\n      RP-MINE-1:\n"
            "        when: {risk: critical}\n"
            "        then: {add_gate: verify.analyze, force_minimum_approach: full}\n")
    plan, new = _migrate(text, base)
    assert yaml.safe_load(new) == {"schema": 1}
    assert any("verify.analyze has no evidence token" in line for line in plan.dropped)
    assert any(line.startswith("rules.mine.rules.RP-MINE-1.then.force_minimum_approach")
               for line in plan.dropped), plan.dropped


@pytest.mark.parametrize("stage, expected", [("verify", "ship"), ("implement", "build"),
                                             ("define", "build"), ("ship", "ship")])
def test_a_command_passes_guardrail_becomes_a_project_check(stage, expected, base):
    text = ("schema: 1\nallow_project_commands: true\nchecks:\n  arch-rule:\n"
            "    statement: The architecture rules hold.\n    kind: deterministic\n"
            "    impl: command-passes\n    params: {command: python3 scripts/fitness.py}\n"
            "gates:\n  arch-gate:\n    kind: guardrail\n    name: Architecture holds\n"
            f"    stage: {stage}\n    when: {{risk: critical}}\n    checks: [arch-rule]\n")
    _plan, new = _migrate(text, base)
    assert yaml.safe_load(new)["project_checks"] == [
        {"id": "arch-rule", "name": "Architecture holds",
         "command": "python3 scripts/fitness.py", "stage": expected,
         "when": {"risk": "critical"}}]


def test_the_agent_review_block_becomes_agent_review_on(base):
    text = ("schema: 1\nchecks:\n  agent-review:\n    statement: An agent reviewed it.\n"
            "    kind: judged\n    reviewers: [agent]\n    inputs: [acceptance-criteria]\n"
            "    severity: advisory\n    on_skipped: not-applicable\nstages:\n  ship:\n"
            "    set:\n      entry: {add: [agent-review]}\n")
    plan, new = _migrate(text, base)
    assert yaml.safe_load(new) == {"schema": 1, "agent_review": True}
    assert "agent_review: on" in new
    assert plan.left == []


def test_approvers_issue_waiver_is_renamed_and_project_waiver_deleted(base):
    text = ("schema: 1\napprovers:\n  # who approves an issue's waiver\n"
            "  issue-waiver: [sam]\n  project-waiver: [kim]\n")
    _plan, new = _migrate(text, base)
    assert yaml.safe_load(new) == {"schema": 1, "approvers": {"waiver": ["sam"]}}
    assert "# who approves an issue's waiver" in new


def test_a_flow_mapping_is_written_again_without_the_removed_key(base):
    _plan, new = _migrate("schema: 1\napprovers: {waiver: [sam], project-waiver: [kim]}\n",
                          base)
    assert yaml.safe_load(new) == {"schema": 1, "approvers": {"waiver": ["sam"]}}


def test_a_migrated_key_that_holds_an_unmigrated_one_is_left_whole(base):
    text = "schema: 1\nrules:\n  caps: {}\n  floors: {}\n"
    plan, new = _migrate(text, base)
    assert new == text
    (item,) = plan.left
    assert item["key"] == "rules" and "rules.caps" in item["edit"], item


# --- the line edit keeps comments -----------------------------------------------------

def test_comments_stay_and_a_deleted_key_takes_its_own_comment_block(base):
    text = ("# The project's settings.\n\nschema: 1\n\n# Who owns it.\nowner: sam\n\n"
            "# The model tiers 8.x dispatched.\nmodels:\n  fast: small\n\n"
            "project:\n  name: x  # shown in headers\n  # the readiness build\n"
            "  build_command: make\n  test_command: pytest -q\n")
    _plan, new = _migrate(text, base)
    assert new == ("# The project's settings.\n\nschema: 1\n\n# Who owns it.\nowner: sam\n\n"
                   "project:\n  name: x  # shown in headers\n  test_command: pytest -q\n")


# --- the command ----------------------------------------------------------------------

def test_the_dry_run_prints_the_diff_and_writes_nothing(tmp_path):
    root = _project(tmp_path, "schema: 1\nextends: compass:default@6\nprices: {}\n")
    before = (root / "compass.yml").read_bytes()
    done = _run(root, "--settings-only")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "-extends: compass:default@6" in done.stdout
    assert "+acceptance_strategy: {state: off" in done.stdout
    assert "Dry run: nothing was written." in done.stdout
    assert (root / "compass.yml").read_bytes() == before


def test_apply_writes_and_a_second_run_has_nothing_to_do(tmp_path):
    root = _project(tmp_path, "schema: 1\nextends: compass:default@7\nmodels: {}\n")
    # 9.0.0 does not read the pin, so `S17` is on until migrate writes the setting.
    assert acceptance_strategy.setting(str(root)) == ("on", None)
    done = _run(root, "--settings-only", "--apply")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "extends" not in yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))
    state, reason = acceptance_strategy.setting(str(root))
    assert state == "off" and "compass:default@7" in reason
    again = _run(root, "--settings-only")
    assert again.returncode == 0, again.stdout
    assert "holds no key 9.0.0 removed" in again.stdout


def test_a_file_the_lint_refuses_is_not_written(tmp_path):
    root = _project(tmp_path, "schema: 1\nautonomy: sometimes\nprices: {}\n")
    before = (root / "compass.yml").read_bytes()
    done = _run(root, "--settings-only", "--apply")
    assert done.returncode == 2, done.stdout + done.stderr
    assert "autonomy: 'sometimes' is not one of" in done.stdout
    assert (root / "compass.yml").read_bytes() == before


def test_a_left_key_names_the_edit(tmp_path):
    root = _project(tmp_path, "schema: 1\ndimensions: {}\n")
    done = _run(root, "--settings-only", "--apply")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "dimensions: left as it is - compass migrate does not rewrite it; " \
           "delete it: nothing replaces it" in done.stdout


def test_issues_only_leaves_compass_yml(tmp_path):
    root = _project(tmp_path, "schema: 1\nprices: {}\n")
    before = (root / "compass.yml").read_bytes()
    done = _run(root, "--issues-only", "--apply")
    assert done.returncode == 0, done.stdout + done.stderr
    assert (root / "compass.yml").read_bytes() == before


def test_issue_with_settings_only_is_refused(tmp_path):
    root = _project(tmp_path, "schema: 1\n")
    done = _run(root, "--issue", "x", "--settings-only")
    assert done.returncode != 0
    assert "--settings-only" in done.stdout + done.stderr


def test_settings_only_and_issues_only_cannot_be_given_together(tmp_path):
    root = _project(tmp_path, "schema: 1\n")
    done = _run(root, "--settings-only", "--issues-only")
    assert done.returncode == 2
    assert "not allowed with" in done.stderr


def test_an_old_settings_file_is_left_because_9_0_0_still_reads_it(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("prices: {}\n", encoding="utf-8")
    done = _run(root, "--settings-only", "--apply")
    assert done.returncode == 0, done.stdout + done.stderr
    assert ".compass/config.yml: left as it is - 9.0.0 still reads it" in done.stdout
    assert (root / ".compass" / "config.yml").read_text() == "prices: {}\n"


# --- this repository ------------------------------------------------------------------

def test_this_repository_compass_yml_keeps_s17_off(tmp_path):
    """A copy of this repository's `compass.yml`: the owner moved it to 9.0.0
    (commit af632567), so migrate has nothing to do, `S17` stays off through
    `acceptance_strategy: off`, and the lint names no removed setting."""
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    shutil.copy(ROOT / "compass.yml", root / "compass.yml")
    before = (root / "compass.yml").read_bytes()
    done = _run(root, "--settings-only")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "holds no key 9.0.0 removed" in done.stdout, done.stdout
    assert (root / "compass.yml").read_bytes() == before
    assert acceptance_strategy.setting(str(root))[0] == "off"
    lint = subprocess.run([sys.executable, str(CLI), "policy", "lint"], cwd=root,
                          capture_output=True, text=True, timeout=120)
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "L-SETTING-REMOVED" not in lint.stdout, lint.stdout
