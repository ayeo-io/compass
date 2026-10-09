"""The board page: one HTML string built from board rows.

Each test name carries the id of the scenario it checks. The tests cover the
lanes, the cards, the header and the legend, then the detail panel, then page
safety and colour. The rows are built by hand to follow the row keys that
docs/board.md lists, so these tests need no project on disk. The module under
test is imported inside each test so a missing module fails the test and not
the collection.
"""
from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

STAGES = ("assess", "define", "refine", "plan", "breakdown", "implement",
          "verify", "ship")
LANE_NAMES = ["backlog", "assess", "define", "refine", "plan", "breakdown",
              "implement", "verify", "ship", "done, last 7 days"]
GENERATED = "2026-10-09 12:00"


def _page():
    from compass_pkg import board_page
    return board_page


# --- a small page reader ------------------------------------------------------

class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self):
        out = []
        for child in self.children:
            out.append(child if isinstance(child, str) else child.text())
        return " ".join(" ".join(out).split())

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def find_all(self, tag=None, cls=None):
        return [n for n in self.walk()
                if (tag is None or n.tag == tag)
                and (cls is None or cls in n.classes)]


class _Reader(HTMLParser):
    VOID = {"meta", "br", "hr", "img", "input", "link"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [])
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in self.VOID:
            self.cur = node

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def read(page_html):
    reader = _Reader()
    reader.feed(page_html)
    return reader.root


def lanes(root):
    """lane name -> the lane's node, in page order."""
    out = {}
    for node in root.find_all("section", "lane"):
        out[node.attrs["aria-label"]] = node
    return out


def cards(node):
    return node.find_all("a", "card")


def _ancestors(node):
    out = []
    while node.parent is not None:
        node = node.parent
        out.append(node.tag)
    return out


def heading_count(lane):
    return int(lane.find_all("span", "count")[0].text())


def panel_for(root, card):
    target = card.attrs["href"][1:]
    found = [n for n in root.find_all("section", "panel") if n.attrs.get("id") == target]
    assert len(found) == 1, "href %r matches %d panels" % (card.attrs["href"], len(found))
    return found[0]


def card_named(root, slug):
    found = [c for c in cards(root) if c.find_all("span", "slug")[0].text() == slug]
    assert len(found) == 1, "%d cards for %s" % (len(found), slug)
    return found[0]


# --- hand-made rows (the keys docs/board.md lists) ----------------------------

def row(slug, **kw):
    base = {"slug": slug, "delivery_approach": "full", "state": "in-progress",
            "stage": "implement", "gates": "0/7", "evidence": "current",
            "lane": "implement", "gate_list": [], "assessment": None,
            "policy_rules_fired": [], "stage_depths": {}, "tree": "this checkout",
            "manifest_path": ".compass/work/%s/manifest.yml" % slug,
            "also_in": 0, "created": None, "set_aside": False,
            "recommendation": False, "unplaceable": None}
    base.update(kw)
    return base


SECTION_OF_STATE = {"backlog": "backlog", "ready": "ready",
                    "in-progress": "in_progress", "in-review": "in_review"}


def data_of(*rows, **extra):
    """board() style data: each row sits in the section its state gives."""
    data = {k: [] for k in ("backlog", "ready", "in_progress", "stale", "in_review",
                            "done_this_week", "closed", "other", "unreadable")}
    data.update(friction=None, counts={}, total=len(rows), done_by_reason={})
    for r in rows:
        if r.get("evidence") == "stale":
            key = "stale"
        elif r["state"] == "done":
            key = "done_this_week" if r.get("close_reason", "completed") == "completed" else "closed"
        else:
            key = SECTION_OF_STATE[r["state"]]
        data[key].append(r)
    data.update(extra)
    return data


def one_checkout():
    return {"read": ["this checkout"], "skipped": 0, "note": None}


def render(*rows, trees=None, **extra):
    return _page().render_page(data_of(*rows, **extra), GENERATED, trees or one_checkout())


def page_root(*rows, **kw):
    return read(render(*rows, **kw))


def _backlog_row(slug, created, **kw):
    kw.setdefault("reason", "")
    return row(slug, state="backlog", stage="define", lane="backlog", gates="0/0",
               created=created, set_aside=True, **kw)


# --- group B: lanes, cards, header, legend ------------------------------------

def test_trc_b1_lanes_in_pipeline_order():
    root = page_root(row("alpha", lane="implement"))
    found = lanes(root)
    assert list(found) == LANE_NAMES
    from compass_pkg.core import display_stage
    assert list(found)[1:9] == [display_stage(s) for s in STAGES]
    for lane in found.values():
        assert heading_count(lane) == (1 if lane is found["implement"] else 0)


def test_trc_b2_backlog_shows_ten_oldest_then_more():
    # 14 set-aside issues, created on different dates, given out of order.
    days = list(range(14, 0, -1))
    rows = [_backlog_row("issue-%02d" % d, "2026-09-%02d" % d) for d in days]
    root = page_root(*rows)
    lane = lanes(root)["backlog"]
    assert heading_count(lane) == 14
    top = [c for c in cards(lane) if "details" not in _ancestors(c)]
    assert [c.find_all("span", "slug")[0].text() for c in top] == \
        ["issue-%02d" % d for d in range(1, 11)]
    more = lane.find_all("details")
    assert len(more) == 1
    assert more[0].find_all("summary")[0].text() == "+4 more"
    assert "open" not in more[0].attrs
    assert [c.find_all("span", "slug")[0].text() for c in cards(more[0])] == \
        ["issue-%02d" % d for d in range(11, 15)]
    for c in cards(lane):
        panel_for(root, c)


def test_trc_b4_set_aside_card_shows_its_reason():
    root = page_root(
        _backlog_row("a", "2026-09-01", reason="waiting for the API decision"),
        _backlog_row("b", "2026-09-02"))
    a, b = card_named(root, "a").text(), card_named(root, "b").text()
    assert "set aside" in a and "reason: waiting for the API decision" in a
    assert "set aside" in b and "no reason recorded" in b
    assert "reason:" not in b


def test_trc_b6_stage_cards_show_state_stage_and_gates():
    first = row("impl", state="in-progress", stage="implement", lane="implement",
                gates="0/7")
    second = row("ver", state="in-review", stage="verify", lane="verify",
                 gates="5/8", delivery_approach="regular")
    root = page_root(first, second)
    lane_cards = {n: [c.find_all("span", "slug")[0].text() for c in cards(lanes(root)[n])]
                  for n in ("implement", "verify")}
    assert lane_cards == {"implement": ["impl"], "verify": ["ver"]}
    a, b = card_named(root, "impl").text(), card_named(root, "ver").text()
    for word in ("impl", "full", "in-progress", "gates 0/7"):
        assert word in a
    for word in ("ver", "regular", "in-review", "gates 5/8"):
        assert word in b


def css_of(page_html):
    found = re.findall(r"<style>(.*?)</style>", page_html, re.S)
    assert len(found) == 1
    return found[0]


def border_style(page_html, card):
    """The CSS border-style a card resolves to: `.card`, then `.card.<class>`."""
    value = None
    for selector, body in re.findall(r"([^{}@]+)\{([^{}]*)\}", css_of(page_html)):
        selector = selector.strip()
        wanted = set(card.classes)
        if not all(part in wanted for part in selector.split(".")[1:]) or \
                not selector.startswith(".card"):
            continue
        match = re.search(r"border-style\s*:\s*([a-z]+)", body)
        if match:
            value = match.group(1)
    return value


def test_trc_b7_blocked_card_shows_reason_and_a_different_border():
    blocked = row("stuck", blocked="waiting for the schema review")
    free = row("free")
    page_html = render(blocked, free)
    root = read(page_html)
    first, second = card_named(root, "stuck"), card_named(root, "free")
    assert "blocked: waiting for the schema review" in first.text()
    assert "blocked" not in second.text() and "blocked" not in str(second.classes)
    assert border_style(page_html, first) and border_style(page_html, second)
    assert border_style(page_html, first) != border_style(page_html, second)


def test_trc_b9_stale_evidence_flag_in_the_stage_lane():
    stale = row("old", evidence="stale")
    fresh = row("new")
    page_html = render(stale, fresh)
    root = read(page_html)
    first, second = card_named(root, "old"), card_named(root, "new")
    assert first in cards(lanes(root)["implement"])
    assert "stale evidence" in first.text()
    assert "stale evidence" not in second.text()
    assert border_style(page_html, first) != border_style(page_html, second)


def test_trc_b10_recommendation_flag_on_backlog_state_cards():
    set_aside = _backlog_row("held-idea", "2026-09-01", recommendation=True)
    defining = row("defining", state="backlog", stage="define", lane="define",
                   recommendation=True)
    plain = row("plain", state="backlog", stage="define", lane="define")
    root = page_root(set_aside, defining, plain)
    assert "recommendation" in card_named(root, "held-idea").text()
    assert "recommendation" in card_named(root, "defining").text()
    assert "recommendation" not in card_named(root, "plain").text()


def _done_row(slug, completed, lane="done", **kw):
    return row(slug, state="done", stage=None, lane=lane, gates="3/3", evidence=None,
               completed=completed, close_reason="completed", **kw)


def test_trc_b11_done_lane_newest_first_capped_at_ten():
    rows = [_done_row("done-%02d" % d, "2026-10-%02d" % d) for d in range(1, 14)]
    rows.append(_done_row("too-old", "2026-09-28", lane=None))
    root = page_root(*rows)
    lane = lanes(root)["done, last 7 days"]
    assert heading_count(lane) == 13
    top = [c for c in cards(lane) if "details" not in _ancestors(c)]
    assert [c.find_all("span", "slug")[0].text() for c in top] == \
        ["done-%02d" % d for d in range(13, 3, -1)]
    assert "done (completed)" in top[0].text() and "2026-10-13" in top[0].text()
    more = lane.find_all("details")[0]
    assert more.find_all("summary")[0].text() == "+3 more"
    assert "open" not in more.attrs
    assert [c.find_all("span", "slug")[0].text() for c in cards(more)] == \
        ["done-03", "done-02", "done-01"]
    assert "too-old" not in [c.find_all("span", "slug")[0].text() for c in cards(root)]


def header_text(root):
    found = root.find_all("header")
    assert len(found) == 1
    return found[0].text()


def test_trc_b12_header_counts_done_issues_by_close_reason():
    rows = [_done_row("recent", "2026-10-07"),
            _done_row("old", "2026-09-28", lane=None),
            row("np1", state="done", stage=None, lane=None, close_reason="not-planned"),
            row("np2", state="done", stage=None, lane=None, close_reason="not-planned"),
            row("dup", state="done", stage=None, lane=None, close_reason="duplicate")]
    root = page_root(*rows, done_by_reason={"completed": 2, "not-planned": 2, "duplicate": 1})
    text = header_text(root)
    for line in ("done (completed) 2", "done (not-planned) 2", "done (duplicate) 1"):
        assert line in text
    shown = [c.find_all("span", "slug")[0].text() for c in cards(root)]
    assert shown == ["recent"]


def test_trc_b13_header_summarises_the_board():
    rows = [_backlog_row("b1", "2026-09-01"),
            row("r1", state="ready", stage="plan", lane="plan", gates="0/7"),
            row("p1", blocked="waiting"), row("p2"),
            row("p3", evidence="stale"),
            row("v1", state="in-review", stage="verify", lane="verify", gates="2/8"),
            _done_row("d1", "2026-10-08")]
    trees = {"read": ["this checkout", "side"], "skipped": 2,
             "note": "git could not list the worktrees"}
    page_html = render(*rows, trees=trees, done_by_reason={"completed": 1})
    text = header_text(read(page_html))
    for fragment in ("7 issues", "backlog 1", "ready 1", "in-progress 3", "in-review 1",
                     "blocked 1", "stale evidence 1", "done (completed) 1",
                     GENERATED, "Trees read: 2 (this checkout, side)", "Trees skipped: 2",
                     "git could not list the worktrees",
                     "advisory and changes no issue state"):
        assert fragment in text, fragment
    assert page_html.count(GENERATED) == 1


def test_trc_b13_header_uses_the_singular_for_one_issue():
    text = header_text(read(render(row("only"))))
    assert "1 issue" in text
    assert "1 issues" not in text


def test_trc_b19_legend_says_lane_is_stage_and_word_is_state():
    root = page_root(row("alpha"))
    legend = root.find_all("section", "legend")
    assert len(legend) == 1
    text = legend[0].text()
    assert ("The lane shows where an issue is in the pipeline. The word on each card "
            "is its state, read from its records.") in text
    assert "backlog lane holds issues not yet assessed and issues set aside" in text


# --- group C: the detail panel ------------------------------------------------

def test_trc_c1_card_opens_its_panel_without_script():
    page_html = render(row("alpha"), row("beta"))
    root = read(page_html)
    found = cards(root)
    assert len(found) == 2
    for card in found:
        assert card.attrs["href"].startswith("#")
        panel_for(root, card)
    css = css_of(page_html)
    assert re.search(r"\.panel\s*\{[^}]*display\s*:\s*none", css)
    assert re.search(r"\.panel:target\s*\{[^}]*display\s*:\s*block", css)
    assert "<script" not in page_html.lower()


def panel_of(page_html, slug):
    root = read(page_html)
    return panel_for(root, card_named(root, slug))


ASSESSMENT = {"risk": "cross-cutting", "familiarity": "brownfield-mapped", "size": "large",
              "goal": "delivery", "role": "engineer", "labels": ["public-api", "cli"]}


def test_trc_c2_panel_shows_the_five_dimensions_and_labels():
    panel = panel_of(render(row("alpha", assessment=ASSESSMENT)), "alpha")
    dims = {dt.text(): dd.text() for dt, dd in zip(panel.find_all("dt"), panel.find_all("dd"))}
    for name in ("risk", "familiarity", "size", "goal", "role"):
        assert dims[name] == ASSESSMENT[name]
    labels = [n.text() for n in panel.find_all("li", "label")]
    assert labels == ["public-api", "cli"]


def test_trc_c3_panel_shows_each_rule_with_rationale_and_changed_lines():
    rules = [{"id": "RP-REQUIRE-003", "kind": "require", "rationale": "gates stay",
              "changed": ["gates: +verify.security", "stages.plan: thorough"]},
             {"id": "RP-CAP-001", "kind": "cap", "rationale": None, "changed": []}]
    page_html = render(row("fired", assessment=ASSESSMENT, policy_rules_fired=rules),
                       row("quiet", assessment=ASSESSMENT))
    first = panel_of(page_html, "fired").text()
    for fragment in ("RP-REQUIRE-003", "require", "gates stay", "gates: +verify.security",
                     "stages.plan: thorough", "RP-CAP-001", "cap"):
        assert fragment in first
    assert "No policy rule fired" not in first
    assert "No policy rule fired" in panel_of(page_html, "quiet").text()


def test_trc_c4_panel_lists_stage_depths_and_marks_the_current_stage():
    depths = {"assess": "thorough", "define": "thorough", "refine": "collapsed",
              "plan": "thorough", "breakdown": "skipped", "implement": "thorough",
              "verify": "thorough", "ship": "thorough"}
    panel = panel_of(render(row("alpha", assessment=ASSESSMENT, stage_depths=depths)),
                     "alpha")
    items = panel.find_all("li", "stage")
    assert [i.find_all("span", "stage-name")[0].text() for i in items] == list(STAGES)
    assert [i.find_all("span", "depth")[0].text() for i in items] == \
        [depths[s] for s in STAGES]
    marked = [i.find_all("span", "stage-name")[0].text() for i in items
              if "current" in i.text()]
    assert marked == ["implement"]
    assert panel.text().count("current") == 1


def test_trc_c5_panel_lists_each_gate_with_its_status():
    gates = [{"id": "verify.correctness", "status": "passed"},
             {"id": "verify.governance", "status": "pending"},
             {"id": "verify.security", "status": "failed"}]
    panel = panel_of(render(row("alpha", assessment=ASSESSMENT, gates="1/3",
                                gate_list=gates)), "alpha")
    items = [(g.find_all("span", "gate-id")[0].text(), g.find_all("span", "gate-status")[0].text())
             for g in panel.find_all("li", "gate")]
    assert items == [("verify.correctness", "passed"), ("verify.governance", "pending"),
                     ("verify.security", "failed")]
    headings = [h.text() for h in panel.find_all("h3")]
    assert "Gates 1/3" in headings


def test_trc_c6_panel_shows_manifest_path_and_tree():
    page_html = render(row("alpha"), row("side-only", tree="side", also_in=2,
                                         manifest_path=".compass/work/side-only/manifest.yml"))
    here = panel_of(page_html, "alpha").text()
    assert ".compass/work/alpha/manifest.yml" in here
    assert "Tree this checkout" in here
    there = panel_of(page_html, "side-only").text()
    assert "Tree side" in there and "Tree this checkout" not in there


def _unassessed(slug):
    return row(slug, delivery_approach="not assessed", state="backlog", stage="assess",
               lane="backlog", gates="0/0", created="2026-09-01")


def test_trc_c7_unassessed_panel_says_it_is_not_assessed():
    page_html = render(_unassessed("beta"))
    root = read(page_html)
    card = card_named(root, "beta")
    assert "not assessed" in card.text()
    panel = panel_for(root, card)
    text = panel.text()
    assert "not assessed" in text
    assert ("The assessment, policy rules and stage depths appear once the issue "
            "is assessed.") in text
    assert not panel.find_all("dl", "dims") and not panel.find_all("li", "stage")
    assert "No policy rule fired" not in text


def test_trc_c8_assessed_open_issue_shows_the_resume_command_as_text():
    page_html = render(row("alpha", assessment=ASSESSMENT))
    panel = panel_of(page_html, "alpha")
    assert [c.text() for c in panel.find_all("code")].count("/compass:resume alpha") == 1
    for tag in ("button", "form", "input", "script"):
        assert "<" + tag not in page_html


def test_trc_c9_unassessed_issue_uses_the_assess_commands_real_arguments():
    panel = panel_of(render(_unassessed("beta")), "beta")
    commands = [c.text() for c in panel.find_all("code")]
    assert "compass issue use beta" in commands
    assert "/compass:assess <describe the work in one sentence>" in commands
    assert commands.index("compass issue use beta") < commands.index(
        "/compass:assess <describe the work in one sentence>")
    assert "/compass:assess beta" not in panel.text()


def test_trc_c10_done_panel_shows_close_reason_and_no_next_command():
    panel = panel_of(render(_done_row("finished", "2026-10-05")), "finished")
    text = panel.text()
    assert "done (completed)" in text and "2026-10-05" in text
    assert not panel.find_all("code") or all(
        "/compass:" not in c.text() and "compass issue" not in c.text()
        for c in panel.find_all("code"))
    assert "Next command" not in text


# --- group D: page safety and colour ------------------------------------------

SYSTEM_FONTS = {"system-ui", "-apple-system", "segoe ui", "sans-serif", "ui-monospace",
                "sfmono-regular", "menlo", "consolas", "monospace"}


def every_state_page():
    rows = [_unassessed("idea"), _backlog_row("later-idea", "2026-09-01", reason="later"),
            row("early", state="backlog", stage="define", lane="define"),
            row("soon", state="ready", stage="plan", lane="plan", gates="0/7",
                assessment=ASSESSMENT),
            row("busy", blocked="waiting", assessment=ASSESSMENT),
            row("aged", evidence="stale"),
            row("check", state="in-review", stage="verify", lane="verify", gates="2/8"),
            _done_row("shipped", "2026-10-07")]
    return render(*rows, done_by_reason={"completed": 1})


def test_trc_d1_page_has_no_script_external_resource_font_or_form():
    page_html = every_state_page()
    low = page_html.lower()
    assert "<script" not in low and "<form" not in low
    root = read(page_html)
    for node in root.walk():
        assert "src" not in node.attrs
        assert not [a for a in node.attrs if a.startswith("on")]
        if "href" in node.attrs:
            assert node.attrs["href"].startswith("#")
    css = css_of(page_html).lower()
    for banned in ("url(", "@import", "@font-face"):
        assert banned not in css
    families = [f for decl in re.findall(r"font-family\s*:([^;}]*)", css)
                for f in decl.split(",")]
    assert families
    assert {f.strip().strip('"\'') for f in families} <= SYSTEM_FONTS
    metas = [n for n in root.find_all("meta") if n.attrs.get("http-equiv")]
    assert [(m.attrs["http-equiv"], m.attrs["content"]) for m in metas] == [
        ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")]


def _luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _scheme_blocks(css):
    media = re.search(r"@media\s*\(prefers-color-scheme:\s*light\)\s*\{\s*:root\s*\{([^}]*)\}\s*\}", css)
    assert media, "no light scheme block"
    dark = re.search(r"(?<![\w-]):root\s*\{([^}]*)\}", css.replace(media.group(0), ""))
    assert dark, "no default scheme block"

    def props(body):
        return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;?", body))
    return props(dark.group(1)), props(media.group(1))


def test_trc_d2_dark_by_default_light_by_preference_and_4_5_contrast():
    css = css_of(every_state_page())
    dark, light = _scheme_blocks(css)
    texts, backgrounds = ("--text", "--muted", "--accent"), ("--bg", "--surface")
    for scheme in (dark, light):
        for name in texts + backgrounds:
            assert name in scheme
    assert _luminance(dark["--bg"]) < _luminance(dark["--text"])
    assert _luminance(light["--bg"]) > _luminance(light["--text"])
    for scheme in (dark, light):
        for t in texts:
            for b in backgrounds:
                assert _contrast(scheme[t], scheme[b]) >= 4.5, (t, b, scheme[t], scheme[b])
    # Colours live only in the two custom-property blocks.
    outside = re.sub(r"(?<![\w-]):root\s*\{[^}]*\}", "", css)
    outside = re.sub(r"@media[^{]*\{\s*\}", "", outside)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb|hsl", outside)


def test_trc_d3_every_recorded_value_is_escaped():
    bad = lambda what: 'x<script>alert("%s")</script>' % what  # noqa: E731
    values = {k: bad(k) for k in ("slug", "rationale", "changed", "label", "reason",
                                  "blocked", "tree", "id", "kind", "path", "role",
                                  "gate", "approach")}
    assessment = dict(ASSESSMENT, labels=[values["label"]], role=values["role"])
    r = row(values["slug"], delivery_approach=values["approach"], assessment=assessment,
            policy_rules_fired=[{"id": values["id"], "kind": values["kind"],
                                 "rationale": values["rationale"],
                                 "changed": [values["changed"]]}],
            gate_list=[{"id": values["gate"], "status": values["gate"]}],
            blocked=values["blocked"], tree=values["tree"], also_in=1,
            manifest_path=values["path"], set_aside=True, reason=values["reason"])
    page_html = render(r)
    assert "<script" not in page_html.lower()
    for name, value in values.items():
        assert value not in page_html, name
        assert html.escape(value, quote=True) in page_html, name
    root = read(page_html)
    card = cards(root)[0]
    panel_for(root, card)
    assert "tree " + values["tree"] in card.text() and "also in 1 tree" in card.text()


def test_trc_d3_card_names_other_trees_only():
    here = card_named(page_root(row("alpha")), "alpha").text()
    assert "tree" not in here and "also in" not in here
    root = page_root(row("beta", tree="b", also_in=2))
    assert "tree b" in card_named(root, "beta").text()
    assert "also in 2 trees" in card_named(root, "beta").text()


def test_trc_d5_empty_data_renders_ten_empty_lanes():
    empty = {"backlog": [], "ready": [], "in_progress": [], "stale": [], "in_review": [],
             "done_this_week": [], "closed": [], "other": [], "unreadable": [],
             "friction": None, "counts": {}, "total": 0}
    page_html = _page().render_page(empty, GENERATED, None)
    root = read(page_html)
    found = lanes(root)
    assert list(found) == LANE_NAMES
    assert all(heading_count(lane) == 0 and not cards(lane) for lane in found.values())
    assert "There are no issues yet." in root.text()
    assert "Trees read: 1 (this checkout)" in header_text(root)


def test_trc_b17_unplaceable_note_lists_each_folder_with_tree_and_reason():
    # The lane is set on purpose: the page must not place a row it was told is unplaceable.
    schema4 = row("future", unplaceable="its schema version 4 is not one this Compass reads",
                  lane="implement", tree="side")
    page_html = render(
        row("fine"), schema4,
        other=[{"slug": "odd", "delivery_approach": "full", "status": "paused",
                "note": "its status 'paused' is not one Compass sets", "tree": "this checkout",
                "manifest_path": ".compass/work/odd/manifest.yml", "also_in": 0}],
        unreadable=[{"slug": "broken", "note": "unreadable manifest.yml", "tree": "side",
                     "manifest_path": ".compass/work/broken/manifest.yml", "also_in": 0}])
    root = read(page_html)
    note = root.find_all("section", "unplaceable")
    assert len(note) == 1
    items = {i.find_all("span", "slug")[0].text(): i.text() for i in note[0].find_all("li")}
    assert set(items) == {"future", "odd", "broken"}
    assert "tree side" in items["future"] and "schema version 4" in items["future"]
    assert "tree side" in items["broken"] and "unreadable manifest.yml" in items["broken"]
    assert "paused" in items["odd"]
    assert [c.find_all("span", "slug")[0].text() for c in cards(root)] == ["fine"]
    assert "3 unplaceable" in header_text(root)


def test_trc_d5_a_board_with_only_unplaceable_folders_is_not_called_empty():
    root = page_root(row("future", unplaceable="schema 4", lane=None))
    assert "There are no issues yet." not in root.text()


def test_trc_b8_blocked_flag_outside_in_flight_states_is_not_counted_or_shown():
    # board() sets the blocked key only for in-progress and in-review rows, so rows
    # in other states reach the page without it and the page shows none.
    ready = row("soon", state="ready", stage="plan", lane="plan")
    aside = _backlog_row("later", "2026-09-01")
    root = page_root(ready, aside, row("busy", blocked="waiting"))
    assert "blocked" not in card_named(root, "soon").text()
    assert "blocked" not in card_named(root, "later").text()
    assert "blocked 1" in header_text(root)


RETIRED = ("held", "queued", "parked", "landed", "abandoned", "active", "route")


def test_trc_b14_no_retired_status_word_anywhere_on_the_page():
    page_html = every_state_page()
    for word in RETIRED:
        assert not re.search(r"(?<![\w-])%s(?![\w-])" % word, page_html, re.I), word
    assert ":active" not in page_html


def test_trc_b15_panels_show_stored_depths_and_size_unchanged():
    depths = {"assess": "thorough", "refine": "lightweight", "breakdown": "multiagent"}
    odd = {"assess": "thorough", "breakdown": "solo-or-pair"}
    assessment = dict(ASSESSMENT, size="medium")
    page_html = render(row("modern", assessment=assessment, stage_depths=depths),
                       row("archive", assessment=assessment, stage_depths=odd))
    text = panel_of(page_html, "modern").text()
    assert "breakdown multiagent" in text and "refine lightweight" in text
    assert "medium" in text
    assert "breakdown solo-or-pair" in panel_of(page_html, "archive").text()


def test_trc_b17_an_open_row_with_no_lane_is_listed_not_dropped():
    root = page_root(row("lost", lane=None), row("gone", state="done", stage=None, lane=None,
                                                  close_reason="not-planned"),
                     done_by_reason={"not-planned": 1})
    note = root.find_all("section", "unplaceable")
    assert len(note) == 1
    listed = [i.find_all("span", "slug")[0].text() for i in note[0].find_all("li")]
    assert listed == ["lost"]
