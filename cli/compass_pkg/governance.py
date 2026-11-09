# compass_pkg.governance - the lint of a project's own governance files
"""The structural lint of the files a project keeps in its `governance/`
folder: `quarantine.yml`, `review-rules.yml` and `architecture-sources.yml`.
Each is optional and read by path. `compass policy lint` reports each fault as
an `L-GOVERNANCE-FILE` finding, and `compass ci` runs that lint as its first
step.

9.0.0 does not read `routing-policy.yml` or `guardrails.yml` (ADR-098): the
check set (`governance/check-set.yml`) is the only machine-readable policy. A
project that holds a copy of either and no `compass.yml` is refused
(`governance-copy-removed`), so nothing lints a copy that nothing reads.
"""
# DEPENDENCY: standard library (os, re, types); compass_pkg.policy, policy_cmd,
# review_rules.
import os
import re
import types

from compass_pkg.policy import architecture_sources_lint_errors, _lint_errors_quarantine
from compass_pkg.review_rules import lint_errors as review_rules_lint_errors

#: An error line starts `[file.yml] ` or `file.yml: `, naming the file it is about.
_FILE = re.compile(r"^(?:\[([^\]]+)\]|([\w.-]+\.yml):) ")


def files_errors(root):
    """`[(path, message)]` for each fault in the optional files of
    `<root>/governance/`. `path` names the file from the project root."""
    gov = os.path.join(root, "governance")
    if not os.path.isdir(gov):
        return []
    out = []
    for text in (_lint_errors_quarantine(gov) + review_rules_lint_errors(gov)
                 + architecture_sources_lint_errors(gov)):
        found = _FILE.match(text)
        name = (found.group(1) or found.group(2)) if found else ""
        message = text[found.end():] if found else text
        out.append((f"governance/{name}" if name else "governance", message))
    return out


def cmd_policy_lint(args):
    """`compass ci`'s policy step: `compass policy lint` in text form.
    Returns 1 when it finds an error, else 0."""
    from compass_pkg import policy_cmd
    return policy_cmd.run_policy_lint(types.SimpleNamespace(file=None))
