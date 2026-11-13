# compass_pkg.retired - the assessment dimension and the rules 7.0.0 removed
"""What 7.0.0 removed from the assessment, and what replaces it (ADR-070).

`role` is no longer an assessment dimension. The two blocking role rules are
now artifact rules, keyed on the documents on disk, and the designer's role
default is dropped. A 6.x record keeps working: a recorded role is not read,
and a stored generation keeps the rules it was assessed under. The role flags
(`quick-fix start --role` and `--justify role=`) are deleted in 9.0.0
(ADR-098): argparse refuses the first, and the second gets the refusal of any
dimension that needs no justification. The message for a recorded role is
built here, so every command says it the same way.

"""
# DEPENDENCY: standard library. Imported by compass_pkg.routing,
# compass_pkg.evidence_required and compass_pkg.migrate.
from __future__ import annotations

#: The assessment dimensions the shipped default no longer declares.
DIMENSIONS = ("role",)

RELEASE = "7.0.0"

NOT_READ = (f"role is no longer an assessment dimension from {RELEASE} (ADR-070), "
            f"so the value is ignored")


def notice(where):
    """The one line a command prints on standard error for a role it ignores."""
    return f"compass: {where}: {NOT_READ}"
