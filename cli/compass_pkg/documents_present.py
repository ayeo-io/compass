# compass_pkg.documents_present - which of an issue's documents are on disk
"""The derived reading `artifacts`: the documents of an issue that are on disk.

An artifact rule (`when: {artifacts_any: [...]}`) fires on a document the CLI
can see, not on who said they were in the room (ADR-070). The command that
evaluates an approach reads presence here and hands it to the evaluator beside
the assessment. It is never written into the manifest's `assessment:` block,
which holds judgement only (ADR-001).

Only the kinds a condition of the policy names are looked for. A kind is
present when the registry names a path that resolves to a file, or when its
file is in the issue's documents folder or beside the manifest.
"""
# DEPENDENCY: standard library (os); compass_pkg.core (resolve_artifact,
# unregistered_document, FOUND). Imported by compass_pkg.routing.
from __future__ import annotations

from compass_pkg.core import FOUND, resolve_artifact, unregistered_document

KEY = "artifacts"
CONDITION = "artifacts_any"


def kinds_named(policy):
    """Every document kind an `artifacts_any` condition anywhere in `policy` names."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == CONDITION:
                    for kind in (value if isinstance(value, list) else [value]):
                        if isinstance(kind, str) and kind not in found:
                            found.append(kind)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(policy)
    return found


def present(task_dir, policy):
    """The kinds `policy` names whose document the issue in `task_dir` has, sorted."""
    out = []
    for kind in kinds_named(policy):
        try:
            state = resolve_artifact(task_dir, kind)[0]
        except Exception:                       # noqa: BLE001 - an unreadable registry finds nothing
            state = None
        if state == FOUND or unregistered_document(task_dir, f"{kind}.md"):
            out.append(kind)
    return sorted(out)


def with_presence(assessment, task_dir, policy):
    """A copy of `assessment` with `artifacts` filled from the disk. A value the
    caller already gave (an ad-hoc `--assessment artifacts=...`) is kept."""
    out = dict(assessment or {})
    if KEY not in out and task_dir:
        out[KEY] = present(task_dir, policy)
    return out
