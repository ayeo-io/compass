# compass_pkg.retired - the assessment dimension and the rules 7.0.0 removed
"""What 7.0.0 removed from the assessment, and what replaces it (ADR-070).

`role` is no longer an assessment dimension. The two blocking role rules are
now artifact rules, keyed on the documents on disk, and the designer's role
default is dropped. 6.x records and calls keep working: a recorded role is not
read, a role flag is accepted and ignored, and a stored generation keeps the
rules it was assessed under. The messages that say so are built here, so every
command says it the same way.

"""
# DEPENDENCY: standard library. Imported by compass_pkg.routing,
# compass_pkg.justifications, compass_pkg.quick_fix_cmd, compass_pkg.evidence_required and compass_pkg.migrate.
from __future__ import annotations

#: The assessment dimensions the shipped default no longer declares.
DIMENSIONS = ("role",)

RELEASE = "7.0.0"

NOT_READ = (f"role is no longer an assessment dimension from {RELEASE} (ADR-070), "
            f"so the value is ignored")


def notice(where):
    """The one line a command prints on standard error for a role it ignores."""
    return f"compass: {where}: {NOT_READ}"
