#!/usr/bin/env python3
"""Write, or check, the four generated tables of `docs/upgrade-9-0-0.md`.

The guide names what 9.0.0 removed. Four of its tables come from data, so the
page cannot disagree with the CLI:

- the removed `compass.yml` keys, from `removed_parts.REPLACEMENTS`, the same
  table `compass policy lint` and `compass migrate` read;
- the removed verbs and flags, from `removed_parts.COMMANDS`, the same table
  the parse error reads;
- the removed slash commands, from `REMOVED_SLASH` below, checked against the
  commands of 8.0.4 (`COMMANDS_8_0_4`) and the `commands/` folder;
- the deleted checks, from `check_registry.REMOVED` and
  `removed_parts.READY_CHECKS`, the set `compass check` refuses a setting or a
  waiver for (`check_registry.DELETED_CHECKS`).

Each table sits between two marker lines. With no option this script rewrites
the text between each pair. `--check` writes nothing and exits 1 when the page
differs from a fresh render. `tests/test_upgrade_9_0_0_guide.py` runs the same
render, so a stale page fails the build.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDE = os.path.join(ROOT, "docs", "upgrade-9-0-0.md")
sys.path.insert(0, os.path.join(ROOT, "cli"))

from compass_pkg import check_registry, removed_parts  # noqa: E402

#: The slash commands Compass 8.0.4 shipped (`git ls-tree v8.0.4 commands/`).
#: Held here so the check runs in a clone without the tag; the test compares
#: this list with the tag when the tag is present.
COMMANDS_8_0_4 = (
    "approve", "assess", "breakdown", "consult", "define", "delegate", "design",
    "flow", "go", "implement", "init", "intent", "plan", "position", "quick-fix",
    "refine", "reject", "resume", "revoke", "ship", "status", "verify",
)

#: Each group of slash commands 9.0.0 removed, what to use instead, and the
#: decision record that removed it. `/compass:flow` is still shipped.
REMOVED_SLASH = (
    (("define", "refine", "plan"), "the specify stage of `/compass:go`", "ADR-092"),
    (("breakdown", "implement"), "the build stage of `/compass:go`", "ADR-092"),
    (("verify",), "the ship stage of `/compass:go`, and `/compass:ship`", "ADR-092"),
    (("intent", "position", "design", "consult"),
     "nothing: the four role entry points have no replacement", "ADR-093"),
)

MARKERS = {
    "settings": ("<!-- compass:upgrade-settings-table -->",
                 "<!-- /compass:upgrade-settings-table -->"),
    "commands": ("<!-- compass:upgrade-commands-table -->",
                 "<!-- /compass:upgrade-commands-table -->"),
    "slash": ("<!-- compass:upgrade-slash-table -->",
              "<!-- /compass:upgrade-slash-table -->"),
    "checks": ("<!-- compass:upgrade-checks-table -->",
               "<!-- /compass:upgrade-checks-table -->"),
}


def _family(key):
    """`(catalog, id)` for a key that is one entry of a catalog, such as
    `stages.design`, else None."""
    head, _, rest = key.partition(".")
    return (head, rest) if rest and "." not in rest and "*" not in rest else None


def settings_lines():
    """The removed `compass.yml` keys, one row per `REPLACEMENTS` key. Entries
    of one catalog that follow each other with the same replacement share one
    row. The same rows as the table of `docs/configuration.md`."""
    groups = []
    for key, row in removed_parts.REPLACEMENTS.items():
        family = _family(key)
        last = groups[-1] if groups else None
        if family and last and last[0] == family[0] and last[2] == row:
            last[1].append(family[1])
        else:
            groups.append((family[0] if family else key, [family[1]] if family else [], row))
    lines = ["| Removed key | Replacement | `compass migrate` |", "|---|---|---|"]
    for head, ids, (settings, migrated) in groups:
        name = (f"`{head}.{ids[0]}`" if len(ids) == 1 else
                f"`{head}.<id>`: " + ", ".join(f"`{i}`" for i in ids)) if ids else f"`{head}`"
        instead = " or ".join(f"`{s}`" for s in settings) if settings else "removed"
        lines.append(f"| {name} | {instead} | {'rewrites it' if migrated else 'no'} |")
    return lines


def command_lines():
    """The removed verbs and flags, one row per `removed_parts.COMMANDS` entry.
    The spelling leaves out the leading `compass `, as the 7.0.0 guide does."""
    lines = ["| Removed | Use instead | Decision |", "|---|---|---|"]
    for _tokens, name, instead, adr in removed_parts.COMMANDS:
        spelling = name.removeprefix("compass ")
        lines.append(f"| `{spelling}` | {instead} | {adr} |")
    return lines


def slash_lines():
    """The removed slash commands, one row per group of `REMOVED_SLASH`."""
    lines = ["| Removed | Use instead | Decision |", "|---|---|---|"]
    for names, instead, adr in REMOVED_SLASH:
        removed = ", ".join(f"`/compass:{n}`" for n in names)
        lines.append(f"| {removed} | {instead} | {adr} |")
    return lines


def check_lines():
    """The deleted checks: each of `check_registry.REMOVED` with the release
    that removed it, then the Definition of Ready checks (9.0.0, ADR-092)."""
    lines = ["| Deleted check | Removed in |", "|---|---|"]
    for check_id, removed in check_registry.REMOVED.items():
        lines.append(f"| `{check_id}` | {removed.removed_in} |")
    for check_id in removed_parts.READY_CHECKS:
        lines.append(f"| `{check_id}` | {removed_parts.RELEASE} |")
    return lines


RENDERERS = {"settings": settings_lines, "commands": command_lines, "slash": slash_lines,
             "checks": check_lines}


def held(text, name):
    """The lines of `text` between the two markers of the table `name`."""
    start, end = MARKERS[name]
    if start not in text or end not in text:
        raise ValueError(f"{GUIDE}: the markers of the {name} table are missing")
    return text.split(start, 1)[1].split(end, 1)[0].strip().splitlines()


def render(text):
    """`text` with each table between its markers rewritten from the data."""
    for name, lines_of in RENDERERS.items():
        start, end = MARKERS[name]
        held(text, name)
        before, rest = text.split(start, 1)
        _old, after = rest.split(end, 1)
        text = before + start + "\n" + "\n".join(lines_of()) + "\n" + end + after
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when the page is stale")
    args = parser.parse_args(argv)
    with open(GUIDE, encoding="utf-8") as handle:
        text = handle.read()
    fresh = render(text)
    if args.check:
        if fresh != text:
            print(f"{GUIDE} is stale: run scripts/render-upgrade-guide.py")
            return 1
        return 0
    if fresh != text:
        with open(GUIDE, "w", encoding="utf-8") as handle:
            handle.write(fresh)
        print(f"{GUIDE}: tables rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
