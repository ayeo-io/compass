#!/usr/bin/env python3
"""Write, or check, the document-set diagram.

`architecture/document-set-7-0-0.svg` draws the documents each stage writes,
the traditional document each one stands in for, the blocks rendered from the
manifest, and what reads them at project level. The picture is data in this
file: the columns, the boxes and the links. With no option this writes the
SVG. `--check` writes nothing and exits 1 when the committed file differs from
a fresh render. The render uses nothing outside the standard library and is
byte-identical from one run to the next, so `tests/test_document_set_diagram.py`
can refuse a stale copy.

The diagram is the target state for 7.0.0. When that release ships, the
subtitle that says so goes, and the picture moves into the methodology page.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "architecture", "document-set-7-0-0.svg")

WIDTH, HEIGHT = 2000, 1176
TEAL = "#0f766e"
GREY = "#4b5563"
COLOURS = {
    "prd": ("#fef3c7", "#d97706"),
    "req": ("#dbeafe", "#2563eb"),
    "design": ("#ede9fe", "#7c3aed"),
    "test": ("#dcfce7", "#16a34a"),
    "review": ("#ffe4e6", "#e11d48"),
    "status": ("#f3f4f6", "#4b5563"),
    "machine": ("#e2e8f0", "#0f172a"),
    "project": ("#fafaf9", "#78716c"),
}
STAGES = ["ASSESS", "DEFINE", "REFINE", "PLAN", "BREAKDOWN", "IMPLEMENT", "VERIFY", "SHIP"]

# The project-level boxes: column, span in columns, title, lines.
PROJECT = [
    ("ASSESS", 1, "compass.yml + default preset", ["policy and the catalogue", "of document kinds"]),
    ("DEFINE", 2, "governance/decisions/", ["maintainer rulings; the decisions block",
                                            "cites the ones whose evidence names the issue"]),
    ("PLAN", 1, "architecture/decisions/", ["ADR-nnn, from project-", "scoped design decisions"]),
    ("BREAKDOWN", 1, "compass board", ["cross-issue view, local file,", "reads every manifest"]),
    ("IMPLEMENT", 1, "docs/system-spec.md", ["living spec, derived from", "completed issues"]),
    ("VERIFY", 1, "docs/compass/README.md", ["index of every issue by state,", "rendered; the front door"]),
    ("SHIP", 1, "GitHub issue", ["labels, body set once, one", "maintained comment (opt-in)"]),
]

# The issue pack: key, column, row, title, lines, colour, tags, rendered block.
PACK = [
    ("DA", "ASSESS", 0, "delivery-approach.md",
     ["why this much process:", "assessment, rules fired,", "de-scope ledger"], "status", "Q R F H S", "assessment, rules"),
    ("IN", "ASSESS", 1, "intent.md",
     ["product requirements: problem,", "outcome, success signals, non-goals", "(spike: question + timebox)"], "prd", "R-lightweight F S", ""),
    ("BR", "ASSESS", 2, "bug-report.md",
     ["reproduction, measured,", "what the fix must decide"], "prd", "H, bugs", ""),
    ("AC", "DEFINE", 0, "acceptance-criteria.md",
     ["requirements: prose summary,", "Gherkin scenarios (TRC ids),", "NFR table"], "req", "Q R F H", "coverage"),
    ("RR", "REFINE", 0, "requirements-review.md",
     ["ambiguity ledger; agent", "decisions flagged for the", "define checkpoint"], "req", "R-lightweight F", "Definition of Ready"),
    ("PO", "REFINE", 1, "product-owner-review.md",
     ["intent fidelity, read at", "the plan gate"], "review", "F", ""),
    ("TD", "PLAN", 0, "technical-design.md",
     ["HLD: approach, structure, data", "& interfaces, verification plan,", "risks, DD-n, work units"], "design", "R F", "status + digest"),
    ("LL", "PLAN", 1, "low-level-design/<unit>.md",
     ["LLD per work unit:", "signatures, contracts, tests"], "design", "F", ""),
    ("AN", "PLAN", 2, "architecture-notes.md",
     ["architect: invariants, risks,", "which DD-n become ADRs"], "design", "F cross-cutting", ""),
    ("TM", "PLAN", 3, "threat-model / rollback-plan",
     ["earned by labels: auth,", "payments, personal-data,", "migrations"], "design", "by rule", ""),
    ("DM", "BREAKDOWN", 0, "distribution-map.md",
     ["units to subtasks, waves,", "independence, caps"], "design", "2+ subtasks", "caps, subtasks"),
    ("CO", "IMPLEMENT", 0, "code + tests",
     ["each test bound to a TRC id", "from acceptance-criteria;", "red then green recorded"], "test", "Q R F H", ""),
    ("VR", "VERIFY", 0, "verification-report.md",
     ["test report: scenario results,", "review dimensions,", "release line"], "test", "R F H", "gates, DoD, evidence"),
    ("RV", "VERIFY", 1, "review-<n>.md",
     ["one file per round: scope,", "verdict, blocking, probes"], "review", "R F", ""),
    ("VN", "VERIFY", 2, "verification-note.md",
     ["one screen: scenario, records,", "gates, changed files,", "release line"], "test", "Q", "whole note"),
    ("SC", "VERIFY", 3, "spike-conclusion.md",
     ["discard, graduate or defer;", "what was learned"], "test", "S", ""),
    ("RM", "SHIP", 0, "README.md, issue page",
     ["the ask, acceptance results,", "related issues, decisions,", "artifacts, traceability chart"], "status", "all", "every block"),
    ("LR", "SHIP", 1, "launch-readiness.md",
     ["every claim traced", "to a passing scenario"], "prd", "marketer", ""),
]

# The machine band: x, width, title, lines. The last width is filled in.
MACHINE = [
    (52, 600, "manifest.yml", ["assessment · approach · stages · gates · scenarios[].tests · changed_files",
                              "artifacts[].status + digest · evidence registry · follow_ups · depends_on",
                              "decisions_taken · release_note · github link"]),
    (676, 380, "evidence/", ["red-TRC-*.json, green-TRC-*.json, check output,",
                            "review records, approvals (typed, digested)"]),
    (1080, 280, "generations/", ["the configuration this issue", "ran against, pinned"]),
    (1384, None, "compass check · compass issue render · after_command",
     ["checks read the record; render rewrites every teal block;",
      "after each record-changing command: re-render, sync GitHub"]),
]

LEGEND = [("Product requirements / brief", "prd"), ("Requirements", "req"), ("Design: HLD, LLD, ADR input", "design"),
          ("Test plan & report", "test"), ("Review record", "review"), ("Status / audit", "status"),
          ("Machine record", "machine")]


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Canvas:
    """Collects SVG elements. Labels and headers are drawn last, over the lines."""

    def __init__(self):
        self.body = []
        self.top = []

    def box(self, x, y, w, h, title, lines, kind, tags="", pill=""):
        fill, stroke = COLOURS[kind]
        self.body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" '
                         f'stroke="{stroke}" stroke-width="1.6"/>')
        self.body.append(f'<text x="{x+10}" y="{y+19}" font-size="13" font-weight="700" '
                         f'fill="#1f2937">{_esc(title)}</text>')
        yy = y + 35
        for line in lines:
            self.body.append(f'<text x="{x+10}" y="{yy}" font-size="11.2" fill="#374151">{_esc(line)}</text>')
            yy += 14
        if pill:
            pw = len(pill) * 6.1 + 14
            self.body.append(f'<rect x="{x+8}" y="{y+h-34}" width="{pw}" height="14" rx="7" fill="{TEAL}"/>')
            self.body.append(f'<text x="{x+8+pw/2}" y="{y+h-23.5}" font-size="9.5" text-anchor="middle" '
                             f'fill="#ffffff">{_esc(pill)}</text>')
        if tags:
            self.body.append(f'<text x="{x+w-8}" y="{y+h-8}" font-size="10.5" text-anchor="end" fill="#6b7280" '
                             f'font-family="ui-monospace,Menlo,monospace">{_esc(tags)}</text>')
        return (x, y, w, h)

    def label(self, x, y, text, colour=GREY, size=10.5):
        tw = len(text) * size * 0.58 + 8
        self.top.append(f'<rect x="{x-tw/2}" y="{y-10}" width="{tw}" height="14" fill="#ffffff" '
                        f'fill-opacity="0.95" rx="3"/>')
        self.top.append(f'<text x="{x}" y="{y+1}" font-size="{size}" text-anchor="middle" '
                        f'fill="{colour}">{_esc(text)}</text>')

    def path(self, d, colour=GREY, dashed=False, head=True):
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        marker = ""
        if head:
            marker = ' marker-end="url(#t)"' if colour == TEAL else ' marker-end="url(#a)"'
        self.body.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.6"{dash}{marker}/>')


def render():
    """The diagram as SVG text."""
    c = _Canvas()
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
           f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="Inter,Segoe UI,Helvetica,Arial,sans-serif">',
           '<defs><marker id="a" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
           '<path d="M0,0 L9,4.5 L0,9 z" fill="#4b5563"/></marker>'
           f'<marker id="t" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
           f'<path d="M0,0 L9,4.5 L0,9 z" fill="{TEAL}"/></marker></defs>',
           f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
           '<text x="40" y="34" font-size="20" font-weight="700" fill="#111827">'
           'Compass 7.0.0 document set: what each stage writes, and what reads it</text>',
           '<text x="40" y="54" font-size="12" fill="#6b7280">Target state for the 7.0.0 release. '
           'Until it ships, the set a project gets is the one docs/methodology.md section 6 describes.</text>',
           '<text x="40" y="70" font-size="12" fill="#6b7280">Colour is the traditional document the file '
           'stands in for. Tags: Q quick fix · R regular · F full · H hotfix · S spike. A teal pill names '
           'the block rendered from the manifest, never kept by hand.</text>',
           '<g transform="translate(0,16)">']

    x0, colw, gap = 60, 176, 72
    cx = {s: x0 + i * (colw + gap) for i, s in enumerate(STAGES)}

    def cc(s):
        return cx[s] + colw / 2

    def gx(a, b):
        return (cx[a] + colw + cx[b]) / 2

    right = cx["SHIP"] + colw + 24

    # project band
    py, pbh = 76, 92
    c.body.append(f'<rect x="40" y="{py}" width="{right-40}" height="{pbh}" rx="10" fill="#fafaf9" stroke="#d6d3d1"/>')
    c.body.append(f'<text x="52" y="{py+17}" font-size="11.5" font-weight="700" fill="#78716c">'
                  'PROJECT LEVEL, shared across issues</text>')
    pb, ph = py + 26, 56
    pbot = pb + ph
    for col, span, title, lines in PROJECT:
        c.box(cx[col], pb, colw * span + gap * (span - 1), ph, title, lines, "project")

    # stage headers, drawn last
    sy = py + pbh + 78
    for s in STAGES:
        c.top.append(f'<rect x="{cx[s]}" y="{sy}" width="{colw}" height="24" rx="6" fill="#111827"/>')
        c.top.append(f'<text x="{cx[s]+colw/2}" y="{sy+16.5}" font-size="12" font-weight="700" '
                     f'text-anchor="middle" fill="#ffffff">{s}</text>')

    # the pack
    bh, rgap = 100, 44
    rows = [sy + 24 + 46]
    for _ in range(3):
        rows.append(rows[-1] + bh + rgap)
    c.body.append(f'<text transform="translate(26,{(rows[0]+rows[3]+bh)/2}) rotate(-90)" font-size="11.5" '
                  'font-weight="700" text-anchor="middle" fill="#4b5563">ISSUE PACK  docs/compass/&lt;created&gt;-&lt;slug&gt;/</text>')
    b = {}
    for key, col, row, title, lines, kind, tags, pill in PACK:
        b[key] = c.box(cx[col], rows[row], colw, bh, title, lines, kind, tags, pill)

    # machine band
    my, mh = rows[3] + bh + 64, 118
    c.body.append(f'<rect x="40" y="{my}" width="{right-40}" height="{mh}" rx="10" fill="#f1f5f9" stroke="#94a3b8"/>')
    c.body.append(f'<text x="52" y="{my+17}" font-size="11.5" font-weight="700" fill="#0f172a">MACHINE SIDE  '
                  '.compass/work/&lt;slug&gt;/  the record. Nothing above states a fact the record does not hold.</text>')
    mb = my + 28
    for x, w, title, lines in MACHINE:
        c.box(x, mb, w if w else right - 12 - x, 76, title, lines, "machine")

    # row-0 flow, horizontal, labels in the gap above the row
    r0 = rows[0]
    yrow = r0 + 18

    def flow(a, bb, text):
        x1, x2 = b[a][0] + b[a][2], b[bb][0]
        c.path(f'M{x1},{yrow} L{x2},{yrow}')
        c.label((x1 + x2) / 2, r0 - 12, text)

    flow("AC", "RR", "QA'd")
    flow("RR", "TD", "DoR gates plan")
    flow("TD", "DM", "work units")
    flow("DM", "CO", "subtasks, worktrees")
    flow("CO", "VR", "what shipped")
    flow("VR", "RM", "results")
    DA, IN, AC, PO, TD, RV, CO, VR, RM = (b[k] for k in ("DA", "IN", "AC", "PO", "TD", "RV", "CO", "VR", "RM"))
    c.path(f'M{DA[0]+DA[2]},{r0+42} L{AC[0]},{r0+42}')
    c.label(gx("ASSESS", "DEFINE"), r0 + 30, "depth")
    g = gx("ASSESS", "DEFINE")
    c.path(f'M{IN[0]+IN[2]},{rows[1]+36} L{g},{rows[1]+36} L{g},{r0+78} L{AC[0]},{r0+78}')
    c.label(g, rows[1] + 22, "INT-n serve")
    # spec to design: down, along the row gap, up the left lane, into the design's left edge
    gy = r0 + bh + rgap / 2
    g = gx("REFINE", "PLAN")
    lane_l, lane_r = g - 14, g + 14
    c.path(f'M{AC[0]+110},{r0+bh} L{AC[0]+110},{gy} L{lane_l},{gy} L{lane_l},{r0+bh-32} L{TD[0]},{r0+bh-32}')
    c.label(cc("REFINE"), gy - 12, "scenario groups become work units")
    # product-owner review to design: right lane, lower entry
    c.path(f'M{PO[0]+PO[2]},{rows[1]+50} L{lane_r},{rows[1]+50} L{lane_r},{r0+bh-10} L{TD[0]},{r0+bh-10}')
    c.label(lane_r - 16, rows[1] + 38, "gate", size=9.5)
    c.path(f'M{TD[0]+100},{r0+bh} L{TD[0]+100},{rows[1]}')
    c.label(TD[0] + 100, rows[1] - 10, "per unit", size=9.5)
    c.path(f'M{RV[0]+70},{rows[1]} L{RV[0]+70},{r0+bh}')
    c.label(RV[0] + 70, rows[1] - 10, "rounds", size=9.5)

    # project-level links
    hy = pbot + 34
    c.path(f'M{cc("ASSESS")},{pbot} L{cc("ASSESS")},{DA[1]}')
    c.label(cc("ASSESS"), hy, "policy computes the approach", size=9.8)
    c.path(f'M{cc("PLAN")},{TD[1]} L{cc("PLAN")},{pbot}')
    c.label(cc("PLAN"), hy, "project-scoped DD-n", size=9.8)
    xa, xb = cc("VERIFY") - 56, cc("IMPLEMENT") + 40
    c.path(f'M{xa},{VR[1]} L{xa},{hy} L{xb},{hy} L{xb},{pbot}')
    c.label((xa + xb) / 2, hy - 12, "release line", size=9.8)
    xa, xb = cc("SHIP") - 56, cc("VERIFY") + 40
    c.path(f'M{xa},{RM[1]} L{xa},{hy} L{xb},{hy} L{xb},{pbot}')
    c.label((xa + xb) / 2, hy - 12, "listed", size=9.8)
    c.path(f'M{cc("SHIP")+30},{RM[1]} L{cc("SHIP")+30},{pbot}')
    c.label(cc("SHIP") + 36, hy, "one comment", size=9.8)
    g, hy2 = gx("BREAKDOWN", "IMPLEMENT"), pbot + 18
    c.path(f'M{g},{my} L{g},{hy2} L{cc("BREAKDOWN")+40},{hy2} L{cc("BREAKDOWN")+40},{pbot}', colour=TEAL, dashed=True)
    c.label(g, rows[1] + 40, "board() reads all manifests", colour=TEAL, size=9.5)

    # the record
    c.path(f'M{cc("IMPLEMENT")},{CO[1]+CO[3]} L{cc("IMPLEMENT")},{my}')
    c.label(cc("IMPLEMENT"), rows[2] + 40, "tdd-red / tdd-green write records", size=9.8)
    c.path(f'M{cc("DEFINE")},{my} L{cc("DEFINE")},{AC[1]+AC[3]}', colour=TEAL, dashed=True)
    c.label(cc("DEFINE"), rows[2] + 40, "compass issue render: every teal block,", colour=TEAL, size=9.8)
    c.label(cc("DEFINE"), rows[2] + 54, "after each record-changing command", colour=TEAL, size=9.8)
    ex = right - 10
    c.path(f'M{ex},{my} L{ex},{RM[1]+RM[3]/2} L{RM[0]+RM[2]},{RM[1]+RM[3]/2}', colour=TEAL, dashed=True)
    c.label(ex - 18, rows[2] + 40, "state", colour=TEAL, size=9.5)

    out.extend(c.body)
    out.extend(c.top)

    # legend
    ly, lx = HEIGHT - 16 - 38, 40
    for name, kind in LEGEND:
        fill, stroke = COLOURS[kind]
        out.append(f'<rect x="{lx}" y="{ly-12}" width="16" height="12" rx="2" fill="{fill}" stroke="{stroke}"/>')
        out.append(f'<text x="{lx+22}" y="{ly-2}" font-size="11.5" fill="#374151">{_esc(name)}</text>')
        lx += len(name) * 6.6 + 52
    out.append(f'<text x="40" y="{ly+18}" font-size="11" fill="#6b7280">Quick fix pack: '
               'delivery-approach, acceptance-criteria (one scenario), verification-note, README.   '
               'Spike: delivery-approach, intent, spike-conclusion, README.</text>')
    out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when the file is stale")
    parser.add_argument("--out", default=TARGET, help="where to write (default: the tracked file)")
    args = parser.parse_args(argv)
    fresh = render()
    if args.check:
        current = open(args.out, encoding="utf-8").read() if os.path.exists(args.out) else None
        if current != fresh:
            rel = os.path.relpath(args.out, ROOT)
            print(f"{rel} is stale: run scripts/render-document-set.py", file=sys.stderr)
            return 1
        return 0
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(fresh)
    print(os.path.relpath(args.out, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
