# compass_pkg.dod_due - when the Definition of Done is due for `dod-evidence-typed`
"""Whether `dod-evidence-typed` judges an issue's Definition of Done yet.

The items are judged once every gate has passed (ADR-091): before then the
check has nothing to check, unless another issue's outstanding follow-up that
targets this one fails it (`inbound`).

A path issue (ADR-092) owes the Definition of Done only when its
`evidence_required` lists `definition-of-done`, whatever its manifest says
of stage modes. An issue assessed before 9.0.0 owes it by its `verify` mode,
which `checks._check_dod_evidence_typed` reads.
"""
# DEPENDENCY: compass_pkg.check_results, compass_pkg.gate_status, compass_pkg.path_readers.
from __future__ import annotations

from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.path_readers import owes


def waits_for_gates(task, inbound):
    """The verdict while a gate has not passed, or None once every gate has."""
    from compass_pkg import gate_status
    if gate_status.all_gates_passed(task):
        return None
    if inbound:
        return False, "; ".join(inbound)
    waiting = gate_status.unmet_gates(task)
    return NOTHING_TO_CHECK, ("the Definition of Done is judged once every gate has "
                              "passed; %s" % ("%d gate(s) have not passed: %s"
                                              % (len(waiting), ", ".join(waiting))
                                              if waiting else "the issue has no gate"))


def path_verdict(task, inbound):
    """The verdict of a path issue's Definition of Done before its items are read,
    or None when the items are due. A path issue writes no verification report,
    so a report on disk changes nothing here."""
    if not owes(task, "definition-of-done"):
        if inbound:
            return False, "; ".join(inbound)
        return NOTHING_TO_CHECK, ("this path issue's evidence_required does not list "
                                  "definition-of-done, so it holds no Definition of Done")
    return waits_for_gates(task, inbound)
