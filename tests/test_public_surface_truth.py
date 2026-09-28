"""The surface a newcomer reads first says what is true.

Issue: public-docs-tell-the-truth. Scenarios `TRC-A1` to `TRC-A6`, `TRC-D2`,
`TRC-E1`, `TRC-F1`, `TRC-F2`.

An outside engineering review of 3.2.0 opened the README and found `issk`,
opened the safety contract and found it titled for version 1.0, and opened the
portability guide and found filenames that do not exist. Each of these checks
is one of those defects turned into something that fails.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Live prose surfaces. Decision records are excluded on purpose: they record
#: what was decided at the time, and rewriting one would falsify the account.
PROSE_ROOTS = ("approaches", "skills", "agents", "commands", "templates",
               "docs", "governance", "architecture")
EXEMPT = ("architecture/decisions/", "templates/architecture/decisions/",
          "docs/compass/",
          "docs/proposals/", "docs/analysis/", "docs/system-spec.md")


def _prose_files() -> list[Path]:
    files = [p for r in PROSE_ROOTS for p in (REPO_ROOT / r).rglob("*.md")]
    files += [REPO_ROOT / n for n in ("README.md", "CLAUDE.md", "AGENTS.md")]
    return [p for p in files
            if p.is_file() and not str(p.relative_to(REPO_ROOT)).startswith(EXEMPT)]


# --- `TRC-A1` -----------------------------------------------------------------

def test_a1_no_file_says_issk():
    """`TRC-A1` - a rename search-and-replaced "issue" into "issk".

    It reached the README twice, the five-minute guide, and the architecture
    context file. It is the first word a newcomer reads about the framework's
    central object.
    """
    hits = [f"{p.relative_to(REPO_ROOT)}:{n}"
            for p in _prose_files()
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "issk" in line]
    assert not hits, "the word 'issk' survives in:\n  " + "\n  ".join(hits)


# --- `TRC-A2` -----------------------------------------------------------------

def test_a2_contract_title_carries_no_version():
    """`TRC-A2` - a title carrying a version has to move at every major.

    The version moves into the body, where a check can compare it to VERSION.
    """
    title = (REPO_ROOT / "docs" / "safety-contract.md").read_text(
        encoding="utf-8").splitlines()[0]
    assert not re.search(r"\b\d+\.\d+", title), (
        f"the safety contract's title still carries a version: {title!r}. A "
        f"title that must move at every major is a scheduled defect")


def test_a2b_contract_states_the_version_it_applies_from():
    body = (REPO_ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8")
    m = re.search(r"applies from (?:Compass |version )?[`]?(\d+)\.(\d+)\.(\d+)",
                  body, re.I)
    assert m, ("the contract does not state the version it applies from. The "
               "title no longer carries one, so the body must")
    stated = tuple(int(x) for x in m.groups())
    current = tuple(int(x) for x in
                    (REPO_ROOT / "VERSION").read_text().strip().split("."))
    assert stated <= current, (
        f"the contract claims to apply from {stated}, which is later than "
        f"VERSION {current} - it is describing a release that does not exist")


# --- `TRC-A3` -----------------------------------------------------------------

def test_a3_guide_does_not_deny_the_marketplace():
    """`TRC-A3` - the guide denied a channel the project publishes on."""
    body = " ".join((REPO_ROOT / "docs" / "security.md").read_text(
        encoding="utf-8").replace("`", "").split())
    assert "no Compass plugin marketplace" not in body, (
        "docs/security.md still says there is no Compass plugin marketplace. "
        "The README's primary install path is the marketplace and the manifest "
        "ships in this repository")
    assert "marketplace" in body.lower(), (
        "the supply-chain caution the denial was carrying has gone with it - "
        "the guide should still tell a reader to treat a marketplace install "
        "with the same care")


# --- `TRC-A4` -----------------------------------------------------------------

def test_a4_named_files_resolve():
    """`TRC-A4` - docs/portability.md listed approach files that do not exist.

    Scoped to filenames a document presents as shipping with the framework:
    a backticked or bare path ending in .md under a known framework directory.
    """
    # The lookbehind is what keeps this about OUR files. A path with a segment
    # in front of it - `obra/superpowers/skills/...`, or the tail of a URL -
    # names another project's file, and asserting it exists here would be
    # wrong. Without it, a document that compares Compass to another framework
    # cannot cite that framework's files at all. Scoping by a prose caveat
    # instead was considered and rejected: a caveat is the thing a reader
    # skims past, and the guard cannot read it.
    named = re.compile(r"(?<![\w/.-])((?:approaches|governance|templates|skills"
                       r"|agents|commands|docs)/[\w./-]+\.md)\b")
    missing = []
    for p in _prose_files():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for path in named.findall(line):
                if not (REPO_ROOT / path).exists():
                    missing.append(f"{p.relative_to(REPO_ROOT)}:{n}: {path}")
    assert not missing, (
        "documents name files that do not exist:\n  " + "\n  ".join(missing))


# --- `TRC-A5` -----------------------------------------------------------------

def test_a5_architecture_context_uses_current_stage_names():
    """`TRC-A5` - the context file describes the system as it is now.

    `architecture/decisions/` is exempt as history. `system-context.md` is not
    a decision record; it says what is true today, in current stage names
    only.
    """
    body = (REPO_ROOT / "architecture" / "system-context.md").read_text(encoding="utf-8")
    for retired in ("Frame", "Specify", "Clarify", "Distribute", "Land"):
        assert not re.search(rf"\bwritten by {retired}\b", body), (
            f"architecture/system-context.md still says the manifest is written "
            f"by {retired}, a stage that no longer exists")


# --- `TRC-A6` -----------------------------------------------------------------

RETIRED_STAGES = ("Frame", "Specify", "Clarify", "Distribute", "Land")


def _printed_strings() -> list[tuple[Path, int, str]]:
    """Every string literal in the CLI that is not a docstring.

    Parsed rather than grepped. Comments and docstrings are position-exempt
    (PX-1) because the parser discards them - there is no path from a comment
    to a user, and a comment explaining an old name is the record. A string
    literal is the opposite: it is what the user reads.
    """
    out = []
    files = list((REPO_ROOT / "cli" / "compass_pkg").glob("*.py"))
    files.append(REPO_ROOT / "cli" / "compass")
    for p in files:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover
            continue
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
                if ast.get_docstring(node, clean=False):
                    docstrings.add(id(node.body[0].value))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in docstrings):
                out.append((p, node.lineno, node.value))
    return out


def test_a6_printed_strings_name_no_retired_stage():
    """`TRC-A6` - a message must not tell a user to run a stage that is gone.

    Worse than the documentation drift. A reader can put a document down; a
    user meeting "has Frame run?" is being told to run a stage that does not
    exist, while already stuck.
    """
    strings = _printed_strings()
    assert len(strings) > 200, (
        f"only {len(strings)} string literals parsed out of the CLI - the "
        f"parse has broken and this check would pass without inspecting "
        f"anything")

    hits = []
    for p, lineno, value in strings:
        for stage in RETIRED_STAGES:
            if re.search(rf"\b{stage}\b", value):
                hits.append(f"{p.relative_to(REPO_ROOT)}:{lineno}: "
                            f"{stage!r} in {value.strip()[:60]!r}")
    assert not hits, (
        f"{len(hits)} retired stage name(s) in strings the CLI prints:\n  "
        + "\n  ".join(hits))


# --- `TRC-E1` -----------------------------------------------------------------

def test_e1_failure_message_claim_is_checked_or_narrowed():
    """`TRC-E1` - guarantee 7 claimed something about EVERY failure message.

    Nothing checks it, and nothing can: judging whether prose explains a cause
    is not mechanisable. So it is narrowed to what is true, and says which
    messages it covers.
    """
    body = " ".join((REPO_ROOT / "docs" / "safety-contract.md").read_text(
        encoding="utf-8").replace("`", "").replace("*", "").split())
    assert "every failure message tells you" not in body.lower(), (
        "the contract still claims every failure message explains itself. "
        "Nothing checks that, and no check could")
    assert re.search(r"(structured failure|failure message)", body, re.I), (
        "the narrowed guarantee no longer says anything about failure "
        "messages - narrowing past what is true is its own defect")


# --- `TRC-F1` -----------------------------------------------------------------

def test_f1_decay_rule_states_its_ask():
    """`TRC-F1` - the mechanical half. The judgement half needs a reader.

    This half can pass alone, on purpose: the reader's answer is recorded as
    evidence when it arrives, and anything it finds becomes its own issue
    rather than blocking a release.
    """
    body = (REPO_ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    # The rule has no heading and does not use the word "decay", so it is
    # found by its opening sentence.
    anchor = "**Correct a retired name in a comment you were touching anyway.**"
    assert anchor in body, (
        "the rule about retired names in comments is not where this check "
        "expects it. If it moved or was reworded, this check has stopped "
        "reading the thing it was written for")
    # The anchor sentence IS the imperative, so it stays in the section.
    # Bounded by the next bullet as well as the next bold paragraph: the rule
    # is a list item now, and stopping only at a blank-line-then-bold ran on
    # through the rest of the strategy and into the following heading, so the
    # bare-code check below was reporting on codes the rule never mentions.
    rest = body.split(anchor, 1)[1]
    for boundary in ("\n\n**", "\n- **", "\n\n*", "\n### "):
        rest = rest.split(boundary, 1)[0]
    assert rest.strip(), (
        "the rule's body is empty after the section boundary was applied, so "
        "everything below would inspect only the anchor sentence this check "
        "selected - which cannot fail. The rule was reformatted and the "
        "boundary list no longer fits it")
    section = anchor + rest
    flat = " ".join(section.replace("`", "").replace("*", "").split())

    # The rule has two halves and they need different checks.
    #
    # The ACTION is the anchor itself - "Correct a retired name in a comment
    # you were touching anyway" - and the assertion above already pins that
    # sentence verbatim. Searching the section for an action verb therefore
    # matched text this check had selected: the body could be replaced with
    # anything and it still passed, which was checked by blanking it.
    #
    # The BOUND is the body, and nothing guarded it. Without "no sweep, no
    # obligation to go looking" the rule reads as an instruction to hunt down
    # every retired name in the repository, which is the opposite of what it
    # asks and a great deal more work.
    body_only = " ".join(rest.replace("`", "").replace("*", "").split())
    assert re.search(r"no sweep|no obligation|way past|touching anyway",
                     body_only, re.I), (
        f"the decay rule no longer bounds what it asks for. Its body reads "
        f"{body_only[:120]!r}. Without the limit, 'correct a retired name' "
        f"reads as an instruction to sweep the repository for every one of "
        f"them")
    bare = re.findall(r"\b([GS]\d+)\b(?!\s*[-\u2013\u2014:(])", flat)
    assert not bare, (
        f"the decay rule uses short codes without expanding them: {bare}. A "
        f"reader outside the conversation cannot resolve them")


# --- `TRC-F2` -----------------------------------------------------------------

def test_f2_launch_article_carries_no_working_notes():
    """`TRC-F2` - the mechanical half of "does it read as publication copy"."""
    article = REPO_ROOT / "docs" / "launch-article.md"
    assert article.is_file(), "docs/launch-article.md is missing"
    body = article.read_text(encoding="utf-8")
    tells = [t for t in ("TODO", "TBD", "FIXME", "XXX", "draft note",
                         "[ ]", "placeholder") if t in body]
    assert not tells, (
        f"the article carries working-notes markers: {tells}. It is published "
        f"copy, not a scratchpad")


# --- `TRC-D2` -----------------------------------------------------------------

def test_d2_repairs_change_only_retired_names():
    """`TRC-D2` - the sweep changed wording, not structure.

    Fourteen of the repaired files are under agents/ and skills/ - instructions
    to an agent, not prose - so a careless rename changes behaviour rather than
    reading.

    What is checked is a structural fingerprint of the pre-repair text,
    committed alongside it: heading levels and order, fenced code blocks,
    table rows, list items. A repair that drops a step, merges a table row
    or edits a code example fails this; one that renames a stage does not.

    What is checked instead is the structural property the map was a proxy for,
    fingerprinted from the pre-repair text and committed: heading levels and
    order, fenced code blocks, table rows, list items. All 59 were identical
    across the repair. A repair that drops a step, merges a table row or edits
    a code example fails this; one that renames a stage does not.

    Twenty-two more moved with the same issue, and none of their fingerprints
    changed: the shipped examples' documents were relocated from
    `.compass/work/<slug>/` to `docs/compass/<created>-<slug>/` by
    `compass migrate`. Only the key moved. A relocation that also edited a
    document would still show here, because the fingerprint travelled with it.

    A third entry moved for a different reason: `approaches/quick-fix.md`
    gained one `##` section, "Running it", naming the single-command entry
    point `/compass:quick-fix`. Seven headings to eight, everything else
    identical. Re-baselined here in the same change that added the section, so
    the snapshot stays a record of a sanctioned state.

    Two entries were re-baselined at 4.0.0, deliberately and in one change:
    `governance/strategies.md` (list_items 32 -> 88, one heading level added)
    and `governance/guardrails.md` (10 -> 22), when both were cut from prose
    to directives and their incidents moved to `strategies-rationale.md`. The
    fingerprint is a snapshot of a sanctioned state, not of the original text,
    so a sanctioned restructure moves it - visibly, in the same commit.

    Nine were re-baselined by `prose-breaks-the-writing-style`. The list is
    counted from the fixture, not merged from the batches' own notes: each
    batch recorded only the entries it saw, and the merged set is larger than
    either recorded.

    - `agents/orchestrator.md` (list_items 12 -> 15) and `agents/planner.md`
      (22 -> 24), where a long paragraph became a vertical list - the
      writing-style rule this issue exists to apply.
    - `docs/quickstart.md` (11 -> 15) and `docs/routing-deep-dive.md`
      (12 -> 20), the same rule over two longer documents.
    - `approaches/hotfix.md` (12 -> 11) and `governance/routing-policy.md`
      (18 -> 17), each losing a bullet that was really a continuation line of
      the one above it, once the idiom or sentence break that put it on its
      own dashed line went.
    - `governance/guardrails.md` (heading_levels ten entries -> nine,
      table_rows 3 -> 0), losing its placeholder amendment-log heading and
      table - git is the log, so a rendered `{{DATE}}`/`{{NAME}}` table
      taught nothing.
    - `governance/strategies.md` (88 -> 89), gaining one: a run-on bullet
      that named two purposes inline became a parent bullet with two nested
      ones, which is the same "one point in one sentence, a vertical list for
      a set of items" rule the rest of the rewrite applied.
    - the shipped `initiative-new-subsystem` example's own distribution map
      (list_items 11 -> 10), losing a bullet that stated a
      `.compass/config.yml` `max_worktrees` value the file does not
      declare - a stated fact the audit found the source contradicted, not
      a wording swap.

    One was re-baselined three times, by three issues:
    `docs/safety-contract.md` (list_items 19 -> 21 -> 23 -> 25).
    `red-record-identity-cutoff` made the two conditions under which an
    unstamped red record still counts a vertical list, `hook-failure-matrix`
    did the same for the two gaps in checking a shell write inside a
    worktree, and `evidence-binding` for the two ways a record's tree is
    judged.

    Two were re-baselined by `orchestrator-loop-hardening`, which adopted the
    multiagent loop's rules: `agents/orchestrator.md` gained a
    "Briefing a reviewer" section and two numbered steps, and
    `skills/worktree-multiagent/SKILL.md` gained the brief-file, budget,
    batching and no-subagent rules as list items.

    The other 47 are untouched, and a NEW structural change to any of the 59
    still fails.
    """
    import json
    snap = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / "repaired-file-structure.json")
        .read_text(encoding="utf-8"))
    assert len(snap) > 50, (
        f"only {len(snap)} files in the structure fixture - it has been "
        f"truncated, and this check would pass over almost nothing")

    drift = []
    for rel, expected in sorted(snap.items()):
        p = REPO_ROOT / rel
        if not p.is_file():
            drift.append(f"{rel}: gone")
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        actual = {
            "heading_levels": [len(m.group(1)) for l in lines
                               if (m := re.match(r"^(#+)\s", l))],
            "fences": sum(1 for l in lines if l.lstrip().startswith("```")),
            "table_rows": sum(1 for l in lines if l.lstrip().startswith("|")),
            "list_items": sum(1 for l in lines
                              if re.match(r"^\s*(?:[-*]|\d+\.)\s", l)),
        }
        for key in expected:
            if actual[key] != expected[key]:
                drift.append(f"{rel}: {key} changed")
    assert not drift, (
        "the vocabulary repair changed document structure, not just wording:\n  "
        + "\n  ".join(drift))


# --- shipped prose cites only what a reader has ------------------------------

def test_shipped_prose_names_no_path_that_is_not_distributed():
    """A citation into a gitignored tree resolves for the maintainer and for
    nobody else.

    `test_a4_named_files_resolve` above checks a named file exists ON THIS
    MACHINE. That passes for a path under `docs/compass/<dated-slug>/`, which
    is an issue's own record and deliberately not committed - so the citation
    reads as good locally and is dead for every reader, and only continuous
    integration says so.

    Checked with `git check-ignore`, because the question is what git
    distributes, not what happens to be on disk.
    """
    import subprocess

    named = re.compile(r"(?<![\w/.-])((?:approaches|governance|templates|skills"
                       r"|agents|commands|docs)/[\w./-]+\.md)\b")
    cited = {}
    for p in _prose_files():
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for path in named.findall(line):
                cited.setdefault(path, []).append(
                    f"{p.relative_to(REPO_ROOT)}:{n}")
    assert cited, "no citations found at all - this check is inspecting nothing"

    r = subprocess.run(["git", "check-ignore", "--stdin"],
                       input="\n".join(sorted(cited)), cwd=str(REPO_ROOT),
                       capture_output=True, text=True)
    ignored = [p for p in r.stdout.splitlines() if p.strip()]
    offenders = [f"{p} (cited by {', '.join(cited[p])})"
                 for p in ignored if p in cited]
    assert not offenders, (
        "shipped prose cites files git does not distribute, so they resolve "
        "for whoever wrote them and for nobody else:\n  "
        + "\n  ".join(offenders))
