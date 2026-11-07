"""The readiness measure 9.0.0 removed, and what stays (ADR-093).

`compass readiness`, `compass init --readiness`, the readiness floor at
`approach evaluate --write` and the session-start readiness line are gone. A
command line that names one fails to parse, exits 2 and names the removal. The
shipped default declares an empty `readiness:` catalogue, a frozen preset keeps
its own, and a project's `readiness:` is left out of the merge with the warning
`L-SETTING-REMOVED`. The readiness-only `project.*` commands get the same
warning, and the merge keeps them; `project.test_micro_command` gets none.

Issue: #354 [Remove role entry points, the board, retro reporting, evals and the
Codex adapter].
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from check_set_files import shipped  # noqa: E402
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

#: The readiness-only fields of `project`, which only `compass readiness` read.
READINESS_FIELDS = ("build_command", "lint_command", "format_check_command",
                    "typecheck_command", "secret_scan", "structured_logging")


def _run(args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=120,
                          stdin=subprocess.DEVNULL)


def _git(root, *args):
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True)


# --- the removed verb and flag --------------------------------------------------------

REMOVED = {
    ("readiness",): ("compass readiness", "nothing measures the repository"),
    ("readiness", "--json"): ("compass readiness", "nothing measures the repository"),
    ("readiness", "--fix-list"): ("compass readiness", "nothing measures the repository"),
    ("init", "--readiness"): ("compass init --readiness",
                              "compass init sets up the project; nothing measures it"),
}


@pytest.mark.parametrize("argv", sorted(REMOVED), ids=" ".join)
def test_a_removed_readiness_call_names_its_removal(tmp_path, argv):
    name, instead = REMOVED[argv]
    proc = _run(list(argv), tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert proc.stdout == "", proc.stdout
    assert f"'{name}' was removed in 9.0.0 (ADR-093)" in proc.stderr, proc.stderr
    assert instead in proc.stderr, proc.stderr
    assert not (tmp_path / ".compass").exists()


def test_compass_init_still_makes_a_project_and_measures_nothing(tmp_path):
    (tmp_path / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    proc = _run(["init", "--json"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / ".compass" / "work").is_dir()
    assert "readiness" not in proc.stdout
    assert not (tmp_path / ".compass" / "readiness.yml").exists()


# --- the catalogue --------------------------------------------------------------------

def test_the_shipped_default_declares_no_readiness_signal():
    doc = shipped("readiness.yml")
    assert doc == {"schema": 1, "readiness": {}}
    vocabulary = shipped("vocabulary.yml")
    assert not [k for k in vocabulary["vocabulary"] if k.startswith("readiness.")]


@pytest.mark.parametrize("preset", ["default@6", "default@7"])
def test_a_frozen_preset_keeps_its_readiness_catalogue(preset):
    doc = yaml.safe_load((ROOT / "governance" / "presets" / preset / "readiness.yml")
                         .read_text(encoding="utf-8"))
    assert "tests-declared-and-under-two-minutes" in doc["readiness"]


# --- a project that still holds the removed settings ----------------------------------

def _project(tmp_path, **more):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.com",
         "commit", "-q", "-m", "base")
    assert _run(["init"], root).returncode == 0
    doc = {"schema": 1, "owner": "someone", **more}
    (root / "compass.yml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return root


OVERRIDE = {"tests-declared-and-under-two-minutes":
            {"set": {"params": {"set": {"command": "test_micro_command"}}}}}


def _removed_warnings(root):
    """The `L-SETTING-REMOVED` findings of `compass policy lint` on the project's
    `compass.yml`, by path, after checking it holds no error."""
    from compass_pkg import policy_cmd
    found = policy_cmd.settings_findings(str(root / "compass.yml"), str(root))
    errors = [f for f in found if f.level == "error"]
    assert errors == [], [(e.code, e.path, e.message) for e in errors]
    return {f.path: f.message for f in found if f.code == "L-SETTING-REMOVED"}


def test_a_project_readiness_block_and_commands_are_named_once_each(tmp_path):
    project = {"name": "demo", "test_command": "pytest -q",
               "test_micro_command": "pytest -q tests/test_one.py",
               **{field: "true" for field in READINESS_FIELDS}}
    root = _project(tmp_path, readiness=OVERRIDE, project=project)
    found = _removed_warnings(root)
    assert sorted(found) == sorted(["readiness"] + [f"project.{f}" for f in READINESS_FIELDS])
    for message in found.values():
        assert "removed in 9.0.0 (ADR-093)" in message, message
        # Nothing replaces a readiness key, and `compass migrate` deletes it
        # (ADR-098 decisions 6 and 7).
        assert message.endswith("Removed: nothing replaces it. `compass migrate` "
                                "rewrites it."), message
    assert "project.test_micro_command" not in found


def test_the_merge_drops_a_project_readiness_block_and_keeps_its_commands(tmp_path):
    from compass_pkg import effective, project_settings
    project = {"name": "demo", "test_micro_command": "pytest -q", "lint_command": "true",
               "secret_scan": "gitleaks"}
    root = _project(tmp_path, readiness=OVERRIDE, project=project)
    resolution = effective.resolve_live(str(root))
    # An empty catalogue is left out of the resolved configuration, as `artifacts` is.
    assert "readiness" not in resolution.resolved, resolution.resolved.get("readiness")
    assert "readiness" not in str(resolution.provenance)
    kept = project_settings.settings(str(root))["project"]
    assert kept["lint_command"] == "true" and kept["secret_scan"] == "gitleaks"
    assert kept["test_micro_command"] == "pytest -q"


def test_a_project_with_no_readiness_setting_gets_no_readiness_warning(tmp_path):
    root = _project(tmp_path, project={"name": "demo", "test_command": "pytest -q",
                                       "test_micro_command": "pytest -q"})
    assert _removed_warnings(root) == {}


# --- the readiness floor --------------------------------------------------------------

def test_an_autonomous_issue_is_assessed_with_no_readiness_record(tmp_path):
    root = _project(tmp_path, autonomy="autonomous")
    work = root / ".compass" / "work" / "change"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "3.0", "issue": "change", "created": "2026-11-06",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery", "labels": []},
        "evidence": []}, sort_keys=False), encoding="utf-8")
    assert not (root / ".compass" / "readiness.yml").exists()
    shown = _run(["approach", "evaluate", "--issue", "change", "--json"], root)
    assert shown.returncode == 0, shown.stderr
    assert "readiness" not in shown.stdout
    written = _run(["approach", "evaluate", "--issue", "change", "--write"], root)
    assert written.returncode == 0, written.stdout + written.stderr
    assert "readiness" not in written.stdout + written.stderr
    manifest = yaml.safe_load((work / "manifest.yml").read_text(encoding="utf-8"))
    assert "readiness" not in manifest
    assert manifest.get("delivery_approach")


# --- the session-start line -----------------------------------------------------------

def test_the_session_start_context_has_no_readiness_line(tmp_path):
    import json
    root = _project(tmp_path, autonomy="autonomous")
    contract = tmp_path / "contract.md"
    contract.write_text("# Contract\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "hooks" / "py" / "session_start_context.py"),
         str(contract), str(root / ".compass"), str(root), "{}"],
        env={"PYTHONPATH": str(ROOT / "cli"), "PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
        capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    assert proc.returncode == 0, proc.stderr
    context = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context.startswith("# Contract")
    assert "readiness" not in context.lower(), context
