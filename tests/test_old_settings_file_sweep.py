"""No source file names the old settings file without naming its replacement.

From 6.0.0 a project's settings live in `compass.yml`, and the CLI-written
state lives in the state file in `.compass/`. `.compass/config.yml` is read
only for a project that has not moved (ADR-043). A comment, a message or a
check that names only the old file sends a reader to a file a new project does
not have, or tests for a file this repository no longer has.

`tests/test_settings_prose.py` scans markdown. This scan covers the other
tracked sources: the CLI, the hook and scripts, the eval harness, CI and the
Makefile. A paragraph (lines between blank lines) that names the old file must
also name `compass.yml` or the state file.

Scenario id: IDR-7, in the acceptance criteria of the issue `init-docs-release`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OLD = ".compass/config.yml"
NEW = re.compile(r"(?<![.\w])compass\.yml|state\.yml|state file")

SCANNED = ("cli/", "hooks/", "scripts/", "evals/", "ci/", ".github/", "Makefile")
SUFFIXES = (".py", ".sh", ".yml", ".yaml", ".toml", "Makefile")
# Files that define the fallback to the old file, or are fixtures of it.
EXEMPT = ("cli/vendor/",
          # The scenario names the old file as a file an agent must not touch.
          "evals/scenarios/")


def _tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    for rel in out.split("\0"):
        if rel.startswith(SCANNED) and rel.endswith(SUFFIXES) \
                and not rel.startswith(EXEMPT):
            path = ROOT / rel
            if path.is_file():
                yield rel, path


def names_only_the_old_file(text):
    """The first line of each paragraph of `text` that names the old file and
    never `compass.yml` or the state file."""
    return [p.strip().splitlines()[0] for p in re.split(r"\n\s*\n", text)
            if OLD in p and not NEW.search(p)]


def test_idr_7_the_scan_flags_a_paragraph_that_names_only_the_old_file():
    assert names_only_the_old_file("# reads .compass/config.yml\nx = 1\n")
    assert not names_only_the_old_file("# reads compass.yml or .compass/config.yml\n")
    assert not names_only_the_old_file("# the state file, not .compass/config.yml\n")
    assert not names_only_the_old_file("nothing here\n")


def test_idr_7_no_source_names_only_the_old_settings_file():
    offenders, scanned = {}, 0
    for rel, path in _tracked():
        scanned += 1
        hits = names_only_the_old_file(path.read_text(encoding="utf-8"))
        if hits:
            offenders[rel] = hits
    assert scanned > 100
    assert not offenders, offenders
