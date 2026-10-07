#!/usr/bin/env python3
# =============================================================================
# compass_pkg.governance - the governance drift report and `compass policy lint`
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
from compass_pkg import project_settings
from compass_pkg.core import CompassError, FRAMEWORK_ROOT, find_compass_dir, find_governance, load_yaml
from compass_pkg.review_rules import lint_errors as review_rules_lint_errors
from compass_pkg.policy import _jsonschema_errors, architecture_sources_lint_errors, _lint_errors_guardrails, _lint_errors_quarantine, _lint_errors_routing_policy, _schema_note



# --- governance drift --------------------------------------------------------
# A project that runs `/compass:init` gets a COPY of governance/. The framework
# later ships new floors and checks; the copy never learns about them. The
# failure is DIRECTIONAL and therefore quiet: stale governance never fails
# loudly, it produces a lighter delivery approach. A project can lose half its
# routing guardrails while every check still passes.
#
# This compares the DECLARED RULE IDS of the two policies, not their content. A
# project that reworded a rationale, reordered its floors, or added rules of its
# own has not drifted, and a detector that fires on those gets switched off.
# The cost of that choice: a project that keeps every id but empties a rule's
# body reads as current. That limit is stated in the report rather than hidden.

# Where rule ids live in each governance file: (file, path-to-list, kind).
_DRIFT_RULE_SOURCES = (
    ("routing-policy.yml", ("routing_guardrails", "floors"), "floor"),
    ("routing-policy.yml", ("routing_guardrails", "caps"), "cap"),
    ("routing-policy.yml", ("routing_guardrails", "loop_ceilings"), "loop ceiling"),
    ("routing-policy.yml", ("routing_guardrails", "immovable_gates"), "immovable gate"),
    ("routing-policy.yml", ("routing_guardrails", "role_rules"), "role rule"),
    ("routing-policy.yml", ("routing_strategies", "default_shapes"), "route shape"),
    ("routing-policy.yml", ("routing_strategies", "advisory_strategies"), "advisory strategy"),
    ("guardrails.yml", ("defaults",), "guardrail"),
    ("guardrails.yml", ("spike_guardrails",), "spike guardrail"),
)


class DriftReport(object):
    """What a project's governance lacks relative to the framework's.

    `comparable` is not decoration: an unreadable framework policy must degrade
    to "could not compare" rather than crashing the lint, so each caller can
    decide what to say about that.
    """

    __slots__ = ("missing_rules", "missing_checks", "waived", "waiver_errors",
                 "project_versions", "framework_versions", "comparable",
                 "reason", "same_dir")

    def __init__(self):
        self.missing_rules = []      # [(file, id, kind)]
        self.missing_checks = []     # [(file, name)]
        self.waived = []             # [(id, reason)]
        self.waiver_errors = []      # [str]
        self.project_versions = {}
        self.framework_versions = {}
        self.comparable = True
        self.reason = ""
        self.same_dir = False

    @property
    def drifted(self):
        return bool(self.missing_rules or self.missing_checks)

    @property
    def count(self):
        return len(self.missing_rules) + len(self.missing_checks)


def _dig(data, path):
    for key in path:
        if not isinstance(data, dict):
            return []
        data = data.get(key)
    return data or []


def _rule_ids(data, path):
    """Rules by id. Ignores anything whose id is not a string.

    A list- or dict-valued id would raise an unhashable-type TypeError in
    `approach evaluate`, which calls this with no lint first, and stop
    assessment with a traceback instead of a report.
    """
    out = {}
    for r in _dig(data, path):
        if isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"]:
            out[r["id"]] = r
    return out


def governance_drift(project_gov, framework_gov=None):
    """Compare a project's governance against the framework's shipped copy.

    Pure with respect to the filesystem: reads two directories, returns data.
    No printing and no exit codes - three commands consume this and each
    formats differently.
    """
    report = DriftReport()
    if framework_gov is None:
        framework_gov = os.path.join(FRAMEWORK_ROOT, "governance")

    # A project with no governance/ of its own IS the framework's. There is
    # nothing to compare and nothing is missing (ADR-006).
    if os.path.realpath(project_gov) == os.path.realpath(framework_gov):
        report.same_dir = True
        return report

    loaded = {}
    for name in ("routing-policy.yml", "guardrails.yml"):
        fw_path = os.path.join(framework_gov, name)
        try:
            fw = load_yaml(fw_path)
            if not isinstance(fw, dict):
                raise CompassError("not a mapping")
        except Exception as exc:                       # noqa: BLE001
            report.comparable = False
            report.reason = ("could not read the framework's %s (%s)"
                             % (name, exc))
            return report
        try:
            pr = load_yaml(os.path.join(project_gov, name))
            if not isinstance(pr, dict):
                raise CompassError("not a mapping")
        except Exception as exc:                       # noqa: BLE001
            report.comparable = False
            report.reason = ("could not read the project's %s (%s) - drift "
                             "cannot be reported until it parses" % (name, exc))
            return report
        loaded[name] = (pr, fw)
        report.project_versions[name] = str(pr.get("version", "unknown"))
        report.framework_versions[name] = str(fw.get("version", "unknown"))

    # waivers: a recorded decision, not drift. Declared on the project side.
    rp_project = loaded["routing-policy.yml"][0]
    waived_ids = {}
    for entry in _dig(rp_project, ("routing_guardrails", "waived")):
        # isinstance str, not just truthiness: a list-valued id would raise
        # `unhashable type` when used as a dict key below.
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) \
                or not entry["id"]:
            report.waiver_errors.append(
                "a `waived:` entry has no `id` - a waiver names the rule it waives")
            continue
        rid = entry["id"]
        reason = (entry.get("reason") or "").strip()
        if not reason:
            report.waiver_errors.append(
                "waiver for %s has no `reason` - a waiver records a decision, "
                "so it requires one" % rid)
            continue
        waived_ids[rid] = reason

    known_framework_ids = set()
    # Check names, evidence types and gate requirements are waivable too - the
    # missing-check loop below honours a waiver for them, so they must count as
    # known ids or that path fails as "a rule that does not exist".
    _fw_guardrails = loaded["guardrails.yml"][1]
    for group in ("checks", "evidence_types", "gate_evidence_requirements"):
        known_framework_ids |= set(_fw_guardrails.get(group) or {})
    for fname, path, kind in _DRIFT_RULE_SOURCES:
        pr, fw = loaded[fname]
        fw_ids = _rule_ids(fw, path)
        known_framework_ids |= set(fw_ids)
        pr_ids = _rule_ids(pr, path)
        for rid in sorted(set(fw_ids) - set(pr_ids)):
            if rid in waived_ids:
                continue
            report.missing_rules.append((fname, rid, kind))

    for rid, reason in sorted(waived_ids.items()):
        if rid not in known_framework_ids:
            report.waiver_errors.append(
                "waiver names %s, which does not exist in the framework's "
                "policy - usually a typo" % rid)
        else:
            report.waived.append((rid, reason))

    pr_gr, fw_gr = loaded["guardrails.yml"]
    for group in ("checks", "evidence_types", "gate_evidence_requirements"):
        fw_names = set((fw_gr.get(group) or {}))
        pr_names = set((pr_gr.get(group) or {}))
        for name in sorted(fw_names - pr_names):
            if name in waived_ids:
                continue
            report.missing_checks.append(("guardrails.yml", name))

    return report


def _print_drift(report, strict):
    """Render a DriftReport for `compass policy lint`. Returns True if it
    should be treated as a failure."""
    if report.same_dir:
        return False
    if not report.comparable:
        print("\ncompass policy lint: could not compare against the framework's "
              "governance - %s." % report.reason)
        print("  Structural validation above still applies.")
        return False

    waiver_failed = False
    if report.waiver_errors:
        # A malformed waiver is a CONFIG error, not drift. Drift is advisory
        # because an adopter should not get a red build for being behind; a
        # waiver naming a rule that does not exist is something they wrote and
        # is meaningless, so it fails in either mode. It also falls through, so
        # a bad waiver cannot hide the drift it was meant to explain away.
        print("\ncompass policy lint: FAIL - the `waived:` block is malformed")
        for e in report.waiver_errors:
            print("  - %s" % e)
        waiver_failed = True

    if not report.drifted and not report.waived:
        # `waiver_failed`, not False: a project with a malformed waiver and no
        # drift still wrote something meaningless, and must not exit 0.
        return waiver_failed

    if report.drifted:
        n_rules, n_checks = len(report.missing_rules), len(report.missing_checks)
        print("\ncompass policy lint: %s - project governance is missing %d rule(s) "
              "and %d check(s) the framework ships"
              % ("FAIL" if strict else "WARN", n_rules, n_checks))
        for name in ("routing-policy.yml", "guardrails.yml"):
            rules = [(rid, kind) for f, rid, kind in report.missing_rules if f == name]
            checks = [n for f, n in report.missing_checks if f == name]
            if not rules and not checks:
                continue
            pv = report.project_versions.get(name, "unknown")
            fv = report.framework_versions.get(name, "unknown")
            behind = " - the project's copy is behind" if pv != fv else ""
            print("  %s (project v%s, framework v%s)%s:" % (name, pv, fv, behind))
            for rid, kind in rules:
                print("      %-14s %s" % (rid, kind))
            for n in checks:
                print("      %s" % n)
        print("  Copy the rule from the framework's governance/ to adopt it, or "
              "record a deliberate omission under `routing_guardrails.waived:` "
              "with a reason.")
        print("  Note: this compares declared rule ids. A rule you have kept by "
              "id but changed the body of is not reported.")
        if not strict:
            print("  Advisory by default. Set %s to make this fail."
                  % _drift_setting_hint())

    if report.waived:
        print("  waived by this project (a recorded decision, not drift):")
        for rid, reason in report.waived:
            print("      %-14s %s" % (rid, reason))

    return waiver_failed or bool(strict and report.drifted)


def _drift_setting_hint():
    """`governance_drift: strict`, with the file the project's settings are
    read from. The project root is the working directory's when no `.compass/`
    is found."""
    try:
        root = os.path.dirname(find_compass_dir())
    except CompassError:
        root = os.getcwd()
    return project_settings.named(root, "governance_drift", "strict")


def _drift_is_strict():
    """Read `governance_drift:` from the project's settings. Advisory by default:
    failing by default would turn every existing adopter's build red the moment
    they upgrade, which punishes upgrading (ADR-006)."""
    try:
        cfg = project_settings.lenient(os.path.dirname(find_compass_dir()))
    except project_settings.SettingsConflict:
        raise
    except Exception:                                   # noqa: BLE001
        return False
    return str(cfg.get("governance_drift", "advisory")).strip().lower() == "strict"


def cmd_policy_lint(args):
    gov = find_governance()
    rp = load_yaml(os.path.join(gov, "routing-policy.yml"))
    gr = load_yaml(os.path.join(gov, "guardrails.yml"))
    # The built-in lint always runs - the no-dependency floor, and the only
    # thing that cross-checks declared guardrail checks against CHECK_FNS.
    errs = (_lint_errors_routing_policy(rp)
            + _lint_errors_guardrails(gr)
            + _lint_errors_quarantine(gov)
            + review_rules_lint_errors(gov)
            + architecture_sources_lint_errors(gov))
    # JSON Schema validation runs additionally when `jsonschema` is installed.
    schema_ran = False
    for inst, sname, label in (
        (rp, "routing-policy.schema.json", "routing-policy.yml"),
        (gr, "guardrails.schema.json", "guardrails.yml"),
    ):
        je = _jsonschema_errors(inst, sname)
        if je is not None:
            schema_ran = True
            errs += [f"[{label}] {e}" for e in je]
    if errs:
        # Structural errors stop the drift comparison. A policy that fails to
        # parse would otherwise be reported as missing every framework rule -
        # true, and useless. Fix the syntax, then see the drift.
        print("compass policy lint: FAIL")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("compass policy lint: PASS - routing-policy.yml and guardrails.yml "
          "are structurally valid." + ("\n" + _schema_note(schema_ran)
                                        if not schema_ran else ""))
    drift_failed = _print_drift(governance_drift(gov), _drift_is_strict())
    return 1 if drift_failed else 0
