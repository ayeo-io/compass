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
    "the outcome the intent names?",
    "- **Product marketer** - reads for *claims*: every line of launch copy must point at a "
    "scenario id here.",
    "- **Engineer** - reads for *tests*: scenarios are the acceptance suite and seed the TDD "
    "red→green cycle.",
    "- **QA** - reads for *coverage*: which scenarios are exercised, which edges are not.",
    "- **Designer** - UI behavior authored in `ui-contract.md` flows in here as scenarios.",
)
#: A leading section number: "1. ", "5a. " or "4b ".


def _cli(cwd, *argv):
    """`(code, stdout, stderr)` of one CLI call in `cwd`, with no issue selected."""
    run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), *argv], cwd=cwd, capture_output=True,
        text=True, timeout=180, stdin=subprocess.DEVNULL,
        env={"PATH": "/usr/bin:/bin", "HOME": str(cwd), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
             "NO_COLOR": "1", "PYTHONDONTWRITEBYTECODE": "1",
             "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    return run.returncode, run.stdout, run.stderr


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


#: The issue of the generation-1 fixtures, and the headings the shipped catalogue listed for the
#: design before they lost their numbers.


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
    """The output of `render`, `check`, `approach show` and `lint` on a fixture issue.
    `approach show` reads the assessment from the manifest, as the receipt did before
    9.0.0 removed it (ADR-091)."""
    import rendered_blocks_support as sup

    out = {}
    for name, argv in (("render", ("issue", "render", "--issue", sup.SLUG)),
                       ("check", ("check", "--issue", sup.SLUG, "--json")),
                       ("show", ("approach", "show", "--issue", sup.SLUG)),
                       ("lint", ("issue", "lint", "--issue", sup.SLUG))):
        code, text, err = sup.run(root, *argv)
        out[name] = (code, _normal(text + err, root))
    return out


def _differences(old, new):
    """The commands whose outputs differ between the two fixture runs."""
    return sorted(k for k in old if old[k] != new[k])


# --- U2: header block and quick-fix record ---

HEADER_OPEN = "<!-- compass:render document-header -->"
BLOCK_CLOSE = "<!-- /compass:render -->"
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


QF_LAYER = {"schema": 1, "rules": {"floors": {"set": {"rules": {"set": {"RP-PROJECT-QF": {
    "order": 99, "when": {"labels_any": ["docs-only"]}, "then": {"add_gate": "verify.architecture"},
    "rationale": "A docs-only fix still gets an architecture check."}}}}}}}
QF_REASONS = {"risk": ("trivial", "risk reason"), "familiarity": ("brownfield-mapped",
              "familiarity reason"), "size": ("atomic", "size reason"),
              "goal": ("delivery", "goal reason")}
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

- A docs-only fix still gets an architecture check (RP-PROJECT-QF, requirement)

## Intent

INT-1: Fix it.

## Scenario

TRC-001: A quick fix shows its reasons
"""


def _u2_quick_fix(root, slug):
    """Run `quick-fix start` for `slug` in `root` with a reason for each of the 4 dimensions
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
        # The fixture writes a spec at the fixed path, which is read whenever it
        # exists (ADR-091); this case is the issue without one.
        (root / sup.DOCS / "acceptance-criteria.md").unlink()
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


U3_DECLARED = {
    "field table": ("| Name | Type | Required | Meaning | Written by | Read by |\n"
                    "|---|---|---|---|---|---|\n"
                    "| `generation` | integer | no | the stored configuration | assess | check |\n"),
    "erDiagram": ("```mermaid\nerDiagram\n    ISSUE ||--o{ GENERATION : stores\n```\n"),
    "contract table": ("| Inputs | Outputs | Exit codes | Errors |\n|---|---|---|---|\n"
                       "| `compass check --json` | one row per check | 0 or 1 | none new |\n"),
}


def _u3_evaluate(root, reason):
    import artifact_status_support as sup

    code, out, err = sup.run(root, "approach", "evaluate", "--issue", sup.SLUG, "--write",
                             "--reason", reason)
    assert code == 0, out + err


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


def _u3_cli_in(root, *argv, codes=(0,)):
    done = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv], cwd=root,
                          capture_output=True, text=True, timeout=1800,
                          env={"PATH": "/usr/bin:/bin", "HOME": str(root), "LANG": "C.UTF-8",
                               "NO_COLOR": "1", "CLAUDE_PROJECT_DIR": str(root),
                               "PYTHONDONTWRITEBYTECODE": "1"})
    assert done.returncode in codes, (argv, done.stdout[-2000:] + done.stderr[-2000:])
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
    # A dry run exits 1 when an issue folder cannot be rendered, such as one with no
    # manifest (the maintainer's archive holds 4); its plan is still printed.
    plan = json.loads(_u3_cli_in(root, "issue", "render", "--all", "--dry-run", "--json",
                                 codes=(0, 1)))
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
    "third": ("no-section", 'the catalog of generation 1 does not list'),
    "fourth": ("not-registered", "is registered with a path"),
}


def _u3_corpus_mismatches(impl, scratch):
    """The corpus cases of `impl` whose computed verdict differs from `expected.yml`."""
    import check_corpus_runner as runner

    computed = runner.computed_verdicts(impl, scratch)
    expected = {name: case["verdict"] for name, case in _u3_corpus(impl).items()}
    return sorted(name for name in expected if computed.get(name) != expected[name])


def test_dss_34_mutation_job_timeout():
    # The two section checks join the mutation proofs, and the job ran past 5 minutes
    # in CI with them, so it needs a longer limit.
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "compass.yml")
                              .read_text(encoding="utf-8"))
    assert workflow["jobs"]["check-mutation"]["timeout-minutes"] >= 15

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


def _u4_check_rows(root, slug=None):
    """`{check name: row}` of `compass check --json` on the fixture issue."""
    import rendered_blocks_support as sup

    code, out, err = sup.run(root, "check", "--issue", slug or sup.SLUG, "--json")
    assert out.strip().startswith("{"), out + err
    return code, {c["name"]: c for c in json.loads(out)["checks"]}


def _u4_statuses(rows):
    return {name: row.get("status") for name, row in rows.items()}


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


# --- U5: owning docs, public surface and this issue's checks ---

U5_PRESET = ROOT / "governance" / "presets" / "default"
U5_CHECKS = ("nfr-rows-resolved", "contracts-declared")
U5_SECTIONS = ("Non-functional requirements", "Data and interfaces", "Verification plan",
               "Risks and dependencies")
U5_DOCS = ("docs/artifact-catalog.md", "docs/rendered-blocks.md", "docs/upgrade-7-0-0.md")
#: What each of the three docs must name: the four sections, the two checks, the two
#: new blocks and the Kind column.
U5_NAMES = U5_SECTIONS + U5_CHECKS + ("document-header", "dependencies", "Kind")
U5_ISSUE = ROOT / ".compass" / "work" / "document-set-sections"


def _u5_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _u5_code(path):
    """The lines of a preset file that are not comments."""
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


def _u5_derive(tmp_path):
    """`(glossary, catalogue document)` of a fresh generation in a copy of the files the
    generator reads."""
    mini = tmp_path / "mini"
    for rel in ("governance/terminology.yml", "governance/presets/default/artifacts.yml",
                "docs/glossary.md", "docs/artifact-catalog.md"):
        target = mini / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    (mini / ".compass").mkdir()
    out = tmp_path / "fresh"
    code, text, err = _cli(mini, "_derive-glossary", "--internal", "--root", str(mini),
                           "--out", str(out / "glossary.md"),
                           "--catalogue-out", str(out / "artifact-catalog.md"))
    assert code == 0, text + err
    return ((out / "glossary.md").read_text(encoding="utf-8"),
            (out / "artifact-catalog.md").read_text(encoding="utf-8"))


def test_dss_32_own_issue_passes_both_checks():
    # The issue's work folder is untracked, so CI never has it, and both checks decline on
    # a closed issue. The lasting proof of this scenario is the recorded command output.
    if not (U5_ISSUE / "manifest.yml").is_file():
        pytest.skip("the issue's manifest is untracked and absent from this checkout")
    manifest = _u5_yaml(U5_ISSUE / "manifest.yml")
    from compass_pkg import status_words
    if status_words.is_closed(manifest):
        pytest.skip("the issue is closed, and both section checks decline on a closed issue")
    generation = manifest.get("generation")
    assert isinstance(generation, int) and generation >= 2, generation
    assert manifest["delivery_approach"] == "full"
    # approach evaluate logs a reassessment only when the approach changes, and this
    # one did not, so the stored generation's completion record is the proof of the move.
    complete = _u5_yaml(U5_ISSUE / "generations" / str(generation) / "complete")
    for name in ("resolved.yml", "provenance.yml", "versions.yml", "records.yml"):
        assert name in complete["files"], (name, complete)
    resolved = _u5_yaml(U5_ISSUE / "generations" / str(generation) / "resolved.yml")
    for name in U5_CHECKS:
        assert name in resolved["checks"], name
    listed = {heading for entry in resolved["artifacts"].values()
              for heading in (entry.get("sections") or {}).get("thorough") or []}
    for heading in U5_SECTIONS:
        assert heading in listed, heading
    # Every check run rewrites the generation's results.yml with a timestamp, and no
    # test may change the archive, so the file is put back as it was.
    results = U5_ISSUE / "generations" / str(generation) / "results.yml"
    before = results.read_bytes() if results.is_file() else None
    try:
        code, out, err = _cli(ROOT, "check", "--issue", "document-set-sections", "--json")
    finally:
        if before is None:
            results.unlink(missing_ok=True)
        else:
            results.write_bytes(before)
    rows = {row["name"]: row for row in json.loads(out)["checks"]}
    for name in U5_CHECKS:
        assert rows[name]["status"] == "pass", rows[name]
        assert "nothing to check" not in rows[name]["detail"], rows[name]
