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

HEADER_OPEN = "<!-- compass:render document-header -->"
BLOCK_CLOSE = "<!-- /compass:render -->"
#: The lines `template show` printed before the header block replaced them.
DROPPED_LINES = ("**Home:**", "**Traditional name:**", "**Depth:**")
HSLUG, HCREATED = "hdr", "2026-10-14"
HDOCS = f"docs/compass/{HCREATED}-{HSLUG}"
#: A fixed approval time on another day than the issue's created date.
APPROVED_AT = "2026-10-16T09:00:00Z"
_U2_GIT = ("GIT_AUTHOR_NAME", "t", "GIT_AUTHOR_EMAIL", "t@example.com",
           "GIT_COMMITTER_NAME", "t", "GIT_COMMITTER_EMAIL", "t@example.com")


def _u2_run(cwd, *argv):
    """`(code, stdout, stderr)` of one CLI call in the project `cwd`."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(cwd), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "NO_COLOR": "1", "COLUMNS": "200", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "CLAUDE_PROJECT_DIR": str(cwd)}
    env.update(dict(zip(_U2_GIT[::2], _U2_GIT[1::2])))
    run = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv], cwd=cwd,
                         capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
                         env=env)
    return run.returncode, run.stdout, run.stderr


def _u2_git_repo(root):
    root.mkdir(parents=True)
    for argv in (["init", "-q"], ["add", "-A"], ["commit", "-q", "--allow-empty", "-m", "base"]):
        subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *argv],
                       cwd=root, check=True, capture_output=True)
    return root


def _u2_show(tmp_path, kind, depth):
    scratch = tmp_path / "plain"
    scratch.mkdir(exist_ok=True)
    code, out, err = _u2_run(scratch, "issue", "template", "show", kind, "--depth", depth)
    assert code == 0, out + err
    return out


def _u2_head(text):
    """The lines from the first `# ` title to the first `## ` heading."""
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith("# "))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return lines[start:end]


def _u2_header_problems(name, text, entry):
    """Why `text` does not open with a title and one header block holding the document's
    header lines, with no header line outside it. With a catalogue `entry`, the block must
    also hold the entry's stage, owner and audience, and the audience must be printed once."""
    head = _u2_head(text)
    opens = [i for i, line in enumerate(head) if line == HEADER_OPEN]
    if len(opens) != 1:
        return ["%s: %d header block pairs after the title" % (name, len(opens))]
    start = opens[0]
    end = head.index(BLOCK_CLOSE, start)
    problems = []
    if any(line.strip() for line in head[1:start]):
        problems.append("%s: lines between the title and the header block" % name)
    stray = [line for line in head[:start] + head[end + 1:] if line.startswith("> **")]
    if stray:
        problems.append("%s: header lines outside the block: %r" % (name, stray))
    problems += ["%s: holds %s" % (name, marker) for marker in DROPPED_LINES if marker in text]
    if entry is not None:
        inside = head[start + 1:end]
        audience = " ".join(str(entry["audience"]).split())
        if "> **Stage:** %s · **Owner:** %s" % (entry["stage"], entry["owner"]) not in inside:
            problems.append("%s: the block lacks the stage and owner" % name)
        if "> **Audience:** " + audience not in inside:
            problems.append("%s: the block lacks the audience" % name)
        if text.count(audience) != 1:
            problems.append("%s: the audience is printed %d times" % (name, text.count(audience)))
    return problems


def _u2_block(path, kind):
    """The lines inside the first block of `kind` in the document at `path`."""
    from compass_pkg import rendered_blocks

    parsed = rendered_blocks.parse(Path(path).read_text(encoding="utf-8"), Path(path).name)
    block = next(b for b in parsed.blocks if b.kind == kind)
    return [line.rstrip("\r\n") for line in parsed.lines[block.start + 1:block.end]]


def _u2_manifest(root, slug):
    return yaml.safe_load((root / ".compass" / "work" / slug / "manifest.yml").read_text(
        encoding="utf-8"))


def _u2_write_manifest(root, slug, body):
    (root / ".compass" / "work" / slug / "manifest.yml").write_text(
        yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _u2_check_row(root, slug, name):
    code, out, err = _u2_run(root, "check", "--issue", slug, "--json")
    assert out.strip().startswith("{"), out + err
    return {c["name"]: c for c in json.loads(out)["checks"]}[name]


def test_dss_5_templates_open_with_header_block(tmp_path):
    from compass_pkg import rendered_blocks

    preset = _preset()
    assert "document-header" in rendered_blocks.KINDS and "header" in rendered_blocks.KINDS
    checked = []
    for kind, entry in sorted(preset.items()):
        path = TEMPLATES / f"{kind}.md"
        if kind == "verification-note" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert _u2_header_problems(f"templates/{kind}.md", text, None) == []
        for depth in sorted(entry["sections"]):
            out = _u2_show(tmp_path, kind, depth)
            assert _u2_header_problems(f"{kind} {depth}", out, entry) == [], out[:3000]
        checked.append(kind)
    assert len(checked) == 17, checked
    # The verification note keeps its one block and gains no header block.
    note = (TEMPLATES / "verification-note.md").read_text(encoding="utf-8")
    assert [b.kind for b in rendered_blocks.parse(note, "verification-note.md").blocks] == [
        "verification-note"]
    out = _u2_show(tmp_path, "verification-note", "lightweight")
    assert [b.kind for b in rendered_blocks.parse(out, "show").blocks] == ["verification-note"]
    assert not [marker for marker in DROPPED_LINES if marker in out], out
    # Planted faults: a header line outside the block, and a dropped line printed again.
    entry = preset["technical-design"]
    out = _u2_show(tmp_path, "technical-design", "thorough")
    stray = out.replace(HEADER_OPEN, "> **Audience:** x\n" + HEADER_OPEN, 1)
    assert any("outside the block" in p for p in _u2_header_problems("p", stray, entry))
    home = out.replace(BLOCK_CLOSE, BLOCK_CLOSE + "\n> **Home:** x", 1)
    assert any("**Home:**" in p for p in _u2_header_problems("p", home, entry))
    bare = out.replace(HEADER_OPEN + "\n", "", 1).replace(BLOCK_CLOSE + "\n", "", 1)
    assert _u2_header_problems("p", bare, entry) == ["p: 0 header block pairs after the title"]


def _u2_header_issue(tmp_path):
    """A full issue created 2026-10-14 whose intent and spec are registered with files and
    whose design is registered as a draft holding an empty header block."""
    root = _u2_git_repo(tmp_path / "repo")
    assert _u2_run(root, "init")[0] == 0
    work = root / ".compass" / "work" / HSLUG
    work.mkdir(parents=True)
    _u2_write_manifest(root, HSLUG, {
        "schema_version": "2.0", "issue": HSLUG, "created": HCREATED,
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped", "size": "large",
                       "goal": "delivery", "role": "engineer", "labels": []},
        "justifications": {"risk": "r", "familiarity": "f", "size": "s", "goal": "g",
                           "role": "o"},
        "evidence": []})
    (root / ".compass" / "current-task").write_text(HSLUG + "\n", encoding="utf-8")
    code, out, err = _u2_run(root, "approach", "evaluate", "--issue", HSLUG, "--write")
    assert code == 0, out + err
    assert _u2_manifest(root, HSLUG)["delivery_approach"] == "full"
    docs = root / HDOCS
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "intent.md").write_text("# Intent\n\nText.\n", encoding="utf-8")
    (docs / "acceptance-criteria.md").write_text("# Spec\n\nText.\n", encoding="utf-8")
    (docs / "technical-design.md").write_text(
        "# Plan - hdr\n\n%s\n%s\n\n## Approach\n\nText.\n" % (HEADER_OPEN, BLOCK_CLOSE),
        encoding="utf-8")
    for kind in ("intent", "acceptance-criteria", "technical-design"):
        code, out, err = _u2_run(root, "issue", "artifact", "set", kind, "--status", "draft",
                                 "--path", f"{HDOCS}/{kind}.md", "--issue", HSLUG)
        assert code == 0, out + err
    return root


def _u2_render(root, slug=HSLUG):
    code, out, err = _u2_run(root, "issue", "render", "--issue", slug)
    assert code == 0, out + err


def _u2_set_entry(root, kind, **fields):
    body = _u2_manifest(root, HSLUG)
    for entry in body["artifacts"]:
        if entry["kind"] == kind:
            entry.update(fields)
    _u2_write_manifest(root, HSLUG, body)


def test_dss_6_header_block_facts(tmp_path):
    root = _u2_header_issue(tmp_path)
    design = root / HDOCS / "technical-design.md"
    _u2_render(root)
    audience = " ".join(str(_preset()["technical-design"]["audience"]).split())
    draft = _u2_block(design, "document-header")
    assert draft == [
        "> **Issue:** hdr · **Approach:** full",
        "> **Stage:** plan · **Owner:** planner",
        "> **Status:** draft",
        "> **Date:** 2026-10-14",
        # intent is an assess document and the spec a define one: stage order, then name.
        "> **Reads:** [intent.md](intent.md), [acceptance-criteria.md](acceptance-criteria.md)",
        "> **Audience:** " + audience], draft
    code, out, err = _u2_run(root, "issue", "artifact", "set", "technical-design", "--status",
                             "approved", "--path", f"{HDOCS}/technical-design.md", "--issue",
                             HSLUG)
    assert code == 0, out + err
    _u2_set_entry(root, "technical-design", approved_at=APPROVED_AT)
    _u2_render(root)
    approved = _u2_block(design, "document-header")
    changed = [(a, b) for a, b in zip(draft, approved) if a != b]
    assert len(approved) == len(draft) and changed == [
        ("> **Status:** draft", "> **Status:** approved"),
        ("> **Date:** 2026-10-14", "> **Date:** 2026-10-16")], approved


def test_dss_7_header_block_stable(tmp_path):
    root = _u2_header_issue(tmp_path)
    design = root / HDOCS / "technical-design.md"
    preset = _preset()
    registered = {a["kind"]: a for a in _u2_manifest(root, HSLUG)["artifacts"]}
    # Documents of earlier stages that the issue does not register are on disk and unlisted.
    unregistered = [kind for kind, entry in preset.items()
                    if entry.get("stage") in ("assess", "define", "refine")
                    and kind not in registered]
    assert unregistered, registered
    for kind in unregistered:
        (root / HDOCS / preset[kind]["file"]).write_text("# %s\n" % kind, encoding="utf-8")
    assert registered["requirements-review"].get("path") is None
    code, out, err = _u2_run(root, "issue", "artifact", "set", "technical-design", "--status",
                             "approved", "--path", f"{HDOCS}/technical-design.md", "--issue",
                             HSLUG)
    assert code == 0, out + err
    _u2_set_entry(root, "technical-design", approved_at=APPROVED_AT)
    _u2_render(root)
    before = design.read_bytes()
    reads = next(line for line in _u2_block(design, "document-header")
                 if line.startswith("> **Reads:**"))
    assert "requirements-review" not in reads, reads
    assert not [k for k in unregistered if preset[k]["file"] in reads], reads
    # A later render with no record changed changes no byte.
    _u2_render(root)
    assert design.read_bytes() == before
    # Registering it again reads the same masked digest, so it stays approved.
    code, out, err = _u2_run(root, "issue", "artifact", "set", "technical-design", "--status",
                             "approved", "--path", f"{HDOCS}/technical-design.md", "--issue",
                             HSLUG)
    assert code == 0, out + err
    entry = {a["kind"]: a for a in _u2_manifest(root, HSLUG)["artifacts"]}["technical-design"]
    assert entry["status"] == "approved", entry
    # A listed document's file deleted, no record changed: the block keeps its bytes.
    (root / HDOCS / "intent.md").unlink()
    _u2_render(root)
    assert design.read_bytes() == before
    # A status changed in the manifest with no render is stale at verify.
    body = _u2_manifest(root, HSLUG)
    body["current_phase"] = "verify"
    for one in body["artifacts"]:
        if one["kind"] == "technical-design":
            one["status"] = "awaiting-approval"
    _u2_write_manifest(root, HSLUG, body)
    row = _u2_check_row(root, HSLUG, "rendered-blocks-current")
    assert row["status"] == "fail", row
    assert f"{HDOCS}/technical-design.md" in row["detail"] and "document-header" in row["detail"]


QF_LAYER = {"schema": 1, "rules": {"floors": {"set": {"rules": {"set": {"RP-PROJECT-QF": {
    "order": 99, "when": {"labels_any": ["docs-only"]}, "then": {"add_gate": "verify.analyze"},
    "rationale": "A docs-only fix still gets a consistency check."}}}}}}}
QF_REASONS = {"risk": ("trivial", "risk reason"), "familiarity": ("brownfield-mapped",
              "familiarity reason"), "size": ("atomic", "size reason"),
              "goal": ("delivery", "goal reason"), "role": ("engineer", "role reason")}
#: The record `quick-fix start` wrote before its sections were rendered blocks.
QF_ARCHIVED = """\
# Delivery approach - old-fix

**Approach:** quick fix

## Assessment

| Dimension | Value | Reason |
|---|---|---|
| Risk | trivial | risk reason |
| Familiarity | brownfield-mapped | familiarity reason |
| Size | atomic | size reason |
| Goal | delivery | goal reason |
| Role | engineer | role reason |

## Policy rules fired

- A docs-only fix still gets a consistency check (RP-PROJECT-QF, requirement)

## Intent

INT-1: Fix it.

## Scenario

TRC-001: A quick fix shows its reasons
"""


def _u2_quick_fix(root, slug):
    """Run `quick-fix start` for `slug` in `root` with a reason for each of the 5 dimensions
    and the label that fires the project's rule; the record's path."""
    argv = ["quick-fix", "start", slug, "--labels", "docs-only", "--intent", "Fix it.",
            "--scenario", "A quick fix shows its reasons", "--test", "tests/test_x.py::test_x"]
    for name, (value, reason) in QF_REASONS.items():
        argv += ["--" + name, f"{value} - {reason}"]
    code, out, err = _u2_run(root, *argv)
    assert code == 0 and "quick fix" in out, out + err
    return next((root / "docs" / "compass").glob(f"*-{slug}")) / "delivery-approach.md"


def _u2_quick_fix_project(tmp_path):
    root = _u2_git_repo(tmp_path / "qf")
    (root / ".compass").mkdir()
    (root / "compass.yml").write_text(yaml.safe_dump(QF_LAYER), encoding="utf-8")
    return root, _u2_quick_fix(root, "fix-it")


def _u2_archive(root):
    """A second quick fix whose record and manifest are as they were before the change: the
    hand-written tables and no `justifications` key."""
    record = _u2_quick_fix(root, "old-fix")
    record.write_text(QF_ARCHIVED, encoding="utf-8")
    body = _u2_manifest(root, "old-fix")
    body.pop("justifications")
    _u2_write_manifest(root, "old-fix", body)
    return record


def _u2_heading_of(text, index):
    """The `## ` heading above line `index`."""
    lines = text.splitlines()
    return next(line[3:] for line in reversed(lines[:index]) if line.startswith("## "))


def test_dss_28_quick_fix_record_blocks(tmp_path):
    from compass_pkg import quick_fix_cmd, record_triggers, rendered_blocks
    from test_rendered_blocks_check import test_dcj_75_trigger_table_complete

    root, record = _u2_quick_fix_project(tmp_path)
    text = record.read_text(encoding="utf-8")
    parsed = rendered_blocks.parse(text, record.name)
    assert [b.kind for b in parsed.blocks] == ["document-header", "assessment", "policy-rules"]
    assert [_u2_heading_of(text, b.start) for b in parsed.blocks[1:]] == [
        "Assessment", "Policy rules fired"]
    header = _u2_block(record, "document-header")
    assert "> **Issue:** fix-it · **Approach:** quick fix" in header, header
    assessment = _u2_block(record, "assessment")
    for name, (value, reason) in QF_REASONS.items():
        assert "| %s | %s | %s |" % (name.capitalize(), value, reason) in assessment, assessment
    rules = "\n".join(_u2_block(record, "policy-rules"))
    assert "RP-PROJECT-QF" in rules and "A docs-only fix" in rules, rules
    # The command writes the marker pairs and no block text of its own.
    written = quick_fix_cmd._delivery_approach_md(
        slug="fix-it", intent_text="Fix it.", scenario_id="TRC-001", scenario_text="S",
        ledger=[("plan", "collapsed", "no design decision on this size")], advice=())
    own = rendered_blocks.parse(written, "written.md")
    assert [b.kind for b in own.blocks] == ["document-header", "assessment", "policy-rules"]
    assert all(b.end == b.start + 1 for b in own.blocks), written
    assert "cmd_quick_fix_start" in record_triggers.RENDER_TRIGGERS
    assert "cmd_quick_fix_start" not in record_triggers.EXEMPT
    test_dcj_75_trigger_table_complete()
    # No hand-written assessment or rules table; the prose sections stay.
    masked = rendered_blocks.masked_text(text)
    assert "| Risk |" not in masked and "| Dimension |" not in masked
    assert "RP-PROJECT-QF" not in masked
    assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == [
        "Assessment", "Policy rules fired", "Intent", "Scenario", "De-scope ledger"]
    assert "INT-1: Fix it." in masked and "TRC-001: A quick fix shows its reasons" in masked
    _u2_render(root, "fix-it")
    assert record.read_text(encoding="utf-8") == text


def test_dss_33_receipt_reads_rendered_record(tmp_path):
    root, record = _u2_quick_fix_project(tmp_path)
    archived = _u2_archive(root)
    assert "compass:render" in record.read_text(encoding="utf-8")
    assert "compass:render" not in archived.read_text(encoding="utf-8")
    shown = {}
    for slug in ("fix-it", "old-fix"):
        code, out, err = _u2_run(root, "issue", "receipt", "--issue", slug)
        assert code == 0, out + err
        section = out.split("Assessment\n----------\n", 1)[1].split("\n\n", 1)[0]
        shown[slug] = {line.split()[0]: line for line in section.splitlines()}
        for name in ("risk", "familiarity", "size"):
            value, reason = QF_REASONS[name]
            assert value in shown[slug][name] and reason in shown[slug][name], (slug, section)
        goal = shown[slug]["goal"]
        assert "delivery (engineer)" in goal and "goal reason" in goal, (slug, section)
    # The rendered record's reasons come from the manifest, which holds the role's too; the
    # archived record's come from its table, which the receipt reads for the goal only.
    assert "role: role reason" in shown["fix-it"]["goal"]
    assert shown["old-fix"]["goal"].rstrip().endswith("goal reason")


def test_dss_29_quick_fix_record_stale_until_rendered(tmp_path):
    from compass_pkg import rendered_blocks

    root, record = _u2_quick_fix_project(tmp_path)
    archived = _u2_archive(root)
    rel = str(record.relative_to(root))
    body = _u2_manifest(root, "fix-it")
    body["current_phase"] = "verify"
    _u2_write_manifest(root, "fix-it", body)
    # The issue page shows the stage, so the new stage is rendered first.
    _u2_render(root, "fix-it")
    assert _u2_check_row(root, "fix-it", "rendered-blocks-current")["status"] == "pass"
    before = record.read_text(encoding="utf-8")
    body["assessment"]["risk"] = "contained"
    _u2_write_manifest(root, "fix-it", body)
    row = _u2_check_row(root, "fix-it", "rendered-blocks-current")
    assert row["status"] == "fail", row
    assert rel in row["detail"] and "assessment" in row["detail"], row["detail"]
    _u2_render(root, "fix-it")
    assert _u2_check_row(root, "fix-it", "rendered-blocks-current")["status"] == "pass"
    after = record.read_text(encoding="utf-8")
    assert "| Risk | contained | risk reason |" in _u2_block(record, "assessment")
    assert rendered_blocks.masked_text(after) == rendered_blocks.masked_text(before)
    # An archived record holds no markers, so render and migrate leave it as it is.
    old = archived.read_bytes()
    _u2_render(root, "old-fix")
    code, out, err = _u2_run(root, "issue", "migrate", str(root / ".compass" / "work"),
                             "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    assert archived.read_bytes() == old

# --- U3: section checks and the archive boundary ---

# --- U4: coverage Kind column and dependencies block ---

# --- U5: owning docs, public surface and this issue's checks ---
