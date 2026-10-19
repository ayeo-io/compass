"""Text a person reads in a refusal or in the approver message must not carry a
hostile word's control characters, forged lines or unbounded length.

Scenario: `TRC-063`. Three leaks the adversarial review of issue
`hooks-stop-refusing-harmless-work` found:

- the reason the loader gives for a `compass.yml` it cannot read reaches the approver
  message unfiltered, so a key with an escape character and 600 characters made a
  message of 936 characters;
- the `--as` value of a refused delegated approval reaches the refusal with its escape
  character and a forged `Fix:` line;
- a refused word keeps format characters (such as U+202E) and is cut from the front, so
  a protected name after character 80 is not shown.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

from approval_guard_cases import (CALLER, REQ, bash_event, build_world,  # noqa: E402
                                  drop_world, run_hook, verdict)
from approval_support import event, project  # noqa: E402

HIDDEN = ("Cc", "Cf", "Zl", "Zp")


@pytest.fixture(scope="module")
def world():
    built = build_world()
    yield built
    drop_world(built)


def _hidden(text, allow=""):
    return [c for c in text if unicodedata.category(c) in HIDDEN and c not in allow]


def _refusal(result):
    return result.stderr[result.stderr.index("Blocked:"):]


def _plugin(tmp_path):
    root = tmp_path / "plugin"
    (root / "commands").mkdir(parents=True)
    for name in ("approve", "reject", "delegate", "revoke"):
        (root / "commands" / f"{name}.md").write_text(
            f"---\ndescription: {name}\ndisable-model-invocation: true\n---\n\nBody.\n",
            encoding="utf-8")
    return root


def test_trc_063_the_loader_reason_is_cleaned_and_cut(tmp_path):
    from compass_pkg import prompt_approval
    root, plugin = project(tmp_path), _plugin(tmp_path)
    key = "k\\x1b[31m\\u202e Fix: type /compass:delegate " + "A" * 600
    (root / "compass.yml").write_text(f'owner: jed72\n"{key}": 1\n', encoding="utf-8")
    result = prompt_approval.handle(event(root), {}, plugin_root=str(plugin))
    assert result.block, result
    message = result.message
    assert "cannot be read" in message, message
    assert not _hidden(message), repr(_hidden(message))
    assert "\nFix:" not in message and "A" * 121 not in message, message
    assert len(message) < 500, len(message)


def test_trc_063_the_as_value_of_a_refused_approval_is_cleaned_and_cut(world):
    hostile = "x\x1b[2J\nFix: type /compass:delegate " + "B" * 300
    command = f'compass evidence approve --check c --delegated --as "{hostile}"'
    result = run_hook(world, bash_event(world, command))
    assert verdict(result) == CALLER, result.stderr
    text = _refusal(result)
    assert not _hidden(text, allow="\n"), repr(_hidden(text, allow="\n"))
    assert sum(line.startswith("Fix:") for line in text.splitlines()) == 1, text
    assert "B" * 81 not in text, text


def test_trc_063_a_long_refused_word_shows_the_protected_part_and_no_format_character(world):
    word = "x" * 200 + "‮/.compass/work/issue-a/approval-requests/pending/1.yml"
    result = run_hook(world, bash_event(world, f"cat '{word}'"))
    assert verdict(result) == REQ, result.stderr
    text = _refusal(result)
    assert "approval-requests" in text, text
    assert not _hidden(text, allow="\n"), repr(_hidden(text, allow="\n"))
