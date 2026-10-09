"""`compass policy migrate` (ADR-035, ADR-037, ADR-042, ADR-043).

The command turns copied legacy governance and `.compass/config.yml` into a
`compass.yml` overlay over the shipped default preset. The tests build small
scratch projects from the shipped governance files, change them, and run the
real CLI or the planner in `policy_migrate`.

Scenario ids: `PM-1` to `PM-11` (issue `policy-migrate`). Each test name
starts with its scenario id.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

CLI = ROOT / "cli" / "compass"
SHIPPED = ROOT / "governance"


def _api():
    from compass_pkg import policy_migrate
    return policy_migrate


# --- helpers ---------------------------------------------------------------------

def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "100", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


def _project(tmp_path):
    (tmp_path / ".compass").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _copy_governance(root, edit=None):
    """The shipped routing policy and guardrails in `root/governance/`. With
    `edit`, both are parsed, handed to `edit(policy, guardrails)` and written
    back; without it the bytes are copied."""
    governance = root / "governance"
    governance.mkdir(exist_ok=True)
    if edit is None:
        for name in ("routing-policy.yml", "guardrails.yml"):
            shutil.copyfile(SHIPPED / name, governance / name)
        return
    policy = yaml.safe_load((SHIPPED / "routing-policy.yml").read_text(encoding="utf-8"))
    guardrails = yaml.safe_load((SHIPPED / "guardrails.yml").read_text(encoding="utf-8"))
    edit(policy, guardrails)
    for name, doc in (("routing-policy.yml", policy), ("guardrails.yml", guardrails)):
        (governance / name).write_text(yaml.safe_dump(doc, sort_keys=False),
                                       encoding="utf-8")


def _copy_release(root, tag, edits=()):
    """The governance files a shipped release held, from the table of
    releases, in `root/governance/`. `edits` are `(file index, old, new)` text
    replacements, 0 for the routing policy and 1 for the guardrails."""
    from compass_pkg import shipped_releases
    texts = list(shipped_releases.texts(tag))
    for index, old, new in edits:
        assert texts[index].count(old) == 1, (tag, old)
        texts[index] = texts[index].replace(old, new)
    (root / "governance").mkdir(exist_ok=True)
    for name, text in zip(("routing-policy.yml", "guardrails.yml"), texts):
        (root / "governance" / name).write_bytes(text.encode("utf-8"))


# --- PM-9 -------------------------------------------------------------------------

def test_PM_9_a_project_with_nothing_to_migrate_exits_0_and_writes_nothing(tmp_path):
    root = _project(tmp_path)
    code, out, err = _run(root, "policy", "migrate")
    assert code == 0, out + err
    assert "nothing to migrate" in out
    assert not (root / "compass.yml").exists()


# --- PM-7 -------------------------------------------------------------------------

def _tree(root):
    """Every file under `root` with its bytes, to prove a refusal writes nothing."""
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_PM_7_an_existing_compass_yml_is_refused_and_nothing_is_written(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root)
    (root / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 2, out + err
    assert "compass.yml already exists" in err
    assert _tree(root) == before


def test_PM_7_both_settings_files_name_the_keys_the_old_file_still_sets(tmp_path):
    root = _project(tmp_path)
    (root / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    (root / ".compass" / "config.yml").write_text(
        "mode: enforced\nautonomy: balanced\n", encoding="utf-8")
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate")
    assert code == 2, out + err
    assert "compass.yml already exists" in err
    assert "autonomy, mode" in err or "mode, autonomy" in err
    assert _tree(root) == before


def test_PM_7_one_governance_file_without_the_other_is_refused(tmp_path):
    root = _project(tmp_path)
    (root / "governance").mkdir()
    shutil.copyfile(SHIPPED / "guardrails.yml", root / "governance" / "guardrails.yml")
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate")
    assert code == 2, out + err
    assert "governance/routing-policy.yml" in err
    assert _tree(root) == before


def test_PM_7_the_framework_repository_is_refused():
    code, out, err = _run(ROOT, "policy", "migrate")
    assert code == 2, out + err
    assert "framework" in err


# --- PM-2, PM-3, PM-4 ---------------------------------------------------------------

def _plan(root):
    return _api().plan(str(root))


def _ops(made):
    return [(o["catalogue"], o["id"], o["operation"]) for o in made.ops]


def _tighten_and_add(policy, guardrails):
    """An added guardrail gate, a lower subtask ceiling and an added floor rule:
    each adds an obligation, so the copy is stricter than the default."""
    guardrails["defaults"].append({
        "id": "G9", "name": "Project gate", "statement": "The project's own gate.",
        "checks": ["scenarios-have-tests"], "checked_at": ["verify"]})
    policy["route_shapes"]["regular"]["subtask_ceiling"] = 1
    policy["routing_guardrails"]["floors"].append({
        "id": "RP-FLOOR-900", "when": {"risk": "critical"},
        "force_minimum_route": "full", "rationale": "The project always runs critical work in full."})


def _drop_first_floor(policy, guardrails):
    policy["routing_guardrails"]["floors"].pop(0)


def test_PM_2_an_unchanged_copy_migrates_to_an_empty_overlay(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root)
    made = _plan(root)
    assert made.result == "ready"
    assert made.ops == []
    assert made.blocked == []
    assert made.equivalence["result"] == "equivalent"
    assert yaml.safe_load(made.compass_yml) == {"schema": 1, "extends": "compass:default@6"}


def test_PM_3_a_changed_copy_migrates_to_exactly_its_differing_entries(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root, _tighten_and_add)
    made = _plan(root)
    assert made.result == "ready"
    assert _ops(made) == [("approaches", "regular", "set"), ("rules", "floors", "set"),
                          ("gates", "G9", "add"), ("vocabulary", "gates.G9", "add")]
    assert made.equivalence["result"] == "equivalent"
    assert made.blocked == []
    doc = yaml.safe_load(made.compass_yml)
    assert doc["approaches"] == {"regular": {"set": {"subtask_ceiling": 1}}}
    assert list(doc["rules"]["floors"]["set"]["rules"]) == ["set"]
    assert list(doc["rules"]["floors"]["set"]["rules"]["set"]) == ["RP-FLOOR-900"]


def test_PM_4_a_loosening_gets_an_unapproved_stub_and_blocks(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root, _drop_first_floor)
    made = _plan(root)
    assert made.result == "blocked"
    assert [o["waiver"] for o in made.ops] == ["UNAPPROVED"]
    doc = yaml.safe_load(made.compass_yml)
    waiver = doc["rules"]["floors"]["waiver"]
    assert waiver["approved_by"] == "UNAPPROVED" and "approved_on" not in waiver
    codes = {b["code"] for b in made.blocked}
    assert "W-UNAPPROVED" in codes


def test_PM_4_a_migrated_configuration_that_is_not_equivalent_blocks(tmp_path, monkeypatch):
    root = _project(tmp_path)
    _copy_governance(root)
    api = _api()
    real = api.classify.classify

    def planted(parent, child, **kwargs):
        out = real(parent, child, **kwargs)
        if kwargs.get("child_name") == "base plus overlay":
            out.result, out.reason = "loosening", "planted difference"
        return out

    monkeypatch.setattr(api.classify, "classify", planted)
    made = _plan(root)
    assert made.result == "blocked"
    assert made.equivalence["result"] == "loosening"
    blocked = [b for b in made.blocked if b["code"] == "MIG-NOT-EQUIVALENT"]
    assert len(blocked) == 1 and "planted difference" in blocked[0]["message"]


# --- PM-5 -------------------------------------------------------------------------

OLD_CONFIG = """\
# the project's settings
version: 1.0.0
mode: advisory
autonomy: autonomous
initialised:
  by: compass init
  at: '2026-01-01'
records_signed_since: '2026-09-24'
governance_drift: strict
enforcement:
  code_globs:
    - "src/*.py"
swarm:
  worktree_root: ../wt
project:
  name: Demo
max_worktrees: 3
test_command: pytest -q
roles:
  enabled: [engineer]
artifacts:
  work_dir: .compass/work
"""


def test_PM_5_settings_fold_into_compass_yml_and_state_goes_to_state_yml(tmp_path):
    root = _project(tmp_path)
    (root / ".compass" / "config.yml").write_text(OLD_CONFIG, encoding="utf-8")
    made = _plan(root)
    doc = yaml.safe_load(made.compass_yml)
    assert doc == {
        "schema": 1, "extends": "compass:default@6",
        "adoption": "advisory", "autonomy": "autonomous", "governance_drift": "strict",
        "enforcement": {"code_globs": ["src/*.py"]},
        "multiagent": {"worktree_root": "../wt", "max_worktrees": 3},
        "project": {"name": "Demo", "test_command": "pytest -q"}}
    assert list(doc) == ["schema", "extends", "adoption", "autonomy", "governance_drift",
                         "enforcement", "multiagent", "project"]
    assert made.result == "ready"
    assert made.state == {"initialised": {"by": "compass init", "at": "2026-01-01"},
                          "records_signed_since": "2026-09-24"}
    assert made.moved == [
        {"key": "mode", "to": "adoption"}, {"key": "autonomy", "to": "autonomy"},
        {"key": "governance_drift", "to": "governance_drift"},
        {"key": "enforcement", "to": "enforcement"},
        {"key": "swarm", "to": "multiagent"}, {"key": "project", "to": "project"},
        {"key": "max_worktrees", "to": "multiagent.max_worktrees"},
        {"key": "test_command", "to": "project.test_command"}]
    assert [d["key"] for d in made.dropped] == ["version"]
    assert made.unread == ["roles", "artifacts"]


# --- PM-1, PM-6, PM-8 -----------------------------------------------------------------

def _full_project(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root, _tighten_and_add)
    (root / ".compass" / "config.yml").write_text(OLD_CONFIG, encoding="utf-8")
    return root


def test_PM_1_a_dry_run_prints_the_file_and_writes_nothing(tmp_path):
    root = _full_project(tmp_path)
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate")
    assert code == 0, out + err
    assert "dry run" in out
    assert "schema: 1" in out and "extends: compass:default@6" in out
    assert "equivalent" in out
    assert "--apply" in out
    assert _tree(root) == before


def _settings_view(root):
    """What the readers return for the settings both files carry."""
    from compass_pkg import project_settings
    data = project_settings.settings(str(root))
    return ({**{k: data[k] for k in ("adoption", "autonomy", "enforcement",
                                     "governance_drift")},
             "project_name": data["project"]["name"]},
            {k: project_settings.scalar(str(root), k)
             for k in ("worktree_root", "max_worktrees", "test_command")},
            project_settings.state(str(root)))


def test_PM_6_apply_writes_compass_yml_last_and_keeps_every_source(tmp_path):
    root = _full_project(tmp_path)
    originals = {rel: (root / rel).read_bytes() for rel in (
        "governance/routing-policy.yml", "governance/guardrails.yml", ".compass/config.yml")}
    before = _settings_view(root)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    assert "applied" in out
    assert (root / "compass.yml").is_file()
    for rel, data in originals.items():
        assert (root / ".compass" / "legacy" / Path(rel).name).read_bytes() == data
    for rel in ("governance/routing-policy.yml", "governance/guardrails.yml"):
        assert (root / rel).read_bytes() == originals[rel]
    assert not (root / ".compass" / "config.yml").exists()
    marker = yaml.safe_load((root / ".compass" / "migration.yml").read_text(encoding="utf-8"))
    assert list(marker["sources"]) == [
        "governance/routing-policy.yml", "governance/guardrails.yml", ".compass/config.yml"]
    assert marker["created_state"] is True
    assert _settings_view(root) == before
    code, out, err = _run(root, "policy", "lint")
    assert code == 0 and "PASS" in out, out + err
    assert _run(root, "policy", "show")[0] == 0


def test_PM_6_apply_on_a_blocked_plan_writes_nothing_and_exits_1(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root, _drop_first_floor)
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 1, out + err
    assert "W-UNAPPROVED" in out
    assert _tree(root) == before


def test_PM_6_compass_yml_is_written_last_and_after_every_copy(tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    api = _api()
    real = api.atomic_write_text
    written = []

    def record(path, text, **kwargs):
        written.append(os.path.relpath(path, root))
        return real(path, text, **kwargs)

    monkeypatch.setattr(api, "atomic_write_text", record)
    api.apply(str(root), api.plan(str(root)))
    assert written[-1] == "compass.yml"
    assert written[:3] == [".compass/legacy/routing-policy.yml",
                           ".compass/legacy/guardrails.yml", ".compass/legacy/config.yml"]
    assert written.index(".compass/migration.yml") < written.index("compass.yml")


def test_PM_6_an_existing_state_file_is_kept_and_the_marker_says_so(tmp_path):
    root = _full_project(tmp_path)
    state = root / ".compass" / "state.yml"
    state.write_text("initialised: {by: someone, at: '2026-02-02'}\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    assert state.read_text(encoding="utf-8") == "initialised: {by: someone, at: '2026-02-02'}\n"
    marker = yaml.safe_load((root / ".compass" / "migration.yml").read_text(encoding="utf-8"))
    assert marker["created_state"] is False


def test_PM_8_an_interrupted_apply_finishes_on_the_next_run(tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    api = _api()
    assert callable(getattr(api, "apply", None)) and hasattr(api, "remove_old_config")

    def stop(_root):
        raise OSError("stopped before the old settings file was removed")

    monkeypatch.setattr(api, "remove_old_config", stop)
    with pytest.raises(OSError):
        api.apply(str(root), api.plan(str(root)))
    assert (root / "compass.yml").is_file() and (root / ".compass" / "config.yml").is_file()
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    assert not (root / ".compass" / "config.yml").exists()
    assert (root / ".compass" / "legacy" / "config.yml").is_file()


def test_PM_8_an_edited_old_file_is_not_finished_but_refused(tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    api = _api()
    assert callable(getattr(api, "apply", None)) and hasattr(api, "remove_old_config")
    monkeypatch.setattr(api, "remove_old_config", lambda _root: (_ for _ in ()).throw(OSError("stop")))
    with pytest.raises(OSError):
        api.apply(str(root), api.plan(str(root)))
    with open(root / ".compass" / "config.yml", "a", encoding="utf-8") as fh:
        fh.write("autonomy: controlled\n")
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 2, out + err
    assert (root / ".compass" / "config.yml").is_file()


# --- PM-10 ------------------------------------------------------------------------

EXAMPLE = ROOT / "tests" / "fixtures" / "policy-migrate-example.json"
TOP_KEYS = ["schema", "mode", "result", "base_release", "sources", "adopted", "overlay",
            "settings", "equivalence", "behaviour", "blocked_by", "files", "compass_yml"]


def _example_project(tmp_path):
    """The project the pinned example is for: a copy of release 5.3.0 with one
    floor tightened, a mode and two keys of the old file that need a decision."""
    root = _project(tmp_path)
    _copy_release(root, "v5.3.0", [
        (0, "      never_skip: [refine, verify, ship]\n",
         "      never_skip: [define, refine, verify, ship]\n")])
    (root / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: advisory\nroles:\n  enabled: [engineer]\n", encoding="utf-8")
    return root


def _masked(text):
    """The document with each source digest, the grid size and the count of
    points that differ replaced. A digest follows the bytes of a file this test
    writes with whatever YAML library is installed, and the other two follow the
    shipped preset."""
    document = json.loads(text)
    for source in document["sources"]:
        source["digest"] = "sha256:..."
    for key in ("equivalence", "behaviour"):
        if document[key]:
            document[key]["points"] = 0
    if document["behaviour"]:
        document["behaviour"]["changed"] = 0
    return json.dumps(document, indent=2)


def test_PM_10_the_json_has_fixed_keys_in_a_fixed_order(tmp_path):
    root = _example_project(tmp_path)
    code, out, err = _run(root, "policy", "migrate", "--json")
    assert code == 0, out + err
    document = json.loads(out)
    assert list(document) == TOP_KEYS
    assert document["schema"] == 1 and document["mode"] == "dry-run"
    assert document["result"] == "ready"
    assert list(document["overlay"]) == ["counts", "entries"]
    assert list(document["overlay"]["counts"]) == ["add", "set", "replace", "remove"]
    assert list(document["overlay"]["entries"][0]) == ["catalogue", "id", "operation", "waiver"]
    assert list(document["settings"]) == ["moved", "state", "dropped", "unread"]
    assert list(document["equivalence"]) == ["result", "reason", "points", "scan"]
    assert list(document["base_release"]) == ["release", "chosen_by"]
    assert list(document["behaviour"]) == ["result", "reason", "points", "changed"]
    assert list(document["adopted"][0]) == ["catalogue", "id", "operation"] \
        if document["adopted"] else document["adopted"] == []
    assert list(document["sources"][0]) == ["path", "digest"]
    assert list(document["files"][0]) == ["action", "path", "to"]
    assert document["sources"][0]["digest"].startswith("sha256:")


def test_PM_10_the_same_input_gives_the_same_bytes(tmp_path):
    first = _example_project(tmp_path / "a")
    second = _example_project(tmp_path / "b")
    one = _run(first, "policy", "migrate", "--json")[1]
    assert one == _run(first, "policy", "migrate", "--json")[1]
    assert _masked(one) == _masked(_run(second, "policy", "migrate", "--json")[1])
    assert str(tmp_path) not in one


def test_PM_10_apply_json_reports_applied_and_the_blocked_document_lists_the_stubs(tmp_path):
    root = _example_project(tmp_path / "ok")
    document = json.loads(_run(root, "policy", "migrate", "--apply", "--json")[1])
    assert document["mode"] == "apply" and document["result"] == "applied"
    blocked = _project(tmp_path / "blocked")
    _copy_governance(blocked, _drop_first_floor)
    code, out, err = _run(blocked, "policy", "migrate", "--json")
    document = json.loads(out)
    assert code == 1 and document["result"] == "blocked"
    assert list(document["blocked_by"][0]) == ["code", "path", "message"]
    assert document["overlay"]["entries"][0]["waiver"] == "UNAPPROVED"


def test_PM_10_nothing_to_migrate_and_a_refusal_keep_the_contract(tmp_path):
    empty = _project(tmp_path / "empty")
    document = json.loads(_run(empty, "policy", "migrate", "--json")[1])
    assert list(document) == TOP_KEYS
    assert document["result"] == "nothing-to-migrate" and document["compass_yml"] is None
    refused = _project(tmp_path / "refused")
    (refused / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    code, out, err = _run(refused, "policy", "migrate", "--json")
    assert code == 2 and out == "" and "compass.yml already exists" in err


def test_PM_10_the_pinned_example_is_the_real_output(tmp_path):
    root = _example_project(tmp_path)
    out = _run(root, "policy", "migrate", "--json")[1]
    pinned = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.is_file() else ""
    assert pinned == _masked(out) + "\n"
    page = ROOT / "docs" / "policy-migrate.md"
    text = page.read_text(encoding="utf-8") if page.is_file() else ""
    shown = [block for block in re.findall(r"```json\n(.*?)```", text, re.S)
             if '"mode": "dry-run"' in block]
    assert len(shown) == 1 and _masked(shown[0]) == pinned.strip()


# --- PM-11 ------------------------------------------------------------------------

def test_PM_11_the_owning_doc_help_text_and_corpus_entries_exist():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert any("cli/compass_pkg/policy_migrate.py" in line and "docs/policy-migrate.md" in line
               for line in readme.splitlines())
    assert "(policy-migrate.md)" in readme
    from compass_pkg import verb_help
    text = verb_help.VERB_DESCRIPTIONS.get("policy migrate", "")
    assert "--apply" in text and "dry run" in text and "2 when it refuses" in text
    import compat_commands as cc
    entries = {e["id"]: e for e in cc.load()}
    assert {"policy-migrate-copied", "policy-migrate-nothing", "policy-migrate-refused"} \
        <= set(entries)
    assert [entries[i]["exit"] for i in ("policy-migrate-copied", "policy-migrate-nothing",
                                         "policy-migrate-refused")] == [0, 0, 2]


# --- PM-13 ------------------------------------------------------------------------

RELEASE_TAGS = ["v4.0.0", "v5.0.0", "v5.3.0", "v5.6.0"]


@pytest.mark.parametrize("tag", RELEASE_TAGS)
def test_PM_13_an_unedited_older_release_migrates_with_no_stub_and_no_refusal(tmp_path, tag):
    root = _project(tmp_path)
    _copy_release(root, tag)
    made = _plan(root)
    assert made.result == "ready"
    from compass_pkg import shipped_releases
    table = {r["tag"]: r for r in shipped_releases.table()}
    same = [t for t, r in table.items() if (r["routing_policy"], r["guardrails"])
            == (table[tag]["routing_policy"], table[tag]["guardrails"])]
    # Two tags that shipped the same files are one release; the newest is named.
    assert made.base_release == {"release": same[-1], "chosen_by": "version"}
    assert made.ops == [] and made.blocked == []
    assert made.equivalence["result"] == "equivalent"
    assert yaml.safe_load(made.compass_yml) == {"schema": 1, "extends": "compass:default@6"}
    if tag != "v5.6.0":
        assert made.adopted, "an older release has defaults the current one adds"


def test_PM_13_an_unedited_copy_of_the_current_files_adopts_nothing(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root)
    made = _plan(root)
    assert made.base_release == {"release": "current", "chosen_by": "version"}
    assert made.adopted == [] and made.behaviour["result"] == "equivalent"


LOOSENINGS = {
    "a check blocks on fewer assessments": (
        1, "    blocking_when: { blast_radius: [cross-cutting, critical] }\n",
        "    blocking_when: { blast_radius: [critical] }\n"),
    "a gate drops its check": (
        1, "    checks: [scenario-has-id-and-intent]\n    checked_at: [clarify, verify]",
        "    checks: []\n    checked_at: [clarify, verify]"),
    "a floor is deleted": (
        0, "    - id: RP-FLOOR-003\n      when: { labels_any: [auth, payments, personal-data, migrations] }\n"
           "      force_minimum_route: expedition\n      rationale: \"Domain risk overrides size. "
           "A one-line auth change is not small.\"\n\n", ""),
}


@pytest.mark.parametrize("name", sorted(LOOSENINGS))
def test_PM_13_a_local_loosening_of_the_base_release_still_blocks(tmp_path, name):
    root = _project(tmp_path)
    _copy_release(root, "v5.6.0", [LOOSENINGS[name]])
    made = _plan(root)
    assert made.result == "blocked"
    assert made.base_release["release"] == "v5.6.0"
    assert len(made.ops) == 1 and made.ops[0]["waiver"] == "UNAPPROVED"
    assert {b["code"] for b in made.blocked} & {"W-UNAPPROVED", "K-LOCK-REFUSED"}


def test_PM_13_a_local_tightening_of_an_older_release_is_one_entry_and_ready(tmp_path):
    root = _project(tmp_path)
    _copy_release(root, "v5.6.0", [
        (0, "      never_skip: [refine, verify, ship]\n",
         "      never_skip: [define, refine, verify, ship]\n")])
    made = _plan(root)
    assert made.result == "ready" and _ops(made) == [("rules", "floors", "set")]


def test_PM_13_the_release_with_the_fewest_entries_is_chosen_when_versions_do_not_match(tmp_path):
    root = _project(tmp_path)
    _copy_release(root, "v5.3.0")
    for name in ("routing-policy.yml", "guardrails.yml"):
        path = root / "governance" / name
        path.write_text(path.read_text(encoding="utf-8").replace("\nversion: ", "\nversion: 9."),
                        encoding="utf-8")
    made = _plan(root)
    assert made.base_release == {"release": "v5.3.0", "chosen_by": "fewest-entries"}
    assert made.ops == [] and made.result == "ready"


def test_PM_13_a_copy_far_from_every_release_falls_back_to_the_current_files(tmp_path, monkeypatch):
    root = _project(tmp_path)
    _copy_governance(root, lambda policy, guardrails: policy.update(version="9.9.9"))
    (root / "governance" / "guardrails.yml").write_text(
        (root / "governance" / "guardrails.yml").read_text(encoding="utf-8").replace(
            "\nversion: ", "\nversion: 9."), encoding="utf-8")
    monkeypatch.setattr(_api(), "FAR_ENTRIES", -1)
    made = _plan(root)
    assert made.base_release == {"release": None, "chosen_by": "as-built"}


def test_PM_13_the_report_names_the_base_release_and_what_the_default_adds(tmp_path):
    root = _project(tmp_path)
    _copy_release(root, "v5.0.0")
    code, out, err = _run(root, "policy", "migrate")
    assert code == 0, out + err
    assert "base release: v5.0.0 (chosen by the version lines)" in out
    assert out.index("adopted from the current default") < out.index("overlay:")
    document = json.loads(_run(root, "policy", "migrate", "--json")[1])
    assert document["base_release"] == {"release": "v5.0.0", "chosen_by": "version"}
    assert document["adopted"] and set(document["adopted"][0]) == {"catalogue", "id", "operation"}
    assert document["behaviour"]["result"] in ("tightening", "loosening", "incomparable",
                                               "equivalent")
    assert "an issue with no stored generation is judged by it at once" in out


# --- PM-14 ------------------------------------------------------------------------

PROJECT_GUARDRAIL = """project:
  - id: Q1
    name: "Lint passes"
    statement: "The project lints clean."
    checks: [command-passes]
    params: { command: "make lint" }
    checked_at: [verify]
"""


def test_PM_14_a_project_guardrail_becomes_a_project_check_and_gate(tmp_path):
    root = _project(tmp_path)
    _copy_release(root, "v5.6.0", [(1, "project: []\n", PROJECT_GUARDRAIL)])
    made = _plan(root)
    assert made.result == "ready", made.blocked
    assert _ops(made) == [("checks", "Q1-lint-passes", "add"), ("gates", "Q1", "add"),
                          ("vocabulary", "checks.Q1-lint-passes", "add"),
                          ("vocabulary", "gates.Q1", "add")]
    doc = yaml.safe_load(made.compass_yml)
    assert doc["checks"]["Q1-lint-passes"]["impl"] == "command-passes"
    assert doc["checks"]["Q1-lint-passes"]["params"] == {"command": "make lint"}
    assert doc["gates"]["Q1"]["checks"] == ["Q1-lint-passes"]
    assert doc["gates"]["Q1"]["stage"] == "verify" and "locked" not in doc["gates"]["Q1"]


def test_PM_14_the_migrated_project_guardrail_survives_apply_and_lint(tmp_path):
    root = _project(tmp_path)
    _copy_release(root, "v5.6.0", [(1, "project: []\n", PROJECT_GUARDRAIL)])
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    assert "Q1-lint-passes" in (root / "compass.yml").read_text(encoding="utf-8")
    assert _run(root, "policy", "lint")[0] == 0
    assert "checks.Q1-lint-passes.params" in _run(root, "policy", "show")[1]


def test_PM_14_a_value_only_the_legacy_views_hold_blocks_by_name(tmp_path):
    root = _project(tmp_path)
    _copy_release(root, "v5.6.0", [
        (1, "    checks: [scenario-has-id-and-intent]\n    checked_at: [clarify, verify]",
         "    checks: [scenario-has-id-and-intent]\n    checked_at: [clarify, verify, land]")])
    made = _plan(root)
    assert made.result == "blocked"
    named = [b for b in made.blocked if b["code"] == "MIG-UNEXPRESSED"]
    assert [b["path"] for b in named] == ["gates.G2.checked_at"]
    assert "land" in named[0]["message"]


@pytest.mark.parametrize("extra, path", [
    ("    owner: platform-team\n", "project.Q2.owner"),
    ("    params: { floor: 80 }\n", "project.Q2.params"),
])
def test_PM_14_a_project_guardrail_field_the_catalogue_cannot_state_blocks_by_name(
        tmp_path, extra, path):
    root = _project(tmp_path)
    _copy_release(root, "v5.6.0", [(1, "project: []\n", """project:
  - id: Q2
    name: "Other"
    statement: "A project gate."
    checks: [scenarios-have-tests]
""" + extra + "    checked_at: [verify]\n")])
    made = _plan(root)
    assert made.result == "blocked"
    named = [b for b in made.blocked if b["code"] == "MIG-UNEXPRESSED"]
    assert [b["path"] for b in named] == [path]


# --- PM-15 ------------------------------------------------------------------------

def _floor_ids(policy):
    return [r["id"] for r in policy["routing_guardrails"]["floors"]]


def _drop_middle_floor(policy, guardrails):
    floors = policy["routing_guardrails"]["floors"]
    del floors[2]


def _swap_two_floors(policy, guardrails):
    floors = policy["routing_guardrails"]["floors"]
    floors[1], floors[2] = floors[2], floors[1]


def test_PM_15_a_rule_removed_from_the_middle_is_one_overlay_entry(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root, _drop_middle_floor)
    made = _plan(root)
    assert _ops(made) == [("rules", "floors", "set")]
    rules = yaml.safe_load(made.compass_yml)["rules"]["floors"]["set"]["rules"]
    assert list(rules) == ["remove"] and len(rules["remove"]) == 1
    assert made.equivalence["result"] == "equivalent"


def test_PM_15_two_swapped_rules_carry_order_and_nothing_else_does(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root, _swap_two_floors)
    made = _plan(root)
    assert _ops(made) == [("rules", "floors", "set")]
    rules = yaml.safe_load(made.compass_yml)["rules"]["floors"]["set"]["rules"]["set"]
    assert len(rules) == 2
    assert made.equivalence["result"] == "equivalent"
    assert all("order" in rule for rule in rules.values())


def test_PM_15_a_rule_added_in_the_middle_keeps_the_order_unambiguous(tmp_path):
    root = _project(tmp_path)

    def add(policy, guardrails):
        policy["routing_guardrails"]["floors"].insert(1, {
            "id": "RP-FLOOR-901", "when": {"risk": "critical"},
            "force_minimum_route": "full", "rationale": "Inserted."})

    _copy_governance(root, add)
    made = _plan(root)
    assert made.equivalence["result"] == "equivalent"
    rules = yaml.safe_load(made.compass_yml)["rules"]["floors"]["set"]["rules"]["set"]
    orders = [rule["order"] for rule in rules.values()]
    assert len(set(orders)) == len(orders)
    merged = _api().merge.resolve([_api().policy_lint.load_parent()[0],
                                   _api().layers.Layer("project", "project", made.doc, "")])[0]
    seen = [r["order"] for r in merged["rules"]["floors"]["rules"].values()]
    assert len(set(seen)) == len(seen)


# --- PM-16 ------------------------------------------------------------------------

def test_PM_16_a_migrated_project_is_refused_with_the_way_back_not_a_step_that_loses_settings(tmp_path):
    root = _full_project(tmp_path)
    assert _run(root, "policy", "migrate", "--apply")[0] == 0
    before = _tree(root)
    code, out, err = _run(root, "policy", "migrate")
    assert code == 2 and out == ""
    assert "Move compass.yml away" not in err and "move compass.yml away" not in err
    assert "legacy" in err and "migration.yml" in err
    assert _tree(root) == before


def test_PM_16_a_hand_written_compass_yml_is_not_told_to_move_away(tmp_path):
    root = _project(tmp_path)
    (root / "compass.yml").write_text("schema: 1\nautonomy: balanced\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "migrate")
    assert code == 2 and "away" not in err and "already" in err


def test_PM_16_a_compass_yml_with_no_schema_is_someone_elses_file(tmp_path):
    root = _project(tmp_path)
    (root / "compass.yml").write_text("name: other\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "migrate")
    assert code == 2
    assert "no `schema:`" in err and "already on the overlay" not in err


def test_PM_16_the_legacy_copy_is_byte_exact_for_crlf_files(tmp_path):
    root = _project(tmp_path)
    _copy_governance(root)
    path = root / "governance" / "routing-policy.yml"
    crlf = path.read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(crlf)
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    assert (root / ".compass" / "legacy" / "routing-policy.yml").read_bytes() == crlf
    marker = yaml.safe_load((root / ".compass" / "migration.yml").read_text(encoding="utf-8"))
    import hashlib
    assert marker["sources"]["governance/routing-policy.yml"] == \
        "sha256:" + hashlib.sha256(crlf).hexdigest()


def test_PM_16_a_run_stopped_before_compass_yml_still_records_that_it_made_state_yml(
        tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    api = _api()
    real = api.atomic_write_text

    def stop_at_compass_yml(path, text, **kwargs):
        if os.path.basename(path) == "compass.yml":
            raise OSError("stopped")
        return real(path, text, **kwargs)

    monkeypatch.setattr(api, "atomic_write_text", stop_at_compass_yml)
    with pytest.raises(OSError):
        api.apply(str(root), api.plan(str(root)))
    monkeypatch.undo()
    assert (root / ".compass" / "state.yml").is_file()
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert code == 0, out + err
    marker = yaml.safe_load((root / ".compass" / "migration.yml").read_text(encoding="utf-8"))
    assert marker["created_state"] is True


def test_PM_16_a_resumed_run_reports_the_digest_and_no_file_text(tmp_path, monkeypatch):
    root = _full_project(tmp_path)
    api = _api()
    monkeypatch.setattr(api, "remove_old_config",
                        lambda _root: (_ for _ in ()).throw(OSError("stop")))
    with pytest.raises(OSError):
        api.apply(str(root), api.plan(str(root)))
    monkeypatch.undo()
    document = json.loads(_run(root, "policy", "migrate", "--json")[1])
    assert document["result"] == "ready" and document["compass_yml"] is None
    assert [s["path"] for s in document["sources"]] == [".compass/config.yml"]
    assert document["sources"][0]["digest"].startswith("sha256:")
    assert document["base_release"] is None and document["adopted"] == []


# --- PM-17 ------------------------------------------------------------------------

def test_PM_17_the_extends_string_is_built_from_the_resolvers_parse(tmp_path):
    from compass_pkg import layers, policy_lint
    root = _project(tmp_path)
    _copy_governance(root)
    made = _plan(root)
    extends = yaml.safe_load(made.compass_yml)["extends"]
    name, major = layers.parse_extends(extends)
    assert (name, str(major)) == ("default", policy_lint.load_parent()[1]["version"].split(".")[0])
    assert layers.default_extends(major) == extends
    assert not hasattr(_api(), "EXTENDS")


def test_PM_17_governance_drift_is_moved_and_lint_accepts_it_at_the_top_level(tmp_path):
    root = _project(tmp_path)
    (root / ".compass" / "config.yml").write_text("governance_drift: strict\n", encoding="utf-8")
    made = _plan(root)
    assert made.moved == [{"key": "governance_drift", "to": "governance_drift"}]
    assert made.dropped == []
    assert _run(root, "policy", "migrate", "--apply")[0] == 0
    assert yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))[
        "governance_drift"] == "strict"
    code, out, err = _run(root, "policy", "lint")
    assert code == 0 and "PASS" in out, out + err


# --- PM-18 ------------------------------------------------------------------------

def test_PM_18_the_output_says_when_the_overlay_takes_effect(tmp_path):
    root = _full_project(tmp_path)
    code, out, err = _run(root, "policy", "migrate")
    # Since the readers moved onto the effective view, compass.yml governs an
    # issue with no generation at once, and one with a generation at reassess.
    assert "an issue with no stored generation is judged by it at once" in out
    assert "keeps that generation until its next reassess" in out
    assert "governance copies" in out
    assert "do not change compass check" not in out
    code, out, err = _run(root, "policy", "migrate", "--apply")
    assert "an issue with no stored generation is judged by it at once" in out


def test_PM_18_overlay_between_keeps_every_kind_of_change():
    api = _api()
    base = {"checks": {"a": {"statement": "s", "kind": "deterministic", "severity": "blocking",
                             "on_skipped": "fail", "impl": "x"},
                       "gone": {"statement": "g", "kind": "deterministic",
                                "severity": "blocking", "on_skipped": "fail"},
                       "lost": {"statement": "l", "kind": "deterministic",
                                "severity": "blocking", "on_skipped": "fail", "impl": "y"}}}
    legacy = copy.deepcopy(base)
    del legacy["checks"]["gone"]
    legacy["checks"]["a"]["severity"] = "advisory"
    del legacy["checks"]["lost"]["impl"]
    legacy["checks"]["new"] = {"statement": "n", "kind": "human", "severity": "blocking",
                               "on_skipped": "fail"}
    overlay, ops = api.overlay_between(base, legacy)
    assert [(o["id"], o["operation"]) for o in ops] == [
        ("a", "set"), ("gone", "remove"), ("lost", "replace"), ("new", "add")]
    assert overlay["checks"]["a"] == {"set": {"severity": "advisory"}}
    assert overlay["checks"]["gone"] == {"remove": True}
    assert overlay["checks"]["lost"]["replace"] is True and "impl" not in overlay["checks"]["lost"]


def test_PM_18_a_real_difference_between_the_copy_and_the_overlay_is_not_equivalent(
        tmp_path, monkeypatch):
    root = _project(tmp_path)
    _copy_governance(root, _drop_first_floor)
    api = _api()
    real = api.overlay_between

    def forgetting(base, legacy):
        overlay, ops = real(base, legacy)
        return {}, []

    monkeypatch.setattr(api, "overlay_between", forgetting)
    made = _plan(root)
    assert made.result == "blocked"
    assert made.equivalence["result"] != "equivalent"
    assert "MIG-NOT-EQUIVALENT" in {b["code"] for b in made.blocked}
