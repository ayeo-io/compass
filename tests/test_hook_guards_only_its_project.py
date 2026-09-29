"""The pre-tool hook guards the project it is for, and nothing else.

Reported from the field (GitHub #57, filed against 2.0.0 and reproduced on
3.1.1). `is_enforced_path()` classified a path by extension and glob but never
checked the path was inside the project. The project-relative path is computed
only when the target happens to be under `PROJECT_DIR`; anywhere else `rel`
stayed absolute, and the extension rules fired regardless.

So any `.py`, `.ts` or `.go` file anywhere on the machine was treated as this
project's production code - a scratch file in a session temp directory, a
throwaway script in a detached worktree. Neither can reach `main` by any path.

The friction is not the point. The refusal told the author to write a failing
test or re-run assessment as a spike. For a file outside the project neither
is a coherent action. The only ways forward were to bypass the hook or
abandon the work. A guardrail issuing unactionable instructions teaches
people to look for the bypass, which is the behaviour it exists to prevent.

Scenario ids: see field-feedback-hook-scope-and-restage/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _project(tmp_path):
    """A project with an active issue and NO failing test on record."""
    root = tmp_path / "proj"
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "current-task").write_text("demo\n")
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: demo\ncreated: "2026-08-14"\n'
        'status: active\ndelivery_approach: feature\n'
        'assessment:\n  risk: contained\n  familiarity: brownfield-mapped\n'
        '  size: small\n  goal: delivery\n  role: engineer\n  labels: []\n')
    (work / "delivery-approach.md").write_text("# Delivery approach\n")
    (work / "acceptance-criteria.md").write_text("# Acceptance criteria\n")
    return root


def _hook(root, target):
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": str(target),
                                         "content": "x = 1\n"}})
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True,
        cwd=str(root), timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "HOME": str(root), "CLAUDE_PROJECT_DIR": str(root)})


def test_ff_1_outside_the_project_is_allowed(tmp_path):
    root = _project(tmp_path)
    outside = tmp_path / "elsewhere" / "scratch_probe.py"
    outside.parent.mkdir(parents=True)

    r = _hook(root, outside)

    assert r.returncode == 0, (
        f"the hook blocked a file outside the project it governs "
        f"({outside}). It cannot reach main by any path, and the advice the "
        f"refusal gives is not actionable for it:\n{r.stdout}{r.stderr}")


def test_ff_2_inside_the_project_is_still_blocked(tmp_path):
    """The control.

    Without it, a containment check that answered "not ours" for everything
    would satisfy the outside-the-project scenario while switching
    enforcement off completely.
    """
    root = _project(tmp_path)
    inside = root / "src" / "app.py"
    inside.parent.mkdir(parents=True)

    r = _hook(root, inside)

    assert r.returncode == 2, (
        f"the hook allowed production code inside the project with no failing "
        f"test on record - red-before-green is no longer enforced anywhere:\n"
        f"{r.stdout}{r.stderr}")
    # Wording changed under `refusal-template`: refusals now open with
    # "Blocked:", not "Compass: BLOCKED -" (RTP-1's three-line shape).
    assert "Blocked:" in (r.stdout + r.stderr)


def test_ff_2b_a_relative_path_is_still_guarded(tmp_path):
    """The second control, and the reason the fix resolves before comparing.

    A Bash redirect (`echo x > src/app.py`) yields a RELATIVE path. Comparing
    that against an absolute project directory answers "outside", so the
    obvious one-line containment check would have switched enforcement off for
    every redirect - the exact write the hook exists to catch.
    """
    root = _project(tmp_path)
    (root / "src").mkdir()

    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": "src/app.py",
                                         "content": "x = 1\n"}})
    r = subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True,
        cwd=str(root), timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "HOME": str(root), "CLAUDE_PROJECT_DIR": str(root)})

    assert r.returncode == 2, (
        f"a relative path inside the project was allowed - the containment "
        f"check compared it without resolving it first:\n{r.stdout}{r.stderr}")
