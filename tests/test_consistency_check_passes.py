"""The consistency-check-passes check fails on findings and passes on none.

It is the one shipped check that had no test feeding it a broken input, so
it had no mutation proof on record (`tests/mutation_proofs.yml`). The pair
below is that proof: the same issue fails with findings or no evidence, and
passes once the evidence records zero findings.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.checks import _check_coherence_check_passes  # noqa: E402


def _issue(tmp_path, findings):
    task = {"gates": [{"id": "verify.analyze", "status": "pending"}],
            "evidence": []}
    if findings is not None:
        (tmp_path / "analyze.json").write_text(
            json.dumps({"finding_count": findings}), encoding="utf-8")
        task["evidence"].append({"id": "EV-AN", "type": "consistency-check",
                                 "path": "analyze.json"})
    return task


def test_findings_or_no_evidence_fail_the_check(tmp_path):
    ok, detail = _check_coherence_check_passes(_issue(tmp_path, 2), str(tmp_path))
    assert ok is False and "2 finding" in detail
    ok, detail = _check_coherence_check_passes(_issue(tmp_path, None), str(tmp_path))
    assert ok is False and "no consistency-check evidence" in detail


def test_zero_findings_pass_the_check(tmp_path):
    ok, _ = _check_coherence_check_passes(_issue(tmp_path, 0), str(tmp_path))
    assert ok is True
