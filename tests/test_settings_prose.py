"""Prose that tells an agent or a person where a setting is read, or what
`compass init` writes, matches what the CLI does (ADR-043).

`compass init` writes the state file in `.compass/` and no settings file. A
setting is read from `compass.yml`, or from `.compass/config.yml` in a project
that has no `compass.yml`. A sentence that names only the old file sends an
agent to a file a new project does not have.

Scenario id: SH-8, in the acceptance criteria of the issue
`settings-reader-hook`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OLD = ".compass/config.yml"
NEW = re.compile(r"(?<![./\w])compass\.yml")

# Prose an agent or a person reads to learn where a setting lives.
SCANNED = ("commands", "agents", "skills", "templates", "approaches", "docs")
EXTRA = ("README.md", "ci/README.md", "governance/routing-policy.md",
         "governance/strategies.md")
# The reference that defines both files, the generated refusal list, the
# derived living spec, and decision-record templates that record history.
EXEMPT = ("docs/configuration.md", "docs/refusal-codes.md",
          "docs/system-spec.md", "docs/system-spec-archive.md",
          "templates/architecture/")


def _prose_files():
    paths = []
    for top in SCANNED:
        paths += (ROOT / top).rglob("*.md")
    paths += [ROOT / p for p in EXTRA]
    for path in sorted(set(paths)):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("docs/compass/") or rel.startswith(EXEMPT):
            continue
        yield rel, path


def _paragraphs(text):
    return re.split(r"\n\s*\n", text)


# Paragraphs that name the old file correctly without `compass.yml`: the
# eval judge guards that one file by name, and the state-file rule is about
# where `init` writes, not where a setting is read.
ALLOWED = {"docs/headless-runner.md": "another protected file",
           "docs/safety-contract.md": "records_signed_since"}


def _names_only_the_old_file(text, allowed=None):
    """The paragraphs of `text` that name the old file and never `compass.yml`."""
    return [p.strip().splitlines()[0] for p in _paragraphs(text)
            if OLD in p and not NEW.search(p)
            and not (allowed and allowed in p)]


def test_sh8_the_scan_flags_a_paragraph_that_names_only_the_old_file():
    assert _names_only_the_old_file("The `.compass/config.yml` holds it.\n")
    assert not _names_only_the_old_file(
        "In `compass.yml`, or `.compass/config.yml` without one.\n")
    assert not _names_only_the_old_file("Nothing here.\n")


def test_sh8_no_prose_names_only_the_old_settings_file():
    offenders = {}
    scanned = 0
    for rel, path in _prose_files():
        scanned += 1
        hits = _names_only_the_old_file(path.read_text(encoding="utf-8"),
                                        ALLOWED.get(rel))
        if hits:
            offenders[rel] = hits
    assert scanned > 100
    assert not offenders, offenders


def test_sh8_init_is_not_said_to_write_a_settings_file():
    for rel in ("commands/init.md", "docs/quickstart.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "already written a minimal" not in text, rel
        assert not re.search(r"Creates `\.compass/config\.yml`", text), rel
        assert "compass.yml" in text, rel
    init = (ROOT / "commands" / "init.md").read_text(encoding="utf-8")
    assert re.search(r"writes no settings file", init), init[:200]
    assert "project.name" in init and "project.test_command" in init
