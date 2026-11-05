# compass_pkg.path_readers - what the checks and hooks read on a path issue
"""The small rules every check, list and hook shares for a path issue (ADR-092).

A path issue is one whose manifest holds `evidence_required`
(`path_stages.is_path_issue`). What it owes is that list, not its stage
modes, and it waits only at the path stages. An issue assessed before 9.0.0
owes nothing here: its readers keep the rules they had.

These rules are not in `path_stages`, whose source the classifier's verdict
digest pins (`tests/test_classifier_speed.py`), because none of them decides a
route.
"""
# DEPENDENCY: compass_pkg.stable_ids and compass_pkg.path_stages only, so `core`
# can import it without a cycle.
from __future__ import annotations

from compass_pkg.path_stages import is_path_issue
from compass_pkg.stable_ids import (PATH_STAGE_IDS, STAGE_ASSESS, STAGE_DEFINE,
                                    STAGE_IMPLEMENT, STAGE_PLAN, STAGE_REFINE, STAGE_VERIFY)

#: The stage hand-offs an issue assessed before 9.0.0 can wait at (ADR-063, ADR-083).
#: The routing table check and the classifier read this tuple, so a configuration
#: cannot list a path checkpoint until the live preset declares the path stages.
LEGACY_CHECKPOINT_STAGES = (STAGE_ASSESS, STAGE_DEFINE, STAGE_REFINE, STAGE_PLAN,
                            STAGE_IMPLEMENT, STAGE_VERIFY)
#: Every stage a checkpoint outcome or request can name: the path stages, then the
#: legacy ones, so an old issue's `define` outcome still reads and still closes.
CHECKPOINT_STAGES = PATH_STAGE_IDS + tuple(
    s for s in LEGACY_CHECKPOINT_STAGES if s not in PATH_STAGE_IDS)

#: The check-id prefix of the Definition of Ready, which a path issue does not owe.
READY_PREFIX = "dor-"


def owes(task, token):
    """True when a path issue's `evidence_required` lists `token`. An old issue
    owes no token: its rules read its stages and its approach."""
    if not is_path_issue(task):
        return False
    listed = task.get("evidence_required")
    return isinstance(listed, list) and token in listed


def checkpoint_stages_of(task):
    """The stages whose hand-off this issue can wait at. A path issue waits at
    the path stages and an old issue at the legacy ones, so neither reads an
    outcome written in the other's stage names."""
    return PATH_STAGE_IDS if is_path_issue(task) else LEGACY_CHECKPOINT_STAGES
