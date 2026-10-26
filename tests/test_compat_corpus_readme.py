"""The recorded command corpus keeps its pins; one dated entry says why one moved.

The scenario that keeps the recorded pins (`TRC-057`) of the issue
`language-key-and-us-english`. The file name is the one in the manifest; the
corpus holds no README.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml
from hook_text import hook_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CORPUS = "tests/fixtures/compat"
PIN_FILE = CORPUS + "/contract-4-commands.yml"


def _recorded(path=PIN_FILE):
    """The same file as it stands on the base branch, or None without one."""
    for ref in ("origin/main", "main"):
        done = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=ROOT,
                              capture_output=True, text=True)
        if done.returncode == 0:
            return done.stdout
    return None


def _entries(text):
    return {e["id"]: e for e in yaml.safe_load(text)["entries"]}


def test_trc_057():
    now_text = (ROOT / PIN_FILE).read_text(encoding="utf-8")
    now = _entries(now_text)
    assert now["init-fresh"]["stdout_contains"] == "initialized Compass"
    # One dated comment block above the entry names this issue.
    head = now_text.split("- id: init-fresh")[0].rstrip().splitlines()
    block = []
    for line in reversed(head):
        if not line.startswith("#"):
            break
        block.append(line)
    comment = " ".join(reversed(block))
    assert "2026-10-19" in comment and "language-key-and-us-english" in comment
    # No other pin moved, no map that accepts either spelling, no README.
    recorded = _recorded()
    if recorded is not None:
        then = _entries(recorded)
        assert set(then) == set(now)
        for name, entry in then.items():
            if name == "init-fresh":
                assert entry["exit"] == now[name]["exit"]
                continue
            assert now[name] == entry, name
    assert now_text.count("stdout_contains: \"initialized Compass\"") == 1
    assert list((ROOT / CORPUS).rglob("README*")) == []
    # The refusal-code pins of the hook corpus are as recorded 5.6.0 output.
    hook_path = CORPUS + "/contract-5-hook.yml"
    hook = hook_text(ROOT / hook_path)
    assert "code: not-initialised" in hook and "code: not-initialized" not in hook
    base_hook = _recorded(hook_path)
    if base_hook is not None:
        assert hook == base_hook
