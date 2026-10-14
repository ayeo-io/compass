"""Scenarios DSS-1 to DSS-33 of the issue `document-set-sections`.

Each test is named for its scenario id, as the manifest declares
(`tests/test_document_set_sections.py::test_dss_<n>`). The scenarios are in
`document-set-sections/acceptance-criteria.md`.

The file has five regions, one per work unit. A unit writes only inside its own
region, and copies a helper it needs from another region into its own.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

# --- U1: Catalogue, templates and headings ---

PRESET = ROOT / "governance" / "presets" / "default" / "artifacts.yml"
TEMPLATES = ROOT / "templates"
ROLES_GUIDE = ROOT / "docs" / "roles-guide.md"
ROLE_HEADING = "How each role reads this file"
#: The five lines of the role block, as the spec template held them before this change.
ROLE_LINES = (
    "- **Product owner / manager** - reads for *intent fidelity*: do these scenarios deliver "
    "the outcome in `intent.md`?",
    "- **Product marketer** - reads for *claims*: every line of launch copy must point at a "
    "scenario id here.",
    "- **Engineer** - reads for *tests*: scenarios are the acceptance suite and seed the TDD "
    "red→green cycle.",
    "- **QA** - reads for *coverage*: which scenarios are exercised, which edges are not.",
    "- **Designer** - UI behaviour authored in `ui-contract.md` flows in here as scenarios.",
)
#: A leading section number: "1. ", "5a. " or "4b ".
NUMBERED = re.compile(r"^\d{1,2}[a-z]?\.?\s+")
SPEC_FOUR = ("Non-functional requirements",)
DESIGN_FOUR = ("Data and interfaces", "Verification plan", "Risks and dependencies")


def _preset():
    return yaml.safe_load(PRESET.read_text(encoding="utf-8"))["artifacts"]


def _cli(cwd, *argv):
    """`(code, stdout, stderr)` of one CLI call in `cwd`, with no issue selected."""
    run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), *argv], cwd=cwd, capture_output=True,
        text=True, timeout=180, stdin=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "HOME": str(cwd), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
             "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1",
             "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    return run.returncode, run.stdout, run.stderr


def _show(tmp_path, kind, depth):
    scratch = tmp_path / "plain"
    scratch.mkdir(exist_ok=True)
    code, out, err = _cli(scratch, "issue", "template", "show", kind, "--depth", depth)
    assert code == 0, out + err
    return out


def _headings(text):
    """The `## ` headings of a text outside code fences."""
    found, fenced = [], False
    for line in text.splitlines():
        if line.startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            found.append(line[3:].strip())
    return found


def _section_problems(kind, depth, output, preset):
    """One line per fault: a heading the catalogue lists for `kind` at `depth` that the output
    holds not exactly once, or holds out of the catalogue's order. Names the kind and heading."""
    wanted = list(preset[kind]["sections"][depth])
    held = [re.sub(r"\s*\(optional\)$", "", h) for h in _headings(output)]
    problems = []
    for heading in wanted:
        count = sum(1 for h in held if h == heading or re.sub(r"\{\{.*?\}\}", "<>", h)
                    == re.sub(r"<[^<>]*>", "<>", heading))
        if count != 1:
            problems.append("%s %s: %r appears %d times" % (kind, depth, heading, count))
    return problems


def _numbered_problems(path, text):
    return ["%s: %r" % (path, h) for h in _headings(text) if NUMBERED.match(h)]


def _before(output, first, second):
    held = _headings(output)
    return first in held and second in held and held.index(first) < held.index(second)


def test_dss_1_the_catalogue_and_template_show_carry_the_four_sections(tmp_path):
    preset = _preset()
    for depth, after in (("thorough", "Coverage ledger"), ("lightweight", "Coverage ledger")):
        out = _show(tmp_path, "acceptance-criteria", depth)
        assert _section_problems("acceptance-criteria", depth, out, preset) == []
        assert list(SPEC_FOUR) == [h for h in preset["acceptance-criteria"]["sections"][depth]
                                   if h in SPEC_FOUR], depth
        for heading in SPEC_FOUR:
            assert _headings(out).count(heading) == 1
            assert _before(out, heading, after), (depth, heading)
    for depth, after in (("thorough", "Work units"), ("lightweight", "Gate")):
        out = _show(tmp_path, "technical-design", depth)
        assert _section_problems("technical-design", depth, out, preset) == []
        for heading in DESIGN_FOUR:
            assert _headings(out).count(heading) == 1
            assert heading in preset["technical-design"]["sections"][depth]
            assert _before(out, heading, after), (depth, heading)
    # A planted fault that drops one of the 4 names the kind and the heading.
    out = _show(tmp_path, "technical-design", "thorough")
    broken = out.replace("## Verification plan\n", "", 1)
    found = _section_problems("technical-design", "thorough", broken, preset)
    assert any("technical-design" in p and "Verification plan" in p for p in found), found
    spec = _show(tmp_path, "acceptance-criteria", "lightweight")
    broken = spec.replace("## Non-functional requirements\n", "", 1)
    found = _section_problems("acceptance-criteria", "lightweight", broken, preset)
    assert any("acceptance-criteria" in p and "Non-functional requirements" in p
               for p in found), found


def test_dss_2_no_shipped_heading_carries_a_number(tmp_path):
    problems = []
    for path in sorted(TEMPLATES.glob("*.md")):
        problems += _numbered_problems(path.name, path.read_text(encoding="utf-8"))
    for kind, entry in sorted(_preset().items()):
        for depth, listed in sorted(entry["sections"].items()):
            problems += ["artifacts.yml %s %s: %r" % (kind, depth, h) for h in listed
                         if NUMBERED.match(h)]
    assert problems == []
    # The lightweight design prints no optional section and leaves no gap in its headings.
    out = _show(tmp_path, "technical-design", "lightweight")
    assert "(optional)" not in out
    assert _headings(out) == _preset()["technical-design"]["sections"]["lightweight"]
    # Every kind's template opens with its title and one header block pair, with no
    # hand-written header line before the first heading. The verification note holds only
    # its own block (decision Q8). The real parser reads each template, so each marker
    # names a registered block kind.
    from compass_pkg import rendered_blocks
    for kind in sorted(_preset()):
        text = (TEMPLATES / (kind + ".md")).read_text(encoding="utf-8")
        found = rendered_blocks.parse(text, kind + ".md")
        kinds = [b.kind for b in found.blocks]
        if kind == "verification-note":
            assert "document-header" not in kinds, kind
            continue
        assert kinds.count("document-header") == 1, kind
        head = text.split("\n## ", 1)[0].split("\n# ", 1)[1].splitlines()[1:]
        opening = [line for line in head if line.strip()][:2]
        assert opening == ["<!-- compass:render document-header -->",
                           "<!-- /compass:render -->"], (kind, opening)
        assert [line for line in head if line.startswith("> ")] == [], (kind, head)
    # A planted heading fails the test, naming the file and the heading.
    planted =(TEMPLATES / "technical-design.md").read_text(encoding="utf-8") + "\n## 9. Extra\n"
    found = _numbered_problems("technical-design.md", planted)
    assert found == ["technical-design.md: '9. Extra'"], found
    assert _numbered_problems("x.md", "## 5a. Cross\n\n## 4b Odd\n\n## 2026 roadmap\n") == [
        "x.md: '5a. Cross'", "x.md: '4b Odd'"]


def test_dss_3_the_role_block_lives_only_in_the_roles_guide():
    holders = [p.name for p in sorted(TEMPLATES.glob("*.md"))
               if ROLE_HEADING in p.read_text(encoding="utf-8")]
    assert holders == []
    assert ROLE_HEADING not in PRESET.read_text(encoding="utf-8")
    guide = ROLES_GUIDE.read_text(encoding="utf-8")
    for line in ROLE_LINES:
        assert guide.count(line) == 1, line
    for path in sorted(TEMPLATES.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for line in ROLE_LINES:
            assert line not in text, (path.name, line)


CONCERNS = ["performance", "capacity", "compatibility", "security", "privacy", "operability",
            "accessibility"]


def _section_body(output, heading):
    """The lines under `## <heading>` up to the next `## ` heading."""
    lines = output.splitlines()
    start = lines.index("## " + heading) + 1
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return body


def _tables(lines):
    """`[header cells, [row cells ...]]` for each pipe table in `lines`, outside code fences."""
    tables, current, fenced = [], None, False
    for line in lines:
        if line.startswith(("```", "~~~")):
            fenced = not fenced
        text = line.strip()
        if fenced or not text.startswith("|"):
            current = None
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", text.strip("|"))]
        if current is None:
            current = [cells, []]
            tables.append(current)
        elif not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            current[1].append(cells)
    return tables


def test_dss_8_the_spec_template_holds_the_concern_table(tmp_path):
    out = _show(tmp_path, "acceptance-criteria", "thorough")
    tables = _tables(_section_body(out, "Non-functional requirements"))
    assert [t[0] for t in tables] == [["Concern", "Scenario", "Reason it does not apply"]]
    rows = tables[0][1]
    assert [re.sub(r"[*`]", "", r[0]).lower() for r in rows] == CONCERNS
    assert all(len(r) == 3 for r in rows)
    # A planted fault that swaps two rows is reported.
    swapped = [rows[1], rows[0]] + rows[2:]
    assert [re.sub(r"[*`]", "", r[0]).lower() for r in swapped] != CONCERNS


def _fence_openers(lines):
    """The first content line of each fenced block in `lines`."""
    found, fenced, first = [], False, False
    for line in lines:
        if line.startswith(("```", "~~~")):
            fenced = not fenced
            first = fenced
        elif fenced and first:
            found.append(line.strip())
            first = False
    return found


def _prose(lines):
    """The text of `lines` outside code fences, HTML comments and tables."""
    text, fenced, commented = [], False, False
    for line in lines:
        if line.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        stripped = line.strip()
        if commented or stripped.startswith("<!--"):
            commented = "-->" not in stripped
            continue
        if stripped and not stripped.startswith("|"):
            text.append(stripped)
    return " ".join(text)


def test_dss_13_the_design_template_shows_the_three_declaration_forms(tmp_path):
    out = _show(tmp_path, "technical-design", "thorough")
    body = _section_body(out, "Data and interfaces")
    assert [t[0] for t in _tables(body)] == [
        ["Name", "Type", "Required", "Meaning", "Written by", "Read by"],
        ["Inputs", "Outputs", "Exit codes", "Errors"]]
    assert "erDiagram" in _fence_openers(body)
    prose = _prose(body).lower()
    for word in ("contract", "verb", "endpoint", "hook", "trigger"):
        assert word in prose, word
    # A planted fault that drops the diagram is reported.
    assert "erDiagram" not in _fence_openers([l for l in body if "erDiagram" not in l])


def test_dss_17_the_design_template_holds_the_verification_plan_table(tmp_path):
    out = _show(tmp_path, "technical-design", "thorough")
    body = _section_body(out, "Verification plan")
    assert [t[0] for t in _tables(body)] == [["Group", "Kind", "Fixture or environment"]]
    text = "\n".join(body)
    for kind in ("unit", "integration", "acceptance", "judged review", "manual"):
        assert "`%s`" % kind in text, kind
    assert "Not tested" in text
    after = body[[i for i, l in enumerate(body) if "Not tested" in l][0]:]
    items = [l for l in after if l.lstrip().startswith("- ")]
    assert items and all(re.search(r".+ - .*reason", l, re.I) for l in items), items


def test_dss_21_the_design_template_holds_the_risk_table_and_dependencies_block(tmp_path):
    from compass_pkg import rendered_blocks

    out = _show(tmp_path, "technical-design", "thorough")
    body = _section_body(out, "Risks and dependencies")
    assert [t[0] for t in _tables(body)] == [["Risk", "Likelihood", "Effect", "Addressed by"]]
    found = rendered_blocks.parse(out, "technical-design.md")
    lines = out.splitlines()
    inside = [b for b in found.blocks if b.kind == "dependencies"]
    assert len(inside) == 1
    start = lines.index("## Risks and dependencies")
    end = start + 1 + len(body)
    assert start < inside[0].start < end
    # A planted fault that drops the marker pair is reported.
    broken = out.replace("<!-- compass:render dependencies -->\n<!-- /compass:render -->\n", "")
    assert [b for b in rendered_blocks.parse(broken, "x.md").blocks
            if b.kind == "dependencies"] == []


#: The issue of the generation-1 fixtures, and the headings the shipped catalogue listed for the
#: design before they lost their numbers.
EARLIER_SLUG = "feature"
EARLIER_DESIGN = ["1. Approach", "6. Design decisions (ADR-style)", "7. Governance check",
                  "8. Work units", "Gate"]


def _earlier_generation_project(tmp_path):
    """A scratch project with one issue stored on generation 1, whose catalogue lists the
    numbered design headings."""
    root = tmp_path / "earlier"
    task_dir = root / ".compass" / "work" / EARLIER_SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": EARLIER_SLUG, "created": "2026-10-07",
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "medium", "goal": "delivery", "role": "engineer", "labels": []},
        "evidence": []}, sort_keys=False), encoding="utf-8")
    (root / "compass.yml").write_text(yaml.safe_dump({
        "schema": 1, "artifacts": {"technical-design": {"set": {"sections": {
            "thorough": EARLIER_DESIGN}}}}}, sort_keys=False), encoding="utf-8")
    code, out, err = _cli(root, "approach", "evaluate", "--issue", EARLIER_SLUG, "--write")
    assert code == 0, out + err
    return root


def _bare_headings(output, wanted):
    """The headings of `wanted` that `output` prints with no text under them."""
    lines = output.splitlines()
    bare = []
    for heading in wanted:
        if "## " + heading not in lines:
            bare.append(heading)
            continue
        after = lines[lines.index("## " + heading) + 1:]
        body = []
        for line in after:
            if line.startswith("## "):
                break
            body.append(line)
        if not "".join(body).strip():
            bare.append(heading)
    return bare


_SPEC_BODY = """\
## {group} - Export

### Scenario: Export the ledger
<!-- traceability id: TRC-1 · serves: INT-1 -->

```gherkin
Scenario: Export the ledger
  Given a ledger
  When it is exported
  Then 1 file is written
```

### Scenario: Export an empty ledger
<!-- traceability id: TRC-2 · serves: INT-1 -->

```gherkin
Scenario: Export an empty ledger
  Given an empty ledger
  When it is exported
  Then 0 rows are written
```
"""

_ROLE_BLOCK = "## How each role reads this file\n\n" + "\n".join(ROLE_LINES) + "\n\n"

_DESIGN_BODY = """\
{approach}

{decisions}

### `DD-1` - Keep one writer

- **Context:** Two writers raced.
- **Decision:** One writer.
- **Governance tie:** ADR-051

### `DD-2` - Name the file

- **Context:** Readers could not find it.
- **Decision:** Name it for its kind.
"""


def _fixture_issue(path, numbered):
    """One rendered-blocks fixture issue whose documents use numbered headings and the role
    block (`numbered`) or the named headings."""
    import rendered_blocks_support as sup

    root = sup.rich_issue(path)
    group = "1. Scenario group A" if numbered else "Scenario group A"
    spec = "# Spec\n\n" + (_ROLE_BLOCK if numbered else "") + _SPEC_BODY.format(group=group)
    spec +="\n## Coverage ledger\n\n" + sup.block("coverage")
    sup.write_doc(root, "acceptance-criteria", spec)
    design = "# Plan\n\n" + _DESIGN_BODY.format(
        approach="## 1. Approach" if numbered else "## Approach",
        decisions="## 6. Design decisions (ADR-style)" if numbered
        else "## Design decisions (ADR-style)")
    sup.write_doc(root, "technical-design", design)
    sup.write_doc(root, "requirements-review", "# RR\n\n## Gate\n\n" + sup.block("dor"))
    sup.write_doc(root, "verification-report", "# VR\n\n" + "".join(
        ("## %s\n\n" % name) + sup.block(kind) for name, kind in (
            (("1. " if numbered else "") + "Scenario acceptance results", "coverage"),
            (("4. " if numbered else "") + "Gate decision", "gates"),
            ("Gate", "dod"),
            (("2. " if numbered else "") + "Test suite evidence", "evidence"),
            (("6. " if numbered else "") + "Decisions taken for the user", "decisions-taken"))))
    return root


def _normal(text, root):
    return re.sub(r"\d{8}T\d{6}Z", "<time>", text.replace(str(root), "<root>"))


def _blocks_of(root):
    """`{file: [(kind, interior)]}` for each document of the fixture issue."""
    import rendered_blocks_support as sup
    from compass_pkg import rendered_blocks

    found = {}
    for path in sorted((Path(root) / sup.DOCS).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parsed = rendered_blocks.parse(text, path.name)
        found[path.name] = [(b.kind, "".join(parsed.lines[b.start + 1:b.end]))
                            for b in parsed.blocks]
    return found


def _four_commands(root):
    """The output of `render`, `check`, `receipt`, `analyze` and `lint` on a fixture issue."""
    import rendered_blocks_support as sup

    out = {}
    for name, argv in (("render", ("issue", "render", "--issue", sup.SLUG)),
                       ("check", ("check", "--issue", sup.SLUG, "--json")),
                       ("receipt", ("issue", "receipt", "--issue", sup.SLUG)),
                       ("analyze", ("analyze", "--issue", sup.SLUG)),
                       ("lint", ("issue", "lint", "--issue", sup.SLUG))):
        code, text, err = sup.run(root, *argv)
        out[name] = (code, _normal(text + err, root))
    return out


def _differences(old, new):
    """The commands whose outputs differ between the two fixture runs."""
    return sorted(k for k in old if old[k] != new[k])


def test_dss_4_readers_find_sections_in_numbered_and_named_documents_alike(tmp_path):
    old = _fixture_issue(tmp_path / "numbered", True)
    new = _fixture_issue(tmp_path / "named", False)
    first, second = _four_commands(old), _four_commands(new)
    # Each command gives the same answer from both documents, apart from the documents'
    # own content digests.
    for name in ("render", "receipt", "analyze", "lint"):
        assert first[name] == second[name], name
    check = [json.loads(second_run[1]) for second_run in (first["check"], second["check"])]
    assert [(c["name"], c["status"]) for c in check[0]["checks"]] == [
        (c["name"], c["status"]) for c in check[1]["checks"]]
    assert first["check"][0] == second["check"][0]
    # The decisions block lists the same DD-n headings from both designs.
    blocks_old, blocks_new = _blocks_of(old), _blocks_of(new)
    decisions = dict(blocks_new["README.md"])["decisions"]
    assert "DD-1" in decisions and "DD-2" in decisions
    assert dict(blocks_old["README.md"]) == dict(blocks_new["README.md"])
    # The Definition of Ready and of Done items and the coverage ledger are read from both.
    for name in ("requirements-review.md", "verification-report.md", "acceptance-criteria.md"):
        assert blocks_old[name] == blocks_new[name], name
    assert dict(blocks_new["requirements-review.md"])["dor"].strip()
    assert dict(blocks_new["verification-report.md"])["dod"].strip()
    assert "TRC-1" in dict(blocks_new["acceptance-criteria.md"])["coverage"]
    # The receipt reads the assessment from the manifest.
    assert "risk            contained" in second["receipt"][1]
    # No check and no lint finding reports a numbered heading or a role block.
    for run in (first, second):
        for name in ("check", "lint", "analyze"):
            assert not re.search(r"numbered heading|role block|How each role", run[name][1]), name
    # A planted fault is reported: a document read differently once its headings are named.
    broken = dict(second)
    broken["lint"] = (0, second["lint"][1] + "\n  a numbered heading: 6. Design decisions\n")
    assert _differences(first, broken) == ["lint"]


def test_dss_31_template_show_on_an_earlier_generation_keeps_its_prose(tmp_path):
    from compass_pkg import template_lists

    root = _earlier_generation_project(tmp_path)
    code, out, err = _cli(root, "issue", "template", "show", "technical-design", "--issue",
                          EARLIER_SLUG, "--depth", "thorough")
    assert code == 0, out + err
    held = yaml.safe_load(next((root / ".compass" / "work" / EARLIER_SLUG / "generations" / "1"
                                ).glob("resolved.yml")).read_text(encoding="utf-8"))
    assert held["artifacts"]["technical-design"]["sections"]["thorough"] == EARLIER_DESIGN
    assert _bare_headings(out, EARLIER_DESIGN) == [], out
    # The prose is the named template's, under the numbered heading.
    assert "{{APPROACH}}" in out.split("## 1. Approach", 1)[1]
    assert "### `DD-1`" in out.split("## 6. Design decisions (ADR-style)", 1)[1]
    # A leading section number matches the named heading of the same text.
    assert template_lists.same_heading("1. Approach", "Approach")
    assert template_lists.same_heading("5a. Cross-cutting concerns", "Cross-cutting concerns")
    assert template_lists.same_heading("Design decisions (ADR-style)",
                                       "6. Design decisions (ADR-style)")
    # A year or a three-digit number is part of the words.
    assert not template_lists.same_heading("2026 roadmap", "roadmap")
    assert not template_lists.same_heading("100. Roadmap", "Roadmap")
    # A planted fault that strips nothing leaves headings bare.
    assert _bare_headings("## 1. Approach\n\n## Gate\n\ntext\n", ["1. Approach", "Gate"]) == [
        "1. Approach"]


# --- U2: header block and quick-fix record ---

# --- U3: section checks and the archive boundary ---

NFR = "nfr-rows-resolved"
CONTRACTS = "contracts-declared"
SECTION_CHECKS = (NFR, CONTRACTS)
U3_FULL = {"risk": "cross-cutting", "size": "large"}
U3_CONCERNS = ("performance", "capacity", "compatibility", "security", "privacy",
               "operability", "accessibility")

_U3_SCENARIO = """\
### Scenario: {title}
<!-- traceability id: {sid} · serves: INT-1 -->

```gherkin
Scenario: {title}
  Given a ledger of 500 rows
  When it is exported
  Then {then}
  And {also}
```
"""

#: The scenarios of the fixture spec: id, title, Then line and the And line after it.
U3_SCENARIOS = (
    ("TRC-1", "Export is fast", "the file is written within 3 seconds", "it opens"),
    ("TRC-2", "Old files still open", "0 old files fail to open", "none is rewritten"),
    ("TRC-10", "Export names the file", "the file is named for the ledger", "it is listed"),
)

#: The concern table of a fully resolved spec: performance and compatibility cite scenarios
#: with a numbered Then, the other five give a reason.
U3_ROWS = {
    "performance": ("TRC-1", ""),
    "capacity": ("", "No stored data grows."),
    "compatibility": ("TRC-2", ""),
    "security": ("", "No input crosses a trust boundary."),
    "privacy": ("", "No personal data is read."),
    "operability": ("", "Nothing runs unattended."),
    "accessibility": ("", "No interface changes."),
}


def _u3_table(rows):
    lines = ["| Concern | Scenario | Reason it does not apply |", "|---|---|---|"]
    lines += ["| %s | %s | %s |" % (name, cited, reason) for name, (cited, reason) in rows]
    return "\n".join(lines) + "\n"


def _u3_spec(rows=None, section=True, scenarios=U3_SCENARIOS):
    """A spec with three scenarios and, with `section`, a Non-functional requirements
    table of `rows` (a list of `(concern, (scenario cell, reason cell))`)."""
    body = ["# Spec - feature\n", "## Scenario group A - Export\n"]
    body += [_U3_SCENARIO.format(sid=sid, title=title, then=then, also=also)
             for sid, title, then, also in scenarios]
    if section:
        body.append("## Non-functional requirements\n\n"
                    + _u3_table(list(U3_ROWS.items()) if rows is None else rows))
    body.append("## Coverage ledger\n\nNone yet.\n")
    return "\n".join(body)


def _u3_project(tmp_path, assessment=U3_FULL, compass_yml=None):
    """A git repository holding one issue at generation 1, assessed onto the shipped
    default, with the scenarios of the fixture spec in its manifest."""
    import artifact_status_support as sup

    root = sup.project(tmp_path, compass_yml=compass_yml or {"schema": 1, "owner": "jed72"},
                       assessment=assessment)
    body = sup.manifest(root)
    body["scenarios"] = [{"id": sid, "title": title, "intent": "INT-1"}
                         for sid, title, _, _ in U3_SCENARIOS]
    sup.write_manifest(root, body)
    return root


def _u3_write_spec(root, text, depth="thorough", register=True):
    """Write the spec and, with `register`, give its registry entry a path at `depth`
    (`None` removes the depth key)."""
    import artifact_status_support as sup

    (root / sup.DOCS / "acceptance-criteria.md").write_text(text, encoding="utf-8")
    if not register:
        return
    sup.add_entry(root, "acceptance-criteria")
    if depth != "thorough":
        body = sup.manifest(root)
        for one in body["artifacts"]:
            if one["kind"] == "acceptance-criteria":
                one.pop("depth")
                if depth is not None:
                    one["depth"] = depth
        sup.write_manifest(root, body)


def _u3_check(root, slug="feature"):
    """`(exit code, {check: (status, detail)})` of `compass check --json`."""
    import artifact_status_support as sup

    code, out, err = sup.run(root, "check", "--issue", slug, "--json")
    try:
        found = json.loads(out)
    except ValueError:
        raise AssertionError(out + err)
    return code, {c["name"]: (c["status"], c["detail"]) for c in found["checks"]}


def _u3_exit_without(rows, names=SECTION_CHECKS):
    """The exit code `compass check` gives when the rows `names` are left out: 1 when
    any other row fails, else 0."""
    return int(any(status == "fail" for name, (status, _) in rows.items()
                   if name not in names))


def _u3_fails(root, check, *named):
    """Run `compass check` and assert that `check` fails naming each of `named`, with a
    non-zero exit that the row causes."""
    code, rows = _u3_check(root)
    status, detail = rows[check]
    assert status == "fail", (check, status, detail)
    for word in named:
        assert word in detail, (word, detail)
    assert code == 1
    return detail


def _u3_passes(root, check):
    code, rows = _u3_check(root)
    assert rows[check][0] == "pass", rows[check]
    return rows[check][1]


def test_dss_9_nfr_passes_resolved_table(tmp_path):
    root = _u3_project(tmp_path)
    _u3_write_spec(root, _u3_spec())
    code, rows = _u3_check(root)
    assert rows[NFR] == ("pass", "7 of 7 concerns resolved"), rows.get(NFR)
    assert code == _u3_exit_without(rows)


def test_dss_10_nfr_fails_bad_rows(tmp_path):
    root = _u3_project(tmp_path)
    good = list(U3_ROWS.items())

    def rows_with(name, value):
        return [(n, value if n == name else v) for n, v in good]

    breaks = (
        # The security row's Scenario and Reason cells are both empty.
        (_u3_spec(rows_with("security", ("", ""))),
         ("security", "has neither a scenario nor a reason")),
        # A cell holding only a placeholder is empty.
        (_u3_spec(rows_with("security", ("{{…}}", "{{…}}"))),
         ("security", "has neither a scenario nor a reason")),
        # The privacy row is deleted.
        (_u3_spec([(n, v) for n, v in good if n != "privacy"]), ("privacy", "is missing")),
        # A row cites DSS-99, which the manifest does not hold.
        (_u3_spec(rows_with("performance", ("DSS-99", ""))), ("performance", "DSS-99")),
        # The whole section is deleted.
        (_u3_spec(section=False), ("Non-functional requirements",)),
    )
    for text, named in breaks:
        _u3_write_spec(root, text)
        _u3_fails(root, NFR, *named)
        # The fix the detail names, alone, makes the check pass again.
        _u3_write_spec(root, _u3_spec())
        assert _u3_passes(root, NFR) == "7 of 7 concerns resolved"


CORPUS_ROOT = ROOT / "tests" / "fixtures" / "impls"


def _u3_corpus(impl):
    """`{case: expected.yml}` of an implementation's corpus."""
    return {path.parent.name: yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in sorted((CORPUS_ROOT / impl).glob("*/expected.yml"))}


def test_dss_11_nfr_number_rule_by_depth(tmp_path):
    root = _u3_project(tmp_path)
    good = list(U3_ROWS.items())
    # The performance row cites TRC-10: no digit in its Then line or the line after it.
    unnumbered = _u3_spec([(n, ("TRC-10", "") if n == "performance" else v) for n, v in good])
    _u3_write_spec(root, unnumbered, depth="thorough")
    _u3_fails(root, NFR, "performance", "TRC-10", "no number")
    # At lightweight the same table passes.
    _u3_write_spec(root, unnumbered, depth="lightweight")
    assert _u3_passes(root, NFR) == "7 of 7 concerns resolved"
    # At both depths a row with only a reason passes.
    reason_only = _u3_spec([(n, ("", "Measured elsewhere.") if n == "performance" else v)
                            for n, v in good])
    for depth in ("thorough", "lightweight"):
        _u3_write_spec(root, reason_only, depth=depth)
        assert _u3_passes(root, NFR) == "7 of 7 concerns resolved", depth
    # The id must end where it ends: with TRC-10 written before TRC-1, a row citing TRC-1 is
    # judged by TRC-1's numbered Then, not by TRC-10's.
    reordered = _u3_spec(scenarios=tuple(reversed(U3_SCENARIOS)))
    _u3_write_spec(root, reordered, depth="thorough")
    assert _u3_passes(root, NFR) == "7 of 7 concerns resolved"
    # With no depth key the catalogue lists nothing, so there is nothing to check.
    _u3_write_spec(root, unnumbered, depth=None)
    code, rows = _u3_check(root)
    assert rows[NFR][0] == "nothing-to-check", rows[NFR]
    assert "at no depth" in rows[NFR][1]
    assert code == _u3_exit_without(rows)
    # One corpus case holds that shape.
    held = [name for name, case in _u3_corpus(NFR).items()
            if case["verdict"] == "nothing-to-check" and "no depth key" in case["input"]]
    assert len(held) == 1, _u3_corpus(NFR)


def _u3_declared(root, slug="feature"):
    """The check ids the issue's newest stored generation declares."""
    folder = root / ".compass" / "work" / slug / "generations"
    newest = max(int(p.name) for p in folder.iterdir() if p.name.isdigit())
    resolved = yaml.safe_load((folder / str(newest) / "resolved.yml").read_text(encoding="utf-8"))
    return set(resolved.get("checks") or {})


def test_dss_12_nfr_nothing_to_check_without_spec(tmp_path):
    shapes = (("quick-fix", {"risk": "trivial", "size": "small"}),
              ("spike", {"goal": "exploration"}),
              ("regular", {}))
    for approach, assessment in shapes:
        root = _u3_project(tmp_path / approach, assessment=assessment)
        import artifact_status_support as sup
        assert sup.manifest(root)["delivery_approach"] == approach
        assert NFR in _u3_declared(root), approach
        code, rows = _u3_check(root)
        assert rows.get(NFR) == ("nothing-to-check",
                                 "no acceptance-criteria is registered with a path"), (
            approach, rows.get(NFR))
        assert code == _u3_exit_without(rows), approach


CONTRACTS_HEADING = "Data and interfaces"
U3_SCHEMA = "schemas/manifest.schema.json"


def _u3_template_section(heading):
    """The `## <heading>` section of the shipped design template, heading included."""
    text = (TEMPLATES / "technical-design.md").read_text(encoding="utf-8")
    start = text.index("## %s\n" % heading)
    end = text.index("\n## ", start + 3)
    return text[start:end + 1]


def _u3_design(section):
    """A design whose Data and interfaces section is `section` (heading included, or
    empty for no section)."""
    return ("# Plan - feature\n\n## Approach\n\nOne writer.\n\n" + section
            + "\n## Gate\n\nNone yet.\n")


def _u3_write_design(root, text, changed=(U3_SCHEMA,), register=True):
    """Write the design, register it with a path, and set `changed_files`."""
    import artifact_status_support as sup

    (root / sup.DOCS / "technical-design.md").write_text(text, encoding="utf-8")
    if register:
        sup.add_entry(root, "technical-design")
    body = sup.manifest(root)
    body["changed_files"] = [{"path": p, "scenarios": ["TRC-1"]} for p in changed]
    sup.write_manifest(root, body)


def _u3_write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_dss_14_contracts_fails_undeclared(tmp_path):
    import inspect

    import artifact_status_support as sup
    from compass_pkg import section_checks

    root = _u3_project(tmp_path, assessment={})
    assert sup.manifest(root)["delivery_approach"] == "regular"
    empty = _u3_design(_u3_template_section(CONTRACTS_HEADING))
    _u3_write(root, "tools/cli.py", "def build(sub):\n    sub.add_parser('go')\n")
    for path in (U3_SCHEMA, "governance/presets/default/checks.yml", "docs/x.schema.json",
                 "tools/cli.py"):
        _u3_write_design(root, empty, changed=(path,))
        _u3_fails(root, CONTRACTS, path, CONTRACTS_HEADING)
    # With the section heading removed, it fails naming the absent section.
    _u3_write_design(root, _u3_design(""))
    detail = _u3_fails(root, CONTRACTS, U3_SCHEMA, CONTRACTS_HEADING)
    assert "has no" in detail, detail
    # The shipped patterns are read from checks.yml, not from the implementation.
    checks = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "checks.yml"
                             ).read_text(encoding="utf-8"))["checks"]
    params = checks[CONTRACTS]["params"]
    assert params == {"trigger_paths": ["schemas/*", "governance/presets/*", "*.schema.json"],
                      "trigger_contents": [{"path": "*.py", "contains": "add_parser("}]}
    source = inspect.getsource(section_checks)
    for pattern in ("schemas/", "governance/presets", ".schema.json", "add_parser("):
        assert pattern not in source, pattern
    # A project layer that adds the trigger pattern "api/**" makes a change to a YAML file
    # under the api folder fail the same way, once the issue is assessed onto it. The merge grammar changes a
    # map key by key, so the layer sets `trigger_paths` to the shipped list and the pattern.
    _u3_write_design(root, empty, changed=("api/v1.yaml",))
    code, rows = _u3_check(root)
    assert rows[CONTRACTS][0] == "nothing-to-check", rows[CONTRACTS]
    (root / "compass.yml").write_text(yaml.safe_dump({
        "schema": 1, "owner": "jed72",
        "checks": {CONTRACTS: {
            "set": {"params": {"set": {
                "trigger_paths": params["trigger_paths"] + ["api/**"]}}},
            "waiver": {"reason": "Our API files are contracts too.", "approved_by": "jed72",
                       "approved_on": "2026-10-14"}}}}, sort_keys=False), encoding="utf-8")
    code, out, err = sup.run(root, "approach", "evaluate", "--issue", sup.SLUG, "--write",
                             "--reason", "add the api trigger pattern")
    assert code == 0, out + err
    _u3_fails(root, CONTRACTS, "api/v1.yaml", CONTRACTS_HEADING)


U3_DECLARED = {
    "field table": ("| Name | Type | Required | Meaning | Written by | Read by |\n"
                    "|---|---|---|---|---|---|\n"
                    "| `generation` | integer | no | the stored configuration | assess | check |\n"),
    "erDiagram": ("```mermaid\nerDiagram\n    ISSUE ||--o{ GENERATION : stores\n```\n"),
    "contract table": ("| Inputs | Outputs | Exit codes | Errors |\n|---|---|---|---|\n"
                       "| `compass check --json` | one row per check | 0 or 1 | none new |\n"),
}


def test_dss_15_contracts_passes_declared(tmp_path):
    root = _u3_project(tmp_path, assessment={})
    for form, body in U3_DECLARED.items():
        _u3_write_design(root, _u3_design("## %s\n\n%s" % (CONTRACTS_HEADING, body)))
        detail = _u3_passes(root, CONTRACTS)
        assert U3_SCHEMA in detail and "1 contract" in detail, (form, detail)
    # A section holding only the text "None." still fails.
    _u3_write_design(root, _u3_design("## %s\n\nNone.\n" % CONTRACTS_HEADING))
    _u3_fails(root, CONTRACTS, U3_SCHEMA, CONTRACTS_HEADING)


def test_dss_16_contracts_nothing_to_check(tmp_path):
    import artifact_status_support as sup

    root = _u3_project(tmp_path / "regular", assessment={})
    _u3_write(root, "cli/compass_pkg/flow.py", "def run():\n    return 1\n")
    _u3_write_design(root, _u3_design(_u3_template_section(CONTRACTS_HEADING)),
                     changed=("cli/compass_pkg/flow.py",))
    code, rows = _u3_check(root)
    assert rows[CONTRACTS] == ("nothing-to-check",
                               "no changed file matches a trigger pattern of contracts-declared")
    assert code == _u3_exit_without(rows)
    # A quick fix and a hotfix that change a schema register no technical design.
    for approach, assessment in (("quick-fix", {"risk": "trivial", "size": "small"}),
                                 ("hotfix", {"urgency": "live-defect", "size": "small"})):
        root = _u3_project(tmp_path / approach, assessment=assessment)
        assert sup.manifest(root)["delivery_approach"] == approach
        assert CONTRACTS in _u3_declared(root), approach
        body = sup.manifest(root)
        body["changed_files"] = [{"path": U3_SCHEMA, "scenarios": ["TRC-1"]}]
        sup.write_manifest(root, body)
        code, rows = _u3_check(root)
        assert rows[CONTRACTS] == ("nothing-to-check",
                                   "no technical-design is registered with a path"), approach
        assert code == _u3_exit_without(rows), approach


def _u3_evaluate(root, reason):
    import artifact_status_support as sup

    code, out, err = sup.run(root, "approach", "evaluate", "--issue", sup.SLUG, "--write",
                             "--reason", reason)
    assert code == 0, out + err


def test_dss_24_earlier_generation_runs_neither_check(tmp_path):
    import artifact_status_support as sup

    # Generation 1 is stored from a configuration that declares neither check, as one
    # stored before this change does: the project layer removes both.
    waiver = {"reason": "Stored before the section checks.", "approved_by": "jed72",
              "approved_on": "2026-10-14"}
    earlier = {"schema": 1, "owner": "jed72",
               "checks": {check: {"remove": True, "waiver": waiver} for check in SECTION_CHECKS},
               "vocabulary": {"checks." + check: {"remove": True} for check in SECTION_CHECKS}}
    root = _u3_project(tmp_path, assessment={}, compass_yml=earlier)
    assert sup.manifest(root)["generation"] == 1
    assert not set(SECTION_CHECKS) & _u3_declared(root)
    _u3_write_spec(root, "# Spec\n\n## Summary\n\nNo section.\n")
    _u3_write_design(root, _u3_design(_u3_template_section(CONTRACTS_HEADING)))
    code, rows = _u3_check(root)
    assert not set(SECTION_CHECKS) & set(rows), rows
    assert code == _u3_exit_without(rows)
    # `issue migrate --config` changes no configuration, so the issue still runs neither.
    code, out, err = sup.run(root, "issue", "migrate", "--config", "--issue", sup.SLUG)
    assert code == 0, out + err
    assert not set(SECTION_CHECKS) & _u3_declared(root)
    code, rows = _u3_check(root)
    assert not set(SECTION_CHECKS) & set(rows), rows
    # Assessed onto the configuration now, generation 2 declares both, and both fail.
    (root / "compass.yml").write_text(yaml.safe_dump({"schema": 1, "owner": "jed72"}),
                                      encoding="utf-8")
    _u3_evaluate(root, "move onto the section checks")
    assert sup.manifest(root)["generation"] == 2
    assert set(SECTION_CHECKS) <= _u3_declared(root)
    _u3_fails(root, NFR, "Non-functional requirements")
    _u3_fails(root, CONTRACTS, U3_SCHEMA, CONTRACTS_HEADING)
    # An issue waiver that makes either check advisory turns its failure into an advisory
    # failure that does not fail the run.
    body = sup.manifest(root)
    body["config"] = {"checks": {}}
    for n, check in enumerate(SECTION_CHECKS):
        body["config"]["checks"][check] = {
            "set": {"severity": "advisory"},
            "waiver": {"reason": "Judged by hand on this issue.", "approved_by": "EV-W%d" % n}}
        body["evidence"].append({
            "id": "EV-W%d" % n, "type": "human-approval", "decision": "approved",
            "approver": "jed72", "role": "owner", "scope": "waiver",
            "timestamp": "2026-10-14T09:00:00Z",
            "waiver": {"scope": "issue", "entry": "checks.%s" % check,
                       "fields": {"severity": {"from": "blocking", "to": "advisory"}}}})
    sup.write_manifest(root, body)
    _u3_evaluate(root, "waive the section checks")
    code, rows = _u3_check(root)
    for check in SECTION_CHECKS:
        assert rows[check][0] == "advisory", rows[check]
    assert code == _u3_exit_without(rows)


def _u3_sweep(root, workers=2):
    """`{slug: (exit, {check: status})}` of `compass check --json` on every issue under
    `root`, run `workers` at a time."""
    from concurrent.futures import ThreadPoolExecutor

    from compat_baseline import _issues

    def one(slug):
        done = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "check",
                               "--issue", slug, "--json"], cwd=root, capture_output=True,
                              text=True, timeout=600,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(root),
                                   "LANG": "C.UTF-8", "NO_COLOR": "1",
                                   "CLAUDE_PROJECT_DIR": str(root),
                                   "PYTHONDONTWRITEBYTECODE": "1"})
        try:
            rows = {c["name"]: c["status"] for c in json.loads(done.stdout)["checks"]}
        except (ValueError, KeyError, TypeError):
            rows = {"unreadable output": done.stdout[-200:] + done.stderr[-200:]}
        return slug, (done.returncode, rows)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(one, _issues(root)))


def _u3_judged(results):
    """The issues on which either section check gave a verdict other than nothing to check."""
    return sorted("%s: %s %s" % (slug, check, rows[check])
                  for slug, (_, rows) in results.items() for check in SECTION_CHECKS
                  if check in rows and rows[check] != "nothing-to-check")


def test_dss_26_archive_sweep_and_compat_contract(tmp_path):
    from archive import archive_root, checkable_root, full_archive, sample_root
    from compat_baseline import (ARCHIVE, allow_7_0_0_moves, archive_differences,
                                 archive_results)

    # The allow-list admits a new row for either check only as nothing to check, and only
    # when the recorded verdicts have no row for it.
    from test_compat_contracts import test_contract_3_allows_only_the_three_moves_of_7_0_0

    base = {"check_exit": 0, "lint_exit": 0, "receipt_exit": 0,
            "verdicts": {"dod-evidence-typed": "pass", "suite-passed": "pass"}}
    good = {"check_exit": 0, "lint_exit": 0, "receipt_exit": 0,
            "verdicts": {"rendered-blocks-current": "pass",
                         "dod-evidence-typed": "nothing-to-check", "suite-passed": "pass"}}

    def differs(old=base, **verdicts):
        now = dict(good, verdicts=dict(good["verdicts"], **verdicts))
        return archive_differences(*allow_7_0_0_moves({"x": old}, {"x": now}))

    assert differs() == []
    for check in SECTION_CHECKS:
        assert differs(**{check: "nothing-to-check"}) == [], check
        for verdict in ("fail", "pass", "advisory", "refused"):
            assert differs(**{check: verdict}), (check, verdict)
        recorded_row = dict(base, verdicts=dict(base["verdicts"], **{check: "pass"}))
        assert differs(recorded_row, **{check: "nothing-to-check"}), check
    # The three moves of 7.0.0 and the exit code stay as they were: contract 3's own test of
    # the allow-list still holds.
    for verdicts in ({"suite-passed": "fail"}, {"rendered-blocks-current": "fail"},
                     {"dod-evidence-typed": "fail"}, {"extra-check": "pass"}):
        assert differs(**verdicts), verdicts
    assert archive_differences(*allow_7_0_0_moves({"x": base}, {"x": dict(good, check_exit=1)}))
    test_contract_3_allows_only_the_three_moves_of_7_0_0()

    # On the archive sample, contract 3 passes and neither check judges an issue.
    recorded = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    assert recorded["version"] == "5.6.0" and len(recorded["issues"]) == 16
    # No baseline file was rewritten: the recorded verdicts hold no row for either check.
    assert not any(set(SECTION_CHECKS) & set(r["verdicts"]) for r in recorded["issues"].values())
    now = archive_results(checkable_root())
    old, new = allow_7_0_0_moves(recorded["issues"], now)
    assert archive_differences(old, new) == []
    judged = [(slug, check) for slug, r in now.items() for check in SECTION_CHECKS
              if r["verdicts"].get(check, "nothing-to-check") != "nothing-to-check"]
    assert judged == []
    failing = sorted(s for s, r in recorded["issues"].items() if r["check_exit"])
    assert sorted(s for s, r in now.items() if r["check_exit"]) == failing
    if not full_archive():
        return
    # The maintainer's archive, copied, so a check run never writes into it.
    source = archive_root()
    copy = tmp_path / "archive"
    for part in (".compass/work", "docs/compass", "governance"):
        if (source / part).is_dir():
            shutil.copytree(source / part, copy / part, symlinks=True)
    if (source / "compass.yml").is_file():
        shutil.copy(source / "compass.yml", copy / "compass.yml")
    results = _u3_sweep(copy)
    assert _u3_judged(results) == []
    # A nothing-to-check row never counts as a failure, so the issues that fail are the
    # issues that fail with both rows left out.
    assert len(results) == len(list((copy / ".compass" / "work").glob("*/manifest.yml")))


def _u3_copy_archive(source, target):
    """A copy of a project's archive: its issue records, documents and project file."""
    for part in (".compass/work", "docs/compass", "governance"):
        if (source / part).is_dir():
            shutil.copytree(source / part, target / part, symlinks=True)
    if (source / "compass.yml").is_file():
        shutil.copy(source / "compass.yml", target / "compass.yml")
    return target


def _u3_documents(root):
    """`{relative path: text}` of every Markdown document under docs/compass/."""
    base = root / "docs" / "compass"
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="replace")
            for p in sorted(base.rglob("*.md")) if p.is_file()}


def _u3_digests(root):
    """`{(issue, entry id): (path, digest)}` of every registry entry that records a digest."""
    found = {}
    for manifest in sorted((root / ".compass" / "work").glob("*/manifest.yml")):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        for entry in data.get("artifacts") or []:
            if isinstance(entry, dict) and entry.get("digest"):
                found[(manifest.parent.name, entry.get("id"))] = (entry.get("path"),
                                                                  entry["digest"])
    return found


def _u3_heading_lines(text):
    """The heading lines of a document outside code fences and rendered blocks."""
    from compass_pkg import rendered_blocks

    found, fenced = [], False
    for line in rendered_blocks.masked_text(text).split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,6} ", line):
            found.append(line.rstrip())
    return found


def _u3_cli_in(root, *argv):
    done = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv], cwd=root,
                          capture_output=True, text=True, timeout=1800,
                          env={"PATH": "/usr/bin:/bin", "HOME": str(root), "LANG": "C.UTF-8",
                               "NO_COLOR": "1", "CLAUDE_PROJECT_DIR": str(root),
                               "PYTHONDONTWRITEBYTECODE": "1"})
    assert done.returncode == 0, (argv, done.stdout[-2000:] + done.stderr[-2000:])
    return done.stdout


def _u3_migrate_problems(root, plant=None):
    """What the 7.0.0 migrate and a render dry run would do to an archive for the new
    document set: one line per header marker added, heading renamed, role block removed
    or digest moved on a document the migrate left as it was, and per document a render
    would change for a header or coverage block. `plant(root)`, when given, runs after
    the migrate: a test's planted fault."""
    before, digests = _u3_documents(root), _u3_digests(root)
    _u3_cli_in(root, "issue", "migrate", str(root / ".compass" / "work"))
    _u3_cli_in(root, "issue", "migrate", str(root / ".compass" / "work"), "--apply",
               "--i-have-a-copy")
    if plant is not None:
        plant(root)
    after, moved = _u3_documents(root), _u3_digests(root)
    problems = []
    for path, text in after.items():
        if "compass:render document-header" in text:
            problems.append("%s: a header marker was added" % path)
    for path in sorted(set(before) & set(after)):
        if _u3_heading_lines(before[path]) != _u3_heading_lines(after[path]):
            problems.append("%s: a heading was renamed" % path)
        if before[path].count(ROLE_HEADING) != after[path].count(ROLE_HEADING):
            problems.append("%s: a role block was removed" % path)
    for key, (path, digest) in moved.items():
        # The 7.0.0 migrate moves the digest of a document it gives a marker pair
        # (ADR-051 decision 16). A document it leaves byte for byte keeps its digest.
        if (key in digests and digests[key][1] != digest and path in before
                and before.get(path) == after.get(path)):
            problems.append("%s: the digest of %s moved" % (key[0], path))
    plan = json.loads(_u3_cli_in(root, "issue", "render", "--all", "--dry-run", "--json"))
    for one in plan.get("would_write") or []:
        hit = {"document-header", "coverage"} & set(one.get("kinds") or [])
        if hit:
            problems.append("%s: render would change its %s block" % (
                one["path"], ", ".join(sorted(hit))))
    return problems, before


#: A done issue's coverage block as the renderer wrote it before this change. The sample
#: holds no coverage block, so this issue is added to it: a render that changed an archived
#: coverage block would list it.
U3_DONE_SPEC = """\
# Spec - planted-done

## Coverage ledger

<!-- compass:render coverage -->
Coverage: 0 of 1 scenarios passed

| Scenario | Title | Tests | Red | Green | Acceptance | Result |
|---|---|---|---|---|---|---|
| S-1 | Export is fast | - | - | - | - | no test record |
<!-- /compass:render -->
"""


def _u3_plant_done_issue(root):
    slug, docs = "planted-done", "docs/compass/2026-10-12-planted-done"
    _u3_write(root, ".compass/work/%s/manifest.yml" % slug, yaml.safe_dump({
        "schema_version": "3.0", "issue": slug, "created": "2026-10-12", "status": "done",
        "close_reason": "completed",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "medium", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": "regular", "evidence": [],
        "scenarios": [{"id": "S-1", "title": "Export is fast", "intent": "INT-1"}],
        "artifacts": [{"id": "ART-ACCEPTANCE_CRITERIA", "kind": "acceptance-criteria",
                       "status": "approved", "depth": "thorough",
                       "path": docs + "/acceptance-criteria.md"}]}, sort_keys=False))
    _u3_write(root, docs + "/acceptance-criteria.md", U3_DONE_SPEC)


def test_dss_27_migrate_rewrites_nothing(tmp_path):
    from archive import archive_root, full_archive, sample_root

    root = _u3_copy_archive(sample_root(), tmp_path / "sample")
    _u3_plant_done_issue(root)
    problems, before = _u3_migrate_problems(root)
    assert problems == [], "\n".join(problems)
    # The sample holds what the new set changes: numbered headings and the role block.
    assert any(NUMBERED.match(line.lstrip("#").strip())
               for text in before.values() for line in _u3_heading_lines(text))
    assert any(ROLE_HEADING in text for text in before.values())
    # A migrate that renamed a numbered heading, dropped a role block and added a header
    # marker would be reported for each.
    docs = _u3_documents(root)
    numbered = next(p for p, t in before.items() if p in docs and any(
        NUMBERED.match(h.lstrip("#").strip()) for h in _u3_heading_lines(t)))
    with_role = next(p for p, t in before.items() if p in docs and ROLE_HEADING in t)

    def plant(planted):
        text = (planted / numbered).read_text(encoding="utf-8")
        heading = next(h for h in _u3_heading_lines(text)
                       if NUMBERED.match(h.lstrip("#").strip()))
        (planted / numbered).write_text(text.replace(heading, "## Renamed", 1),
                                        encoding="utf-8")
        role = (planted / with_role).read_text(encoding="utf-8")
        (planted / with_role).write_text(
            role.replace(ROLE_HEADING, "Gone", 1)
            + "\n<!-- compass:render document-header -->\n<!-- /compass:render -->\n",
            encoding="utf-8")

    found, _ = _u3_migrate_problems(_u3_copy_archive(sample_root(), tmp_path / "planted"),
                                    plant)
    assert "%s: a heading was renamed" % numbered in found, found
    assert "%s: a role block was removed" % with_role in found, found
    assert "%s: a header marker was added" % with_role in found, found
    if full_archive():
        root = _u3_copy_archive(archive_root(), tmp_path / "full")
        problems, _ = _u3_migrate_problems(root)
        assert problems == [], "\n".join(problems[:50])


#: A layer whose catalogue lists neither section, for spec and design alike.
U3_NO_SECTIONS = {"schema": 1, "owner": "jed72", "artifacts": {
    kind: {"set": {"sections": {"thorough": ["Summary"], "lightweight": ["Summary"]}}}
    for kind in ("acceptance-criteria", "technical-design")}}


def _u3_archive_shape(tmp_path, shape):
    """One of the four archive shapes of DSS-25: a regular issue with a spec lacking the
    section, an empty Data and interfaces section and a schema path in changed_files."""
    import artifact_status_support as sup

    layer = U3_NO_SECTIONS if shape == "third" else None
    if shape == "first":
        root = sup.project(tmp_path / shape, compass_yml={"schema": 1, "owner": "jed72"},
                           evaluate=False)
    else:
        root = _u3_project(tmp_path / shape, assessment={}, compass_yml=layer)
    register = shape != "fourth"
    _u3_write_spec(root, "# Spec\n\n## Summary\n\nNo section.\n", register=register)
    _u3_write_design(root, _u3_design(_u3_template_section(CONTRACTS_HEADING)),
                     register=register)
    if shape == "second":
        body = sup.manifest(root)
        body.update(status="done", close_reason="completed")
        sup.write_manifest(root, body)
    return root


U3_SHAPES = {
    "first": ("no-generation", "the issue predates the section checks"),
    "second": ("closed", "the issue is closed"),
    "third": ("no-section", 'the catalogue of generation 1 does not list'),
    "fourth": ("not-registered", "is registered with a path"),
}


def _u3_corpus_mismatches(impl, scratch):
    """The corpus cases of `impl` whose computed verdict differs from `expected.yml`."""
    import check_corpus_runner as runner

    computed = runner.computed_verdicts(impl, scratch)
    expected = {name: case["verdict"] for name, case in _u3_corpus(impl).items()}
    return sorted(name for name in expected if computed.get(name) != expected[name])


def test_dss_25_checks_decline_archive_shapes(tmp_path, monkeypatch):
    import types

    import artifact_status_support as sup
    from compass_pkg import section_checks

    for shape, (case, detail) in U3_SHAPES.items():
        root = _u3_archive_shape(tmp_path, shape)
        assert ("generation" in sup.manifest(root)) == (shape != "first"), shape
        code, rows = _u3_check(root)
        for check in SECTION_CHECKS:
            status, said = rows[check]
            assert status == "nothing-to-check", (shape, check, said)
            assert detail in said, (shape, check, said)
        assert code == _u3_exit_without(rows), shape
        # Each check's corpus holds the shape with the expected verdict nothing-to-check.
        for check in SECTION_CHECKS:
            assert _u3_corpus(check)[case]["verdict"] == "nothing-to-check", (check, case)
    for check in SECTION_CHECKS:
        assert _u3_corpus_mismatches(check, tmp_path / "corpus" / check) == []
    # A planted change that makes the checks judge the first shape, or the second, fails
    # each corpus on that shape.
    plants = {"no-generation": ("_generation", lambda task: 1),
              "closed": ("status_words", types.SimpleNamespace(is_closed=lambda task: False))}
    for case, (name, fake) in plants.items():
        with monkeypatch.context() as patch:
            patch.setattr(section_checks, name, fake)
            for check in SECTION_CHECKS:
                found = _u3_corpus_mismatches(check, tmp_path / ("planted-" + case) / check)
                assert found == [case], (check, found)

# --- U4: coverage Kind column and dependencies block ---

# --- U5: owning docs, public surface and this issue's checks ---
