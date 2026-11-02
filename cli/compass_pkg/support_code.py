# compass_pkg.support_code - the support code of the four-layer acceptance strategy
"""Which pieces of acceptance support code a project has, and the advisory
check `acceptance-support-present` of strategy `S17`, the four-layer
acceptance strategy.

The support code is four pieces: the alias helper, the driver factory, the
DSL root and the layering test. The first issue the strategy applies to
builds the pieces that are missing, as part of its own work. Their absence
blocks nothing: it limits what the issue can claim (the claim limit,
`CLAIM_LIMIT`).

Compass never reads project code. The project names each piece's path in
`project.acceptance_support`, as it names `project.bdd_runner`, and this
module tests only that each named path exists inside the project root. A
piece with no setting, or a path that does not exist, is missing (decision
of the issue `atdd-strategy`). `compass readiness` prints the pieces in
a block of their own: they are not a readiness signal, so they change neither
the score nor the floor. `docs/readiness.md` and `governance/guardrails.md`
own this behavior.
"""
# DEPENDENCY: standard library (os); compass_pkg.acceptance_strategy,
# catalogue_spec, check_results, core and project_settings, and inside functions
# compass_pkg.layers and outer_loop. It imports no command module, so the check registry can
# import it.
from __future__ import annotations

import os

from compass_pkg import acceptance_strategy, project_settings
from compass_pkg.catalogue_spec import ACCEPTANCE_SUPPORT
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import CompassError

CHECK = "acceptance-support-present"
KEY = "acceptance_support"

#: Each piece of support code: its key under `project.acceptance_support` and
#: the name a person reads, in the order readiness prints them.
PIECES = tuple(zip(ACCEPTANCE_SUPPORT, ("alias helper", "driver factory", "DSL root",
                                         "layering test")))

#: What an issue the strategy applies to can claim while a piece is missing.
#: The check's statement in the default preset holds the same sentence, so
#: `governance/guardrails.yml` states it; a test fails when the two differ.
CLAIM_LIMIT = ("while a piece is missing, the issue can claim that its scenarios "
               "pass, and not that its acceptance tests are isolated from each other "
               "(alias helper), run through a driver chosen at start-up (driver "
               "factory), keep driver detail out of the specifications (DSL root) "
               "or keep the layer rules (layering test).")


def _section(project_root):
    """The `project.acceptance_support` mapping, `{}` when it is not set. A value
    that is not a mapping raises `CompassError` naming the key and the file."""
    where = project_settings.settings_file(project_root)
    project = project_settings.settings(project_root).get("project")
    if project is None:
        return {}
    if not isinstance(project, dict):
        raise CompassError(f"project in {where} must be a mapping")
    section = project.get(KEY)
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise CompassError(f"project.{KEY} in {where} must be a mapping of the pieces "
                           f"{', '.join(k for k, _ in PIECES)} to paths")
    return section


def _inside(project_root, path):
    root = os.path.realpath(project_root)
    full = os.path.realpath(os.path.join(root, path))
    return full == root or full.startswith(root + os.sep)


def pieces(project_root):
    """`[{key, name, path, result, reason}]` for each piece, in `PIECES` order.
    `result` is `present` or `missing`. Only the existence of each named path
    is tested; no file is opened."""
    section = _section(project_root)
    where = project_settings.settings_file(project_root)
    out = []
    for key, name in PIECES:
        path = section.get(key)
        if path is not None and not isinstance(path, str):
            raise CompassError(f"project.{KEY}.{key} in {where} must be a path")
        path = path.strip() if isinstance(path, str) else ""
        if not path:
            result, reason = "missing", f"not declared - set project.{KEY}.{key} in {where}"
        elif os.path.isabs(path) or not _inside(project_root, path):
            result, reason = "missing", f"{path} is outside the project root"
        elif not os.path.exists(os.path.join(project_root, path)):
            result, reason = "missing", f"{path} does not exist"
        else:
            result, reason = "present", path
        out.append({"key": key, "name": name, "path": path or None,
                    "result": result, "reason": reason})
    return out


def missing(found):
    """The names of the missing pieces in `found`, in `PIECES` order."""
    return [p["name"] for p in found if p["result"] == "missing"]


def report(project_root):
    """What `compass readiness` shows: `{pieces, missing}`, or None when the
    project turned the strategy off or pins a default major before it."""
    state, _ = acceptance_strategy.setting(project_root)
    if state == "off" or acceptance_strategy.pinned_below(project_root):
        return None
    found = pieces(project_root)
    return {"pieces": found, "missing": missing(found)}


def lines(reported):
    """The text block of `compass readiness` for `report`'s result."""
    if reported is None:
        return ["  Support code: not reported - the four-layer acceptance strategy is off "
                "for this project."]
    width = max(len(name) for _, name in PIECES)
    out = ["  Support code of the four-layer acceptance strategy (`S17`), reported only: "
           "it changes neither the score nor the floor."]
    out += [f"    {p['name']:<{width}}  {p['result']:<7}  {p['reason']}"
            for p in reported["pieces"]]
    return out


def _check_acceptance_support_present(task, task_dir):
    """The advisory check: on an issue the strategy applies to that has a green
    on record, every piece of support code is named and exists. A missing piece
    states the claim limit."""
    applies, why = acceptance_strategy.in_scope(task, task_dir)
    if not applies:
        return NOTHING_TO_CHECK, f"not required: the strategy does not apply - {why}"
    # The claim limit is about what a passing run lets the issue claim. Before
    # a green there is no claim to limit, and readiness already names the pieces.
    from compass_pkg.outer_loop import green_records
    if not green_records(task, task_dir):
        return NOTHING_TO_CHECK, ("not yet judged: no green is on record, so the issue "
                                  "claims nothing the claim limit could limit")
    from compass_pkg.layers import find_project_root
    root = find_project_root(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))
    gone = [p for p in pieces(root) if p["result"] == "missing"]
    if not gone:
        return True, "every piece of support code is named and exists"
    named = "; ".join(f"{p['name']} ({p['reason']})" for p in gone)
    return False, (f"missing support code: {named}. The first issue the strategy applies "
                   f"to builds the missing pieces. Claim limit: {CLAIM_LIMIT}")
