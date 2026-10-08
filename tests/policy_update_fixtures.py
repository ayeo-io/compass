"""A fixture second shipped default, and projects that extend the first.

Only default@6 ships today. `policy update` reads any major the framework
keeps, so these builders make a framework root of the same shape a real next
major would leave: the previous major kept as `default@6` and the new one as
`default`. The new one is a copy of the real default with named changes, so
the project layers here merge over a full default and the classifier and the
replay run over it.

A project waives one field: `approaches.regular.subtask_ceiling`, raised
from 2 to 5 (a loosening the classifier sees). Each change below says
whether it moves that field.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REAL_DEFAULT = ROOT / "governance" / "presets" / "default"

# The changes a second default can carry. `ceiling` moves the waived field's
# parent value (2 to 3) and loosens the hotfix ceiling (1 to 2); `unrelated`
# rewords one check, which no waiver reads; `drop-entry` removes a check a
# waiver in another fixture sits on.
CHANGES = ("ceiling", "unrelated", "drop-entry", "none")


def _edit(directory, name, change):
    path = directory / f"{name}.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc[name])
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=10000), encoding="utf-8")


def framework_root(base, change="ceiling", version="7.0.0"):
    """A directory shaped like the framework: `governance/presets/default@6`
    (the real default, kept) and `governance/presets/default` at `version`
    with the named change."""
    presets = Path(base) / "governance" / "presets"
    presets.mkdir(parents=True)
    shutil.copytree(REAL_DEFAULT, presets / "default@6")
    shutil.copytree(REAL_DEFAULT, presets / "default")
    new = presets / "default"
    meta = yaml.safe_load((new / "preset.yml").read_text(encoding="utf-8"))
    meta["version"] = version
    (new / "preset.yml").write_text(yaml.safe_dump(meta, sort_keys=False, width=10000),
                                    encoding="utf-8")
    if change == "approvers":
        # The ceiling change, and a different approver list in each default: the
        # old default names alex and the new one names morgan.
        old = presets / "default@6"
        kept = yaml.safe_load((old / "preset.yml").read_text(encoding="utf-8"))
        kept["approvers"] = {"project-waiver": ["alex"]}
        (old / "preset.yml").write_text(yaml.safe_dump(kept, sort_keys=False, width=10000),
                                        encoding="utf-8")
        meta["approvers"] = {"project-waiver": ["morgan"]}
        (new / "preset.yml").write_text(yaml.safe_dump(meta, sort_keys=False, width=10000),
                                        encoding="utf-8")
        change = "ceiling"
    if change == "ceiling":
        # The waived field, and one the project does not override, so the
        # move also changes what the project is held to.
        _edit(new, "approaches", lambda a: (a["regular"].update(subtask_ceiling=3),
                                            a["hotfix"].update(subtask_ceiling=2)))
    elif change == "unrelated":
        _edit(new, "checks", lambda c: c["backfills-paid"].update(
            statement="Every follow-up on the issue is closed before it ships."))
    elif change == "drop-entry":
        _edit(new, "checks", lambda c: c.pop("backfills-paid"))
    elif change != "none":
        raise ValueError(change)
    return Path(base)


CEILING_WAIVER = """\
    waiver:
      reason: Our work splits into more parallel subtasks than the default allows.
      approved_by: jed72
      approved_on: 2026-10-05
"""

# The project file the tests move. The comments and the blank line must
# survive a move byte for byte.
PROJECT = """\
# The project's configuration.
schema: 1
extends: compass:default@6   # the shipped default
owner: jed72

approaches:
  regular:
    set:
      subtask_ceiling: 5
""" + CEILING_WAIVER

# A waiver on a check, for the fixture that drops that check.
DROPPED_PROJECT = """\
schema: 1
extends: compass:default@6
owner: jed72

checks:
  backfills-paid:
    set:
      severity: advisory
    waiver:
      reason: Follow-ups are tracked outside the manifest here.
      approved_by: jed72
      approved_on: 2026-10-05
"""

NO_WAIVER = """\
# A project with no waiver.
schema: 1
extends: compass:default@6   # the shipped default
owner: jed72
"""

MAP_FORM = """\
schema: 1
extends:
  from: compass:default@6   # the shipped default
owner: jed72
"""


def project(base, text=PROJECT):
    """A project root holding `compass.yml` with `text`."""
    base = Path(base)
    (base / ".compass").mkdir(parents=True, exist_ok=True)
    (base / "compass.yml").write_text(text, encoding="utf-8")
    return base
