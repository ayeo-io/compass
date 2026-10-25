"""The delivery board page: one HTML string built from board rows.

`render_page(data, generated, trees)` is a pure function. It reads no file and
runs no command, so a test builds rows by hand. It owns the page's escaping:
every recorded value goes through `_e` and nothing else writes a value into
the markup. The page holds no script and loads nothing from outside.
"""
# DEPENDENCY: standard library (html); compass_pkg.core, compass_pkg.stable_ids.
from __future__ import annotations

import html

from compass_pkg.core import display_stage
from compass_pkg.stable_ids import STAGE_IDS

LANES = ("backlog", *STAGE_IDS, "done")
DONE_LANE_NAME = "done, last 7 days"

_SECTIONS = ("backlog", "ready", "in_progress", "stale", "in_review",
             "done_this_week", "closed")


def _e(value):
    return html.escape(str(value), quote=True)


def _lane_name(lane):
    return DONE_LANE_NAME if lane == "done" else display_stage(lane)


def _rows(data):
    out = []
    for key in _SECTIONS:
        out.extend(data.get(key) or [])
    return out


CAP = 10

# Card borders differ by style as well as colour, so a flag does not rely on
# colour alone: dashed for blocked, dotted for stale evidence.
#
# One meaning per colour, the same colours as the README's explainer: blue
# is the computed approach (the heavier the approach, the stronger the
# blue), yellow is a wait for a person, red is a block, green is done. The
# page loads no font: the title falls back to the reader's serif, the rest to
# the system sans. An empty lane folds to a sideways strip, so the pipeline
# stays readable and the width goes to the lanes that hold cards.
_STYLE = """
:root{--bg:#15171c;--surface:#1b1e25;--line:#30353f;--text:#e4e6ea;--muted:#9aa2ad;--faint:#848c97;
--blue:#58c4dd;--blue-dim:#3c8ea3;--blue-deep:#1f5260;--yellow:#ffd93d;--red:#fc6255;--green:#83c167;--accent:#ffd93d}
@media (prefers-color-scheme: light){:root{--bg:#f7f7f5;--surface:#ffffff;--line:#c9ccd3;--text:#17191e;--muted:#515864;--faint:#666d78;
--blue:#166f87;--blue-dim:#5aa3b7;--blue-deep:#bfe3ec;--yellow:#8a6400;--red:#b5281c;--green:#2f7a2c;--accent:#8a6400}}
*{box-sizing:border-box}
body{margin:0;padding:28px 32px 48px;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:14px;line-height:1.45;display:flex;flex-direction:column}
header{order:0}main{order:1}.legend{order:2;margin:18px 0 0}.unplaceable,.panel{order:3}
code,.slug{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
h1{margin:0 0 10px;font-family:Georgia,"Times New Roman",serif;font-weight:400;font-size:28px;letter-spacing:.01em}
h2{margin:0 0 4px;font-family:Georgia,"Times New Roman",serif;font-weight:400;font-size:24px}
h3{margin:0 0 8px;font-size:12px;font-weight:500;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
header p,.meta,.legend p{margin:2px 0;color:var(--muted);font-size:12px}
.counts{display:flex;flex-wrap:wrap;gap:0 18px;margin:0 0 10px;padding:0;list-style:none;font-size:13px;color:var(--muted)}
.counts li:first-child{color:var(--text)}
main{display:flex;gap:10px;align-items:stretch;overflow-x:auto;margin-top:18px}
.lane{flex:1 1 0;min-width:168px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:10px;min-height:260px}
.lane:not(:has(.card)){flex:0 0 36px;min-width:36px;padding:10px 0}
.lane:not(:has(.card)) h3{writing-mode:vertical-rl;transform:rotate(180deg);margin:0 auto;display:block;color:var(--faint)}
.lane h3{display:flex;justify-content:space-between;gap:8px}
.count{color:var(--faint);font-weight:400;letter-spacing:0}
.card{display:flex;flex-direction:column;gap:5px;margin:0 0 8px;padding:9px 10px 9px 12px;background:var(--bg);color:var(--text);text-decoration:none;border-radius:6px;border-color:var(--line);border-width:1px;border-style:solid;border-left-width:3px;border-left-color:var(--blue-deep)}
.card[data-approach="regular"]{border-left-color:var(--blue-dim)}
.card[data-approach="full"]{border-left-color:var(--blue)}
.card[data-approach="hotfix"]{border-left-color:var(--red)}
.card[data-approach="spike"]{border-left-color:var(--yellow)}
.card[data-approach="not assessed"]{border-left-color:var(--line)}
.card:hover,.card:focus-visible{border-color:var(--accent);outline:none}
.card.dotted{border-style:dotted;border-left-style:solid}
.card.dashed{border-style:dashed;border-left-style:solid;border-color:var(--red)}
.slug{font-size:13px;word-break:break-word;color:var(--text)}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip,.flag{font-size:11px;line-height:1.3;padding:1px 6px;border-radius:3px;border:1px solid var(--line);color:var(--muted)}
.chip:first-child{color:var(--blue);border-color:transparent;padding-left:0}
.card[data-approach="hotfix"] .chip:first-child{color:var(--red)}
.card[data-approach="spike"] .chip:first-child{color:var(--yellow)}
.card[data-approach="not assessed"] .chip:first-child{color:var(--faint)}
.flag{color:var(--accent);border-color:var(--accent)}
.card.dashed .flag{color:var(--red);border-color:var(--red)}
details{margin-top:6px}
summary{color:var(--muted);cursor:pointer;margin-bottom:6px;font-size:12px}
.empty{color:var(--muted)}
.panel{display:none}
.panel:target{display:block}
.panel{margin-top:24px;padding:18px 22px;background:var(--surface);border:1px solid var(--line);border-radius:10px}
.part{margin:14px 0}
.dims{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px}
.dims dt{color:var(--muted)}
.dims dd{margin:0}
.labels,.gates,.stages,.changed{margin:6px 0;padding-left:18px}
.current{color:var(--accent)}
.note{color:var(--accent)}
.rule-id{color:var(--accent)}
"""


def _sort_key(lane):
    if lane == "backlog":
        # Oldest first; a card with no readable date sorts after the dated ones.
        return lambda r: (r.get("created") is None, str(r.get("created") or ""), r["slug"])
    if lane == "done":
        return lambda r: (_neg(str(r.get("completed") or "")), r["slug"])
    return lambda r: r["slug"]


def _neg(text):
    """A key that sorts a date text newest first."""
    return tuple(-ord(ch) for ch in text)


def _state_word(r):
    if r.get("state") == "done":
        return "done (%s)" % (r.get("close_reason") or "completed")
    return str(r.get("state") or "")


def _waiting_for(r):
    """The slugs an open issue still waits for, in the order they are recorded. An entry
    whose issue was not read (state null) is not named; the panel says "not found" or
    "unreadable" for it."""
    if r.get("state") == "done":
        return []
    return [d["issue"] for d in r.get("depends_on") or []
            if not d.get("met") and d.get("state") is not None]


def _card(r, n):
    parts = ['<span class="slug">%s</span>' % _e(r["slug"]),
             '<span class="chips"><span class="chip">%s</span>'
             '<span class="chip">%s</span></span>' % (
                 _e(r.get("delivery_approach") or "not assessed"), _e(_state_word(r)))]
    meta = []
    if r.get("stage"):
        meta.append("stage " + str(display_stage(r["stage"])))
    if r.get("state") == "done" and r.get("completed"):
        meta.append(str(r["completed"]))
    if r.get("state") in ("in-progress", "in-review"):
        meta.append("gates " + str(r.get("gates") or "0/0"))
    if meta:
        parts.append('<span class="meta">%s</span>' % _e(" - ".join(meta)))
    if r.get("set_aside"):
        parts.append('<span class="flag">set aside</span>')
        reason = r.get("reason")
        parts.append('<span class="meta">%s</span>' % (
            _e("reason: " + str(reason)) if reason else "no reason recorded"))
    where = []
    if r.get("tree") and r["tree"] != "this checkout":
        where.append("tree " + str(r["tree"]))
    also = r.get("also_in") or 0
    if also:
        where.append("also in %d tree%s" % (also, "" if also == 1 else "s"))
    if where:
        parts.append('<span class="meta">%s</span>' % _e(" - ".join(where)))
    waits = _waiting_for(r)
    if waits:
        parts.append('<span class="meta">waits for %s</span>' % _e(", ".join(waits)))
    stale = r.get("evidence") == "stale"
    edge = "dashed" if r.get("blocked") is not None else "dotted" if stale else ""
    if r.get("blocked") is not None:
        parts.append('<span class="flag">%s</span>' % _e("blocked: %s" % r["blocked"]))
    if stale:
        parts.append('<span class="flag">stale evidence</span>')
    if r.get("recommendation"):
        parts.append('<span class="flag">recommendation</span>')
    return '<a class="card%s" data-approach="%s" href="#issue-%d">%s</a>' % (
        " " + edge if edge else "", _e(r.get("delivery_approach") or "not assessed"),
        n, "".join(parts))


_DIMENSIONS = ("risk", "familiarity", "size", "goal")


def _assessment_block(r):
    a = r.get("assessment")
    out = ['<section class="part"><h3>Assessment</h3>', '<dl class="dims">']
    for name in _DIMENSIONS:
        value = a.get(name)
        out.append('<dt>%s</dt><dd>%s</dd>' % (
            name, _e(value) if value else "not assessed"))
    out.append('</dl>')
    out.append('<ul class="labels">%s</ul></section>' % "".join(
        '<li class="label">%s</li>' % _e(label) for label in a.get("labels") or []))
    return out


def _rules_block(r):
    rules = r.get("policy_rules_fired") or []
    out = ['<section class="part"><h3>Policy rules fired</h3>']
    if not rules:
        out.append('<p>No policy rule fired</p>')
    for rule in rules:
        out.append('<div class="rule"><span class="rule-id">%s</span> '
                   '<span class="rule-kind">%s</span>' % (
                       _e(rule.get("id")), _e(rule.get("kind"))))
        if rule.get("rationale"):
            out.append('<p class="rationale">%s</p>' % _e(rule["rationale"]))
        out.append('<ul class="changed">%s</ul></div>' % "".join(
            '<li>%s</li>' % _e(line) for line in rule.get("changed") or []))
    out.append('</section>')
    return out


_STAGE_ORDER = LANES[1:9]


def _depths_block(r):
    depths = r.get("stage_depths") or {}
    out = ['<section class="part"><h3>Stage depths</h3>', '<ol class="stages">']
    for stage in _STAGE_ORDER:
        mark = ' <span class="current">current</span>' if r.get("stage") == stage else ""
        out.append('<li class="stage"><span class="stage-name">%s</span> '
                   '<span class="depth">%s</span>%s</li>' % (
                       _e(display_stage(stage)), _e(depths.get(stage) or "not recorded"),
                       mark))
    out.append('</ol></section>')
    return out


def _gates_block(r):
    out = ['<section class="part"><h3>Gates %s</h3>' % _e(r.get("gates") or "0/0"),
           '<ul class="gates">']
    for g in r.get("gate_list") or []:
        out.append('<li class="gate"><span class="gate-id">%s</span> '
                   '<span class="gate-status">%s</span></li>' % (
                       _e(g.get("id")), _e(g.get("status"))))
    out.append('</ul></section>')
    return out


def _documents_block(r):
    """Each registered document: a kind that repeats has a line for every round,
    and a kind with a document per work unit a line for every unit, each named by
    its own entry id."""
    docs = r.get("documents") or []
    out = ['<section class="part"><h3>Documents %d</h3>' % len(docs), '<ul class="documents">']
    for d in docs:
        name = d["kind"] + (" round %d" % d["round"] if d.get("round") else "")
        if d.get("unit"):
            name += " " + d["unit"]
        out.append('<li class="document"><span class="document-kind">%s</span> '
                   '<span class="document-id">%s</span> <span class="document-status">%s</span> '
                   '<code class="document-path">%s</code></li>' % (
                       _e(name), _e(d.get("id")), _e(d.get("text") or d.get("status")),
                       _e(d.get("path") or "-")))
    out.append('</ul></section>')
    return out


def _where_block(r):
    return ['<section class="part"><h3>Where it is read from</h3>',
            '<p class="path">Manifest <code>%s</code></p>' % _e(r.get("manifest_path") or ""),
            '<p>Tree %s</p></section>' % _e(r.get("tree") or "this checkout")]


def _unassessed(r):
    return (r.get("delivery_approach") or "not assessed") == "not assessed"


def _next_block(r):
    if r.get("state") == "done":
        return []
    if _unassessed(r):
        commands = ["compass issue use %s" % r["slug"],
                    "/compass:assess <describe the work in one sentence>"]
    else:
        commands = ["/compass:resume %s" % r["slug"]]
    return ['<section class="part next"><h3>Next command</h3>'] + [
        '<p><code>%s</code></p>' % _e(c) for c in commands] + ['</section>']


def _dependency_word(entry, unreadable):
    if entry.get("met"):
        return "met"
    if entry["issue"] in unreadable:
        return "unreadable"
    if entry.get("state") is None:
        return "not found"
    return "waiting"


def _dependencies_block(r, unreadable):
    out = ['<section class="part deps"><h3>Dependencies</h3>', '<ul class="deps">']
    for d in r["depends_on"]:
        words = [d["issue"], d.get("reason"), "until %s" % d.get("until"), d.get("state"),
                 _dependency_word(d, unreadable)]
        out.append('<li class="dep">%s</li>' % _e(" - ".join(str(w) for w in words if w)))
    out.append('</ul></section>')
    return out


def _panel(r, n, unreadable=frozenset()):
    out = ['<section class="panel" id="issue-%d">' % n, '<h2>%s</h2>' % _e(r["slug"]),
           '<p class="meta">%s - %s</p>' % (
               _e(r.get("delivery_approach") or "not assessed"), _e(_state_word(r)))]
    if r.get("state") == "done" and r.get("completed"):
        out.append('<p class="meta">Completed %s</p>' % _e(r["completed"]))
    if _unassessed(r):
        out.append('<p class="note">The assessment, policy rules and stage depths '
                   'appear once the issue is assessed.</p>')
    else:
        if r.get("assessment"):
            out += _assessment_block(r)
        else:
            out.append('<p class="note">No assessment recorded.</p>')
        if r.get("readiness"):
            out.append('<p class="meta">%s</p>' % _e(r["readiness"]))
        out += _rules_block(r)
        out += _depths_block(r)
        out += _gates_block(r)
        out += _documents_block(r)
    if r.get("depends_on"):
        out += _dependencies_block(r, unreadable)
    out += _next_block(r)
    out += _where_block(r)
    out.append('</section>')
    return "\n".join(out)


_ALL_SECTIONS = _SECTIONS + ("other", "unreadable")
_STATES = ("backlog", "ready", "in-progress", "in-review")


def _generated(value):
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _trees_lines(trees):
    trees = trees or {}
    read = list(trees.get("read") or ["this checkout"])
    out = ['<p class="trees">Trees read: %d (%s)</p>' % (len(read), _e(", ".join(read)))]
    if trees.get("skipped"):
        out.append('<p class="trees">Trees skipped: %d</p>' % trees["skipped"])
    if trees.get("note"):
        out.append('<p class="trees">%s</p>' % _e(trees["note"]))
    return out


def _header(data, generated, trees):
    every = [r for key in _ALL_SECTIONS for r in data.get(key) or []]
    placeable = [r for r in _rows(data) if not r.get("unplaceable")]
    # The board's total counts every issue read, including completed issues
    # too old for the done lane, as `compass flow` does.
    total = data.get("total", len(every))
    tiles = ["%d %s" % (total, "issue" if total == 1 else "issues")]
    tiles += ["%s %d" % (state, sum(1 for r in placeable if r.get("state") == state))
              for state in _STATES]
    tiles.append("%d unplaceable" % len(_unplaceable(data)))
    tiles.append("blocked %d" % sum(1 for r in placeable if r.get("blocked") is not None))
    tiles.append("stale evidence %d" % sum(1 for r in placeable
                                           if r.get("evidence") == "stale"))
    for reason, count in sorted((data.get("done_by_reason") or {}).items()):
        tiles.append("done (%s) %d" % (reason, count))
    out = ['<header>', '<h1>Compass board</h1>', '<ul class="counts">']
    out += ['<li>%s</li>' % _e(t) for t in tiles]
    out += ['</ul>', '<p class="generated">Generated %s</p>' % _e(_generated(generated))]
    out += _trees_lines(trees)
    out += ['<p class="advisory">This page is advisory and changes no issue state.</p>',
            '</header>']
    return out


_LEGEND = ['<section class="legend" aria-label="Legend">',
           '<p>The lane shows where an issue is in the pipeline. '
           'The word on each card is its state, read from its records.</p>',
           '<p>The backlog lane holds issues not yet assessed and issues set aside.</p>',
           '</section>']


def _unplaceable(data):
    """(row, reason) for each folder the page lists in the note instead of a card."""
    found = [(r, r["unplaceable"]) for r in _rows(data) if r.get("unplaceable")]
    # An open issue with no lane would otherwise vanish; a done one is counted.
    found += [(r, "the board gave it no lane") for r in _rows(data)
              if not r.get("unplaceable") and r.get("lane") not in LANES
              and r.get("state") != "done"]
    for key in ("other", "unreadable"):
        for r in data.get(key) or []:
            reason = r.get("note") or "its status %r is not one Compass sets" % r.get("status")
            found.append((r, reason))
    return sorted(found, key=lambda pair: (str(pair[0].get("tree") or ""), pair[0]["slug"]))


def _unplaceable_note(found):
    if not found:
        return []
    out = ['<section class="unplaceable"><h3>Unplaceable</h3>',
           '<p>These folders have no card because the board could not place them.</p><ul>']
    for r, reason in found:
        tree = r.get("tree") or "this checkout"
        out.append('<li><span class="slug">%s</span> - tree %s - %s</li>' % (
            _e(r["slug"]), _e(tree), _e(reason)))
    out.append('</ul></section>')
    return out


def render_page(data, generated, trees):
    by_lane = {lane: [] for lane in LANES}
    for r in _rows(data):
        if r.get("lane") in by_lane and not r.get("unplaceable"):
            by_lane[r["lane"]].append(r)
    out = ['<!doctype html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
           '<meta http-equiv="Content-Security-Policy" '
           'content="default-src \'none\'; style-src \'unsafe-inline\'">',
           '<title>Compass board</title>', '<style>' + _STYLE + '</style>', '</head>', '<body>'] + _header(data, generated, trees) + _LEGEND + ['<main>']
    panels = []
    n = 0
    unreadable = {r["slug"] for r in data.get("unreadable") or []}
    for lane in LANES:
        rows = sorted(by_lane[lane], key=_sort_key(lane))
        name = _e(_lane_name(lane))
        out.append('<section class="lane" aria-label="%s">' % name)
        out.append('<h3>%s <span class="count">%d</span></h3>' % (name, len(rows)))
        for pos, r in enumerate(rows):
            n += 1
            if pos == CAP:
                out.append('<details><summary>+%d more</summary>' % (len(rows) - CAP))
            out.append(_card(r, n))
            panels.append(_panel(r, n, unreadable))
        if len(rows) > CAP:
            out.append('</details>')
        out.append('</section>')
    if not any(data.get(k) for k in _ALL_SECTIONS):
        out.insert(out.index('<main>'), '<p class="empty">There are no issues yet.</p>')
    out += ['</main>'] + _unplaceable_note(_unplaceable(data)) + panels + ['</body>', '</html>']
    return "\n".join(out) + "\n"
