"""A red record with no identity stops unlocking edits after a declared date.

The pre-tool hook unlocks a code edit when a red record sits beside the `.red`
marker. A record stamped by `compass tdd-red` carries a `content_digest`, and
the hook checks it. A record with no digest is "written before records carried
an identity" - or written by hand, as `{"passed": false}` can be.

A project declares `records_signed_since` in `.compass/config.yml`, and
`compass init` writes it. With it set, an unstamped record counts only if its
own timestamp is before that date. With it unset, nothing changes. One
function, `red_first.red_verdict`, gives the verdict for both the hook and
`suite-passed`.

Scenario ids: RIC-1 to RIC-8, in the acceptance criteria of the issue
`red-record-identity-cutoff`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

CUTOFF = "2026-09-24"
BEFORE = "2026-08-01T00:00:00+00:00"
AFTER = "2026-10-01T00:00:00+00:00"
SLUG = "cutoff-sample"


def _record(timestamp=AFTER, *, stamped=True, edited=False):
    payload = {"command": "pytest -q", "scenario": None, "exit_code": 1,
               "passed": False, "log_excerpt": "1 failed"}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    if stamped:
        payload["record_id"] = "fixture0000000000"
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    if edited:
        payload["exit_code"] = 2
    return payload


@pytest.fixture
def project():
    """A project whose path holds no "test", so the hook's test-file
    exemption does not fire on the edit target."""
    root = Path(tempfile.mkdtemp(prefix="compass-cut-"))
    task_dir = root / ".compass" / "work" / SLUG
    (task_dir / "evidence").mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(SLUG)
    (task_dir / "delivery-approach.md").write_text("# Approach\n")
    yield root, task_dir
    shutil.rmtree(root, ignore_errors=True)


def _config(root, cutoff):
    text = "version: 1.0.0\nmode: enforced\n"
    if cutoff:
        text += f"records_signed_since: '{cutoff}'\n"
    (root / ".compass" / "config.yml").write_text(text)


def _plant_red(task_dir, payload):
    (task_dir / "evidence" / "red.json").write_text(json.dumps(payload))
    (task_dir / ".red").write_text("")


def _hook(root):
    event = json.dumps({"tool_name": "Edit",
                        "tool_input": {"file_path": str(root / "src" / "app.py")}})
    return subprocess.run(["bash", str(HOOK)], input=event, capture_output=True,
                          text=True, timeout=120,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


@pytest.mark.parametrize("timestamp", [AFTER, CUTOFF + "T00:00:00+00:00", None])
def test_ric_1_an_unstamped_red_written_since_the_cutoff_does_not_unlock(
        project, timestamp):
    root, task_dir = project
    _config(root, CUTOFF)
    _plant_red(task_dir, _record(timestamp, stamped=False))
    result = _hook(root)
    assert result.returncode == 2, result.stderr
    text = " ".join(result.stderr.split())
    assert "carries no identity" in text
    assert f"records_signed_since: {CUTOFF}" in text


def test_ric_2_an_unstamped_red_written_before_the_cutoff_still_unlocks(project):
    root, task_dir = project
    _config(root, CUTOFF)
    _plant_red(task_dir, _record(BEFORE, stamped=False))
    result = _hook(root)
    assert result.returncode == 0, result.stderr


def test_ric_3_a_project_with_no_cutoff_behaves_as_today(project):
    root, task_dir = project
    _config(root, None)
    _plant_red(task_dir, _record(None, stamped=False))
    result = _hook(root)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("cutoff", [CUTOFF, None])
def test_ric_4_a_stamped_red_is_judged_by_its_digest(project, cutoff):
    root, task_dir = project
    _config(root, cutoff)
    _plant_red(task_dir, _record(AFTER))
    assert _hook(root).returncode == 0
    _plant_red(task_dir, _record(AFTER, edited=True))
    assert _hook(root).returncode == 2


def test_ric_5_compass_init_declares_the_cutoff(tmp_path):
    result = subprocess.run([sys.executable, str(CLI), "init"], cwd=tmp_path,
                            capture_output=True, text=True,
                            env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)})
    assert result.returncode == 0, result.stderr
    # The cutoff is state the CLI writes, so it lives in state.yml (ADR-043).
    config = (tmp_path / ".compass" / "state.yml").read_text()
    # Today or yesterday: the run can cross midnight between init and here.
    today = datetime.date.today()
    days = {today.isoformat(), (today - datetime.timedelta(days=1)).isoformat()}
    assert any(f"records_signed_since: '{d}'" in config for d in days), config


def test_ric_6_suite_passed_applies_the_same_identity_rule(project):
    from compass_pkg.checks import _check_suite_passed
    root, task_dir = project
    _config(root, CUTOFF)
    _plant_red(task_dir, _record(AFTER, stamped=False))
    (task_dir / "evidence" / "green.json").write_text(
        json.dumps({"exit_code": 0, "passed": True}))
    task = {"created": CUTOFF, "scenarios": [{"id": "S-1"}],
            "evidence": [{"id": "EV-T", "type": "test-run",
                          "path": "evidence/green.json"}]}
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is False, why
    _plant_red(task_dir, _record(AFTER))
    ok, why = _check_suite_passed(task, str(task_dir))
    assert ok is True, why


def test_ric_7_the_hook_has_no_identity_rule_of_its_own():
    text = HOOK.read_text(encoding="utf-8")
    assert "from compass_pkg.red_first import verdict_line" in text
    assert "hashlib" not in text, (
        "hooks/pre-tool.sh computes a digest itself; the identity rule must "
        "come from red_first alone")


def test_ric_8_the_safety_contract_states_the_cutoff():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "records_signed_since" in text
    assert "are accepted without a digest check. Refusing them" not in text


# ---------------------------------------------------------------------------
# Review findings: the reader must fail closed, and the refusal must name the
# date the reader applied.
# ---------------------------------------------------------------------------

@pytest.fixture
def install():
    """A copy of the hook, its shell helper and the CLI package, so the red
    reader can be broken without touching the working tree. The path holds no
    "test", so the hook's test-file exemption does not fire."""
    root = Path(tempfile.mkdtemp(prefix="compass-inst-"))
    for part in ("hooks", "scripts", "cli"):
        shutil.copytree(ROOT / part, root / part,
                        ignore=shutil.ignore_patterns("__pycache__"))
    task_dir = root / ".compass" / "work" / SLUG
    (task_dir / "evidence").mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(SLUG)
    (task_dir / "delivery-approach.md").write_text("# Approach\n")
    yield root, task_dir
    shutil.rmtree(root, ignore_errors=True)


def _hook_at(root):
    event = json.dumps({"tool_name": "Edit",
                        "tool_input": {"file_path": str(root / "src" / "app.py")}})
    return subprocess.run(["bash", str(root / "hooks" / "pre-tool.sh")],
                          input=event, capture_output=True, text=True,
                          timeout=120,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


def test_ric_1_a_reader_that_crashes_refuses_with_a_reason(install):
    """Exit 1 from the hook is a non-blocking error: the runtime lets the edit
    through. A reader that cannot run must end in exit 2 and say so."""
    root, task_dir = install
    _config(root, CUTOFF)
    _plant_red(task_dir, _record(AFTER))
    reader = root / "cli" / "compass_pkg" / "red_first.py"
    reader.write_text("raise RuntimeError('broken install')\n")
    result = _hook_at(root)
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert "red-record reader could not run" in " ".join(result.stderr.split())


@pytest.mark.parametrize("line", [
    "records_signed_since : 2026-09-24",
    "'records_signed_since': '2026-09-24'",
    "records_signed_since: 2026-09-24  # set by init",
])
def test_ric_1_the_refusal_names_the_date_the_reader_applied(project, line):
    root, task_dir = project
    (root / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n" + line + "\n")
    _plant_red(task_dir, _record(AFTER, stamped=False))
    result = _hook(root)
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert f"records_signed_since: {CUTOFF}" in " ".join(result.stderr.split())


def test_ric_1_a_config_that_does_not_parse_keeps_the_cutoff(project):
    """A broken config must not turn the cutoff off without a word."""
    root, task_dir = project
    (root / ".compass" / "config.yml").write_text(
        "records_signed_since: [unclosed\n")
    _plant_red(task_dir, _record(AFTER, stamped=False))
    assert _hook(root).returncode == 2


@pytest.mark.parametrize("extra", [{"record_id": "x"}, {"content_digest": ""}])
def test_ric_1_the_refusal_describes_the_record_it_found(project, extra):
    root, task_dir = project
    _config(root, CUTOFF)
    _plant_red(task_dir, dict(_record(AFTER, stamped=False), **extra))
    result = _hook(root)
    assert result.returncode == 2
    assert "has neither" not in result.stderr
    assert "no content_digest" in " ".join(result.stderr.split())


def test_ric_6_the_cutoff_comes_from_the_project_the_caller_names(tmp_path):
    """The hook resolves the project first; the reader must use that
    project's config, not whatever `.compass/` sits above the issue."""
    from compass_pkg.red_first import signed_since
    named = tmp_path / "named" / ".compass"
    named.mkdir(parents=True)
    (named / "config.yml").write_text(f"records_signed_since: '{CUTOFF}'\n")
    elsewhere = tmp_path / "elsewhere" / "issue"
    elsewhere.mkdir(parents=True)
    assert signed_since(str(elsewhere), compass_dir=str(named)) == \
        datetime.date.fromisoformat(CUTOFF)
