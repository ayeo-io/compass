"""A project can turn on an agent review, recorded as advisory evidence.

9.0.0 removed the reviewer agent as required evidence (ADR-090, and decision 6
of ayeo-io/compass-delivery#345). The shipped default declares no judged check,
so nothing changes for a project that does nothing. A project turns the review
on by putting the `compass.yml` block that `docs/judged-checks.md` gives under
"An agent review" into its own file: the judged check `agent-review`, advisory,
listed at the `ship` entry. Then:

- with no review record it shows as advisory and does not fail `compass check`;
- `compass evidence review agent-review --reviewer agent` writes the record, a
  `manual-review` entry, and the check passes;
- a person's record is set aside, because the check lists only `agent`.

Issue: ayeo-io/compass-delivery#352.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_generation_store import (SLUG, _evaluate_write, _project, _run,  # noqa: E402
                                   _write_manifest)

PRESET = ROOT / "governance" / "presets" / "default"
DOC = ROOT / "docs" / "judged-checks.md"
CHECK = "agent-review"
CRITERIA = "# Criteria\n\nGiven a, when b, then c.\n"


def _documented_block():
    """The `compass.yml` block the owning doc gives, parsed, so the test runs
    exactly what a reader copies."""
    text = DOC.read_text(encoding="utf-8")
    assert "## An agent review" in text, "docs/judged-checks.md has no agent review section"
    section = text.split("## An agent review", 1)[1].split("\n## ", 1)[0]
    block = section.split("```yaml\n", 1)[1].split("```", 1)[0]
    return yaml.safe_load(block)


def _turned_on():
    return {"schema": 1, **_documented_block()}


def _project_with_the_review(tmp_path, compass_yml=None):
    root, task_dir = _project(tmp_path, compass_yml=compass_yml or _turned_on())
    assert _evaluate_write(root)[0] == 0
    _write_manifest(task_dir, current_phase="ship")
    (task_dir / "acceptance-criteria.md").write_text(CRITERIA, encoding="utf-8")
    return root, task_dir


def _rows(root):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    return code, [r for r in json.loads(out)["checks"] if r["name"] == CHECK]


def _review(root, reviewer, verdict="pass"):
    return _run(root, "evidence", "review", CHECK, "--issue", SLUG, "--verdict", verdict,
                "--reason", "Read the change against each scenario.", "--reviewer", reviewer)


def test_the_documented_block_declares_the_agent_review_as_advisory():
    block = _documented_block()
    body = block["checks"][CHECK]
    assert block["stages"] == {"ship": {"set": {"entry": {"add": [CHECK]}}}}
    assert body["kind"] == "judged"
    assert body["severity"] == "advisory"
    assert body["reviewers"] == ["agent"]
    assert body["inputs"] == ["acceptance-criteria"]
    assert body["on_skipped"] == "not-applicable"


def test_the_shipped_default_has_no_agent_review():
    checks = yaml.safe_load((PRESET / "checks.yml").read_text(encoding="utf-8"))["checks"]
    assert CHECK not in checks


def test_a_project_that_does_not_turn_it_on_runs_no_agent_review(tmp_path):
    root, _ = _project_with_the_review(tmp_path, compass_yml={"schema": 1})
    assert _rows(root)[1] == []


def test_turned_on_with_no_record_it_is_advisory(tmp_path):
    root, _ = _project_with_the_review(tmp_path)
    _, rows = _rows(root)
    assert len(rows) == 1, rows
    assert rows[0]["status"] == "advisory", rows[0]
    assert "no review record" in rows[0]["detail"], rows[0]


def test_an_agent_record_is_manual_review_evidence_and_passes_the_check(tmp_path):
    root, task_dir = _project_with_the_review(tmp_path)
    code, out, err = _review(root, "agent")
    assert code == 0, out + err
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    entries = [e for e in manifest["evidence"] if e.get("check") == CHECK]
    assert len(entries) == 1 and entries[0]["type"] == "manual-review", entries
    _, rows = _rows(root)
    assert rows[0]["status"] == "pass", rows[0]


def test_a_failing_agent_review_stays_advisory(tmp_path):
    root, _ = _project_with_the_review(tmp_path)
    assert _review(root, "agent", verdict="fail")[0] == 0
    _, rows = _rows(root)
    assert rows[0]["status"] == "advisory" and "verdict is fail" in rows[0]["detail"]


def test_a_persons_record_does_not_clear_the_agent_review(tmp_path):
    root, _ = _project_with_the_review(tmp_path)
    assert _review(root, "jed72")[0] == 0
    _, rows = _rows(root)
    assert rows[0]["status"] == "advisory", rows[0]
