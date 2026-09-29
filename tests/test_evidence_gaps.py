"""The evidence chain is as strong as the documents say it is.

Four rules these tests hold:

- `compass tdd-green --scenario X` refuses when X has no red on record, and
  must not print "red -> green is on record" with zero red records on disk.
- An empty `.red` file - a bare `touch` - must not take the hook from exit 2
  to exit 0 and unlock every production file for the issue.
- The hook refuses on manifest-reader exit 3 and must not fall through on
  another non-zero status such as an ImportError (exit 1) and pass the
  acceptance check silently.
- `stop.sh` must degrade rather than exit 127 without python3.

Scenario ids: EVG-A1..A3, B1..B3, C1..C3, D1, D2 in
evidence-gaps/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
PRE_TOOL = ROOT / "hooks" / "pre-tool.sh"
STOP = ROOT / "hooks" / "stop.sh"
CONTRACT = ROOT / "docs" / "safety-contract.md"

ALLOW, BLOCK = 0, 2

SPINE = """schema_version: '2.0'
task: demo
created: '2026-08-27'
status: active
assessment: {{risk: contained, familiarity: brownfield-mapped, size: atomic, goal: delivery, role: engineer}}
delivery_approach: feature
stages: {{assess: full, define: {define}, refine: light, plan: full, breakdown: solo-or-pair, implement: full, verify: full, ship: full}}
scenarios: []
evidence: []
gates: []
changed_files: []
"""


def _project(tmp_path, *, define="light"):
    root = (tmp_path / "proj").resolve()
    d = root / ".compass" / "work" / "demo"
    d.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "current-task").write_text("demo\n")
    (d / "manifest.yml").write_text(SPINE.format(define=define))
    (d / "delivery-approach.md").write_text("# approach\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "src").mkdir()
    target = root / "src" / "widget.py"
    target.write_text("print(1)\n")
    return root, d, target


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(root),
                          capture_output=True, text=True, timeout=120)


def _shim(tmp_path, code):
    d = tmp_path / f"shim{code}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "python3"
    p.write_text(f"#!/bin/sh\nexit {code}\n")
    p.chmod(0o755)
    return d


def _hook(root, target, *, path_prefix=None, hook=PRE_TOOL):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    if path_prefix:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    payload = {"tool_name": "Edit",
               "tool_input": {"file_path": str(target),
                              "old_string": "print(1)", "new_string": "print(2)"}}
    return subprocess.run(["bash", str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env,
                          cwd=str(root), timeout=60)


# ---------------------------------------------------------------------------
# EVG-A1..A3 - a bound green needs a red
# ---------------------------------------------------------------------------

def test_evg_a1_a_bound_green_needs_a_red_for_the_same_binding(tmp_path):
    root, work, _ = _project(tmp_path)

    r = _cli(root, "tdd-green", "--issue", "demo", "--scenario", "DEMO-1",
             "--", "true")
    out = (r.stdout + r.stderr)

    assert r.returncode != 0, (
        "a green was recorded for a scenario with no red on record, and the "
        f"output claimed 'red -> green is on record':\n{out}")
    assert "DEMO-1" in out, f"the refusal does not name the scenario:\n{out}"
    assert not list((work / "evidence").glob("green-DEMO-1*")), (
        "the refused green was written anyway")


def test_evg_a1b_the_refusal_does_not_claim_a_red_happened(tmp_path):
    """The refusal must not say a red happened."""
    root, _, _ = _project(tmp_path)
    r = _cli(root, "tdd-green", "--issue", "demo", "--scenario", "DEMO-1",
             "--", "true")
    out = (r.stdout + r.stderr).lower()
    assert "red -> green is on record" not in out, (
        "the output still says a red is on record when none is")


def test_evg_a2_an_unbound_green_is_unaffected(tmp_path):
    """A run with no --scenario never claimed a binding, so it has no red to
    match. Requiring one would break every honest unbound run."""
    root, work, _ = _project(tmp_path)

    r = _cli(root, "tdd-green", "--issue", "demo", "--", "true")
    out = (r.stdout + r.stderr)

    assert r.returncode == 0, f"an unbound green was refused:\n{out}"
    assert (work / "evidence" / "green.json").is_file(), out


def test_evg_a3_a_green_after_its_own_red_still_works(tmp_path):
    """The ordinary cycle must be untouched."""
    root, work, _ = _project(tmp_path)

    red = _cli(root, "tdd-red", "--issue", "demo", "--scenario", "DEMO-1",
               "--", "sh", "-c", "echo '1 failed'; exit 1")
    assert red.returncode == 0, (red.stdout + red.stderr)
    assert (work / "evidence" / "red-DEMO-1.json").is_file()

    green = _cli(root, "tdd-green", "--issue", "demo", "--scenario", "DEMO-1",
                 "--", "true")
    assert green.returncode == 0, (green.stdout + green.stderr)
    assert (work / "evidence" / "green-DEMO-1.json").is_file()
    assert not (work / ".red").exists(), "the .red marker was not cleared"


def test_evg_a3b_a_red_for_another_scenario_does_not_satisfy_the_green(tmp_path):
    """The subtler error the loose rule would allow.

    "Any red on this issue" lets a red recorded for one scenario clear a green
    for another - the same class of error as a green with no red, one step
    quieter.
    """
    root, _, _ = _project(tmp_path)
    _cli(root, "tdd-red", "--issue", "demo", "--scenario", "OTHER-1", "--", "sh", "-c", "echo '1 failed'; exit 1")

    r = _cli(root, "tdd-green", "--issue", "demo", "--scenario", "DEMO-1",
             "--", "true")
    assert r.returncode != 0, (
        "a red recorded for OTHER-1 cleared a green bound to DEMO-1:\n"
        + r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# EVG-B1..B3 - the hook reads the record
# ---------------------------------------------------------------------------

def test_evg_b1_an_empty_marker_does_not_unlock_the_edit(tmp_path):
    root, work, target = _project(tmp_path)
    (work / ".red").write_text("")            # what a bare `touch` leaves

    r = _hook(root, target)
    out = (r.stdout + r.stderr)

    assert r.returncode == BLOCK, (
        "an empty .red file unlocked every production file for the issue - "
        f"`touch` is not evidence:\n{out}")
    assert "record" in out.lower(), (
        f"the refusal does not say the marker has no record behind it:\n{out}")


def test_evg_b2_a_real_red_still_unlocks_the_edit(tmp_path):
    root, _, target = _project(tmp_path)
    red = _cli(root, "tdd-red", "--issue", "demo", "--scenario", "DEMO-1",
               "--", "sh", "-c", "echo '1 failed'; exit 1")
    assert red.returncode == 0, (red.stdout + red.stderr)

    r = _hook(root, target)
    assert r.returncode == ALLOW, (
        "a genuine recorded failure did not unlock the edit:\n"
        + r.stdout + r.stderr)


def test_evg_b3_an_edited_record_does_not_unlock_the_edit(tmp_path):
    """Tamper evidence, not forgery resistance - the digest detects edits;
    it does not resist forgery.

    The digest is a plain sha256 with no secret, so a record written from
    scratch with a matching digest still passes. What this catches is a record
    edited after it was written.
    """
    root, work, target = _project(tmp_path)
    _cli(root, "tdd-red", "--issue", "demo", "--scenario", "DEMO-1", "--", "sh", "-c", "echo '1 failed'; exit 1")

    record = work / "evidence" / "red-DEMO-1.json"
    doc = json.loads(record.read_text())
    doc["exit_code"] = 0                       # edited; digest now stale
    doc["passed"] = True
    record.write_text(json.dumps(doc, indent=2))

    r = _hook(root, target)
    assert r.returncode == BLOCK, (
        "a red record edited after it was written still unlocked the edit:\n"
        + r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# EVG-C1..C3 - a Compass that cannot check refuses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", [1, 2, 127])
def test_evg_c1_every_reader_failure_refuses(tmp_path, code):
    """The fail-open, and where it actually lives.

    Only reachable where the acceptance check is the one that would refuse: a
    project with a red on record and no scenarios. With no red the later check
    refuses first and hides it.
    """
    root, work, target = _project(tmp_path, define="full")
    _cli(root, "tdd-red", "--issue", "demo", "--scenario", "DEMO-1", "--", "sh", "-c", "echo '1 failed'; exit 1")

    r = _hook(root, target, path_prefix=str(_shim(tmp_path, code)))
    out = (r.stdout + r.stderr)

    assert r.returncode == BLOCK, (
        f"the manifest reader exited {code} and the hook allowed the edit "
        f"silently. A guardrail that cannot read its own state must fail "
        f"closed:\n{out}")
    assert out.strip(), "the hook refused without saying why"


def test_evg_c1b_exit_three_keeps_its_own_message(tmp_path):
    """Exit 3 names a broken install, which is more useful than a generic
    sentence."""
    root, _, target = _project(tmp_path, define="full")
    _cli(root, "tdd-red", "--issue", "demo", "--scenario", "DEMO-1", "--", "sh", "-c", "echo '1 failed'; exit 1")

    r = _hook(root, target, path_prefix=str(_shim(tmp_path, 3)))
    out = (r.stdout + r.stderr).lower()

    assert r.returncode == BLOCK
    assert "install" in out or "could not run" in out, (
        f"exit 3 lost its specific message:\n{out}")


def test_evg_c2_a_healthy_install_is_unchanged(tmp_path):
    """Every change here makes a broken install refuse. None must change a
    working one."""
    root, _, target = _project(tmp_path)
    _cli(root, "tdd-red", "--issue", "demo", "--scenario", "DEMO-1", "--", "sh", "-c", "echo '1 failed'; exit 1")

    r = _hook(root, target)
    assert r.returncode == ALLOW, (
        "a healthy install with a genuine red now refuses, which is a "
        "regression, not a fix:\n" + r.stdout + r.stderr)


def test_evg_c3_the_stop_hook_degrades_rather_than_crashing(tmp_path):
    """A warner that cannot read has nothing to warn about.

    Note the asymmetry with the pre-tool hook, which is deliberate: a hook
    that cannot check must not permit; a warner that cannot read must not
    crash. Same missing interpreter, opposite correct answers.
    """
    root, _, _ = _project(tmp_path)
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env["PATH"] = f"{_shim(tmp_path, 127)}:{env['PATH']}"

    r = subprocess.run(["bash", str(STOP)], input="{}", capture_output=True,
                       text=True, env=env, cwd=str(root), timeout=60)

    assert r.returncode == 0, (
        f"the stop hook exited {r.returncode} because python3 could not run. "
        "It is a warner - it must degrade, not crash:\n" + r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# EVG-D1 / D2 - the contract says both halves
# ---------------------------------------------------------------------------

def test_evg_d1_the_contract_says_the_hook_reads_the_record():
    text = CONTRACT.read_text(encoding="utf-8").lower()
    assert "red record" in text or "evidence/red" in text, (
        "docs/safety-contract.md does not say the hook reads a record rather "
        "than trusting a marker file's existence")


def test_evg_d2_the_contract_states_the_limit_too():
    """Claiming only the fix would be the failure this issue exists to close."""
    text = " ".join(CONTRACT.read_text(encoding="utf-8").split()).lower()
    assert "by hand" in text or "deliberate" in text, (
        "docs/safety-contract.md claims the record check without saying a "
        "record can still be written by hand with a matching digest. The "
        "digest is a plain sha256 with no secret: it is tamper evidence, not "
        "forgery resistance.")
