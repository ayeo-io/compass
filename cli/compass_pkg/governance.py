#!/usr/bin/env python3
# =============================================================================
# compass_pkg.governance - the structural lint of a governance copy
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



# --- the structural lint of a governance copy -----------------------------
# A project that ran `/compass:init` under 5.x holds a copy of governance/, and
# the framework's own repository holds the frozen views. 9.0.0 removed the
# drift report that compared such a copy with the framework's (ADR-098): the
# copy is read by the legacy readers only. What stays is the check that the
# copy still parses and has the shape the legacy readers need.


def legacy_structure(gov):
    """`(errors, schema_ran)` for the governance files under `gov`: the
    structural lint of the copied policy and guardrails. `compass policy
    lint` prints it, and the legacy `--json` view lists it."""
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
    return errs, schema_ran


def cmd_policy_lint(args):
    """The structural lint of the governance files `find_governance` returns.
    `compass policy lint` runs it for a project with a governance copy and no
    `compass.yml`, and `compass ci` runs it in every project."""
    gov = find_governance()
    errs, schema_ran = legacy_structure(gov)
    if errs:
        print("compass policy lint: FAIL")
        for e in errs:
            print(f"  - {e}")
        return 1
    print("compass policy lint: PASS - routing-policy.yml and guardrails.yml "
          "are structurally valid." + ("\n" + _schema_note(schema_ran)
                                        if not schema_ran else ""))
    return 0
