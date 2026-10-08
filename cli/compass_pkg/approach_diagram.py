# compass_pkg.approach_diagram - `compass approach diagram`
"""The delivery approaches as one HTML table, generated from the policy.

What each approach does lives in `route_shapes` and `autonomy_checkpoints`
in `governance/routing-policy.yml`, which nobody reads for an overview. This
renders them: one row per approach, one column per stage, the weight in each
cell as a word, and "stops for you" where the chosen autonomy setting makes
the stage wait for a person. The shipped policy's render is committed as
`docs/approach-diagram.html`, and a test fails when it goes stale.

The output carries no date and no colour that matters: two renders of one
policy are byte-identical, and every cell reads in plain text.
"""
# DEPENDENCY: standard library (html, os, sys); compass_pkg.core, effective, routing, stable_ids.
from __future__ import annotations

import html
import os
import sys

from compass_pkg.stable_ids import STAGE_IDS
from compass_pkg.core import (AUTONOMY_VALUES, CompassError, find_governance,
                              load_autonomy, load_yaml)
from compass_pkg.routing import canonical_routes

STAGES = STAGE_IDS

# The three ways an issue goes back, whatever its approach.
WAYS_BACK = (
    ("A reassessment", "`/compass:assess --reassess` re-reads the four "
     "dimensions when the work turns out bigger or riskier, and the approach "
     "is computed again."),
    ("A refusal from the pre-tool hook", "an edit is refused until its "
     "precondition holds, such as a failing test on record."),
    ("A failed `compass check`", "the guardrail checks refuse to pass a gate "
     "until the evidence they need is on disk."),
)

_STYLE = """
body { font-family: system-ui, sans-serif; margin: 16px; color: #1a1a1a; background: #fff; }
.wide { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #999; padding: 6px; vertical-align: top; text-align: left; }
th { background: #eee; }
td .stop { display: block; font-weight: bold; }
td.skipped, td.collapsed { color: #555; }
@media (prefers-color-scheme: dark) {
  body { color: #eee; background: #111; }
  th { background: #333; }
  th, td { border-color: #666; }
  td.skipped, td.collapsed { color: #aaa; }
}
"""


LEGACY_SOURCE = "governance/routing-policy.yml"
LAYERED_SOURCE = ("the effective configuration: <code>compass.yml</code> over the "
                  "shipped default preset")


def render(policy, autonomy, stages=None, source=None):
    """The HTML page for `policy` under `autonomy`. `stages` are the columns,
    in order (the eight shipped stages when left out). `source` is the markup
    that names where `policy` came from (the legacy file when left out)."""
    columns = stages or STAGES
    source = source or f"<code>{LEGACY_SOURCE}</code>"
    policy, _ = canonical_routes(policy)
    shapes = policy.get("route_shapes") or {}
    stops = (policy.get("autonomy_checkpoints") or {}).get(autonomy) or {}
    esc = html.escape
    rows = []
    for approach, shape in shapes.items():
        shape = shape if isinstance(shape, dict) else {}
        weights = shape.get("stages") or {}
        cells = []
        for stage in columns:
            weight = str(weights.get(stage, "not set"))
            # A skipped or collapsed stage has no hand-off, so it never waits.
            stop = ('<span class="stop">stops for you</span>'
                    if stage in (stops.get(approach) or [])
                    and weight not in ("skipped", "collapsed") else "")
            cells.append(f'<td data-stage="{stage}" class="{esc(weight)}">'
                         f'{esc(weight)}{stop}</td>')
        gates = ", ".join(esc(str(g)) for g in shape.get("gates") or []) or "none"
        documents = ", ".join(
            f"{esc(str(name))} ({esc(str(depth))})"
            for name, depth in (shape.get("artifacts") or {}).items()) or "none"
        # `null` in the policy means no ceiling; a missing key is not set.
        ceiling = ("no limit" if "subtask_ceiling" in shape
                   and shape["subtask_ceiling"] is None
                   else esc(str(shape.get("subtask_ceiling", "not set"))))
        rows.append(f'<tr data-approach="{esc(approach)}"><th>{esc(approach)}</th>'
                    + "".join(cells)
                    + f"<td>{gates}</td><td>{ceiling}</td><td>{documents}</td></tr>")
    header = ("<tr><th>Approach</th>"
              + "".join(f"<th>{s}</th>" for s in columns)
              + "<th>Gates</th><th>Subtask ceiling</th><th>Documents</th></tr>")
    ways = "".join(f"<li><strong>{esc(name)}</strong>: {esc(text)}</li>"
                   for name, text in WAYS_BACK)
    return (
        "<!doctype html>\n<html lang=\"en-GB\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>Compass delivery approaches</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n"
        "<h1>Compass delivery approaches</h1>\n"
        f"<p>Generated by <code>compass approach diagram</code> from "
        f"{source}, with autonomy set to "
        f"<strong>{esc(autonomy)}</strong>. Each cell names the stage's "
        f"weight, and a stage that waits for a person under this setting "
        f"says so in bold. Do not edit this file by hand.</p>\n"
        f"<div class=\"wide\"><table>\n{header}\n" + "\n".join(rows)
        + "\n</table></div>\n"
        "<p>These are the defaults for each approach. A floor for critical "
        "risk or a domain label (auth, payments, personal data, migrations) "
        "can raise an issue to a heavier approach, and other rules and roles "
        "can add gates, documents or a sign-off that no autonomy setting "
        "removes. <code>governance/routing-policy.md</code> explains each "
        "rule; <code>compass approach summary</code> shows what one issue "
        "gets.</p>\n"
        "<h2>How work comes back</h2>\n"
        f"<ul>{ways}</ul>\n</body>\n</html>\n")


def cmd_approach_diagram(args):
    # A project with a `compass.yml` is drawn from its effective configuration;
    # any other project from the governance files, as before.
    from compass_pkg import effective
    view = effective.view_or_legacy()
    autonomy = args.autonomy or (view.autonomy if view is not None else load_autonomy())
    if autonomy not in AUTONOMY_VALUES:
        raise CompassError(
            f"compass approach diagram: '{autonomy}' is not an autonomy "
            f"setting; use {', '.join(AUTONOMY_VALUES)}.")
    if view is not None:
        page = render(view.evaluator_policy(), autonomy, view.stage_order() or STAGES,
                      LAYERED_SOURCE)
    else:
        policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml")) or {}
        page = render(policy, autonomy)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(page)
        print(f"compass approach diagram: wrote {args.out} ({autonomy}).")
    else:
        sys.stdout.write(page)
    return 0
