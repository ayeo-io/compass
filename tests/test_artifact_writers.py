"""Where a document is written, and what stays behind.

Scenario group B of `docs-compass-artifacts`.

Two directories, and the split between them is the whole point:

  .compass/work/<slug>/          machine state - the manifest, the evidence
                                 records, the TDD markers, the devlog. Read and
                                 written by the CLI.
  docs/compass/<created>-<slug>/ human documents - the spec, the design, the
                                 review. Written for a person, and now living
                                 where a person browsing the repository finds
                                 them.

The date is the manifest's `created:` field, not the day the document is
written: an issue that sits queued for a fortnight would otherwise scatter its
documents across two directories.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"

#: Read and written by the CLI. Stays beside the manifest, named by `TRC-B2`.
MACHINE_STATE = {
    "manifest.yml", "devlog.md", "evidence", ".red", ".spike",
    ".tdd-state.json", "README.md",
}


def _template_documents():
    """Document kinds the framework ships a template for.

    Derived from `templates/*.md` rather than listed here: a list would go
    stale the first time a template is added, and this file would go on
    asserting something about a set that no longer matches the framework.
    """
    return {p.name for p in (ROOT / "templates").glob("*.md")}


#: Templates that are not an issue's documents at all, so neither rule
#: applies. `pull-request-body.md` is a shape for a pull-request description -
#: it is never written into an issue directory in the first place.
NOT_AN_ISSUE_DOCUMENT = {"pull-request-body.md"}


def _human_documents():
    return _template_documents() - MACHINE_STATE - NOT_AN_ISSUE_DOCUMENT


def _project(tmp_path, slug="an-issue", created="2026-09-08"):
    task_dir = tmp_path / ".compass" / "work" / slug
    (task_dir / "evidence").mkdir(parents=True)
    manifest = {
        "schema_version": "2.0", "issue": slug, "created": created,
        "status": "active",
        "artifacts": [
            {"id": "ART-ACCEPTANCE_CRITERIA", "kind": "acceptance-criteria",
             "status": "draft", "reason": "every issue carries one"},
        ],
    }
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (tmp_path / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    return task_dir


def _cli(project, *args):
    return subprocess.run([sys.executable, str(COMPASS_CLI), *args],
                          capture_output=True, text=True, timeout=120,
                          cwd=str(project))


# --- `TRC-B1` -----------------------------------------------------------------

def test_trc_b1_the_docs_directory_is_named_from_the_created_date(tmp_path):
    """`docs/compass/<created>-<slug>`, computed in one place.

    Every writer, the migration and the hooks need the same answer. Three
    copies of the same string join is how they stop agreeing.
    """
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import core

    task_dir = _project(tmp_path, slug="docs-compass-artifacts",
                        created="2026-09-08")
    assert core.docs_dir(str(task_dir)) == os.path.join(
        "docs", "compass", "2026-09-08-docs-compass-artifacts"), (
        "docs_dir does not name the directory from the manifest's created "
        "date and the slug")


def test_trc_b1_the_write_date_is_not_used(tmp_path):
    """The write date is not used, and this test keeps it that way.

    Using the day the document is written puts two documents of the same issue
    in two directories when the first is written either side of midnight.
    """
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import core

    task_dir = _project(tmp_path, slug="s", created="2020-01-01")
    assert "2020-01-01" in core.docs_dir(str(task_dir)), (
        "docs_dir ignored the manifest's created date, so it is deriving the "
        "directory from something that moves")


# --- `TRC-B2` -----------------------------------------------------------------

def test_trc_b2_machine_state_is_named_as_staying(tmp_path):
    """The templates say where each document lives, and the machine-state
    files are the ones that keep saying `.compass/work/`."""
    for name in sorted(MACHINE_STATE):
        template = ROOT / "templates" / name
        if not template.is_file():
            continue
        head = template.read_text(encoding="utf-8")[:400]
        assert ".compass/work/" in head, (
            f"templates/{name} no longer says it lives under .compass/work/. "
            f"It is machine state - the CLI reads it there")


def test_trc_b2_no_human_document_still_claims_the_work_directory():
    """Every template for a human document puts it under `docs/compass/`.

    A catalogue kind's home comes from the catalogue, which declares a bare
    filename, and the skeleton prints the documents folder; its template says
    nothing about location. A template that is not a kind keeps a `Lives at:`
    line, the one an agent copies when it writes the file, so a template that
    still names `.compass/work/` puts the document back where it started
    however carefully the command is worded.
    """
    import yaml

    # The live default declares no kind since 9.0.0 (ADR-091); the templates are the
    # kinds of the last shipped catalogue, which the frozen 7.0.0 preset holds.
    kinds = set(yaml.safe_load((ROOT / "governance" / "presets" / "default@7" /
                                "artifacts.yml").read_text(encoding="utf-8"))["artifacts"])
    stale = []
    for name in sorted(_human_documents()):
        head = (ROOT / "templates" / name).read_text(encoding="utf-8")[:400]
        if name[:-3] in kinds:
            if ".compass/work/" in head:
                stale.append(f"templates/{name}: names .compass/work/")
            continue
        m = re.search(r"^Lives at:\s*(\S+)", head, re.M)
        if not m:
            stale.append(f"templates/{name}: no `Lives at:` line")
        elif ".compass/work/" in m.group(1):
            stale.append(f"templates/{name}: {m.group(1)}")
    assert not stale, (
        "templates for human documents still put them beside the manifest:\n  "
        + "\n  ".join(stale))


def test_trc_b2_the_commands_send_human_documents_to_the_docs_directory():
    """The command files are the other half: an agent reads the command, not
    only the template."""
    offenders = []
    for path in sorted((ROOT / "commands").glob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for doc in sorted(_human_documents()):
                if doc in line and ".compass/work/" in line:
                    offenders.append(
                        f"commands/{path.name}:{n}: {doc} under .compass/work/")
    assert not offenders, (
        "commands still write human documents beside the manifest:\n  "
        + "\n  ".join(offenders))


def test_trc_b2_the_agents_send_human_documents_to_the_docs_directory():
    offenders = []
    for path in sorted((ROOT / "agents").glob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for doc in sorted(_human_documents()):
                if doc in line and ".compass/work/" in line:
                    offenders.append(
                        f"agents/{path.name}:{n}: {doc} under .compass/work/")
    assert not offenders, (
        "agents still write human documents beside the manifest:\n  "
        + "\n  ".join(offenders))


def test_trc_b2_the_split_covers_every_template():
    """A template that is in neither set is a document nobody decided about.

    Without this, adding a template puts it silently outside both checks above
    and it can live anywhere.
    """
    unclassified = (_template_documents() - MACHINE_STATE
                    - NOT_AN_ISSUE_DOCUMENT - _human_documents())
    assert not unclassified, (
        "templates nobody has placed on either side of the split: "
        + ", ".join(sorted(unclassified)))
    assert _human_documents(), "the human-document set is empty - the two "\
        "checks above are asserting nothing"


# --- `TRC-B3` -----------------------------------------------------------------

def test_trc_b3_creating_the_docs_directory_is_reported():
    """A directory appearing with nothing said is how it gets deleted by hand
    or committed by accident. The command that writes the first document has
    to say it made the place to put it."""
    missing, checked = [], []
    for name in ("assess.md", "define.md", "plan.md", "verify.md",
                 "intent.md", "refine.md", "quick-fix.md"):
        text = (ROOT / "commands" / name).read_text(encoding="utf-8")
        if "docs/compass/" not in text:
            continue
        checked.append(name)
        # A sentence that does all three things: names the directory, talks
        # about creating it, and tells the agent to say so. Matched as a set
        # rather than in one order - "say so if you created it" and "if you
        # created it, say so" are the same instruction, and a pattern that
        # only accepts one of them tests the wording rather than the rule.
        told = False
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
            low = sentence.lower()
            if ("docs/compass" in low and "creat" in low
                    and re.search(r"\b(say|says|report|reports|tell|tells)\b", low)):
                told = True
                break
        if not told:
            missing.append(f"commands/{name}")
    # Without this the check passes on an empty list: every command skipped
    # for not mentioning docs/compass, nothing inspected, and a green line.
    assert checked, (
        "no command writes into docs/compass/, so this check inspected "
        "nothing and passed")
    assert not missing, (
        "commands write into docs/compass/ without telling the reader when "
        "they created it:\n  " + "\n  ".join(missing))


# --- `TRC-B4` -----------------------------------------------------------------

@pytest.mark.parametrize("verb", ["check", "next"])
def test_trc_b4_a_reading_command_creates_nothing(tmp_path, verb):
    """Reading is read-only, and the docs directory is the new thing a reader
    could be tempted to create on the way to looking in it."""
    _project(tmp_path)
    before = sorted(p.relative_to(tmp_path).as_posix()
                    for p in tmp_path.rglob("*"))
    _cli(tmp_path, verb, "--issue", "an-issue")
    after = sorted(p.relative_to(tmp_path).as_posix()
                   for p in tmp_path.rglob("*"))
    created = [p for p in after if p not in before]
    # A failing `compass check` appends one line to `.compass/interruptions.log`,
    # an append-only count of interruptions outside every issue folder (the
    # maintainer's choice, issue one-entry-point). It is a count of the run,
    # not a record the reading produced, so it is the one file `check` may
    # create; anything else it creates still fails here.
    if verb == "check":
        created = [p for p in created if p != ".compass/interruptions.log"]
    assert not created, (
        f"`compass {verb}` created {created} - a reading command writes "
        f"nothing")
    assert not (tmp_path / "docs").exists(), (
        f"`compass {verb}` created docs/ on its way to looking for a document")
