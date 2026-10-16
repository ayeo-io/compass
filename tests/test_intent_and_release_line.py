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


# --- IRL-8 ----------------------------------------------------------------------------

#: `compass check --json` on every done issue of the migrated archive sample, recorded
#: once with the CLI before this change (bce610c2), with each registry's intent count.
BEFORE = ROOT / "tests" / "fixtures" / "intent-and-release-line" / "archive-check-before.json"


def archive_verdicts(root, slugs, cli=CLI):
    """The check rows and the intent entries of each issue in `slugs`, read from a copy
    of `root`, so the run cannot change what other tests read."""
    import shutil
    import tempfile
    work = Path(tempfile.mkdtemp()) / "archive"
    shutil.copytree(root, work, ignore=shutil.ignore_patterns(".git"))
    out = {}
    for slug in sorted(slugs):
        done = subprocess.run([sys.executable, str(cli), "check", "--issue", slug, "--json"],
                              cwd=work, capture_output=True, text=True, timeout=300)
        rows = {c["name"]: c["status"] for c in json.loads(done.stdout)["checks"]}
        body = yaml.safe_load((work / ".compass" / "work" / slug / "manifest.yml").read_text())
        out[slug] = {"verdicts": rows, "intent_entries": sum(
            1 for a in body.get("artifacts") or [] if isinstance(a, dict)
            and a.get("kind") == "intent")}
    shutil.rmtree(work.parent, ignore_errors=True)
    return out


def verdict_differences(recorded, now):
    """Every row the before-run recorded must hold its status. A row it did not record is
    a difference unless contract 3's allow-list admits it. No registry may gain an
    intent entry."""
    from compat_baseline import allow_7_0_0_moves
    old, new = allow_7_0_0_moves({s: {"verdicts": v["verdicts"]} for s, v in recorded.items()},
                                 {s: {"verdicts": v["verdicts"]} for s, v in now.items()})
    found = []
    for slug in sorted(recorded):
        before, after = old[slug]["verdicts"], new.get(slug, {}).get("verdicts", {})
        found += [f"{slug}: {name} was {status}, now {after.get(name)}"
                  for name, status in sorted(before.items()) if after.get(name) != status]
        found += [f"{slug}: {name} is new ({after[name]})"
                  for name in sorted(set(after) - set(before))]
        if now.get(slug, {}).get("intent_entries") != recorded[slug]["intent_entries"]:
            found.append(f"{slug}: the registry's intent entries moved")
    return found


def test_irl_8_archive_check_verdicts_unchanged():
    from archive import checkable_root
    recorded = json.loads(BEFORE.read_text(encoding="utf-8"))["issues"]
    assert len(recorded) == 16, sorted(recorded)
    now = archive_verdicts(checkable_root(), recorded)
    differences = verdict_differences(recorded, now)
    assert differences == [], "\n".join(differences)


# --- IRL-5 ----------------------------------------------------------------------------

def _flat(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def test_irl_5_assess_and_define_commands_name_the_intent():
    # `commands/assess.md` keeps to its 2,500-character budget and sends every change
    # that is not a quick fix to `approaches/assess-procedure.md`, so the assess
    # command's instruction to draft the intent is in the procedure it loads.
    assert "approaches/assess-procedure.md" in _flat("commands/assess.md")
    assess_text = _flat("approaches/assess-procedure.md")
    # From 7.0.0 the intent is drafted before the approach is written, so the
    # artifact rule RP-ART-002 reads it (ADR-070).
    for phrase in ("without `--write`",
                   "draft the intent before the write",
                   "`docs/compass/<created>-<slug>/intent.md`",
                   "from the issue description",
                   "`compass issue template show intent --depth <depth>`",
                   "`compass issue artifact set intent --status draft --path <that path>`"):
        assert phrase in assess_text, phrase
    define_text = _flat("commands/define.md").lower()
    for phrase in ("read `intent.md` and correct it before you write any scenario",
                   "present the intent with the scenarios at the define checkpoint"):
        assert phrase in define_text, phrase


# --- IRL-6 ----------------------------------------------------------------------------

LIGHT_INTENT = """# Intent - feature

## Problem

Cards do not show who is waiting.

## Desired outcome

- INT-1: A person sees who each card waits on.
- INT-2: A person sees how long it has waited.

## Success signals

- Fewer questions about who holds a card.

## Non-goals

- No notifications.
"""


def _orphaned(root):
    done = run(root, "analyze", "--issue", SLUG, "--json")
    assert done.returncode == 0, done
    findings = (json.loads(done.stdout).get("sections") or {}).get("findings") or []
    return [f for f in findings if f.get("type") == "orphaned-intent"]


def test_irl_6_analyze_reads_lightweight_intent(tmp_path):
    root = project(tmp_path)
    assert "verify.analyze" not in [g["id"] for g in manifest(root)["gates"]]
    register(root, "intent", status="draft", text=LIGHT_INTENT)
    set_keys(root, scenarios=[{"id": "X-1", "title": "A card shows its waiter",
                               "intent": "INT-3", "tests": []}])
    found = _orphaned(root)
    assert len(found) == 1, found
    assert "X-1" in json.dumps(found[0]) and "INT-3" in json.dumps(found[0]), found
    set_keys(root, scenarios=[{"id": "X-1", "title": "A card shows its waiter",
                               "intent": "INT-2", "tests": []}])
    assert _orphaned(root) == []

    verify_text = _flat("commands/verify.md")
    for phrase in ("run `compass analyze` on an issue that registers an intent",
                   "as `command-output` evidence for `verify.traceability`"):
        assert phrase in verify_text, phrase


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


def _named(heading):
    """A heading without a leading section number such as `6. `."""
    import re
    return re.sub(r"^\d+\.\s*", "", heading)


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
    # The neighbour is named by its text, numbered or not (the named sections dropped
    # the numbers).
    assert _named(headings[at - 1]) == "Decisions taken for the user", headings
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
    assert [_named(s) for s in sections[at - 1:at + 2]] == [
        "Decisions taken for the user", "Release line", "Gate"], sections
    assert_no_gh_call(root)


# --- IRL-9 ----------------------------------------------------------------------------

BOARD = "Board cards now show who is waiting on whom."


def check_row(root, name, slug=SLUG):
    done = run(root, "check", "--issue", slug, "--json")
    report = json.loads(done.stdout)
    rows = [c for c in report["checks"] if c["name"] == name]
    assert rows, [c["name"] for c in report["checks"]]
    return rows[0]


def test_irl_9_ship_commit_stores_release_line(tmp_path):
    root = project(tmp_path)
    write_report(root)
    ready_to_ship(root)
    assert "release_note" not in manifest(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG, "--release-note", BOARD)
    assert done.returncode == 0, done
    landed = manifest(root)
    assert landed.get("land_timestamp") and landed.get("status") == "done", landed
    assert landed["release_note"] == BOARD, landed
    land = landed["land_commit"]
    index = git(root, "show", f"{land}:docs/compass/README.md")
    row = [line for line in index.splitlines() if f"{SLUG}" in line and "|" in line]
    assert row and BOARD in row[0], index
    report = git(root, "show", f"{land}:{REPORT}")
    assert block(report, "release-line") == BOARD, report
    assert check_row(root, "rendered-blocks-current")["status"] == "pass"
    assert_no_gh_call(root)


# --- IRL-12 ---------------------------------------------------------------------------

PASS = ["--", sys.executable, "-c", "pass"]
FAIL = ["--", sys.executable, "-c", "import sys; sys.exit(1)"]


def declare_acceptance(root, slug=SLUG):
    done = run(root, "acceptance", "start", "--kind", "validation", "--issue", slug, *PASS)
    assert done.returncode == 0, done


def test_irl_12_acceptance_record_and_latest_write_wins(tmp_path):
    root = project(tmp_path / "a")
    declare_acceptance(root)
    # A failed acceptance run stores nothing.
    before = manifest_file(root).read_bytes()
    done = run(root, "acceptance", "record", "--issue", SLUG, "--release-note", "Other text.",
               *FAIL)
    assert done.returncode != 0, done
    assert manifest_file(root).read_bytes() == before
    done = run(root, "acceptance", "record", "--issue", SLUG, "--release-note", "First text.",
               *PASS)
    assert done.returncode == 0, done
    assert manifest(root)["release_note"] == "First text."
    ready_to_ship(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode == 0, done
    assert manifest(root).get("land_timestamp"), manifest(root)
    assert manifest(root)["release_note"] == "First text."

    # The same issue before landing, with the first text stored: the latest write wins,
    # and the output says which text it replaced.
    root = project(tmp_path / "b")
    set_keys(root, release_note="First text.")
    ready_to_ship(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG,
               "--release-note", "Second text.")
    assert done.returncode == 0, done
    assert manifest(root)["release_note"] == "Second text."
    replaced = [line for line in done.stdout.splitlines() if "replaced" in line]
    assert replaced == ["compass ship-commit: release line replaced (was: First text.)"], \
        done.stdout
    assert_no_gh_call(root)


# --- IRL-13 ---------------------------------------------------------------------------

def title_reason(root, text, slug=SLUG):
    """The reason `compass scenario add` gives for `text` as a title."""
    done = run(root, "scenario", "add", "X-1", "--title", text, "--intent", "INT-1",
               "--issue", slug)
    assert done.returncode != 0, done
    reason = done.stderr.split("title refused: ", 1)[1].strip()
    assert reason, done.stderr
    return reason


@pytest.mark.parametrize("command, text", [
    ("ship-commit", "Fixed in docs/no-such-file.md"),
    ("acceptance record", "Users now see the page in under a second")])
def test_irl_13_release_line_title_rules(tmp_path, command, text):
    root = project(tmp_path)
    ready_to_ship(root)
    set_keys(root, release_note="Stored text.")
    declare_acceptance(root)
    reason = title_reason(root, text)
    before = state(root)
    argv = (["ship-commit", "-m", "Ship it", "--issue", SLUG] if command == "ship-commit"
            else ["acceptance", "record", "--issue", SLUG])
    done = run(root, *argv, "--release-note", text, *([] if command == "ship-commit" else PASS))
    assert done.returncode != 0, done
    assert reason in " ".join(done.stderr.split()), (reason, done.stderr)
    assert state(root) == before
    assert manifest(root)["release_note"] == "Stored text."
    assert_no_gh_call(root)


# --- IRL-26 ---------------------------------------------------------------------------

HEADINGS = "the living spec reads a line such as ### <slug> (completed <date>) as one of its issue headings"


def derive(root):
    done = run(root, "_derive-system-spec", "--internal")
    assert done.returncode == 0, done
    return (root / "docs" / "system-spec.md").read_bytes()


def test_irl_26_heading_mark_refused_and_one_line_derived(tmp_path):
    root = project(tmp_path)
    # One scenario, so the living spec lists the issue once it lands.
    set_keys(root, scenarios=[{"id": "S-1", "title": "The board lists the cards",
                               "intent": "INT-1", "tests": []}])
    ready_to_ship(root)
    for text, expected in (("### other-issue (completed 2026-10-14)", HEADINGS),
                           ("  # Release", HEADINGS), ("   ", MISSING)):
        before = state(root)
        done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG, "--release-note", text)
        assert done.returncode != 0, (text, done)
        assert expected in " ".join(done.stderr.split()), (text, done.stderr)
        assert state(root) == before, text
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG, "--release-note",
               "  Adds the board.\nWith filters.  ")
    assert done.returncode == 0, done
    stored = manifest(root)["release_note"]
    assert stored == stored.strip() and stored.startswith("Adds the board."), stored

    first = derive(root)
    text = first.decode("utf-8")
    heading = next(line for line in text.splitlines() if line.startswith(f"### {SLUG} "))
    after = text.split(heading + "\n", 1)[1].lstrip("\n").splitlines()[0]
    assert after == "Adds the board. With filters.", text
    assert derive(root) == first
    assert_no_gh_call(root)


# --- IRL-14 ---------------------------------------------------------------------------

GREETING_TEST = (
    "import pathlib\n\n\n"
    "def test_{name}_says_hello():\n"
    "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / '{name}.txt'\n"
    "    assert p.read_text().strip() == 'Hello, %s!'\n")


def greet_command(name, marker=None):
    """The test command of the quick fix `name`. With `marker`, it first writes that
    file, so a test can tell whether it ran."""
    test = f"tests/test_{name}.py::test_{name}_says_hello"
    if marker is None:
        return ["--", sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", test]
    script = (f"import pathlib, subprocess, sys; pathlib.Path({marker!r}).write_text('ran'); "
              f"sys.exit(subprocess.call([sys.executable, '-m', 'pytest', '-q', '-p', "
              f"'no:cacheprovider', {test!r}]))")
    return ["--", sys.executable, "-c", script]


def quick_fix(root, slug, name):
    """A started quick fix with its red on record and the fix written: the state
    `quick-fix finish` lands from."""
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / f"{name}.txt").write_text("Hi, %s!")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / f"test_{name}.py").write_text(GREETING_TEST.format(name=name))
    # Every file is committed first: finish never commits a path that was already
    # changed or untracked when the quick fix started.
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", name)
    done = run(root, "quick-fix", "start", slug,
               "--risk", "trivial - a one-line text change",
               "--familiarity", "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one file, one obvious change",
               "--intent", "The greeting says hello.",
               "--scenario", "Given the greeting, when it is read, then it says hello.",
               "--scenario-id", "QF-1",
               "--test", f"tests/test_{name}.py::test_{name}_says_hello")
    assert done.returncode == 0, done
    done = run(root, "tdd-red", "--issue", slug, "--scenario", "QF-1", *greet_command(name))
    assert done.returncode == 0, done
    (root / "data" / f"{name}.txt").write_text("Hello, %s!")
    return slug


def note_path(root, slug):
    body = manifest(root, slug)
    return f"docs/compass/{body['created']}-{slug}/verification-note.md"


def test_irl_14_quick_fix_finish_release_line(tmp_path):
    root = repo(tmp_path)
    slug = quick_fix(root, "fix-greeting", "greeting")
    done = run(root, "quick-fix", "finish", "--issue", slug, "-m", "Fix the greeting",
               "--release-note", "Greetings now say hello.", *greet_command("greeting"))
    assert done.returncode == 0, done
    landed = manifest(root, slug)
    assert landed.get("land_timestamp") and landed["release_note"] == "Greetings now say hello."
    note = git(root, "show", f"{landed['land_commit']}:{note_path(root, slug)}")
    assert "Release: Greetings now say hello." in note, note

    slug = quick_fix(root, "fix-farewell", "farewell")
    before = manifest_file(root, slug).read_bytes()
    marker = root / "ran.txt"
    done = run(root, "quick-fix", "finish", "--issue", slug, "-m", "Fix the farewell",
               *greet_command("farewell", marker=str(marker)))
    assert done.returncode != 0, done
    assert "--release-note" in done.stderr and MISSING in done.stderr, done.stderr
    assert not marker.exists(), "the test command ran before the refusal"
    assert manifest_file(root, slug).read_bytes() == before
    assert not (root / note_path(root, slug)).exists()
    assert not list((root / ".compass" / "work" / slug / "evidence").glob("green-*"))
    assert_no_gh_call(root)


# --- IRL-24 ---------------------------------------------------------------------------

def test_irl_24_landed_issue_not_refused_or_rewritten(tmp_path):
    root = project(tmp_path)
    ready_to_ship(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG, "--release-note", BOARD)
    assert done.returncode == 0, done
    # A completed issue at a generation that declares the field, with no line: every
    # issue landed before this change looks like this.
    set_keys(root, release_note=ABSENT)
    first_land = manifest(root)["land_commit"]

    # A review fix on top of the landing, its green re-recorded, nothing staged.
    (root / "src" / "new.py").write_text("y = 2\n")
    git(root, "add", "src/new.py")
    git(root, "commit", "-q", "-m", "review fix")
    done = run(root, "tdd-green", "--issue", SLUG, "--", sys.executable, "-c", "pass")
    assert done.returncode == 0, done
    done = run(root, "ship-commit", "-m", "Land again", "--issue", SLUG)
    output = done.stdout + done.stderr
    assert done.returncode == 0, done
    assert "landed at HEAD" in done.stdout, done.stdout
    assert "release line" not in output and "release-line" not in output, output
    landed = manifest(root)
    assert landed["land_commit"] != first_land and "release_note" not in landed, landed

    # Landing it again at HEAD with --release-note is refused: a landed record is not
    # rewritten, and nothing moves.
    before = state(root)
    done = run(root, "ship-commit", "-m", "Land again", "--issue", SLUG,
               "--release-note", "Late text.")
    assert done.returncode != 0, done
    assert f"'{SLUG}' is completed" in done.stderr, done.stderr
    assert state(root) == before and "release_note" not in manifest(root)

    declare_acceptance(root)
    done = run(root, "acceptance", "record", "--issue", SLUG, "--release-note", "Late text.",
               *PASS)
    assert done.returncode != 0, done
    assert f"'{SLUG}' is completed" in done.stderr, done.stderr
    assert "release_note" not in manifest(root)

    set_keys(root, close_reason="not-planned")
    before = manifest_file(root).read_bytes()
    done = run(root, "acceptance", "record", "--issue", SLUG, "--release-note", "Late text.",
               *PASS)
    assert done.returncode != 0, done
    assert f"'{SLUG}' is closed" in done.stderr, done.stderr
    assert manifest_file(root).read_bytes() == before
    assert_no_gh_call(root)


# --- IRL-27 ---------------------------------------------------------------------------

#: `compass acceptance record --release-note "Second text."` run in-process, with the
#: test hook set: after the writer's first read, it sets another key and a different
#: release line on disk. argv: the cli folder to import, the project, the slug.
LOCKED_WRITE_RUN = r"""
import argparse, os, sys
sys.path.insert(0, sys.argv[1])
import compass_pkg  # noqa: F401 - the bundled PyYAML first
import yaml
from compass_pkg import release_line, tdd

root, slug = sys.argv[2], sys.argv[3]
os.chdir(root)


def hook(task_dir):
    path = os.path.join(task_dir, "manifest.yml")
    body = yaml.safe_load(open(path, encoding="utf-8"))
    body["follow_ups"] = [{"id": "FU-HOOK", "summary": "set by the hook"}]
    body["release_note"] = "Disk text."
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(body, fh, sort_keys=False)


release_line.AFTER_FIRST_READ = hook
tdd.cmd_acceptance_record(argparse.Namespace(
    task=slug, scenario=None, command=[sys.executable, "-c", "pass"],
    release_note="Second text.", _mode="summary", json=False, evidence_out=None))
"""


def locked_write(root, cli_folder):
    """Run the in-process write against `cli_folder`; returns the process and the
    manifest it left."""
    declare_acceptance(root)
    set_keys(root, release_note="First text.")
    done = subprocess.run([sys.executable, "-c", LOCKED_WRITE_RUN, str(cli_folder), str(root),
                           SLUG], capture_output=True, text=True, env=env(root), timeout=300)
    return done, manifest(root)


def locked_write_holds(done, body):
    replaced = [line for line in done.stdout.splitlines() if "replaced" in line]
    return (done.returncode == 0 and body.get("release_note") == "Second text."
            and body.get("follow_ups") == [{"id": "FU-HOOK", "summary": "set by the hook"}]
            and replaced == ["compass acceptance record: release line replaced "
                             "(was: Disk text.)"])


def test_irl_27_locked_reread_keeps_other_write(tmp_path):
    import shutil
    root = project(tmp_path / "real")
    done, body = locked_write(root, ROOT / "cli")
    assert locked_write_holds(done, body), (done, body)

    # With the re-read inside the lock removed in a copy, the same run fails: the
    # writer keeps its first read and loses the hook's change.
    copy = tmp_path / "planted" / "cli"
    shutil.copytree(ROOT / "cli", copy, ignore=shutil.ignore_patterns("__pycache__"))
    module = copy / "compass_pkg" / "release_line.py"
    source = module.read_text(encoding="utf-8")
    assert source.count("current = load_yaml(path)") == 1, "the re-read moved"
    module.write_text(source.replace("current = load_yaml(path)", "current = dict(task)"),
                      encoding="utf-8")
    root = project(tmp_path / "plant")
    done, body = locked_write(root, copy)
    assert not locked_write_holds(done, body), (done, body)


# --- IRL-11 ---------------------------------------------------------------------------

def test_irl_11_spike_and_issueless_commit_not_refused(tmp_path):
    root = project(tmp_path / "spike", "spike")
    assert "release_line" not in generation_config(root)["approaches"]["spike"]
    register(root, "spike-conclusion", text="# Spike conclusion\n\nThe question is answered.\n")
    ready_to_ship(root)
    from compass_pkg import release_line
    task_dir = str(root / ".compass" / "work" / SLUG)
    assert release_line.landing_refusal(manifest(root), task_dir) is None
    done = run(root, "ship-commit", "-m", "Conclude the spike", "--issue", SLUG)
    output = done.stdout + done.stderr
    assert "release line" not in output and "release-line" not in output, output
    assert done.returncode == 0, done

    root = repo(tmp_path / "plain")
    (root / "notes.txt").write_text("a note\n")
    git(root, "add", "notes.txt")
    head = git(root, "rev-parse", "HEAD")
    done = run(root, "ship-commit", "-m", "Add a note")
    output = done.stdout + done.stderr
    assert done.returncode == 0, done
    assert git(root, "rev-parse", "HEAD") != head
    assert "release line" not in output and "release-line" not in output, output
    assert_no_gh_call(root)


# --- IRL-4 ----------------------------------------------------------------------------

def _before_this_change(resolved):
    """The regular approach as the shipped default held it before this change."""
    entry = resolved["approaches"]["regular"]
    entry.pop("release_line", None)
    entry["artifacts"].pop("intent", None)


def predating_issue(tmp_path):
    """An open regular issue at generation 1, stored before this change: no intent in its
    registry and no `release_line` in its stored configuration."""
    root = project(tmp_path)
    rewrite_stored(root, _before_this_change)
    body = manifest(root)
    body["artifacts"] = [a for a in body["artifacts"] if a.get("kind") != "intent"]
    write_manifest(root, body)
    assert manifest(root)["generation"] == 1
    return root


def _names(text):
    flat = " ".join(text.split())
    return [word for word in ("intent", "release line", "release-line", "release_line")
            if word in flat]


def test_irl_4_assessed_regular_owes_no_intent_until_reassessed(tmp_path):
    root = predating_issue(tmp_path / "a")
    ready_to_ship(root)
    done = run(root, "check", "--issue", SLUG, "--json")
    report = json.loads(done.stdout)
    # A check's detail names the kind `intent` or the release line only when it judges
    # them; the check `scenario-has-id-and-intent` is about a scenario's intent id.
    named = [c for c in report["checks"] if _names(str(c.get("detail") or ""))]
    assert not named, named
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode == 0, done
    assert not _names(done.stdout + done.stderr), done
    assert manifest(root).get("land_timestamp")

    root = predating_issue(tmp_path / "b")
    done = run(root, "approach", "evaluate", "--issue", SLUG, "--write", "--reason",
               "the new shipped default")
    assert done.returncode == 0, done
    body = manifest(root)
    assert body["generation"] == 2, body.get("generation")
    entries = _entries(root, "intent")
    assert [(e.get("status"), e.get("depth")) for e in entries] == [("draft", "lightweight")], \
        entries
    register(root, "intent", text="# Intent\n\n## Problem\n\nA problem.\n")
    ready_to_ship(root)
    before = state(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode != 0, done
    assert MISSING in done.stderr, done.stderr
    assert state(root) == before
    assert_no_gh_call(root)


# --- IRL-7 ----------------------------------------------------------------------------

def test_irl_7_unwritten_intent_refused_at_landing(tmp_path):
    root = project(tmp_path)
    ready_to_ship(root, skip=("intent",))
    set_keys(root, release_note=BOARD)
    assert [not e.get("path") for e in _entries(root, "intent")] == [True]
    before = state(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode != 0, done
    flat = " ".join(done.stderr.split())
    assert "artifacts-approved" in flat and "intent" in flat, flat
    assert 'compass issue artifact set intent --status omitted --reason "<why>"' in flat, flat
    assert "compass issue artifact set intent" in flat and "--path" in flat, flat
    assert state(root) == before
    assert_no_gh_call(root)


# --- IRL-21 ---------------------------------------------------------------------------

ADR = ROOT / "architecture" / "decisions"


def test_irl_21_key_and_verb_documented(tmp_path):
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    assert schema["properties"]["release_note"]["type"] == "string", schema["properties"].get(
        "release_note")
    assert "release_note" not in (schema.get("required") or [])

    done = subprocess.run([sys.executable, str(CLI), "release", "notes", "--help"],
                          cwd=tmp_path, capture_output=True, text=True, env=env(tmp_path))
    assert done.returncode == 0, done
    help_text = " ".join(done.stdout.split())
    assert "--since" in help_text, help_text
    assert "landing time" in help_text, help_text
    assert "no release line" in help_text and "placed" in help_text, help_text

    # The owning doc of the release line, and of the refusal `ship-commit` runs.
    doc = _flat("docs/release-line.md")
    for phrase in ("release-line-missing", "--release-note", "The latest write wins",
                   "not completed and not closed", "`generation` key", "`release_line: true`",
                   "names the issue"):
        assert phrase in doc, phrase

    catalogue = (ROOT / "docs" / "artifact-catalogue.md").read_text().splitlines()
    assert "- `intent`, lightweight: Problem; Desired outcome; Success signals; Non-goals" \
        in catalogue
    report = next(line for line in catalogue if line.startswith("- `verification-report`,"))
    assert "Decisions taken for the user; Release line; Gate" in report, report

    records = sorted(ADR.glob("ADR-065-*.md"))
    assert len(records) == 1, records
    assert "status: accepted" in records[0].read_text().split("---")[1]
    index = (ADR / "README.md").read_text()
    # The index rows, by the record each row links in its first cell.
    listed = [int(n) for n in __import__("re").findall(r"(?m)^\| \[ADR-(\d{3})\]", index)]
    assert 65 in listed and listed == sorted(listed), listed


# --- IRL-28 ---------------------------------------------------------------------------

#: `rendered_blocks.KINDS` at 5079cef6.
KINDS_BEFORE = ("coverage", "gates", "dod", "dor", "artifacts", "evidence", "follow-ups",
                "decisions-taken", "header", "ask", "decision-required", "acceptance", "related",
                "decisions", "traceability", "deliberately-omitted", "verification-note",
                "index", "assessment", "policy-rules", "stage-weights", "gate-set", "plan-exit",
                "breakdown-exit", "readiness")


def _owning_row(table, module):
    rows = [line for line in table.splitlines() if line.startswith("|") and module in line]
    assert len(rows) == 1, (module, rows)
    return rows[0].rsplit("|", 2)[1].strip()


def test_irl_28_shared_files_hold_both_entries():
    from compass_pkg import record_triggers, rendered_blocks
    assert set(KINDS_BEFORE) <= set(rendered_blocks.KINDS)
    assert "release-line" in rendered_blocks.KINDS
    for command in ("cmd_land_commit", "cmd_acceptance_record"):
        assert command in record_triggers.RENDER_TRIGGERS, command

    import test_cli_renames
    assert test_cli_renames.EXCEPTIONS.get("release notes"), test_cli_renames.EXCEPTIONS
    env_vars = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_cli_renames.py::test_vr_e10_every_registered_verb_follows_the_convention"
         "_or_is_a_named_exception",
         "tests/test_rendered_blocks_check.py::test_dcj_75_trigger_table_complete",
         "tests/test_rendered_blocks_check.py::test_dcj_18_every_command_in_the_table_renders"
         "_the_named_issue"],
        cwd=ROOT, capture_output=True, text=True, env=env_vars, timeout=600)
    assert done.returncode == 0, done.stdout[-2000:]

    table = (ROOT / "docs" / "README.md").read_text().split("## Owning docs", 1)[1]
    assert _owning_row(table, "`cli/compass_pkg/release_line.py`") == "`docs/release-line.md`"
    assert _owning_row(table, "`cli/compass_pkg/release_notes.py`") == "`docs/release-notes.md`"

    upgrade = (ROOT / "docs" / "upgrade-7-0-0.md").read_text()
    assert "\n## The lightweight intent and the release line\n" in upgrade


# --- IRL-30 ---------------------------------------------------------------------------

def _documented(path, starts):
    """The one command line in `path` that starts with `starts`."""
    lines = [line.strip() for line in (ROOT / path).read_text().splitlines()
             if line.strip().startswith(starts)]
    assert len(lines) == 1, (path, starts, lines)
    return lines[0]


def _argv(line, fills):
    """A documented command line as an argument list, with its placeholders filled."""
    import shlex
    for placeholder, value in fills.items():
        line = line.replace(placeholder, value)
    assert "<" not in line, line
    return shlex.split(line)[1:]


def test_irl_30_documented_quick_fix_flow_lands(tmp_path):
    # The ship command tells a person to give the release line on ship-commit.
    ship = " ".join((ROOT / "commands" / "ship.md").read_text().split())
    assert '--release-note "<text written for a user>"' in ship, "commands/ship.md"
    for given in (True, False):
        root = repo(tmp_path / str(given))
        slug = quick_fix(root, "fix-greeting", "greeting")
        test = greet_command("greeting")[1:]
        finish = _documented("commands/quick-fix.md", "compass quick-fix finish")
        argv = _argv(finish, {"<commit message>": "Fix the greeting",
                              "<test command>": " ".join(test),
                              "<line>": "Greetings now say hello."})
        if not given:
            # With --no-commit the line is the person's to give now or at the commit.
            at = argv.index("--release-note")
            del argv[at:at + 2]
        cut = argv.index("--")
        done = run(root, *argv[:cut], "--issue", slug, *argv[cut:])
        assert done.returncode == 0, done
        printed = next(line for line in done.stdout.splitlines() if "compass ship-commit" in line)
        command = printed.split("`")[1]
        assert ("--release-note" in command) is not given, command
        git(root, "add", "-A")
        done = run(root, *_argv(command, {"<message>": "Fix the greeting",
                                          "<release line>": "Greetings now say hello."}))
        assert done.returncode == 0, done
        assert "[release-line-missing]" not in done.stderr
        landed = manifest(root, slug)
        assert landed.get("land_timestamp") and landed["release_note"] == "Greetings now say hello."
        assert_no_gh_call(root)
    upgrade = " ".join((ROOT / "docs" / "upgrade-7-0-0.md").read_text().split())
    section = upgrade.split("## The lightweight intent and the release line")[1]
    assert "compass quick-fix finish" in section and "--no-commit" in section, section


# --- IRL-31 ---------------------------------------------------------------------------

def test_irl_31_merge_keeps_both_features():
    """After the merge with the named document sections, both features' block kinds and
    the report's named headings with the release line are in place."""
    from compass_pkg import rendered_blocks
    for kind in ("release-line", "document-header", "dependencies", *KINDS_BEFORE):
        assert kind in rendered_blocks.KINDS, kind
    sections = yaml.safe_load((PRESET / "artifacts.yml").read_text())["artifacts"][
        "verification-report"]["sections"]["thorough"]
    assert sections[-3:] == ["Decisions taken for the user", "Release line", "Gate"], sections
    assert not [s for s in sections if s[:1].isdigit()], sections
