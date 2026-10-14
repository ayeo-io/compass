"""The lightweight intent on regular, and the release line every shipping issue records.

- A new regular issue owes `intent.md` at depth `lightweight`: Problem, Desired outcome,
  Success signals and Non-goals.
- An issue whose stored configuration marks its approach `release_line: true` records one
  release line in its manifest's `release_note:`. `compass acceptance record`,
  `compass ship-commit` and `compass quick-fix finish` write it with `--release-note`, and
  every landing refuses an issue that owes one and has none.
- The verification report shows the line through the `release-line` rendered block.

Every project here is a real git repository driven through `cli/compass`. GitHub is off,
and a `gh` on PATH fails the test if anything calls it.

Scenario ids: IRL-1 to IRL-15, IRL-21 to IRL-24 and IRL-26 to IRL-28, in the acceptance
criteria of the issue `intent-and-release-line`. Each test name starts with its id.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
import yaml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project_readiness_support as readiness_support  # noqa: E402

SLUG = "feature"
CREATED = "2026-10-10"
DOCS = f"docs/compass/{CREATED}-{SLUG}"

GH_SHIM = """#!/bin/sh
echo "gh $*" >> "{log}"
echo "gh was called during a test that must make no network call" >&2
exit 1
"""

#: A project on autonomous autonomy, so a regular issue lists no checkpoint and
#: the only landing refusal a test meets is the one it sets up.
AUTONOMOUS = {"schema": 1, "owner": "jed72", "autonomy": "autonomous",
              "approvers": {"issue-waiver": ["jed72"]}}

#: The assessments that route to each approach on the shipped default.
ASSESSMENTS = {
    "regular": {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
                "goal": "delivery", "role": "engineer", "labels": []},
    "quick-fix": {"risk": "trivial", "familiarity": "brownfield-mapped", "size": "atomic",
                  "goal": "delivery", "role": "engineer", "labels": []},
    "hotfix": {"risk": "trivial", "familiarity": "brownfield-mapped", "size": "atomic",
               "goal": "delivery", "role": "engineer", "labels": [],
               "urgency": "live-defect"},
    "full": {"risk": "critical", "familiarity": "brownfield-mapped", "size": "large",
             "goal": "delivery", "role": "engineer", "labels": []},
    "spike": {"risk": "trivial", "familiarity": "brownfield-mapped", "size": "small",
              "goal": "exploration", "role": "engineer", "labels": []},
}


# --- running the CLI -------------------------------------------------------------

def _bin(root):
    folder = Path(root) / ".test-bin"
    if not (folder / "gh").exists():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gh").write_text(GH_SHIM.format(log=Path(root) / ".gh-calls"))
        (folder / "gh").chmod(0o755)
    return folder


def env(root, **extra):
    """The environment of every CLI call: no network, no session issue, and a home
    folder inside the project."""
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


def run(root, *argv, cwd=None, **extra):
    return subprocess.run(
        [sys.executable, str(CLI), *argv], cwd=str(cwd or root), env=env(root, **extra),
        capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)


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


def repo(tmp_path, compass_yml=AUTONOMOUS):
    """A git repository with Compass initialised and a project file."""
    root = Path(tmp_path) / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    (root / "README.md").write_text("base\n")
    (root / ".gitignore").write_text(".test-bin/\n.home/\n.gh-calls\n.claude-config/\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    done = run(root, "init")
    assert done.returncode == 0, done
    if compass_yml is not None:
        (root / "compass.yml").write_text(yaml.safe_dump(compass_yml), encoding="utf-8")
        if compass_yml.get("autonomy") == "autonomous":
            # An autonomous issue is assessed only above the readiness floor.
            readiness_support.meet_readiness_floor(root)
    return root


def assess(root, approach="regular", slug=SLUG):
    """One issue at generation 1 on the shipped default, assessed by `compass approach
    evaluate --write`, with its delivery-approach record."""
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    write_manifest(root, {"schema_version": "3.0", "issue": slug, "created": CREATED,
                          "assessment": dict(ASSESSMENTS[approach]), "evidence": []}, slug)
    done = run(root, "approach", "evaluate", "--issue", slug, "--write")
    assert done.returncode == 0, done
    (task_dir / "delivery-approach.md").write_text("# Delivery approach\n")
    assert manifest(root, slug)["delivery_approach"] == approach, manifest(root, slug)
    return task_dir


def project(tmp_path, approach="regular", compass_yml=AUTONOMOUS):
    root = repo(tmp_path, compass_yml)
    assess(root, approach)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    return root


def generation_config(root, slug=SLUG):
    """The configuration the issue's stored generation resolves to."""
    from compass_pkg import effective
    task_dir = str(root / ".compass" / "work" / slug)
    return effective.view_or_legacy(task_dir).config


# --- IRL-23 ---------------------------------------------------------------------------

PRESET = ROOT / "governance" / "presets" / "default"

#: The digest of the locked spike entry's parsed content before this change (bce610c2):
#: sha256 over its JSON with sorted keys.
SPIKE_DIGEST = "5dbd753253467429b3dc6ada79931dfd6318d5819bdf6532479676b839e7d56d"


def _entry_digest(entry):
    import hashlib
    return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def _lint_codes(root):
    done = run(root, "policy", "lint", "--file", "compass.yml", "--json")
    report = json.loads(done.stdout)
    return done, [(f.get("code"), f.get("path")) for f in report.get("findings") or []]


def test_irl_23_default_declares_release_line(tmp_path):
    approaches = yaml.safe_load((PRESET / "approaches.yml").read_text())["approaches"]
    for name in ("quick-fix", "regular", "hotfix", "full"):
        assert approaches[name].get("release_line") is True, (name, approaches[name])
    assert "release_line" not in approaches["spike"], approaches["spike"]

    # The locked spike entry is as it was: its digest over the parsed entry has not moved.
    assert _entry_digest(approaches["spike"]) == SPIKE_DIGEST, approaches["spike"]

    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text())
    approach_props = _approach_properties(schema)
    assert approach_props["release_line"] == {"type": "boolean"} or \
        approach_props["release_line"].get("type") == "boolean", approach_props["release_line"]

    # A project may set the field: lint reports no error for a value equal to the default.
    root = repo(tmp_path / "set")
    (root / "compass.yml").write_text(yaml.safe_dump(dict(
        AUTONOMOUS, approaches={"regular": {"set": {"release_line": True}}})))
    done, codes = _lint_codes(root)
    assert not [c for c in codes if c[0] and c[0][0] in "LMCK"], (codes, done.stdout)

    # Setting it false on regular is a loosening that needs a waiver.
    (root / "compass.yml").write_text(yaml.safe_dump(dict(
        AUTONOMOUS, approaches={"regular": {"set": {"release_line": False}}})))
    done, codes = _lint_codes(root)
    assert ("C-LOOSENING", "approaches.regular.release_line") in codes, (codes, done.stdout)

    # The generated views carry a raised version.
    for name, before in (("routing-policy.yml", "2.22.0"), ("guardrails.yml", "1.29.0")):
        version = yaml.safe_load((ROOT / "governance" / name).read_text())["version"]
        assert tuple(int(p) for p in version.split(".")) > tuple(
            int(p) for p in before.split(".")), (name, version)
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate-legacy-views.py"),
                           "--check"], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def _approach_properties(schema):
    """The properties of one approach entry in the configuration schema."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict) and "ships" in props and "subtask_ceiling" in props:
                found.append(props)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(schema)
    assert found, "the schema declares no approach entry"
    return found[0]


# --- IRL-1 ----------------------------------------------------------------------------

def _entries(root, kind, slug=SLUG):
    return [a for a in manifest(root, slug).get("artifacts") or []
            if isinstance(a, dict) and a.get("kind") == kind]


def test_irl_1_regular_registers_lightweight_intent(tmp_path):
    root = project(tmp_path)
    entries = _entries(root, "intent")
    assert len(entries) == 1, manifest(root).get("artifacts")
    entry = entries[0]
    assert entry.get("status") == "draft" and entry.get("depth") == "lightweight", entry
    assert not entry.get("path"), entry
    done = run(root, "issue", "artifact-path", "intent", "--issue", SLUG)
    assert done.returncode == 0, done
    assert done.stdout.strip() == f"{DOCS}/intent.md", done
    assert_no_gh_call(root)


# --- IRL-2 ----------------------------------------------------------------------------

THOROUGH_INTENT = ["Problem", "Desired outcome", "Success signals", "Constraints", "Non-goals",
                   "Internal FAQ", "Affected roles",
                   "Intent-fidelity check (filled at the pre-plan gate)"]


def _headings(text):
    """The `## ` headings outside code fences and HTML comments."""
    from compass_pkg.template_lists import Template
    return [s["heading"] for s in Template(text).sections]


def _section(text, heading):
    from compass_pkg.template_lists import Template
    found = [s for s in Template(text).sections if s["heading"] == heading]
    assert found, (heading, text)
    return "\n".join(found[0]["body"])


def test_irl_2_template_show_lightweight_intent(tmp_path):
    light = subprocess.run([sys.executable, str(CLI), "issue", "template", "show", "intent",
                            "--depth", "lightweight"], cwd=tmp_path, capture_output=True,
                           text=True, env=env(tmp_path))
    assert light.returncode == 0, light
    assert [line for line in light.stdout.splitlines() if line.startswith("## ")] == [
        "## Problem", "## Desired outcome", "## Success signals", "## Non-goals"], light.stdout
    assert "- INT-1: <outcome>" in _section(light.stdout, "Desired outcome"), light.stdout

    thorough = subprocess.run([sys.executable, str(CLI), "issue", "template", "show", "intent",
                               "--depth", "thorough"], cwd=tmp_path, capture_output=True,
                              text=True, env=env(tmp_path))
    assert thorough.returncode == 0, thorough
    assert _headings(thorough.stdout) == THOROUGH_INTENT, thorough.stdout

    root = repo(tmp_path / "lint")
    done = run(root, "policy", "lint", "--json")
    report = json.loads(done.stdout)
    errors = [f for f in report.get("findings") or []
              if "intent" in json.dumps(f) and f.get("level") == "error"]
    assert not errors, errors
    assert report["counts"]["errors"] == 0, report


# --- IRL-3 ----------------------------------------------------------------------------

@pytest.mark.parametrize("approach, depth", [
    ("full", "thorough"), ("quick-fix", None), ("hotfix", None), ("spike", None)])
def test_irl_3_other_approaches_keep_intent_rules(tmp_path, approach, depth):
    root = repo(tmp_path)
    assess(root, approach)
    entries = _entries(root, "intent")
    if depth is None:
        assert entries == [], entries
    else:
        assert [e.get("depth") for e in entries] == [depth], entries
    # The configuration the issue runs against says the same.
    owed = (generation_config(root)["approaches"][approach].get("artifacts") or {})
    assert owed.get("intent") == depth, owed


# --- landing an issue -------------------------------------------------------------------

#: The texts of the release-line refusals, as a reader sees them.
MISSING = "has no release line"
FLAG = '--release-note "<text written for a user>"'


def register(root, kind, status="approved", slug=SLUG, text=None):
    """Write the document, unless it exists, and register it."""
    path = Path(root) / DOCS / f"{kind}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None or not path.exists():
        path.write_text(text if text is not None else f"# {kind}\n\nFirst version.\n")
    done = run(root, "issue", "artifact", "set", kind, "--status", status,
               "--path", f"{DOCS}/{kind}.md", "--issue", slug)
    assert done.returncode == 0, done
    return done


def set_keys(root, slug=SLUG, **changes):
    body = manifest(root, slug)
    for key, value in changes.items():
        if value is ABSENT:
            body.pop(key, None)
        else:
            body[key] = value
    write_manifest(root, body, slug)
    return body


class _Absent:
    def __repr__(self):
        return "no key"


ABSENT = _Absent()


def ready_to_ship(root, slug=SLUG, skip=(), path="src/new.py"):
    """Every gate passed, every registered document approved, one changed file traced,
    a green on record and the file staged: the state `ship-commit` lands from."""
    for entry in manifest(root, slug).get("artifacts") or []:
        if entry.get("kind") not in skip and entry.get("status") != "approved":
            register(root, entry["kind"], slug=slug)
    body = manifest(root, slug)
    for gate in body["gates"]:
        gate["status"] = "pass"
    body["changed_files"] = [{"path": path, "scenarios": ["S-1"]}]
    write_manifest(root, body, slug)
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text("y = 1\n")
    done = run(root, "tdd-green", "--issue", slug, "--", sys.executable, "-c", "pass")
    assert done.returncode == 0, done
    git(root, "add", path)


def state(root, slug=SLUG):
    """What a refused landing must leave as it was: the manifest's bytes, what is
    staged and HEAD."""
    return (manifest_file(root, slug).read_bytes(), git(root, "diff", "--cached"),
            git(root, "rev-parse", "HEAD"))


# --- IRL-10 ---------------------------------------------------------------------------

@pytest.mark.parametrize("approach, stored", [
    ("quick-fix", ABSENT), ("regular", ABSENT), ("hotfix", ""), ("full", "   ")])
def test_irl_10_ship_commit_refuses_missing_release_line(tmp_path, approach, stored):
    root = project(tmp_path, approach)
    assert generation_config(root)["approaches"][approach]["release_line"] is True
    ready_to_ship(root)
    set_keys(root, release_note=stored)
    before = state(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode != 0, done
    assert f"'{SLUG}'" in done.stderr and MISSING in done.stderr, done.stderr
    assert FLAG in done.stderr, done.stderr
    assert "[release-line-missing]" in done.stderr, done.stderr
    assert state(root) == before
    assert "land_timestamp" not in manifest(root)
    assert_no_gh_call(root)


# --- IRL-22 ---------------------------------------------------------------------------

def rewrite_stored(root, change, slug=SLUG):
    """Change the stored generation's resolved configuration, as a generation stored
    before this change, or under another configuration, holds it, and seal it again so
    it reads as whole."""
    from compass_pkg import atomic_io, generation
    task_dir = root / ".compass" / "work" / slug
    n = manifest(root, slug)["generation"]
    folder = Path(generation.gen_dir(task_dir, n))
    resolved = yaml.safe_load((folder / "resolved.yml").read_text())
    change(resolved)
    (folder / "resolved.yml").write_text(yaml.safe_dump(resolved, sort_keys=False))
    marker = yaml.safe_load((folder / "complete").read_text())
    marker["files"]["resolved.yml"] = atomic_io.digest(resolved)
    (folder / "complete").write_text(yaml.safe_dump(marker, sort_keys=False))
    assert generation.is_whole(task_dir, n)[0], generation.is_whole(task_dir, n)


def _approach_field(resolved, approach, value):
    entry = resolved["approaches"][approach]
    if value is ABSENT:
        entry.pop("release_line", None)
    else:
        entry["release_line"] = value


def _no_issue_named(root):
    (root / ".compass" / "current-task").unlink()
    return ()


def _status(reason):
    def apply(root):
        set_keys(root, status="done", close_reason=reason)
        return ("--issue", SLUG)
    return apply


def _no_generation(root):
    set_keys(root, generation=ABSENT)
    return ("--issue", SLUG)


def _stored(value):
    def apply(root):
        rewrite_stored(root, lambda resolved: _approach_field(resolved, "regular", value))
        return ("--issue", SLUG)
    return apply


@pytest.mark.parametrize("case", [
    "no issue named", "completed", "closed", "no generation key", "no release_line field",
    "release_line false"])
def test_irl_22_refusal_declines_on_each_condition(tmp_path, case):
    setup = {"no issue named": _no_issue_named, "completed": _status("completed"),
             "closed": _status("not-planned"), "no generation key": _no_generation,
             "no release_line field": _stored(ABSENT),
             "release_line false": _stored(False)}[case]
    root = project(tmp_path)
    ready_to_ship(root)
    extra = setup(root)
    assert "release_note" not in manifest(root)
    from compass_pkg import release_line
    task_dir = str(root / ".compass" / "work" / SLUG)
    if case != "no issue named":
        assert release_line.landing_refusal(manifest(root), task_dir) is None, case
    done = run(root, "ship-commit", "-m", "Ship it", *extra)
    output = done.stdout + done.stderr
    assert "release line" not in output and "release-line" not in output, (case, output)
    assert done.returncode == 0, (case, done)
    assert_no_gh_call(root)


# --- IRL-15 ---------------------------------------------------------------------------

REPORT = f"{DOCS}/verification-report.md"


def write_report(root, slug=SLUG):
    """The verification report as `compass issue template show` gives it for the issue."""
    done = run(root, "issue", "template", "show", "verification-report", "--issue", slug)
    assert done.returncode == 0, done
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(done.stdout)
    register(root, "verification-report", status="draft", slug=slug)
    return path


def block(text, kind):
    """The body of the one rendered block of `kind` in `text`."""
    opening, closing = f"<!-- compass:render {kind} -->", "<!-- /compass:render -->"
    assert text.count(opening) == 1, (kind, text)
    return text.split(opening, 1)[1].split(closing, 1)[0].strip("\n")


def test_irl_15_verification_report_release_line_block(tmp_path):
    root = project(tmp_path)
    path = write_report(root)
    headings = _headings(path.read_text())
    at = headings.index("Release line")
    assert headings[at - 1] == "6. Decisions taken for the user", headings
    assert headings[at + 1] == "Gate", headings
    assert _section(path.read_text(), "Release line").count(
        "<!-- compass:render release-line -->") == 1

    set_keys(root, release_note="Adds the board.")
    done = run(root, "issue", "render", "--issue", SLUG)
    assert done.returncode == 0, done
    assert block(path.read_text(), "release-line") == "Adds the board.", path.read_text()

    set_keys(root, release_note=ABSENT)
    done = run(root, "issue", "render", "--issue", SLUG)
    assert done.returncode == 0, done
    empty = block(path.read_text(), "release-line")
    assert "No release line recorded yet." in empty, empty
    assert "compass ship-commit --release-note" in empty, empty

    sections = yaml.safe_load((PRESET / "artifacts.yml").read_text())["artifacts"][
        "verification-report"]["sections"]["thorough"]
    at = sections.index("Release line")
    assert sections[at - 1:at + 2] == ["6. Decisions taken for the user", "Release line",
                                       "Gate"], sections
    assert_no_gh_call(root)
