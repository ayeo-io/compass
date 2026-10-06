"""One malformed manifest does not stop `compass retro`.

A manifest written as a YAML list crashed the whole report with
`AttributeError: 'list' object has no attribute 'get'`. `compass issue
lint` is where a malformed manifest is reported; retro skips it and says so.

Scenario id: RL-1 (issue `retro-skips-list-manifest`).
"""
from __future__ import annotations

from test_quick_fix_verbs import _run, _start, repo  # noqa: F401


def test_rl_1_retro_skips_a_list_manifest_and_names_it(repo):
    assert _start(repo, "good-fix").returncode == 0
    bad = repo / ".compass" / "work" / "bad-fix"
    bad.mkdir()
    (bad / "manifest.yml").write_text("- one\n- two\n")
    result = _run(repo, "retro")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "bad-fix" in result.stdout, result.stdout
    assert "Traceback" not in result.stderr, result.stderr
