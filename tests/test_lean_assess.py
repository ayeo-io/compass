"""A quick fix loads only the part of /compass:assess it uses.

A quick fix read the whole of `commands/assess.md`, about 10,000
characters, and read it again on every later request. The heavier-route
procedure in it - the setup, `--reassess`, procedure steps 1 to 7, voice and
gate - never changes a quick fix. That procedure now lives word for word in
`approaches/assess-procedure.md`, outside `commands/` so it is not a slash
command, and assess names it for every heavier route and for `--reassess`.

A cost-lab spike measured about 9% fewer tokens per quick-fix session. That
is inside run-to-run spread, so no saving is claimed.

Scenario id: LA-1 (issue `lean-assess`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSESS = ROOT / "commands" / "assess.md"
PROCEDURE = ROOT / "approaches" / "assess-procedure.md"

# Every section and step of the full procedure. A step dropped in the move
# would leave a heavier route without it.
PROCEDURE_PARTS = (
    "## Setup", "## `--reassess`", "## Procedure",
    "1. **Create the manifest.**", "1a. **Load project architecture if present.**",
    "2. **Read the four dimensions - this is the judgement**",
    "3. **Compute the delivery approach - this is the mechanism.**",
    "4. **Write `delivery-approach.md`**",
    "5. **Set the `.compass/current-task` pointer**",
    "6. **On a spike, write the `.spike` marker.**", "7. **Confirm.**",
    "## Voice", "## Gate",
)


def test_la_1_assess_is_within_its_budget():
    size = len(ASSESS.read_text(encoding="utf-8"))
    assert size <= 2500, f"commands/assess.md is {size} characters; the budget is 2,500"


def test_la_1_assess_keeps_the_light_path_and_names_the_procedure():
    text = ASSESS.read_text(encoding="utf-8")
    for needed in ("compass quick-fix start", "compass tdd-red",
                   "compass quick-fix finish", "--labels", "created:",
                   "settled decisions", "compass init",
                   "approaches/assess-procedure.md", "--reassess", "--reason"):
        assert needed in text, f"commands/assess.md no longer says {needed!r}"


def test_la_1_the_procedure_keeps_every_step():
    assert PROCEDURE.is_file(), "approaches/assess-procedure.md is missing"
    text = PROCEDURE.read_text(encoding="utf-8")
    missing = [part for part in PROCEDURE_PARTS if part not in text]
    assert not missing, f"the procedure lost: {missing}"


def test_la_1_the_procedure_is_not_a_slash_command():
    assert not (ROOT / "commands" / "assess-procedure.md").exists()
