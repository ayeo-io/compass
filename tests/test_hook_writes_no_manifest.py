"""The pre-tool hook writes no manifest, and judges each call as it did when it
recorded sessions.

Before 9.0.0 the hook added each session id to the issue's `usage.sessions`.
9.0.0 removed that record (ADR-093), so the hook now only reads. Its allow and
deny decisions must not move: a document write is allowed and a code edit
before the scenarios is refused, with the same text, whatever session id the
call carries. A manifest that holds a `usage` block from before 9.0.0 still
reads and lints as one without it, and the `prices` setting that priced that
block is a removed setting.

GitHub is off and a `gh` on PATH fails the test if anything calls it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(HERE))

import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first

import test_issue_dependencies as dbi  # noqa: E402

HOOK = ROOT / "hooks" / "pre-tool.sh"
#: The hook's judgements captured when it still recorded sessions.
BASE = HERE / "fixtures" / "autonomy-ratio-and-cost" / "base-hook-judgements.json"
LOCK = ".manifest.lock"

#: A usage block of the shape `compass ship-commit` wrote before 9.0.0.
OLD_USAGE = {
    "sessions": ["sess-1"], "source": "claude-code", "skipped_lines": 0,
    "total": {"requests": 8, "subagent_requests": 0, "input": 1, "output": 1,
              "cache_write": 1, "cache_read": 1, "cost_usd": 4.25},
    "unattributed": {"requests": 1, "subagent_requests": 0, "input": 1, "output": 1,
                     "cache_write": 1, "cache_read": 1, "cost_usd": 0.5},
    "stages": {"define": {"requests": 3, "subagent_requests": 0, "input": 1, "output": 1,
                          "cache_write": 1, "cache_read": 1, "cost_usd": 1.5},
               "implement": {"measured": False, "reason": "no-window"}},
}


def hook_call(root, tool, target, session=None):
    """Run the pre-tool hook on one tool call, as Claude Code does."""
    env = dbi.env_for(root, CLAUDE_PROJECT_DIR=str(root))
    event = {"tool_name": tool, "tool_input": {"file_path": str(target)}}
    if session is not None:
        event["session_id"] = session
    return subprocess.run(["bash", str(HOOK)], input=json.dumps(event),
                          capture_output=True, text=True, env=env, timeout=120)


def document(root, slug="a"):
    return Path(root) / "docs" / "compass" / f"2026-10-01-{slug}" / "acceptance-criteria.md"


def hook_project(root, slugs=("a",)):
    """A project whose issues sit at define, the first named by the pointer."""
    project = dbi.Project(root)
    for slug in slugs:
        project.issue(slug, "define")
    (project.root / ".compass" / "current-task").write_text(slugs[0] + "\n")
    return project


def _masked(text, root):
    for form in {str(root), os.path.realpath(root)}:
        text = text.replace(form, "<root>")
    return text


def _folder(project, slug):
    folder = project.dir(slug)
    return {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def judgements(tmp_path, sessions):
    """The hook's exit code and refusal for a document write and a code edit,
    for each session id, and a check that no call changed the issue folder."""
    found = {}
    for session in sessions:
        project = hook_project(Path(tmp_path) / f"s-{session}".replace("/", "_"))
        before = _folder(project, "a")
        for name, tool, target in (("document", "Write", document(project.root)),
                                   ("code", "Edit", dbi.code_file(project))):
            done = hook_call(project.root, tool, target, session)
            found[f"{name}, session {session}"] = {
                "exit": done.returncode, "stderr": _masked(done.stderr, project.root)}
        assert _folder(project, "a") == before, session
        assert not (project.dir("a") / LOCK).exists(), session
        dbi.assert_no_gh_call(project.root)
    return found


def test_the_hook_judges_every_call_as_the_session_record_did(tmp_path):
    base = json.loads(BASE.read_text(encoding="utf-8"))
    assert judgements(tmp_path / "base", ("../x", None)) == base
    # A valid session id was recorded before 9.0.0; it is now judged as a call
    # with no session id is.
    valid = judgements(tmp_path / "valid", ("S1",))
    assert valid == {key.replace("session None", "session S1"): value
                     for key, value in base.items() if key.endswith("session None")}


def test_the_hook_writes_no_manifest(tmp_path):
    project = hook_project(tmp_path / "p", slugs=("a", "b"))
    before = {slug: _folder(project, slug) for slug in ("a", "b")}
    for session in ("S1", "S2", "S1"):
        assert hook_call(project.root, "Write", document(project.root), session).returncode == 0
        assert hook_call(project.root, "Edit", dbi.code_file(project), session).returncode == 2
    assert {slug: _folder(project, slug) for slug in ("a", "b")} == before
    assert "usage" not in project.manifest("a")
    dbi.assert_no_gh_call(project.root)


def test_a_manifest_with_an_old_usage_block_reads_and_lints_as_before(tmp_path):
    with_usage = hook_project(tmp_path / "with")
    without = hook_project(tmp_path / "without")
    body = with_usage.manifest("a")
    body["usage"] = OLD_USAGE
    with_usage.write("a", body)

    def outputs(project):
        out = {}
        # Diagnose runs first: a failed `compass check` dates a line in
        # .compass/interruptions.log, which the diagnose timeline shows.
        for args in (("issue", "diagnose", "--issue", "a"), ("issue", "lint", "--issue", "a"),
                     ("check", "--issue", "a")):
            done = dbi.compass(project.root, *args)
            out[" ".join(args[:-2])] = (done.returncode,
                                        _masked(done.stdout, project.root),
                                        _masked(done.stderr, project.root))
        return out

    old, plain = outputs(with_usage), outputs(without)
    assert old == plain
    assert old["issue lint"][0] == 0, old["issue lint"]
    assert "usage" not in old["issue lint"][1] + old["issue lint"][2]
    assert with_usage.manifest("a")["usage"] == OLD_USAGE


def test_the_prices_setting_is_removed_and_lint_names_it():
    """`prices` priced the usage block, which 9.0.0 no longer writes. The key
    stays valid, nothing reads it, and lint warns once."""
    from compass_pkg import check_set, removed_parts, settings_lint
    assert removed_parts.SETTINGS["prices"][1] == "ADR-093"
    findings = settings_lint.lint({"schema": 1, "prices": {"model-a": {"input": 3.0}}},
                                  check_set.resolved())
    found = [f for f in findings if f.code == "L-SETTING-REMOVED"]
    assert len(found) == 1, [(f.code, f.path) for f in findings]
    assert found[0].level == "warning" and found[0].path == "prices"
    assert "removed in 9.0.0" in found[0].message and "ADR-093" in found[0].message
    assert not [f for f in findings if f.level == "error"], findings
