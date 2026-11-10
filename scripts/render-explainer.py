#!/usr/bin/env python3
"""Write, or check, the README's animated explainer.

`assets/compass-explainer.svg` is the picture under the README's pitch: three
sliders for risk, familiarity and size, a policy arrow, the four stages of the
path as bars whose height is the evidence each stage judges, dots on the
stages where a person decides, and five guardrail lines that never move.
GitHub animates it through an `<img>` tag, so the file holds SMIL and CSS only
and no script.

Nothing in the picture is drawn by hand from the policy. Each scene is an
example assessment; this script runs it through `evidence_required.evaluate`,
the same pure function `compass approach evaluate` runs, and draws what comes
back: the rules that fired, how many pieces of evidence each stage judges,
and the stages where a person decides under the `balanced` autonomy setting. A changed shipped policy changes the picture, and
`tests/test_render_explainer.py` fails when the committed file is stale, so
the README cannot disagree with `governance/check-set.yml`.

With no option this writes the file. `--check` writes nothing and exits 1
when the committed file differs from what this writes. Two runs write the
same bytes.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))

from compass_pkg import check_set, effective, evidence_required  # noqa: E402
from compass_pkg.path_writer import checkpoints_for  # noqa: E402
from compass_pkg.stable_ids import PATH_STAGE_IDS as STAGE_IDS  # noqa: E402

OUTPUT = os.path.join(ROOT, "assets", "compass-explainer.svg")
AUTONOMY = "balanced"

# One loop, three scenes. Each scene is an example assessment and the words
# a reader sees for it. The evidence each one owes is not written here: the
# policy computes it. Every change owes the one common row (ADR-099); the
# second and third scenes each add a person's approval to it.
SCENES = (
    ("Fix a typo in the docs",
     {"risk": "trivial", "familiarity": "brownfield-mapped", "size": "atomic"}),
    ("Change how the job queue retries",
     {"risk": "critical", "familiarity": "brownfield-mapped", "size": "small"}),
    ("Rewrite the payments ledger",
     {"risk": "critical", "familiarity": "brownfield-unmapped", "size": "large",
      "labels": ["payments"]}),
)

# The words a reader sees for the evidence a scene owes, by the rules that
# fired beside the common row (`governance/routing-policy.md`).
COMMON_ROW = "RP-EVID-COMMON"
ADDED_NAMES = (("G5", "the common row, the scenario approval and the sign-off"),
               ("RP-EVID-SIGNOFF", "the common row and the scenario approval"))

# The stage of the path that judges each evidence token, as the table in
# `approaches/path.md` places it. Assess judges the request link (#356) and is
# drawn with one more item, the assessment it records.
STAGE_OF_TOKEN = {
    "request": "assess",
    "scenarios": "specify", "scenario-approval": "specify",
    "red-before-green": "build", "outer-loop": "build", "isolation": "build",
    "layering": "build", "definition-of-done": "build", "reproduce-first": "build",
    "suite-green": "ship", "correctness": "ship", "governance": "ship",
    "traceability": "ship", "regression": "ship", "security": "ship",
    "clarity": "ship", "architecture": "ship", "human-approval": "ship",
    "ship-approval": "ship",
}
# The evidence that is a person's decision at ship, beside the checkpoints. The ship
# approval every change owes is not one: Compass reads it from the merged pull
# request's review, so it adds no stop in the session (#355).
PERSON_AT_SHIP = "human-approval"
LOOP_SECONDS = 18

# The dimensions drawn, top to bottom, and the short form of each value that
# fits under a tick. A value with no short form is drawn as it is.
DIMENSIONS = ("risk", "familiarity", "size")
SHORT = {"brownfield-mapped": "mapped", "brownfield-unmapped": "unmapped"}

# The height of a bar is this many pixels for each item the stage judges.
BASELINE = 330
PER_ITEM = 13

# The five guardrails, as the safety contract states them.
GUARDRAILS = ("tested before it ships", "acceptance before code",
              "every change traces to a criterion", "evidence, not assertion",
              "a person approves the irreversible")

# A 3Blue1Brown-style palette: a dark ground, one color for each dimension,
# blue for the computed evidence, green for what never moves.
BG, TEXT, MUTED, TICK = "#15171c", "#d9d9d9", "#9a9a9a", "#444a55"
DIM_COLORS = {"risk": "#fc6255", "familiarity": "#58c4dd", "size": "#ffd93d"}
BAR, STOP, GUARD = "#58c4dd", "#ffd93d", "#83c167"

# Each scene holds, then eases into the next over the last tenth of its
# slot. Seven key times: the start, then a hold end and a move end per scene.
HOLD = 0.9

EASE = "0.4 0 0.2 1"


def _key_times(count):
    """The SMIL keyTimes for `count` scenes in one loop: 0, then for each
    scene the end of its hold and the end of its move, the last move landing
    on 1 as the loop returns to the first scene."""
    slot = 1.0 / count
    times = [0.0]
    for i in range(count):
        times.append(round((i + HOLD) * slot, 4))
        times.append(round((i + 1) * slot, 4))
    times[-1] = 1.0
    return times


def _keyed(values):
    """`values` holds one value per scene; the animation holds each, then
    moves to the next, and comes back to the first."""
    out = []
    for v in values:
        out += [v, v]
    out.append(values[0])
    return out


def _animate(attr, values, spline=True):
    times = _key_times(len(SCENES))
    vals = _keyed(values)
    assert len(vals) == len(times)
    easing = (f' calcMode="spline" keySplines="{";".join([EASE] * (len(times) - 1))}"'
              if spline else "")
    return (f'<animate attributeName="{attr}" values="{";".join(str(v) for v in vals)}" '
            f'keyTimes="{";".join(str(t) for t in times)}" dur="{LOOP_SECONDS}s" '
            f'repeatCount="indefinite"{easing}/>')


def _visible(index):
    """Opacity values that show one scene's text and hide the others."""
    return [1 if i == index else 0 for i in range(len(SCENES))]


def _fading_texts(x, y, cls, texts):
    """One `<text>` per scene at the same place, each visible in its scene."""
    out = []
    for i, text in enumerate(texts):
        hidden = "" if i == 0 else ' opacity="0"'
        out.append(f'    <text class="{cls}" x="{x}" y="{y}"{hidden}>\n'
                   f'      {text}\n'
                   f'      {_animate("opacity", _visible(i), spline=False)}\n'
                   f'    </text>')
    return "\n".join(out)


def scenes(policy):
    """Each scene with what the policy computes for it: the evidence row, the
    evidence it owes, the number of items each stage judges and the stages
    where a person decides under `balanced`."""
    out = []
    for caption, assessment in SCENES:
        result = evidence_required.evaluate(dict(assessment), policy)
        owed = result["evidence_required"]
        unknown = [t for t in owed if t not in STAGE_OF_TOKEN]
        if unknown:
            raise SystemExit(f"render-explainer: no stage for evidence {unknown}")
        items = {stage: sum(1 for t in owed if STAGE_OF_TOKEN[t] == stage)
                 for stage in STAGE_IDS}
        items[STAGE_IDS[0]] += 1
        stops = set(checkpoints_for(owed, AUTONOMY, result["acceptance_applies"]))
        if PERSON_AT_SHIP in owed:
            stops.add("ship")
        fired = result["rules_fired"]
        row = fired[0]
        if row != COMMON_ROW:
            raise SystemExit(f"render-explainer: no name for the evidence row {row}")
        name = next((words for rule, words in ADDED_NAMES if rule in fired), "the common row")
        out.append({"caption": caption, "assessment": assessment, "row": row,
                    "label": f"{name}: {len(owed)} pieces of evidence",
                    "evidence": owed, "items": items, "stops": stops})
    return out


def _sliders(policy, computed):
    vocab = policy["assessment_vocabulary"]
    parts = []
    y = 160
    for dim in DIMENSIONS:
        values = list(vocab[dim])
        x0, x1 = 110, 330
        step = (x1 - x0) / (len(values) - 1)
        xs = {v: round(x0 + i * step) for i, v in enumerate(values)}
        ticks = "".join(
            f'      <circle cx="{xs[v]}" cy="-5" r="2.5" fill="{TICK}"/>'
            f'<text x="{xs[v]}" y="14" text-anchor="middle">{SHORT.get(v, v)}</text>\n'
            for v in values)
        marker = [xs[s["assessment"][dim]] for s in computed]
        parts.append(
            f'  <g transform="translate(40,{y})">\n'
            f'    <text class="dim" x="0" y="0">{dim}</text>\n'
            f'    <line x1="{x0}" y1="-5" x2="{x1}" y2="-5" stroke="{TICK}" stroke-width="2"/>\n'
            f'    <g class="tick">\n{ticks}    </g>\n'
            f'    <circle cx="{marker[0]}" cy="-5" r="7" fill="{DIM_COLORS[dim]}">\n'
            f'      {_animate("cx", marker)}\n'
            f'    </circle>\n'
            f'  </g>')
        y += 60
    return "\n".join(parts)


def _bars(computed):
    parts = []
    x = 530
    pitch = 100
    for stage in STAGE_IDS:
        heights = [s["items"][stage] * PER_ITEM for s in computed]
        ys = [BASELINE - h for h in heights]
        parts.append(
            f'    <rect x="{x}" y="{ys[0]}" width="60" height="{heights[0]}" fill="{BAR}" rx="2">\n'
            f'      {_animate("height", heights)}\n'
            f'      {_animate("y", ys)}\n'
            f'    </rect>')
        # A dot above the bar in each scene where a person decides here.
        stops = [1 if stage in s["stops"] else 0 for s in computed]
        if any(stops):
            parts.append(
                f'    <circle cx="{x + 30}" cy="198" r="4" fill="{STOP}" opacity="0">\n'
                f'      {_animate("opacity", stops, spline=False)}\n'
                f'    </circle>')
        parts.append(f'    <text class="stage" x="{x + 30}" y="350">{stage}</text>')
        x += pitch
    return "\n".join(parts)


def _guardrails():
    lines, labels = [], []
    for i, text in enumerate(GUARDRAILS):
        x = i * 176
        lines.append(f'      <line x1="{x}" y1="18" x2="{x + 160}" y2="18"/>')
        labels.append(f'      <text x="{x}" y="38">{text}</text>')
    return "\n".join(lines), "\n".join(labels)


def render(policy):
    computed = scenes(policy)
    lines, labels = _guardrails()
    captions = _fading_texts(40, 86, "cap", [s["caption"] for s in computed])
    names = _fading_texts(510, 156, "appr", [s["label"] for s in computed])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 500" width="960" height="500" font-family="'Latin Modern Roman','CMU Serif','Computer Modern',Georgia,'Times New Roman',serif">
  <!--
    Generated by scripts/render-explainer.py from governance/check-set.yml.
    Do not edit this file by hand: edit the script, or the policy, and run it.
    One loop of {LOOP_SECONDS} seconds, {len(SCENES)} changes of work. SMIL and
    CSS only, so GitHub animates it through an img tag. No script.
  -->
  <defs>
    <style>
      .dim    {{ fill: {TEXT}; font-size: 17px; }}
      .small  {{ fill: {MUTED}; font-size: 13px; }}
      .tick   {{ fill: #6b6b6b; font-size: 11px; }}
      .stage  {{ fill: {TEXT}; font-size: 13px; text-anchor: middle; }}
      .title  {{ fill: #ececec; font-size: 26px; }}
      .cap    {{ fill: {STOP}; font-size: 19px; font-style: italic; }}
      .appr   {{ fill: {BAR}; font-size: 22px; }}
      .guard  {{ fill: {GUARD}; font-size: 13px; }}
      .eq     {{ fill: {MUTED}; font-size: 15px; }}
    </style>
  </defs>

  <rect width="960" height="500" fill="{BG}"/>

  <text class="title" x="40" y="48">Assess the work. Let policy choose the evidence.</text>

  <g>
{captions}
  </g>

  <text class="small" x="40" y="126">JUDGMENT: three dimensions</text>

{_sliders(policy, computed)}

  <g transform="translate(400,215)">
    <line x1="0" y1="0" x2="70" y2="0" stroke="{MUTED}" stroke-width="2"/>
    <polygon points="70,-6 82,0 70,6" fill="{MUTED}"/>
    <text class="eq" x="41" y="-12" text-anchor="middle">policy</text>
    <text class="small" x="41" y="22" text-anchor="middle">deterministic</text>
  </g>

  <text class="small" x="510" y="126">COMPUTED: the evidence each stage of the path judges</text>

  <g>
{names}
  </g>

  <g>
    <line x1="505" y1="{BASELINE}" x2="925" y2="{BASELINE}" stroke="{TICK}" stroke-width="1.5"/>
{_bars(computed)}
    <text class="small" x="925" y="202" text-anchor="end" fill="{STOP}">● a person decides</text>
  </g>

  <g transform="translate(40,400)">
    <text class="guard" x="0" y="0">Five default guardrails apply to all work that ships code.</text>
    <g stroke="{GUARD}" stroke-width="3" stroke-linecap="round">
{lines}
    </g>
    <g class="tick" fill="{MUTED}">
{labels}
    </g>
  </g>

  <text class="small" x="40" y="478">Same assessment and configuration = same evidence, every time.</text>
</svg>
"""


def load_policy():
    """The routing policy the evaluator reads for a project with no settings:
    the shipped check set (`governance/check-set.yml`)."""
    return effective.EffectiveView("live", None, None, check_set.resolved(),
                                   {}).evaluator_policy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when the committed file is stale")
    parser.add_argument("--out", default=OUTPUT, help="where to write the SVG")
    args = parser.parse_args(argv)
    fresh = render(load_policy())
    if args.check:
        try:
            with open(args.out, encoding="utf-8") as fh:
                committed = fh.read()
        except FileNotFoundError:
            committed = None
        if committed != fresh:
            rel = os.path.relpath(args.out, ROOT)
            print(f"{rel} is stale: run scripts/render-explainer.py", file=sys.stderr)
            return 1
        return 0
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(fresh)
    print(f"wrote {os.path.relpath(args.out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
