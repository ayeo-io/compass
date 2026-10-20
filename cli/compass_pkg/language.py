# compass_pkg.language - the `language` setting: its tag rules and its session line
"""The one owner of the rules for the `language` setting.

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
    """The tag in standard letter case (`en-US`, `zh-Hans`, `de`), or `None`
    when `value` is not text or is not a tag. Rebuilt from the matched groups,
    so no other character of the input can survive."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) > TAG_LIMIT:
        return None                     # no tag is longer; skip the match on long input
    found = _SHAPE.fullmatch(text)
    if not found:
        return None
    lang, script, region = found.groups()
    tag = lang.lower()
    if script:
        tag += "-" + script.title()
    if region:
        tag += "-" + region.upper()
    return tag


def _shown(value):
    """The value as a person reads it in a message: at most `SHOWN`
    characters, then `...`, with every character outside printable ASCII
    replaced by `?`."""
    text = value if isinstance(value, str) else str(value)
    cut = text[:SHOWN] + ("..." if len(text) > SHOWN else "")
    return "".join(ch if " " <= ch <= "~" else "?" for ch in cut)


def problem(value, source="compass.yml"):
    """One sentence that says why `value` is not a tag, or `None` when it is a
    tag or is unset (`None`)."""
    if value is None or canonical(value) is not None:
        return None
    head = f"`language` in {source}"
    if not isinstance(value, str):
        text = f"{head} must be text such as `en-US`, and `{_shown(value)}` is not text."
        if value is False:
            text += " Norwegian is `nb`, not `no`."
        return f"{text} See docs/configuration.md."
    if not value.strip():
        return (f"{head} is empty. Write a tag such as `en-US`, or remove the line to "
                "give no instruction. See docs/configuration.md.")
    guess = canonical(value.replace("_", "-"))
    hint = f" Did you mean `{guess}`?" if guess else ""
    return (f"{head} is `{_shown(value)}`, which is not a language tag. Write a language, "
            "an optional script and an optional region, joined by hyphens: `en-US`, "
            f"`de` or `zh-Hans`.{hint} Leave `language` out to give no instruction. "
            "See docs/configuration.md.")


def line(value):
    """The one line for the session start, or `""` when `value` is no tag."""
    tag = canonical(value)
    return LINE.format(tag=tag) if tag else ""


def hook_line(project_root):
    """The line for the project at `project_root`. It catches nothing: the
    session-start hook wraps the call."""
    return line(project_settings.settings(project_root).get("language"))
