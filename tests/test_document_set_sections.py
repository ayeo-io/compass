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
    """The output of render, check, receipt, `analyze` and lint on a fixture issue."""
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

# --- U4: coverage Kind column and dependencies block ---

U4_SCENARIOS = ("A1", "A2", "B1", "B2", "C1")

_U4_SPEC = """\
# Spec

## Scenario group A - Export

### Scenario: Export one
<!-- traceability id: A1 · serves: INT-1 -->

### Scenario: Export two
<!-- traceability id: A2 · serves: INT-1 -->

## Scenario group B - Import

### Scenario: Import one
<!-- traceability id: B1 · serves: INT-1 -->

### Scenario: Import two
<!-- traceability id: B2 · serves: INT-1 -->

## Failure-mode scenarios

### Scenario: Import a broken file
<!-- traceability id: C1 · serves: INT-1 -->

## Coverage ledger

"""

_U4_PLAN_ROWS = (("A", "unit"), ("B", "integration"), ("B2", "manual"))


def _u4_design(rows, heading="Verification plan"):
    table = "".join("| %s | %s | a scratch project |\n" % row for row in rows)
    return ("# Plan\n\n## Approach\n\nOne writer.\n\n## %s\n\n"
            "| Group | Kind | Fixture or environment |\n|---|---|---|\n%s\n"
            "## Gate\n\nNone.\n" % (heading, table))


def _u4_issue(tmp_path, rows=_U4_PLAN_ROWS, heading="Verification plan"):
    """A rendered-blocks fixture issue whose spec has groups A and B and one scenario in no
    group, and whose design holds a Verification plan with `rows`."""
    import rendered_blocks_support as sup

    root = sup.rich_issue(tmp_path)
    body = sup.manifest(root)
    body["scenarios"] = [{"id": sid, "title": "Scenario " + sid, "intent": "INT-1",
                          "tests": ["tests/test_a.py::test_%s" % sid.lower()]}
                         for sid in U4_SCENARIOS]
    sup.base.write_manifest(root, body)
    sup.write_doc(root, "acceptance-criteria", _U4_SPEC + sup.block("coverage"))
    if rows is not None:
        sup.write_doc(root, "technical-design", _u4_design(rows, heading))
    return root


def _u4_block(text, kind):
    """The interior of the first `kind` block of `text`."""
    from compass_pkg import rendered_blocks

    parsed = rendered_blocks.parse(text, "doc.md")
    found = next(b for b in parsed.blocks if b.kind == kind)
    return "".join(parsed.lines[found.start + 1:found.end])


def _u4_coverage(root):
    """`(header cells, {scenario: cells})` of the spec's coverage table."""
    import rendered_blocks_support as sup

    block = _u4_block(sup.doc_path(root, "acceptance-criteria").read_text(encoding="utf-8"),
                      "coverage")
    rows = [[c.strip() for c in line.strip().strip("|").split(" | ")]
            for line in block.splitlines() if line.startswith("| ")]
    return rows[0], {r[0]: r for r in rows[1:]}


def _u4_kinds(root):
    header, rows = _u4_coverage(root)
    assert "Kind" in header, header
    at = header.index("Kind")
    return {sid: cells[at] for sid, cells in rows.items()}


def test_dss_18_the_coverage_block_shows_each_scenarios_planned_kind(tmp_path):
    import rendered_blocks_support as sup

    root = _u4_issue(tmp_path / "planned")
    code, out, err = sup.render(root)
    assert code == 0, out + err
    header, _rows = _u4_coverage(root)
    assert header == ["Scenario", "Title", "Kind", "Tests", "Red", "Green", "Acceptance",
                      "Result"], header
    # An id row wins over its group row; a scenario in no row reads "not planned".
    assert _u4_kinds(root) == {"A1": "unit", "A2": "unit", "B1": "integration",
                               "B2": "manual", "C1": "not planned"}
    code, clean_lint, err = sup.run(root, "issue", "lint", "--issue", sup.SLUG)
    assert "smoke" not in clean_lint and "Verification plan" not in clean_lint, clean_lint
    lint_code = code

    # A kind that is not one of the five reads "unknown (<word>)", and lint reports the row
    # without changing its exit code.
    smoky = _u4_issue(tmp_path / "smoke", rows=_U4_PLAN_ROWS + (("C1", "smoke"),))
    code, out, err = sup.render(smoky)
    assert code == 0, out + err
    assert _u4_kinds(smoky)["C1"] == "unknown (smoke)"
    code, lint, err = sup.run(smoky, "issue", "lint", "--issue", sup.SLUG)
    assert code == lint_code, lint + err
    note = [line for line in lint.splitlines() if "smoke" in line]
    assert len(note) == 1 and "Verification plan" in note[0] and "C1" in note[0], lint


def _u4_check_rows(root, slug=None):
    """`{check name: row}` of `compass check --json` on the fixture issue."""
    import rendered_blocks_support as sup

    code, out, err = sup.run(root, "check", "--issue", slug or sup.SLUG, "--json")
    assert out.strip().startswith("{"), out + err
    return code, {c["name"]: c for c in json.loads(out)["checks"]}


def _u4_statuses(rows):
    return {name: row.get("status") for name, row in rows.items()}


def test_dss_19_compass_check_reads_the_plan_only_through_the_coverage_block(tmp_path):
    import rendered_blocks_support as sup

    root = _u4_issue(tmp_path)
    sup.edit(root, current_phase="verify")
    code, out, err = sup.render(root)
    assert code == 0, out + err
    _code, before = _u4_check_rows(root)
    assert before["rendered-blocks-current"]["status"] == "pass", before["rendered-blocks-current"]

    # The row "B" changes to acceptance and no render follows.
    edited = [("A", "unit"), ("B", "acceptance"), ("B2", "manual")]
    sup.doc_path(root, "technical-design").write_text(_u4_design(edited), encoding="utf-8")
    _code, stale = _u4_check_rows(root)
    row = stale["rendered-blocks-current"]
    assert row["status"] == "fail", row
    assert "coverage" in row["detail"] and "acceptance-criteria.md" in row["detail"], row
    others = {k: v for k, v in _u4_statuses(stale).items() if k != "rendered-blocks-current"}
    assert others == {k: v for k, v in _u4_statuses(before).items()
                      if k != "rendered-blocks-current"}

    code, out, err = sup.render(root)
    assert code == 0, out + err
    assert _u4_kinds(root)["B1"] == "acceptance"
    _code, after = _u4_check_rows(root)
    assert _u4_statuses(after) == _u4_statuses(before)


#: A design with no Verification plan heading: the words appear only in prose, in a comment
#: and in a code fence, none of which is a heading.
_U4_NO_PLAN_DESIGN = """\
# Plan

## Approach

The Verification plan is not written for this issue.

<!--
## Verification plan
-->

```markdown
## Verification plan

| Group | Kind | Fixture or environment |
|---|---|---|
| A | unit | a scratch project |
```

### Verification plan

| Group | Kind | Fixture or environment |
|---|---|---|
| A | unit | a level-three heading is not the section |

## Gate

None.
"""


def _u4_old_coverage(root):
    """The coverage block exactly as the renderer wrote it before the Kind column existed,
    for the DSS-20 fixture's records."""
    import rendered_blocks_support as sup

    rows = []
    for sid in U4_SCENARIOS:
        red = "`red-%s.json`" % sid if sid == "A1" else "-"
        green = "`green-%s.json`" % sid if sid == "A1" else "-"
        rows.append("| %s | Scenario %s | `tests/test_a.py::test_%s` | %s | %s | - | %s |" % (
            sid, sid, sid.lower(), red, green, "passed" if sid == "A1" else "no test record"))
    modes = sup.manifest(root)["failure_modes_descoped"]
    return "\n".join(
        ["Coverage: 1 of %d scenarios passed" % len(U4_SCENARIOS), "",
         "| Scenario | Title | Tests | Red | Green | Acceptance | Result |",
         "|---|---|---|---|---|---|---|"] + rows
        + ["", "De-scoped failure modes:"]
        + ["- %s - %s" % (m["mode"], m["reason"]) for m in modes]) + "\n"


def _u4_coverage_blocks(root):
    """`{(document, n): interior}` for every coverage block under `docs/compass/`."""
    from compass_pkg import rendered_blocks

    found = {}
    for path in sorted((Path(root) / "docs" / "compass").rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "compass:render coverage" not in text:
            continue
        parsed = rendered_blocks.parse(text, path.name)
        blocks = [b for b in parsed.blocks if b.kind == "coverage"]
        for n, b in enumerate(blocks):
            found[(str(path.relative_to(root)), n)] = "".join(parsed.lines[b.start + 1:b.end])
    return found


def _u4_archive_copy(source, target):
    """A copy of the project at `source` holding what `render --all` reads, with no skip
    state, so every issue is rendered again."""
    target.mkdir(parents=True)
    for rel in (".compass/work", "docs/compass", "governance", "architecture"):
        if (Path(source) / rel).is_dir():
            shutil.copytree(Path(source) / rel, target / rel, symlinks=True)
    for rel in ("compass.yml",):
        if (Path(source) / rel).is_file():
            shutil.copy2(Path(source) / rel, target / rel)
    return target


def _u4_render_all_keeps_coverage(source, scratch):
    """`(blocks before, blocks after, outcome line)` of `compass issue render --all` on a copy
    of the project at `source`."""
    import rendered_blocks_support as sup

    copy = _u4_archive_copy(source, scratch)
    before = _u4_coverage_blocks(copy)
    done = subprocess.run([sys.executable, str(sup.CLI), "issue", "render", "--all"], cwd=copy,
                          env=sup.env(copy), capture_output=True, text=True, timeout=1800,
                          stdin=subprocess.DEVNULL)
    outcome = (done.stdout + done.stderr).strip().splitlines()
    return before, _u4_coverage_blocks(copy), outcome[0] if outcome else ""


def test_dss_20_a_design_with_no_verification_plan_keeps_the_old_coverage_block(tmp_path):
    import archive
    import rendered_blocks_support as sup

    root = _u4_issue(tmp_path / "no-plan", rows=None)
    sup.write_doc(root, "technical-design", _U4_NO_PLAN_DESIGN)
    sup.add_records(root, **{"red-A1": "A1", "green-A1": "A1"})
    sup.edit(root, current_phase="verify")
    code, out, err = sup.render(root)
    assert code == 0, out + err
    spec = sup.doc_path(root, "acceptance-criteria")
    assert _u4_block(spec.read_text(encoding="utf-8"), "coverage") == _u4_old_coverage(root)
    first = spec.read_bytes()
    code, out, err = sup.render(root)
    assert code == 0, out + err
    assert spec.read_bytes() == first
    _code, rows = _u4_check_rows(root)
    assert rows["rendered-blocks-current"]["status"] == "pass", rows["rendered-blocks-current"]

    # The migrated archive sample (or, with COMPASS_FULL_ARCHIVE=1, this checkout's archive):
    # render --all changes no byte of any existing coverage block.
    before, after, outcome = _u4_render_all_keeps_coverage(
        archive.checkable_root(), tmp_path / "archive")
    assert re.search(r"render --all: [1-9]\d* issue\(s\) rendered", outcome), outcome
    changed = sorted(k for k in before if after.get(k) != before[k])
    assert not changed, "%d of %d coverage blocks changed: %s" % (
        len(changed), len(before), changed[:5])


_U4_STAGES = {"assess": "thorough", "define": "thorough", "refine": "skipped",
              "plan": "thorough", "breakdown": "skipped", "implement": "thorough",
              "verify": "thorough", "ship": "thorough"}

#: The waiting issue's `depends_on`: "b" is done, "c" is at plan, "d" has no manifest and
#: "e" has a manifest that cannot be read.
_U4_DEPENDS = [{"issue": "b", "reason": "needs the parse cache", "until": "done"},
               {"issue": "c", "reason": "shares the hook", "until": "done"},
               {"issue": "d", "reason": "reads its schema", "until": "done"},
               {"issue": "e", "reason": "reuses its fixture", "until": "done"}]


def _u4_other_issue(root, slug, close=None):
    """Issue `slug` at plan, or closed with `close`, in the fixture project."""
    import rendered_blocks_support as sup

    task_dir = Path(root) / ".compass" / "work" / slug
    (task_dir / "evidence").mkdir(parents=True, exist_ok=True)
    body = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "small", "goal": "delivery", "role": "engineer"},
            "delivery_approach": "regular", "stages": dict(_U4_STAGES),
            "gates": [{"id": "verify.correctness", "status": "pending", "evidence": []}],
            "scenarios": [{"id": slug.upper() + "-1", "title": slug + " works",
                           "intent": "INT-1", "tests": ["tests/test_x.py::test_it"]}],
            "artifacts": [], "evidence": []}
    if close:
        body.update(status="done", close_reason=close)
    sup.base.write_manifest(root, body, slug=slug)
    return task_dir


def _u4_dependencies_issue(tmp_path, depends=_U4_DEPENDS):
    """A fixture project whose issue (the waiting issue "a" of DSS-22) has a design holding
    a dependencies block, and `depends` as its `depends_on`."""
    import rendered_blocks_support as sup

    root = sup.project(tmp_path)
    _u4_other_issue(root, "b", close="completed")
    _u4_other_issue(root, "c")
    broken = Path(root) / ".compass" / "work" / "e"
    broken.mkdir(parents=True)
    (broken / "manifest.yml").write_text("issue: e\nstatus: [unclosed\n", encoding="utf-8")
    sup.write_doc(root, "technical-design", "# Plan\n\n## Risks and dependencies\n\n"
                  "Dependencies on other issues:\n\n" + sup.block("dependencies"))
    if depends is not None:
        sup.edit(root, depends_on=depends)
    return root


def _u4_dependency_lines(root):
    import rendered_blocks_support as sup

    text = sup.doc_path(root, "technical-design").read_text(encoding="utf-8")
    return _u4_block(text, "dependencies").splitlines()


def _u4_board_words(root):
    """`{dependency: word}` as the board panel words each entry of the waiting issue, from
    `compass flow --json` through the panel's own function."""
    import rendered_blocks_support as sup
    from compass_pkg import board_page

    code, out, err = sup.run(root, "flow", "--json")
    assert code == 0, out + err
    board = json.loads(out)["board"]
    rows = {r["slug"]: r for lane in board.values() for r in lane}
    unreadable = {r["slug"] for r in board.get("unreadable") or []}
    assert "e" in unreadable, board.get("unreadable")
    return {d["issue"]: board_page._dependency_word(d, unreadable)
            for d in rows[sup.SLUG]["depends_on"]}, rows


def test_dss_22_the_dependencies_block_lists_depends_on_in_the_boards_words(tmp_path):
    import rendered_blocks_support as sup

    root = _u4_dependencies_issue(tmp_path / "waits")
    code, out, err = sup.render(root)
    assert code == 0, out + err
    lines = _u4_dependency_lines(root)
    assert lines == ["- b - needs the parse cache - until done - met",
                     "- c - shares the hook - until done - waiting",
                     "- d - reads its schema - until done - not found",
                     "- e - reuses its fixture - until done - unreadable"], lines
    # Each word is the word the board panel shows for that entry.
    words, rows = _u4_board_words(root)
    assert rows["c"]["stage"] == "plan", rows["c"]
    assert {line.split(" - ")[0][2:]: line.rsplit(" - ", 1)[1] for line in lines} == words

    # An issue with no depends_on reads "None".
    none = _u4_dependencies_issue(tmp_path / "free", depends=None)
    code, out, err = sup.render(none)
    assert code == 0, out + err
    assert _u4_dependency_lines(none) == ["None"]


def test_dss_23_a_dependencys_change_makes_the_block_stale_only_as_an_advisory(tmp_path):
    import rendered_blocks_support as sup

    root = _u4_dependencies_issue(tmp_path)
    sup.edit(root, current_phase="verify")
    code, out, err = sup.render(root)
    assert code == 0, out + err
    clean_code, before = _u4_check_rows(root)
    assert before["rendered-blocks-current"]["status"] == "pass", before["rendered-blocks-current"]

    # Issue "c" reaches done and "a" is not rendered.
    _u4_other_issue(root, "c", close="completed")
    stale_code, stale = _u4_check_rows(root)
    row = stale["rendered-blocks-current"]
    assert row["status"] == "advisory", row
    assert "dependencies" in row["detail"] and "technical-design.md" in row["detail"], row
    # The advisory does not fail the check: the exit code and every other verdict stand.
    assert stale_code == clean_code
    assert {k: v for k, v in _u4_statuses(stale).items() if k != "rendered-blocks-current"} \
        == {k: v for k, v in _u4_statuses(before).items() if k != "rendered-blocks-current"}

    # depends remove and depends add re-render the block.
    code, out, err = sup.run(root, "issue", "depends", "remove", "d", "--issue", sup.SLUG)
    assert code == 0, out + err
    assert _u4_dependency_lines(root) == [
        "- b - needs the parse cache - until done - met",
        "- c - shares the hook - until done - met",
        "- e - reuses its fixture - until done - unreadable"]
    code, out, err = sup.run(root, "issue", "depends", "add", "b2", "--reason", "shares the cache",
                             "--until", "plan", "--issue", sup.SLUG)
    assert code == 0, out + err
    assert _u4_dependency_lines(root)[-1] == "- b2 - shares the cache - until plan - not found"
    _code, after = _u4_check_rows(root)
    assert after["rendered-blocks-current"]["status"] == "pass", after["rendered-blocks-current"]

# --- U5: owning docs, public surface and this issue's checks ---
