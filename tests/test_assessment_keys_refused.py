"""An assessment key the manifest schema does not allow is refused early.

Three manifests held `risk_reason`, `familiarity_reason` and `size_reason`
under `assessment:`. `approach evaluate --write` copied them on and
`compass check` passed each issue to landing; only `issue lint`, which a
release runs, refused them (#399). Evaluate, check and lint now share one
check, so a manifest that cannot pass the release lint cannot land.

Scenario id: SK-1 (issue `evaluate-and-check-apply-the-schema`).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from test_quick_fix_verbs import _manifest_path, _run, _start, repo  # noqa: E402,F401


def _add_key(root, slug, key="risk_reason", value="a stray reason"):
    path = _manifest_path(root, slug)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["assessment"][key] = value
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_sk_1_evaluate_write_refuses_an_unknown_assessment_key(repo):
    assert _start(repo, "greeting-fix").returncode == 0
    _add_key(repo, "greeting-fix")
    before = _manifest_path(repo, "greeting-fix").read_text(encoding="utf-8")
    result = _run(repo, "approach", "evaluate", "--issue", "greeting-fix",
                  "--write")
    assert result.returncode != 0, result.stdout
    assert "risk_reason" in result.stderr
    assert "risk" in result.stderr and "familiarity" in result.stderr
    # Refused before writing: nothing was copied into evaluated_assessment.
    assert _manifest_path(repo, "greeting-fix").read_text(
        encoding="utf-8") == before


def test_sk_1_check_fails_on_an_unknown_assessment_key(repo):
    assert _start(repo, "greeting-fix").returncode == 0
    _add_key(repo, "greeting-fix")
    result = _run(repo, "check", "--issue", "greeting-fix")
    assert result.returncode != 0, result.stdout
    assert "risk_reason" in result.stdout + result.stderr


def test_sk_1_a_clean_assessment_still_evaluates(repo):
    assert _start(repo, "greeting-fix").returncode == 0
    result = _run(repo, "approach", "evaluate", "--issue", "greeting-fix",
                  "--write")
    assert result.returncode == 0, result.stderr


def test_sk_1_the_shared_check_needs_no_jsonschema():
    """The built-in check reads the allowed keys from the schema file with
    the standard library, so a project without jsonschema is covered too."""
    from compass_pkg.core import assessment_key_errors
    errs = assessment_key_errors({"risk": "trivial", "familiarity": "greenfield",
                                  "size": "atomic", "size_reason": "x"})
    assert len(errs) == 1 and "size_reason" in errs[0]
    assert assessment_key_errors({"risk": "trivial", "labels": []}) == []
