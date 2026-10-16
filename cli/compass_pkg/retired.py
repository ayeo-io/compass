# compass_pkg.retired - the assessment dimension and the rules 7.0.0 removed
"""What 7.0.0 removed from the assessment, and what replaces it (ADR-070).

`role` is no longer an assessment dimension. The two blocking role rules are
now artifact rules, keyed on the documents on disk, and the designer's role
default is dropped. 6.x records and calls keep working: a recorded role is not
read, a role flag is accepted and ignored, and a stored generation keeps the
rules it was assessed under. The messages that say so are built here, so every
command says it the same way.

`RULES` must equal the `retired_rules` table in `governance/legacy-views.yml`,
which `compass policy migrate` reads; a test holds the two equal.
"""
# DEPENDENCY: standard library; compass_pkg.classify, read lazily by
# `condition_findings`. Imported by compass_pkg.routing,
# compass_pkg.justifications, compass_pkg.quick_fix_cmd, compass_pkg.preset_test,
# compass_pkg.policy_lint, compass_pkg.merge, compass_pkg.migrate and
# compass_pkg.policy_migrate.
from __future__ import annotations

#: The assessment dimensions the shipped default no longer declares.
DIMENSIONS = ("role",)

#: Each retired rule id, and the rule that replaces it (None: dropped).
RULES = {"RP-ROLE-001": "RP-ART-001", "RP-ROLE-002": "RP-ART-002", "RP-SROLE-001": None}

#: Each retired rule set of the shipped default, and the set that replaces it.
RULE_SETS = {"role_rules": "artifact_rules", "role_defaults": None}

RELEASE = "7.0.0"

NOT_READ = (f"role is no longer an assessment dimension from {RELEASE} (ADR-070), "
            f"so the value is ignored")


def notice(where):
    """The one line a command prints on standard error for a role it ignores."""
    return f"compass: {where}: {NOT_READ}"


def merge_hint(path):
    """Words to add to a merge refusal about `path` (`catalogue.id`), or "". A
    layer written for 6.x can edit a dimension or a rule set the shipped default
    no longer holds; the refusal then says what replaced it."""
    catalogue, _, entry = path.partition(".")
    if catalogue == "dimensions" and entry in DIMENSIONS:
        return (f"; {RELEASE} removed the {entry} dimension: a rule reads the documents "
                f"on disk with artifacts_any, or a label")
    if catalogue == "rules" and entry in RULE_SETS:
        moved = ", ".join(f"{old} is now {new}" for old, new in RULES.items() if new)
        target = RULE_SETS[entry]
        return (f"; {RELEASE} removed this rule set" + (
            f": {moved}, in rules.{target}" if target else ""))
    return ""


def rule_line(rule_id):
    """A sentence about one retired rule id, for `policy migrate`."""
    new = RULES.get(rule_id)
    if new:
        return f"{rule_id} was retired at {RELEASE}; {new} replaces it"
    return f"{rule_id} was retired at {RELEASE}, with no replacement"


def condition_findings(config):
    """`(code, path, message)` for each `when` of a rule, check or gate that reads a
    retired dimension the configuration does not declare (it would match only 6.x
    manifests), and each check or gate `when` that reads `artifacts_any`, which only
    a rule's evaluation fills. `compass policy lint` reports them."""
    from compass_pkg import classify     # classify reaches this module through routing
    out = []
    for catalogue in ("rules", "checks", "gates"):
        hint = "artifacts_any, or a label" if catalogue == "rules" else "a label"
        for entry_id, entry in (config.get(catalogue) or {}).items():
            nested = (entry.get("rules") or {}) if catalogue == "rules" else {"": entry}
            for rule_id, rule in (nested.items() if isinstance(nested, dict) else ()):
                for key in ("when", "blocking_when", "applies_when"):
                    atoms = classify.atoms_of(rule.get(key) if isinstance(rule, dict) else None)
                    path = ".".join(x for x in (catalogue, entry_id, "rules" if rule_id else "",
                                                rule_id, key) if x)
                    named = {a[1] for a in atoms if a[0] in ("in", "at_least")
                             and a[1] in DIMENSIONS} - set(config.get("dimensions") or {})
                    out += [("M-WHEN-RETIRED", path, f"reads {d}, which is not an assessment "
                             f"dimension from {RELEASE}; read {hint}, or declare it")
                            for d in sorted(named)]
                    if catalogue != "rules" and any(a[0] == "artifacts_any" for a in atoms):
                        out.append(("M-WHEN-DOCUMENTS", path,
                                    "reads artifacts_any, which only a rule reads"))
    return out
