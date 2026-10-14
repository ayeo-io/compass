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
    """The output of render, check, receipt, analyze and lint on a fixture issue."""
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

# --- U5: owning docs, public surface and this issue's checks ---
