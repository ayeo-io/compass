# compass_pkg.language - the `language` setting: its tag rules and its session line
"""The one owner of the rules for the `language` setting (DD-1).

`language` in a project's own `compass.yml` is a BCP 47 language tag: a
language, an optional script and an optional region, joined by hyphens, such
as `en-US`, `de` or `zh-Hans`. Unset means no instruction. Only the shape is
checked, never the IANA registry, so no data file and no network are needed.

- `canonical(value)`: the tag in its standard letter case, or `None`.
- `problem(value, source)`: one short sentence that says what is wrong, or
  `None` when the value is a tag or is unset.
- `line(value)`: the one line the session start gives the agent, built from
  the canonical tag only, so a value can never carry text into a session.
- `hook_line(project_root)`: that line for a project. It catches nothing; the
  session-start hook wraps the call so a failure loses only the line.
"""
# DEPENDENCY: standard library (re); compass_pkg.project_settings; imports
# nothing else from Compass.
from __future__ import annotations

import re

from compass_pkg import project_settings

TAG_LIMIT = 12
SHOWN = 20
LINE = ("Write all prose in {tag}. Code identifiers keep their names; "
        "Compass section headings stay in US English.")
# Used with fullmatch: language, optional script, optional region.
_SHAPE = re.compile(r"([A-Za-z]{2,3})(?:-([A-Za-z]{4}))?(?:-([A-Za-z]{2}|[0-9]{3}))?")


def canonical(value):
    raise NotImplementedError


def problem(value, source="compass.yml"):
    raise NotImplementedError


def line(value):
    raise NotImplementedError


def hook_line(project_root):
    raise NotImplementedError
