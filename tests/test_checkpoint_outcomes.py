"""Checkpoint outcomes: a record of each stage hand-off, and the landing refusal.

A stage hand-off that can wait for a person (assess, define, refine or plan)
now leaves a record in the manifest's `checkpoint_outcomes`:

- `compass evidence approve --checkpoint <stage>` records a person's answer as
  a `checkpoint-approval` evidence record and a `waited` outcome;
- `compass issue checkpoint add <stage> --outcome skipped --by <agent>`
  records a hand-off that the autonomy setting passed;
- `compass ship-commit` refuses an issue that lists a checkpoint with no
  outcome, before it writes anything.

Only an issue whose manifest holds the `checkpoint_outcomes` key is judged.
The first assessment writes it; nothing adds it to an older issue.

Every project here is a real git repository driven through `cli/compass`.
GitHub is off, a `gh` on PATH fails the test if anything calls it, and a
person's command gets a pseudo-terminal.

Scenario ids: ARC-1 to ARC-5, ARC-7 and ARC-8, in the acceptance criteria of
the issue `autonomy-ratio-and-cost`. Each test name starts with its id.
"""
from __future__ import annotations

import datetime
import json
import os
import pty
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
import yaml  # noqa: E402

SLUG = "feature"
CREATED = "2026-10-10"
DOCS = f"docs/compass/{CREATED}-{SLUG}"

GH_SHIM = """#!/bin/sh
echo "gh $*" >> "{log}"
echo "gh was called during a test that must make no network call" >&2
exit 1
"""

#: A project on balanced autonomy whose file lists jed72 under approvers.
BALANCED = {"schema": 1, "owner": "jed72", "autonomy": "balanced",
            "approvers": {"issue-waiver": ["jed72"]}}

ASSESSMENT = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
              "goal": "delivery", "role": "engineer", "labels": []}


# --- running the CLI -------------------------------------------------------------

def _bin(root):
    folder = Path(root) / ".test-bin"
    if not (folder / "gh").exists():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gh").write_text(GH_SHIM.format(log=Path(root) / ".gh-calls"))
        (folder / "gh").chmod(0o755)
    return folder


def env(root, **extra):
    """The environment of every CLI call: no network, no session, and transcripts
    under the project's own temporary config folder."""
    root = Path(root)
    (root / ".home").mkdir(parents=True, exist_ok=True)
    values = {
        "PATH": f"{_bin(root)}:{Path(sys.executable).parent}:/usr/bin:/bin",
        "HOME": str(root / ".home"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1", "COLUMNS": "200", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "COMPASS_RENDER_AFTER": "0",
        "CLAUDE_PROJECT_DIR": str(root),
        "CLAUDE_CONFIG_DIR": str(root / ".claude-config"),
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.useConfigOnly",
        "GIT_CONFIG_VALUE_0": "true",
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    values.update(extra)
    return values


def run(root, *argv, terminal=False, cli=CLI, cwd=None, **extra):
    """One CLI call. With `terminal`, standard input is a pseudo-terminal, as a
    person at a keyboard has; otherwise it is empty, as in an agent session."""
    master = slave = None
    if terminal:
        master, slave = pty.openpty()
    try:
        return subprocess.run(
            [sys.executable, str(cli), *argv], cwd=str(cwd or root), env=env(root, **extra),
            capture_output=True, text=True, timeout=300,
            stdin=slave if terminal else subprocess.DEVNULL)
    finally:
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)


def git(root, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                           *args], cwd=root, capture_output=True, text=True,
                          check=True).stdout.strip()


def assert_no_gh_call(root):
    calls = Path(root) / ".gh-calls"
    assert not calls.exists(), calls.read_text()


# --- the project -----------------------------------------------------------------

def manifest_file(root, slug=SLUG):
    return Path(root) / ".compass" / "work" / slug / "manifest.yml"


def manifest(root, slug=SLUG):
    return yaml.safe_load(manifest_file(root, slug).read_text(encoding="utf-8"))


def write_manifest(root, body, slug=SLUG):
    manifest_file(root, slug).write_text(yaml.safe_dump(body, sort_keys=False),
                                         encoding="utf-8")


def edit(root, slug=SLUG, **changes):
    body = manifest(root, slug)
    body.update(changes)
    write_manifest(root, body, slug)
    return body


def project(tmp_path, compass_yml=BALANCED, assessment=None, cli=CLI):
    """A git repository holding one regular issue at generation 1, assessed by
    `compass approach evaluate --write`, with its delivery-approach record."""
    root = Path(tmp_path) / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    (root / "README.md").write_text("base\n")
    (root / ".gitignore").write_text(".test-bin/\n.home/\n.gh-calls\n.claude-config/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    done = run(root, "init", cli=cli)
    assert done.returncode == 0, done
    task_dir = root / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    write_manifest(root, {"schema_version": "3.0", "issue": SLUG, "created": CREATED,
                          "assessment": dict(ASSESSMENT, **(assessment or {})),
                          "evidence": []})
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    if compass_yml is not None:
        (root / "compass.yml").write_text(yaml.safe_dump(compass_yml), encoding="utf-8")
    done = run(root, "approach", "evaluate", "--issue", SLUG, "--write", cli=cli)
    assert done.returncode == 0, done
    (task_dir / "delivery-approach.md").write_text("# Delivery approach\n")
    (root / DOCS).mkdir(parents=True, exist_ok=True)
    return root


def register(root, kind, status="draft", slug=SLUG, cli=CLI):
    """Write the document and register it, which is the stage's own record."""
    path = Path(root) / DOCS / f"{kind}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {kind}\n\nFirst version.\n")
    done = run(root, "issue", "artifact", "set", kind, "--status", status,
               "--path", f"{DOCS}/{kind}.md", "--issue", slug, cli=cli)
    assert done.returncode == 0, done
    return done


def approve(root, stage, *extra, approver="jed72", role="product-owner", slug=SLUG,
            terminal=True):
    return run(root, "evidence", "approve", "--checkpoint", stage, "--issue", slug,
               "--approver", approver, "--role", role, *extra, terminal=terminal)


def skip(root, stage, by="spec-author", *extra, slug=SLUG):
    return run(root, "issue", "checkpoint", "add", stage, "--outcome", "skipped",
               "--by", by, "--issue", slug, *extra)


def outcomes(root, slug=SLUG):
    return manifest(root, slug).get("checkpoint_outcomes")


def generation_files(root, slug=SLUG):
    folder = Path(root) / ".compass" / "work" / slug / "generations"
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def _utc(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def schema_errors(body):
    """Every error the manifest schema reports for `body`."""
    import jsonschema
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    return sorted(e.message for e in jsonschema.Draft7Validator(schema).iter_errors(body))


def refine_done(root):
    """The records show refine complete: its review written and registered."""
    register(root, "acceptance-criteria")
    register(root, "requirements-review")


# --- ARC-3 ------------------------------------------------------------------------

def test_arc_3_agent_records_a_skipped_outcome(tmp_path):
    root = project(tmp_path)
    assert manifest(root)["checkpoints"] == ["define", "plan"]
    refine_done(root)
    devlog = manifest_file(root).parent / "devlog.md"
    devlog.write_text("# Devlog\n")
    generations = generation_files(root)
    assert generations, "the issue holds no stored generation to compare"
    evidence_before = manifest(root).get("evidence")

    before = _now()
    done = skip(root, "refine")
    after = _now()
    assert done.returncode == 0, done
    assert done.stdout.strip() == (
        "compass issue checkpoint add: refine recorded as skipped by spec-author."), done
    entries = outcomes(root)
    assert len(entries) == 1, entries
    entry = entries[0]
    assert {k: v for k, v in entry.items() if k != "at"} == {
        "stage": "refine", "outcome": "skipped", "by": "spec-author"}, entry
    assert before <= _utc(entry["at"]) <= after, entry
    assert manifest(root).get("evidence") == evidence_before
    assert devlog.read_text() == "# Devlog\n"
    assert not schema_errors(manifest(root)), schema_errors(manifest(root))

    same = manifest_file(root).read_bytes()
    done = skip(root, "refine")
    assert done.returncode == 0, done
    assert "already recorded as skipped; nothing was written" in done.stdout, done
    assert manifest_file(root).read_bytes() == same

    done = approve(root, "refine")
    assert done.returncode == 0, done
    refine = [e for e in outcomes(root) if e["stage"] == "refine"]
    assert len(refine) == 1, outcomes(root)
    assert refine[0]["outcome"] == "waited" and refine[0]["by"] == "jed72", refine
    assert generation_files(root) == generations
    assert_no_gh_call(root)
