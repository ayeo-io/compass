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
# unregistered_document, reading_matches, FOUND); effective, status_words and
# refusals, read lazily by the landing refusal. Imported by compass_pkg.routing,
# policy_lint, replay and manifest.
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


def unapplied_rules(task, task_dir):
    """`[(rule id, kinds)]`: the artifact rules of the issue's stored configuration
    that add a gate or ask for a document, whose documents are on disk now, and
    that the last evaluation did not fire. A document written after the issue was
    assessed is the usual cause; the next `compass approach evaluate --write`
    applies the rule. A rule that only blocks a stage is left out: by the landing
    that stage is past, and refusing would add a step and no check."""
    from compass_pkg import effective, status_words
    from compass_pkg.core import reading_matches
    if not isinstance(task, dict) or status_words.is_closed(task) or "generation" not in task:
        return []
    try:
        view = effective.view_or_legacy(task_dir, manifest=task)
        policy = view.evaluator_policy() if view is not None else None
    except Exception:                           # noqa: BLE001 - nothing readable, nothing owed
        return []
    rules = ((policy or {}).get("routing_guardrails") or {}).get("artifact_rules") or []
    fired = {f.get("id") for f in task.get("policy_rules_fired") or [] if isinstance(f, dict)}
    point = with_presence(task.get("assessment") or {}, task_dir, policy)
    out = []
    for rule in rules:
        when = rule.get("when") or {}
        owes = rule.get("gate") or rule.get("require_artifact")
        if owes and kinds_named(when) and rule.get("id") not in fired \
                and reading_matches(when, point):
            out.append((rule.get("id"), sorted(set(kinds_named(when)) & set(point[KEY]))))
    return out


def landing_refusal(task, task_dir):
    """The refusal text for an issue whose documents earned an artifact rule the
    recorded approach does not hold, or None. An entry of `manifest.LANDING_REFUSALS`."""
    import os
    from compass_pkg import refusals
    found = unapplied_rules(task, task_dir)
    if not found:
        return None
    return refusals.render(
        "artifact-rule-not-applied", slug=os.path.basename(os.path.normpath(str(task_dir))),
        rules=", ".join(rule_id for rule_id, _ in found),
        documents=", ".join(f"{kind}.md" for _, kinds in found for kind in kinds))
