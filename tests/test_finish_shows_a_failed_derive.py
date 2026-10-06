"""`compass quick-fix finish` says when the living spec was not re-derived.

Landing re-derives the living spec. The derive refuses when the committed
spec names a landed issue whose records are not in this checkout, because
re-deriving would drop that issue's scenarios. `ship-commit` reports the
refusal, but finish showed only the last line of its output and printed
"shipped", so the issue stayed out of the spec without a word.

Scenario id: `TRC-001` (issue `finish-shows-a-failed-derive`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_quick_fix_verbs import (  # noqa: E402
    _finish, _git, _ready_to_finish, repo,  # noqa: F401
)


def test_trc_001_finish_names_a_failed_spec_derive(repo):
    # The committed spec names an issue landed elsewhere, whose records this
    # checkout does not hold.
    docs = repo / "docs"
    docs.mkdir()
    (docs / "system-spec.md").write_text(
        "# System spec\n\n- **Source issue:** `landed-elsewhere`\n", encoding="utf-8")
    _git(repo, "add", "docs/system-spec.md")
    _git(repo, "commit", "-q", "-m", "spec from main")

    _ready_to_finish(repo, "greet-fix")
    done = _finish(repo, "greet-fix")
    assert done.returncode == 0, done.stdout + done.stderr
    out = done.stdout + done.stderr
    assert "living spec NOT re-derived" in out, out
    assert "landed-elsewhere" in out, out
    assert "compass issue refresh-spec" in out, out
