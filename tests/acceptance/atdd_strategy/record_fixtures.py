"""Record the compass 8.0.4 output that `TRC-A3`, `TRC-A9` and `TRC-X2` compare with.

CI has no compass 8.0.4, so its output is recorded once, here, from a copy of
the tree at commit a74e968 (the 8.0.4 release):

    git archive a74e968 | tar -x -C /tmp/compass-8.0.4
    python3 -m tests.acceptance.atdd_strategy.record_fixtures /tmp/compass-8.0.4/cli/compass

It writes `fixtures/compass-8.0.4/*.json` and the `TRC-X2` project in
`fixtures/assessed-by-8.0.4/`. Run it again only to change what a fixture
holds; the scenarios read the files and never run 8.0.4.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

from tests.acceptance.atdd_strategy import support


def _write(name, code, document):
    out = support.FIXTURES / "compass-8.0.4" / f"{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(support.summary(code, document), indent=2) + "\n",
                   encoding="utf-8")


def _guardrails(old_root):
    """The check lists of guardrails `G1` and `G4` and the spike guardrail ids the
    8.0.4 tree ships, for scenarios `TRC-A1` and `TRC-A19`."""
    doc = yaml.safe_load((old_root / "governance" / "guardrails.yml").read_text(encoding="utf-8"))
    out = support.FIXTURES / "compass-8.0.4" / "guardrails.json"
    out.write_text(json.dumps({
        "checks": {g["id"]: g["checks"] for g in doc["defaults"] if g["id"] in ("G1", "G4")},
        "spike_guardrails": [g["id"] for g in doc["spike_guardrails"]]}, indent=2) + "\n",
        encoding="utf-8")


def main(old_cli):
    old_cli = Path(old_cli).resolve()
    _guardrails(old_cli.parent.parent)
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        for kind in ("validation", "refactor"):
            project = support.Project(scratch / kind, cli=old_cli)
            issue = support.out_of_scope_issue(project, kind, new_cli=False)
            _write("out-of-scope-" + kind, *issue.check())
        project = support.Project(scratch / "spike", cli=old_cli)
        _write("spike", *support.spike_issue(project, new_cli=False).check())
        if support.OLDER_PROJECT.exists():
            shutil.rmtree(support.OLDER_PROJECT)
        support.build_older_issue_project(support.OLDER_PROJECT, old_cli)
        project = support.older_issue_project(scratch / "older", cli=old_cli)
        _write("older-issue", *support.Issue(project, "older").check())


if __name__ == "__main__":
    main(sys.argv[1])
