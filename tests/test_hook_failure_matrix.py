"""One failure rule for the pre-tool hook: the checks no client observes.

Inside an opted-in project, any enforcement check that cannot run exits 2 with
a message naming what could not run. The scenarios a client observes - each
reader that cannot run, a missing python3, a settings file that does not
parse, a missing approach record, a temporary file that cannot be made, a
missing helper - are executable specifications in
`tests/acceptance/hooks/test_hook_refusals.py`, run through both the Claude
Code and the Codex hook clients (ayeo-io/compass-delivery#306).

What stays here reads text a client never sees: the safety contract (HFM-5)
and the hooks' source (HFM-6).

Scenario ids: HFM-1 to HFM-6, in the acceptance criteria of the issue
`hook-failure-matrix`.
"""
from __future__ import annotations

import re
from pathlib import Path

from hook_text import hook_sources  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_hfm_5_the_safety_contract_scopes_the_worktree_redirect_gap():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split()).lower()
    assert "inside a worktree" in text
    assert "the session's issue" in text


def test_hfm_5_the_contract_names_the_absolute_path_gap():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "absolute path" in text
    assert "outside the project" in text


RETIRED = [
    (re.compile(r"\btriage\b", re.I), "triage"),
    (re.compile(r"MultiEdit"), "MultiEdit"),
    (re.compile(r"\bspecify: full\b"), "specify: full"),
]


def test_hfm_6_the_hooks_use_no_retired_word_or_tool_name():
    hits = []
    for script in hook_sources():
        for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            # The acceptance check still reads the retired `specify` key from
            # archived manifests, and its comment says so; that is a key, not
            # a stage name in prose.
            if "retired `specify" in line or 'stages.get("specify")' in line:
                continue
            for pattern, word in RETIRED:
                if pattern.search(line):
                    hits.append(f"{script.name}:{n}: {word}")
    assert not hits, "\n".join(hits)
