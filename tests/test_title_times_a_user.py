"""A scenario title the public-copy check would refuse is refused when it is
recorded.

A title reaches the living spec, which is public copy. One that attached a
duration to a user's experience passed `compass scenario add` and the local
suite, then failed CI after the spec was re-derived (issue #359). The
public-copy patterns now live in `compass_pkg.public_copy`, read by both
`title_problem` and `tests/test_public_copy_claims.py`.

Scenario id: TT-1 (issue `title-times-a-user`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.manifest import title_problem  # noqa: E402


def test_tt_1_a_title_that_times_a_user_is_refused():
    problem = title_problem(str(ROOT), "Given the repo, then the board "
                                      "finishes in under two seconds.")
    assert problem and "duration" in problem, problem


def test_tt_1_a_title_that_claims_an_outside_user_is_refused():
    problem = title_problem(str(ROOT), "Given the fix, then a user reported "
                                      "it works.")
    assert problem and "outside" in problem, problem


def test_tt_1_an_ordinary_title_passes():
    assert title_problem(str(ROOT), "Given a queued issue, then the board "
                                    "shows its age.") is None


def test_tt_1_the_check_and_the_title_share_one_list():
    from compass_pkg import public_copy
    import test_public_copy_claims as check
    assert check.USER_TIMING_PATTERNS is public_copy.USER_TIMING_PATTERNS
    assert check.OUTSIDE_USER_PATTERNS is public_copy.OUTSIDE_USER_PATTERNS
