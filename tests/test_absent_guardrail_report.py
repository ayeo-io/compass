"""A guardrail that does not apply reads as skipped (governance-drift-detection).

9.0.0 reads no copy of `guardrails.yml` (ADR-098), so no project can omit a
shipped guardrail, and the ABSENT report of `TRC-D1` went with the copy. The
history below is why `TRC-D2` exists.

`compass check` gives two guarantees: a guardrail that is ABSENT from the
project's own governance file is reported in the default view, and a
guardrail that genuinely does not apply reads as skipped only under
--verbose. Reproduced: on an issue whose touches list names `auth`, against a
guardrails.yml with `G5` (a human signs off on anything irreversible) removed,
`compass check` printed `G1` through `G4` (the other default checks) and
returned its normal result. Not an ambiguous label - silence, on the exact
surface `G5` exists to guard.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-D1`, `TRC-D2`).
"""

# These tests assert the default view, because the adoption-mode banner and
# the absent-guardrail warning must appear on the first screen.
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"

TASK = """schema_version: '1.1'
task: t
created: '2026-08-03'
status: active
readings:
  blast_radius: contained
  terrain: greenfield
  magnitude: small
  intent: delivery
  urgency: none
  role: engineer
  touches: [{touches}]
route: standard
topology: solo
fired_guardrails: []
phases: {{}}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
backfills: []
reframes: []
friction: []
"""


def _project(tmp_path, *, touches=""):
    proj = tmp_path / "proj"
    (proj / ".compass" / "work" / "t").mkdir(parents=True)
    shutil.copytree(GOVERNANCE, proj / "governance")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (proj / ".compass" / "work" / "t" / "manifest.yml").write_text(
        TASK.format(touches=touches))
    (proj / ".compass" / "current-task").write_text("t\n")
    return proj


def _check(proj, *flags):
    """`compass check`, in the mode the caller asks for.

    The two tests below want different views, and that difference is the point.
    A guardrail this project's governance OMITS is a warning that belongs on
    the first screen - the default view. A guardrail that genuinely does not
    apply to this assessment is detail, and belongs under --verbose.
    """
    return subprocess.run(
        [sys.executable, str(CLI), "check", "--issue", "t", *flags],
        cwd=str(proj), capture_output=True, text=True, timeout=120,
    ).stdout


# ---------------------------------------------------------------------------
# `TRC-D2` - a guardrail that genuinely does not apply still reads as skipped
# ---------------------------------------------------------------------------

def test_trc_d2_a_guardrail_that_genuinely_does_not_apply_should_still_read_as_skipped():
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compass-skip-"))
    try:
        out = _check(_project(tmp, touches=""), "--verbose")
        assert "G5" in out, f"G5 is not reported at all:\n{out}"
        g5_line = next(l for l in out.splitlines() if "G5" in l)
        assert "not applicable" in g5_line.lower(), (
            f"a guardrail that genuinely does not apply no longer reads as "
            f"skipped:\n{g5_line}")
        assert "absent" not in g5_line.lower(), (
            f"a present-but-inapplicable guardrail is being called absent - the "
            f"fix has overshot:\n{g5_line}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
