#!/usr/bin/env python3
# =============================================================================
# compass_pkg.policy - `compass issue lint` and `compass plan lint`
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg.check_cmd import CHECK_FNS
from compass_pkg.core import (CompassError, FRAMEWORK_ROOT, artifact_path,
                              load_manifest, load_yaml, normalize_spine,
                              resolve_issue_dir)



# --- commands: policy lint / issue lint --------------------------------------

# The built-in `_lint_errors_*` functions below are the no-dependency floor:
# they always run, and they do the one thing JSON Schema cannot - cross-check
# that every declared guardrail check is actually implemented in CHECK_FNS.
# `_jsonschema_errors` adds fuller structural validation against the real JSON
# Schema files in schemas/, but only when the optional `jsonschema` library is
# installed. PyYAML stays the CLI's only *hard* dependency.

def _jsonschema_errors(instance, schema_name):
    """Check `instance` against schemas/<schema_name>. Returns a list of
    error strings, or None if `jsonschema` is not installed (caller falls back
    to the built-in structural lint, which always runs anyway)."""
    try:
        import jsonschema
    except ImportError:
        return None
    path = os.path.join(FRAMEWORK_ROOT, "schemas", schema_name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft7Validator(schema)
    errs = []
    for e in sorted(validator.iter_errors(instance),
                    key=lambda x: list(x.absolute_path)):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(f"{loc}: {e.message}")
    return errs


def _lint_errors_routing_policy(p):
    errs = []
    for top in ("routing_strategies", "routing_guardrails", "route_shapes",
                "assessment_vocabulary"):
        if top not in p:
            errs.append(f"missing top-level key: {top}")
    rg = p.get("routing_guardrails", {})
    # Waivers are checked here as well as in the JSON schema, because the schema
    # can only say `waived/0` - it does not know rule ids. A reader fixing a bad
    # waiver needs to be told which rule it was for.
    for i, w in enumerate(rg.get("waived", []) or []):
        if not isinstance(w, dict) or not w.get("id"):
            errs.append(f"`waived:` entry {i} has no `id` - a waiver names the "
                        f"framework rule it waives")
            continue
        if not str(w.get("reason", "")).strip():
            errs.append(f"waiver for {w['id']} has no `reason` - a waiver "
                        f"records a decision, so it requires one")
    for fl in rg.get("floors", []):
        if "id" not in fl:
            errs.append(f"a floor has no id: {fl}")
        if "when" not in fl:
            errs.append(f"floor {fl.get('id', '?')} has no `when`")
        if "rationale" not in fl:
            errs.append(f"floor {fl.get('id', '?')} has no `rationale`")
    for ig in rg.get("immovable_gates", []):
        if "gate" not in ig:
            errs.append(f"an immovable_gate has no `gate`: {ig}")
    shapes = p.get("route_shapes", {})
    for name in ("spike", "express", "standard", "hotfix", "expedition"):
        if name not in shapes:
            errs.append(f"route_shapes is missing the shape named by default_shapes: {name}")
        elif "weight" not in shapes[name]:
            errs.append(f"route_shape '{name}' has no `weight`")
    return errs


def _lint_errors_guardrails(p):
    errs = []
    if "defaults" not in p:
        errs.append("missing top-level key: defaults")
    known_checks = set((p.get("checks") or {}).keys())
    # Check all guardrails (defaults + project) for structural integrity.
    # command-passes `params` validation ONLY applies to project guardrails -
    # the framework's own guardrails (`G4`, evidence not assertion) legitimately
    # register command-passes without per-guardrail params (it's a
    # cross-cutting check that reads params from the project: guardrails it
    # finds at run time).
    for g in list(p.get("defaults", [])) + list(p.get("project", [])):
        if "id" not in g:
            errs.append(f"a guardrail has no id: {g}")
        if not g.get("checks"):
            errs.append(f"guardrail {g.get('id', '?')} has no `checks` - a "
                        f"guardrail with no mechanical check is a strategy")
        for c in g.get("checks", []):
            if c not in known_checks:
                errs.append(f"guardrail {g.get('id', '?')} references check "
                            f"'{c}' not declared under `checks:`")
            elif c not in CHECK_FNS:
                # The integrity rule: a declared guardrail check the CLI does
                # not implement would silently become advisory. Lint catches it
                # here, before an issue relies on it; `compass check` also fails
                # on it at run time. Both, because this is the line that keeps
                # "guardrail" meaning hard-and-blocking.
                errs.append(f"guardrail {g.get('id', '?')} references check "
                            f"'{c}' which the CLI does not implement (not in "
                            f"CHECK_FNS) - implement it, or move the guardrail "
                            f"to strategies.md")

    # command-passes params validation - only for project guardrails.
    # Framework defaults (`G4`) can reference command-passes without params;
    # the params come from the project guardrails that declare the actual
    # commands to run.
    for g in list(p.get("project", [])):
        if "command-passes" not in (g.get("checks") or []):
            continue
        params = g.get("params") or {}
        command = params.get("command")
        script = params.get("script")
        gid = g.get("id", "?")
        # Two declaration forms, and exactly one of them per guardrail.
        # `script:` names a file run with no shell; `command:` is a shell
        # string. Allowing both would need a precedence rule, and a precedence
        # rule is a quiet way to reach the shell from a declaration that looks
        # like the safe form.
        if script is not None and command is not None:
            errs.append(
                f"project guardrail {gid} declares both `params.script` and "
                f"`params.command` - declare one. `script:` runs a file "
                f"without a shell; `command:` runs a shell string"
            )
        elif script is not None:
            if not isinstance(script, str):
                errs.append(
                    f"project guardrail {gid} uses check 'command-passes' but "
                    f"`params.script` is not a string "
                    f"(got {type(script).__name__!r}) - it must be a path "
                    f"relative to the project root"
                )
            elif not script.strip():
                errs.append(
                    f"project guardrail {gid} uses check 'command-passes' but "
                    f"`params.script` is an empty string - name a script path"
                )
            args = params.get("args")
            if args is not None and (
                    not isinstance(args, list)
                    or not all(isinstance(a, str) for a in args)):
                errs.append(
                    f"project guardrail {gid}: `params.args` must be a list of "
                    f"strings - they are passed to the script as separate "
                    f"arguments, never joined into a command line"
                )
        elif command is None:
            errs.append(
                f"project guardrail {gid} uses check "
                f"'command-passes' but both `params.command` and "
                f"`params.script` are missing - add a `script:` path to run a "
                f"file without a shell (preferred), or a `command:` shell "
                f"string"
            )
        elif not isinstance(command, str):
            errs.append(
                f"project guardrail {gid} uses check "
                f"'command-passes' but `params.command` is not a string "
                f"(got {type(command).__name__!r}) - the command must be "
                f"a shell-invocable string"
            )
        elif not command.strip():
            errs.append(
                f"project guardrail {gid} uses check "
                f"'command-passes' but `params.command` is an empty "
                f"string - provide a non-empty shell command"
            )
    return errs


def _schema_note(ran):
    return ("" if ran else
            "  (jsonschema not installed - built-in linter only; "
            "`pip install jsonschema` for full JSON Schema validation)")


def _lint_errors_quarantine(gov_dir):
    """Check governance/quarantine.yml if present.

    Returns a list of error strings. An absent quarantine.yml is not an error
    (zero-setup default, ADR-006). Required fields per entry: test,
    tracking_task, reason, added. An entry without tracking_task is malformed:
    a quarantined test with no tracking issue never gets fixed.
    """
    path = os.path.join(gov_dir, "quarantine.yml")
    if not os.path.isfile(path):
        return []
    try:
        data = load_yaml(path)
    except CompassError as exc:
        return [f"quarantine.yml: {exc}"]
    errs = []
    if not isinstance(data, dict):
        return ["quarantine.yml: top-level value is not a mapping"]
    if "version" not in data:
        errs.append("quarantine.yml: missing required key `version`")
    quarantined = data.get("quarantined")
    if quarantined is None:
        errs.append("quarantine.yml: missing required key `quarantined`")
        return errs
    if not isinstance(quarantined, list):
        errs.append("quarantine.yml: `quarantined` must be a list")
        return errs
    required_fields = ("test", "tracking_task", "reason", "added")
    for i, entry in enumerate(quarantined):
        if not isinstance(entry, dict):
            errs.append(f"quarantine.yml: entry #{i + 1} is not a mapping")
            continue
        for field in required_fields:
            if not entry.get(field):
                errs.append(
                    f"quarantine.yml: entry #{i + 1} (test={entry.get('test', '?')!r}) "
                    f"is malformed - missing or empty `{field}`. A quarantine entry "
                    f"without `tracking_task` is a graveyard, not a registry (TRC-A7)"
                )
    return errs


# --- command: plan lint ------------------------------------------------------
# Scans a technical-design.md for the phrases that mean the plan is not
# actually finished. ADVISORY BY DESIGN: it always exits 0 on findings. A hit
# is a note for the planner to judge, never a gate. The CLI can read a prose
# document to advise; it must not make the document's structure a condition
# of passing.

PLAN_PLACEHOLDER_PHRASES = (
    "TBD",
    "TODO",
    "implement later",
    "add appropriate error handling",
)

# A work unit that promises tests. It is only a finding when nothing test-shaped
# follows it - the promise with nothing behind it is the defect, not the phrase.
PLAN_TEST_PROMISE = "write tests for the above"


def _plan_lint_scannable(text):
    """Yield (lineno, line) with fenced blocks and blockquotes blanked out.

    Blanked rather than dropped, so reported line numbers still match the file
    the author is looking at. Quoted text is skipped because every document that
    explains this check has to quote the phrases it looks for - the skill that
    documents it, the writing guide, and the plan that specified it. A check
    that fires on its own documentation gets switched off.
    """
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            yield lineno, ""
            continue
        if in_fence or stripped.startswith(">"):
            yield lineno, ""
            continue
        yield lineno, line


def _plan_lint_findings(text):
    """Return [(lineno, phrase)] for every placeholder in a plan's prose."""
    lines = list(_plan_lint_scannable(text))
    findings = []

    for lineno, line in lines:
        low = line.lower()
        for phrase in PLAN_PLACEHOLDER_PHRASES:
            if phrase.lower() in low:
                findings.append((lineno, phrase))

        if PLAN_TEST_PROMISE in low:
            # Kept only if nothing test-shaped follows within a short window.
            import re as _re
            following = " ".join(l for n, l in lines if n > lineno)[:600].lower()
            if not _re.search(r"test_\w+|::|\.py\b|\bit\(|\bdescribe\(", following):
                findings.append((lineno, PLAN_TEST_PROMISE))

    return sorted(set(findings))


def _plan_stage_weight(task_slug):
    """What this issue's approach says the plan stage weighs, or None.

    Read so the lint can check its own explanation for a missing design
    against the record, instead of offering a reason that may not apply.
    Returns None when the manifest cannot be read - an unreadable record is not
    evidence that the stage collapsed.
    """
    try:
        task, _path = load_manifest(resolve_issue_dir(task_slug))
    except CompassError:
        return None
    stages = task.get("stages") or {}
    if not isinstance(stages, dict):
        return None
    weight = stages.get("plan")
    return str(weight).strip().lower() if weight else None


def cmd_plan_lint(args):
    # The default path goes through `artifact_path`, which knows both the name
    # this framework writes today and the one a landed issue still holds. This
    # function joined the filename itself, and got it wrong twice: first left
    # at `plan.md` after the artifact became `design.md`, then moved to
    # `technical-design.md` with no fallback, which broke it on every issue
    # that landed holding `design.md`. Every other artifact reader in the CLI
    # goes through the resolver; this one now does too.
    if args.file:
        path = args.file
    else:
        task_dir = resolve_issue_dir(args.task)
        path = artifact_path(task_dir, "technical-design.md")

    if not os.path.isfile(path):
        print(f"compass plan lint: ERROR - no such file: {path}")
        # Say why it might legitimately be absent AND check that reason against
        # the record, rather than explaining away an absence the approach says
        # should not happen.
        weight = _plan_stage_weight(getattr(args, "task", None))
        if weight in ("collapsed", "skipped"):
            print("  This issue's approach records the plan stage as %s, so it "
                  "has no technical-design.md to lint." % weight)
        elif weight:
            print("  This issue's approach records the plan stage as %s, so a "
                  "technical-design.md is expected and is missing." % weight)
        else:
            print("  The plan stage collapses on quick-fix, hotfix and spike "
                  "approaches, so an issue on one of those has no "
                  "technical-design.md to lint.")
        return 2

    with open(path, encoding="utf-8") as fh:
        findings = _plan_lint_findings(fh.read())

    if not findings:
        print(f"compass plan lint: PASS - no placeholders found in {path}")
        return 0

    noun = "placeholder" if len(findings) == 1 else "placeholders"
    print(f"compass plan lint: {len(findings)} possible {noun} in {path} [advisory]")
    for lineno, phrase in findings:
        print(f"  line {lineno}: {phrase}")
    print("\n  Advisory, not a gate - this exits 0. Assess these as judgement in "
          "the strategies\n  walk of the governance check, and either fill them in "
          "or record why they stand.")
    return 0


def cmd_task_lint(args):
    if args.file:
        path = args.file
        task = normalize_spine(load_yaml(path))
    else:
        task_dir = resolve_issue_dir(args.task)
        task, path = load_manifest(task_dir)
    # built-in structural lint (always runs)
    errs = []
    # The manifest is normalised above, so this reads the current key.
    if "issue" not in task:
        errs.append("missing `issue:` (the issue slug)")
    # Each block below checks the shape before reading it. This command's whole
    # job is to report a malformed manifest.yml, so it must not crash on one -
    # a scenario written as a bare string must be reported, not raise
    # AttributeError.
    if "assessment" not in task:
        if (task.get("status") or "active") == "queued":
            # A queued issue has not been assessed yet, so the lint does not
            # ask it for an assessment. Only that field is skipped: the rest
            # of the lint still runs, because a malformed manifest is
            # malformed whether or not work has started.
            pass
        elif task.get("landed_by"):
            # An issue delivered elsewhere never entered the pipeline, so it
            # has no assessment to record. Demanding one leaves inventing a
            # judgement nobody made as the only way to satisfy the lint - and
            # the assessment lives in whatever `landed_by` names, along with
            # the rest of the record.
            pass
        else:
            errs.append(
                "missing `assessment:` - the assess stage records the four "
                "dimensions")
    elif not isinstance(task["assessment"], dict):
        errs.append("`assessment:` must be a mapping of dimension -> value")
    else:
        for dim in ("risk", "familiarity", "size"):
            if dim not in task["assessment"]:
                errs.append(f"assessment is missing required dimension: {dim}")
    for i, s in enumerate(task.get("scenarios") or []):
        if not isinstance(s, dict):
            errs.append(f"scenario #{i + 1} must be a mapping with an `id:`, got: {s!r}")
        elif not s.get("id"):
            errs.append(f"scenario #{i + 1} has no id")
    for cf in task.get("changed_files") or []:
        if not isinstance(cf, dict):
            errs.append(f"a changed_files entry must be a mapping with a `path:`: {cf!r}")
        elif "path" not in cf:
            errs.append(f"a changed_files entry has no `path`: {cf}")
    # Check the `attempts` field on test-run evidence entries
    for ev in task.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "test-run" and "attempts" in ev:
            attempts = ev["attempts"]
            if not isinstance(attempts, int) or attempts < 1:
                errs.append(
                    f"evidence {ev.get('id', '?')}: attempts must be a positive "
                    f"integer (>= 1), got {attempts!r} - "
                    f"an attempt count of 0 or negative is out of domain (TRC-FM2)"
                )
    # JSON Schema validation (when `jsonschema` is installed)
    je = _jsonschema_errors(task, "manifest.schema.json")
    schema_ran = je is not None
    if je:
        errs += je
    if errs:
        print(f"compass issue lint: FAIL - {path}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"compass issue lint: PASS - {path} is structurally valid."
          + ("\n" + _schema_note(schema_ran) if not schema_ran else ""))
    return 0
