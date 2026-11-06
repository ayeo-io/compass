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

Scenario ids: IRL-1 to IRL-5, IRL-7 to IRL-15, IRL-21 to IRL-24 and IRL-26 to IRL-28, in
the acceptance criteria of the issue `intent-and-release-line`. Each test name starts with
its id. IRL-6 tested `compass analyze`, which 9.0.0 removed (ADR-091).
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
    body = manifest(root, slug)
    if approach == "spike":
        assert body["delivery_approach"] == "spike", body
    else:
        # The four-stage path stores `delivery` and the evidence the assessment owes,
        # in place of the 8.x approach (ADR-092 decisions 2 and 3).
        assert body["delivery_approach"] == "delivery", body
        assert body["evidence_required"] and "stages" not in body, body
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


# --- IRL-23 ---------------------------------------------------------------------------

PRESET = ROOT / "governance" / "presets" / "default"

#: The digest of the locked spike entry's parsed content: sha256 over its JSON with
#: sorted keys. 9.0.0 took its `artifacts:` map out (ADR-091), and its stage map now
#: names the path stages it runs, assess, build and ship (ADR-092); nothing else in
#: the entry moved.
SPIKE_DIGEST = "da78de1e9c3f5a303cf2599deaa1f916f614abdb624a525b2a7ee88dcc0bf656"


def _entry_digest(entry):
    import hashlib
    return hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()


def _lint_codes(root):
    done = run(root, "policy", "lint", "--file", "compass.yml", "--json")
    report = json.loads(done.stdout)
    return done, [(f.get("code"), f.get("path")) for f in report.get("findings") or []]


def test_irl_23_default_declares_release_line(tmp_path):
    approaches = yaml.safe_load((PRESET / "approaches.yml").read_text())["approaches"]
    # The shipped default's one approach that ships is the path (ADR-092).
    assert set(approaches) == {"delivery", "spike"}
    assert approaches["delivery"].get("release_line") is True, approaches["delivery"]
    assert "release_line" not in approaches["spike"], approaches["spike"]

    # The locked spike entry is as it was: its digest over the parsed entry has not moved.
    assert _entry_digest(approaches["spike"]) == SPIKE_DIGEST, approaches["spike"]

    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text())
    approach_props = _approach_properties(schema)
    assert approach_props["release_line"] == {"type": "boolean"} or \
        approach_props["release_line"].get("type") == "boolean", approach_props["release_line"]

    # Since 9.0.0 a project's own file cannot change an approach (ADR-092): lint names
    # the key with the one warning and reports no error, whatever the value.
    root = repo(tmp_path / "set")
    for value in (True, False):
        (root / "compass.yml").write_text(yaml.safe_dump(dict(
            AUTONOMOUS, approaches={"regular": {"set": {"release_line": value}}})))
        done, codes = _lint_codes(root)
        assert [c for c in codes if c[0] and c[0][0] in "LMCK"] == [
            ("L-SETTING-REMOVED", "approaches")], (value, codes, done.stdout)

    # A git parent still can. Setting it true there is no change; setting it false on
    # delivery is a loosening that needs a waiver.
    from compass_pkg import policy_lint
    from compass_pkg.layers import Layer
    shipped, _ = policy_lint.load_parent()
    for value, loosening in ((True, False), (False, True)):
        team = Layer("team", "parent", {"schema": 1, "approaches": {"delivery": {"set": {
            "release_line": value}}}}, "d")
        report = policy_lint.lint_chain(shipped, None, extra_parents=(team,))
        codes = [(f.code, f.path) for f in report.findings]
        assert (("C-LOOSENING", "approaches.delivery.release_line") in codes) is loosening, (
            value, codes)
        if not loosening:
            assert not [c for c in codes if c[0][0] in "LMCK"], codes

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



# --- IRL-2 ----------------------------------------------------------------------------



def _named(heading):
    """A heading without a leading section number such as `6. `."""
    import re
    return re.sub(r"^\d+\.\s*", "", heading)


# --- landing an issue -------------------------------------------------------------------

#: The texts of the release-line refusals, as a reader sees them.
MISSING = "has no release line"
FLAG = '--release-note "<text written for a user>"'


def register(root, kind, status="approved", slug=SLUG, text=None):
    """Write the document, unless it exists, and register it."""
    path = Path(root) / DOCS / f"{kind}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if text is not None or not path.exists():
        # A multiagent breakdown refuses a map with no `units:` line (ADR-071).
        units = "\nunits: 2\n" if kind == "distribution-map" else ""
        path.write_text(text if text is not None else f"# {kind}\n\nFirst version.\n{units}")
    # 9.0.0 removed `compass issue artifact set` (ADR-091), so the entry is written as an
    # older release wrote it.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import document_registry
    return document_registry.register(Path(root) / ".compass" / "work" / slug, kind,
                                      f"{DOCS}/{kind}.md", status)


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
    # A quick fix in scope of the four-layer acceptance strategy records the outer
    # loop by default, and its green names a candidate and a client (ADR-085). On
    # the path the quick fix is the light row, routed to the existing DSL (ADR-092).
    held = manifest(root, slug)
    light = (held.get("delivery_approach") == "quick-fix"
             or (held.get("acceptance_strategy") or {}).get("routing") == "existing-dsl")
    named = ("--loop", "outer", "--candidate", "local", "--client", "cli") if light else ()
    done = run(root, "tdd-green", "--issue", slug, *named, "--", sys.executable, "-c", "pass")
    assert done.returncode == 0, done
    _meet_path_records(root, slug)
    git(root, "add", path)


def _meet_path_records(root, slug):
    """On the four-stage path the standard and defect rows owe the Definition of Done,
    and `scenario-approval` lists the specify checkpoint (ADR-092 decisions 3 and 6).
    Record each Definition of Done item with typed evidence and give each listed
    checkpoint a person's outcome, as the gates above are passed, so the landing
    reaches the refusal a test is about."""
    from compass_pkg import effective, item_records
    task_dir = root / ".compass" / "work" / slug
    body = manifest(root, slug)
    if "definition-of-done" in (body.get("evidence_required") or []):
        view = effective.view_or_legacy(str(task_dir), manifest=body)
        (task_dir / "evidence").mkdir(exist_ok=True)
        (task_dir / "evidence" / "dod.txt").write_text("1 passed\n")
        for n, item in enumerate(item_records.items(body, str(task_dir), view, "dod")):
            done = run(root, "evidence", "add", f"EV-DOD-{n + 1}", "--issue", slug,
                       "--type", "command-output", "--path", "evidence/dod.txt",
                       "--meets", item.check)
            assert done.returncode == 0, done
    body = manifest(root, slug)
    have = {e.get("stage") for e in body.get("checkpoint_outcomes") or []}
    for stage in body.get("checkpoints") or []:
        if stage not in have and "checkpoint_outcomes" in body:
            body["checkpoint_outcomes"].append({
                "stage": stage, "outcome": "waited", "by": "jed72",
                "at": "2026-10-10T09:00:00Z", "evidence": "EV-CP-" + stage})
    write_manifest(root, body, slug)


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
    # Every delivery assessment is stored as `delivery` (ADR-092).
    assert generation_config(root)["approaches"]["delivery"]["release_line"] is True
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
    # A path issue has no approach entry of its own: it owes a line when any
    # approach that ships sets the field (ADR-092), so the field changes on each.
    def change(resolved):
        for name, body in resolved["approaches"].items():
            if body.get("ships", True):
                _approach_field(resolved, name, value)

    def apply(root):
        rewrite_stored(root, change)
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


def block(text, kind):
    """The body of the one rendered block of `kind` in `text`."""
    opening, closing = f"<!-- compass:render {kind} -->", "<!-- /compass:render -->"
    assert text.count(opening) == 1, (kind, text)
    return text.split(opening, 1)[1].split(closing, 1)[0].strip("\n")


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

    ready_to_ship(root)
    assert "release_note" not in manifest(root)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG, "--release-note", BOARD)
    assert done.returncode == 0, done
    landed = manifest(root)
    assert landed.get("land_timestamp") and landed.get("status") == "done", landed
    assert landed["release_note"] == BOARD, landed
    assert landed["land_commit"]
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

HEADINGS = ("compass release notes prints the line under a heading such as ### <slug> "
            "(completed <date>), where it would read as a heading of its own")


def test_irl_26_heading_mark_refused_and_the_line_stored_trimmed(tmp_path):
    root = project(tmp_path)
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
               "--release-note", "Greetings now say hello.", "--candidate", "local",
               "--client", "cli", *greet_command("greeting"))
    assert done.returncode == 0, done
    landed = manifest(root, slug)
    assert landed.get("land_timestamp") and landed["release_note"] == "Greetings now say hello."

    slug = quick_fix(root, "fix-farewell", "farewell")
    before = manifest_file(root, slug).read_bytes()
    marker = root / "ran.txt"
    done = run(root, "quick-fix", "finish", "--issue", slug, "-m", "Fix the farewell",
               "--candidate", "local", "--client", "cli",
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


# --- IRL-7 ----------------------------------------------------------------------------

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

    catalogue = (ROOT / "docs" / "artifact-catalog.md").read_text().splitlines()
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
    from compass_pkg import record_triggers
    for command in ("cmd_land_commit", "cmd_acceptance_record"):
        assert command in record_triggers.RECORD_TRIGGERS, command

    import test_cli_renames
    assert test_cli_renames.EXCEPTIONS.get("release notes"), test_cli_renames.EXCEPTIONS
    env_vars = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "tests/test_cli_renames.py::test_vr_e10_every_registered_verb_follows_the_convention"
         "_or_is_a_named_exception",
         "tests/test_record_triggers.py::test_dcj_75_trigger_table_complete"],
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
                              "<line>": "Greetings now say hello.",
                              "<build>": "local", "<client>": "cli"})
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
    # The live default declares no document kind since 9.0.0 (ADR-091); the frozen
    # 7.0.0 preset keeps the report's headings.
    frozen = ROOT / "governance" / "presets" / "default@7" / "artifacts.yml"
    sections = yaml.safe_load(frozen.read_text())["artifacts"][
        "verification-report"]["sections"]["thorough"]
    assert sections[-3:] == ["Decisions taken for the user", "Release line", "Gate"], sections
    assert not [s for s in sections if s[:1].isdigit()], sections


# --- IRL-32 ---------------------------------------------------------------------------

def test_irl_32_upgrade_guide_covers_a_replaced_approach():
    """Scenario id: `TRC-001` in upgrade-guide-replaced-approach/acceptance-criteria.md.
    The upgrade guide tells a project that replaced a shipping approach what to add,
    and the release-line document no longer says a 5.x project owes no line or that a
    landing with no `--issue` is always refused."""
    upgrade = " ".join((ROOT / "docs" / "upgrade-7-0-0.md").read_text().split())
    section = upgrade.split("## The lightweight intent and the release line")[1].split(" ## ")[0]
    for word in ("`release_line: true`", "`intent`", "replaced", "waiver", "`compass policy lint`"):
        assert word in section, word
    line = " ".join((ROOT / "docs" / "release-line.md").read_text().split())
    assert "has no generation and owes no line" not in line
    assert "with no issue named is refused" not in line
    assert "a commit with no issue named is not judged" not in line
