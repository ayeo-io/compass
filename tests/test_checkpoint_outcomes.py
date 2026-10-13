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


# --- the quick fix -----------------------------------------------------------------

GREETING_TEST = (
    "import pathlib\n\n\n"
    "def test_greeting_says_hello():\n"
    "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'greeting.txt'\n"
    "    assert p.read_text().strip() == 'Hello, %s!'\n")
GREET_CMD = ["--", sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "tests/test_greeting.py::test_greeting_says_hello"]


def quick_fix(root, slug="fix-greeting", cli=CLI):
    """A started quick fix with its red on record and the fix written: the
    state `quick-fix finish` lands from."""
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "greeting.txt").write_text("Hi, %s!")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_greeting.py").write_text(GREETING_TEST)
    git(root, "add", "data/greeting.txt", "tests/test_greeting.py")
    git(root, "commit", "-q", "-m", "greeting")
    done = run(root, "quick-fix", "start", slug,
               "--risk", "trivial - a one-line text change",
               "--familiarity", "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one file, one obvious change",
               "--intent", "The greeting says hello.",
               "--scenario", "Given the greeting, when it is read, then it says hello.",
               "--scenario-id", "QF-1",
               "--test", "tests/test_greeting.py::test_greeting_says_hello", cli=cli)
    assert done.returncode == 0, done
    done = run(root, "tdd-red", "--issue", slug, "--scenario", "QF-1", *GREET_CMD, cli=cli)
    assert done.returncode == 0, done
    (root / "data" / "greeting.txt").write_text("Hello, %s!")
    return slug


# --- ARC-4 ------------------------------------------------------------------------

def test_arc_4_skip_refusals(tmp_path):
    root = project(tmp_path)
    refine_done(root)
    assert approve(root, "define").returncode == 0
    cases = [
        (("plan", "spec-author", "skipped"), "plan is a listed checkpoint, so it waits for a person"),
        (("define", "spec-author", "skipped"), "define already holds a waited outcome"),
        (("implement", "builder", "skipped"), "'implement' is not a checkpoint stage"),
        (("refine", "jed72", "skipped"), "--by must name an agent"),
        (("refine", "spec-author", "waited"), "only a person's approval records waited"),
    ]
    for (stage, by, outcome), cause in cases:
        before = manifest_file(root).read_bytes()
        done = run(root, "issue", "checkpoint", "add", stage, "--outcome", outcome,
                   "--by", by, "--issue", SLUG)
        assert done.returncode == 2, (stage, done)
        assert cause in done.stderr, (stage, done.stderr)
        assert manifest_file(root).read_bytes() == before, stage
        if stage == "plan" or outcome == "waited":
            assert f"compass evidence approve --checkpoint {stage}" in done.stderr, done.stderr

    slug = quick_fix(root)
    before = manifest_file(root, slug).read_bytes()
    done = run(root, "issue", "checkpoint", "add", "refine", "--outcome", "skipped",
               "--by", "builder", "--issue", slug)
    assert done.returncode == 2, done
    assert "the route runs no refine hand-off" in done.stderr, done.stderr
    assert manifest_file(root, slug).read_bytes() == before

    # An issue assessed before outcomes were recorded is not judged: the verb
    # refuses it and does not add the key.
    body = manifest(root)
    body.pop("checkpoint_outcomes")
    write_manifest(root, body)
    before = manifest_file(root).read_bytes()
    done = skip(root, "refine")
    assert done.returncode == 2, done
    assert "is not judged and takes no outcome; nothing was written" in done.stderr, done
    assert manifest_file(root).read_bytes() == before
    assert_no_gh_call(root)


# --- ARC-1 ------------------------------------------------------------------------

def _define_done(root):
    """The records show define complete and refine not started."""
    register(root, "acceptance-criteria")


def test_arc_1_person_answers_a_checkpoint(tmp_path):
    root = project(tmp_path)
    _define_done(root)
    body = manifest(root)
    assert body["checkpoints"] == ["define", "plan"] and body["checkpoint_outcomes"] == []
    before = manifest(root)

    done = approve(root, "define")
    assert done.returncode == 0, done
    after = manifest(root)
    added = after["evidence"][len(before["evidence"]):]
    assert after["evidence"][:len(before["evidence"])] == before["evidence"]
    assert len(added) == 1, added
    record = added[0]
    assert record["type"] == "checkpoint-approval", record
    assert {k: v for k, v in record.items() if k not in ("id", "timestamp")} == {
        "type": "checkpoint-approval", "checkpoint": "define", "approver": "jed72",
        "role": "product-owner", "scope": "the define hand-off", "decision": "approved",
        "issue": SLUG, "generation": before["generation"]}, record
    assert "check" not in record
    _utc(record["timestamp"])
    assert not [e for e in after["evidence"] if e.get("type") == "human-approval"]
    assert after["checkpoint_outcomes"] == [{
        "stage": "define", "outcome": "waited", "by": "jed72",
        "at": record["timestamp"], "evidence": record["id"]}]
    unchanged = {k: v for k, v in before.items() if k not in ("evidence", "checkpoint_outcomes")}
    assert {k: v for k, v in after.items() if k in unchanged} == unchanged
    assert set(after) == set(before)
    assert not schema_errors(after), schema_errors(after)
    assert_no_gh_call(root)


# --- ARC-2 ------------------------------------------------------------------------

def test_arc_2_approve_checkpoint_refusals(tmp_path):
    root = project(tmp_path)
    _define_done(root)
    slug = quick_fix(root)
    cases = [
        ("no terminal", dict(stage="define", terminal=False), "needs a terminal"),
        ("agent", dict(stage="define", approver="agent"), "an agent cannot approve"),
        ("not listed", dict(stage="define", approver="sam"),
         "sam is not an approver of this project"),
        ("not a checkpoint", dict(stage="implement"), "'implement' is not a checkpoint stage"),
        ("quick fix refine", dict(stage="refine", slug=slug),
         "the route runs no refine hand-off"),
        ("plan not run", dict(stage="plan"), "plan has not run"),
        ("rejected", dict(stage="define", extra=("--decision", "rejected")),
         "--checkpoint records an approval only"),
    ]
    for name, case, cause in cases:
        target = case.get("slug", SLUG)
        before = manifest_file(root, target).read_bytes()
        done = approve(root, case["stage"], *case.get("extra", ()),
                       approver=case.get("approver", "jed72"), slug=target,
                       terminal=case.get("terminal", True))
        assert done.returncode == 2, (name, done)
        assert cause in done.stderr, (name, done.stderr)
        assert manifest_file(root, target).read_bytes() == before, name

    (manifest_file(root).parent / "devlog.md").write_text("# Devlog\n")
    before = manifest_file(root).read_bytes()
    done = run(root, "evidence", "add", "EV-X", "--type", "checkpoint-approval",
               "--path", "devlog.md", "--issue", SLUG)
    assert done.returncode == 2, done
    assert "compass evidence approve --checkpoint" in done.stderr, done.stderr
    assert manifest_file(root).read_bytes() == before

    # An issue assessed before outcomes were recorded is not judged: the answer
    # is refused and the key is not added.
    body = manifest(root)
    body.pop("checkpoint_outcomes")
    write_manifest(root, body)
    before = manifest_file(root).read_bytes()
    done = approve(root, "define")
    assert done.returncode == 2, done
    assert "is not judged and takes no outcome; nothing was written" in done.stderr, done
    assert manifest_file(root).read_bytes() == before
    assert_no_gh_call(root)

    # A project that declares neither approvers nor an owner: any person answers.
    root = project(tmp_path / "open", compass_yml={"schema": 1, "autonomy": "balanced"})
    _define_done(root)
    done = approve(root, "define", approver="sam", role="engineer")
    assert done.returncode == 0, done
    lines = [line for line in done.stdout.splitlines() if "declares no approvers" in line]
    assert lines == ["compass evidence approve: this project declares no approvers or owner, "
                     "so any person may answer a checkpoint."], done.stdout
    assert outcomes(root)[0]["by"] == "sam" and outcomes(root)[0]["outcome"] == "waited"
    assert_no_gh_call(root)


# --- ARC-7 ------------------------------------------------------------------------

FIXTURES = ROOT / "tests" / "fixtures" / "autonomy-ratio-and-cost"

#: A project whose technical design carries a human check naming jed72, so the
#: test can ask whether any human check reads a checkpoint answer.
HUMAN_DESIGN = {
    "schema": 1, "owner": "jed72", "autonomy": "balanced",
    "approvers": {"issue-waiver": ["jed72"]},
    "checks": {"design-review": {
        "statement": "A person reviewed the design.", "kind": "human",
        "severity": "blocking", "on_skipped": "not-applicable", "approvers": ["jed72"]}},
    "artifacts": {"technical-design": {"set": {"checks": ["design-review"]}}},
}


def _entry_text(path, key, indent):
    lines = (ROOT / path).read_text(encoding="utf-8").splitlines()
    head = " " * indent + key + ":"
    start = next(i for i, line in enumerate(lines) if line.startswith(head))
    out = [lines[start]]
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        out.append(line)
    return "\n".join(out) + "\n"


def _check_lines(root, *names):
    """`compass check`'s exit code, and each line that names one of `names` with
    the more deeply indented detail lines under it."""
    done = run(root, "check", "--issue", SLUG, "--verbose")
    found, depth = [], None
    for line in (done.stdout + done.stderr).splitlines():
        indent = len(line) - len(line.lstrip())
        if any(name in line for name in names):
            found.append(line)
            depth = indent
        elif depth is not None and line.strip() and indent > depth:
            found.append(line)
        else:
            depth = None
    return done.returncode, found


def test_arc_7_checkpoint_record_is_not_the_sign_off(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN, assessment={"risk": "critical"})
    _define_done(root)
    assert "define" in manifest(root)["checkpoints"]
    without = _check_lines(root, "human-approval-present", "design-review")
    assert any("FAIL human-approval-present" in line for line in without[1]), without
    assert any("what: no human-approval evidence" in line for line in without[1]), without

    done = approve(root, "define")
    assert done.returncode == 0, done
    with_record = _check_lines(root, "human-approval-present", "design-review")
    assert with_record == without, (with_record, without)
    body = manifest(root)
    approvals = [e for e in body["evidence"] if e.get("type") in (
        "human-approval", "artifact-approval", "checkpoint-approval")]
    assert [e["type"] for e in approvals] == ["checkpoint-approval"], approvals
    record = approvals[0]

    # The locked check, the gate of G5 and the hard locks are as the base commit has them.
    base = json.loads((FIXTURES / "base-locked-entries.json").read_text())["entries"]
    assert _entry_text("governance/presets/default/checks.yml", "human-approval-present", 2) \
        == base["governance/presets/default/checks.yml#human-approval-present"]
    assert _entry_text("governance/presets/default/gates.yml", "G5", 2) \
        == base["governance/presets/default/gates.yml#G5"]
    assert _entry_text("governance/presets/default/preset.yml", "hard", 2) \
        == base["governance/presets/default/preset.yml#locks.hard"]

    # An issue waiver whose approval names the checkpoint answer is refused with
    # W-APPROVAL-TYPE, as a waiver naming any record that is not a human-approval
    # is: by the configuration lint, so the write that would take the waiver
    # into effect writes nothing, and compass check still fails the sign-off.
    body["config"] = {"checks": {"artifacts-approved": {
        "set": {"severity": "advisory"},
        "waiver": {"reason": "A one-line fix.", "approved_by": record["id"]}}}}
    write_manifest(root, body)
    fault = f"W-APPROVAL-TYPE issue:checks.artifacts-approved: {record['id']} is a " \
            f"checkpoint-approval record, not a human-approval"
    before = manifest_file(root).read_bytes()
    done = run(root, "approach", "evaluate", "--issue", SLUG, "--write", "--reason", "waive")
    assert done.returncode == 2, done
    assert fault in done.stderr, done.stderr
    assert manifest_file(root).read_bytes() == before
    done = run(root, "policy", "lint", "--issue", SLUG)
    assert done.returncode != 0, done
    assert "W-APPROVAL-TYPE" in done.stdout and fault.split(": ", 1)[1] in done.stdout, done
    assert _check_lines(root, "human-approval-present", "design-review") == without
    assert_no_gh_call(root)


# --- ARC-5 ------------------------------------------------------------------------

REGULAR_DOCUMENTS = ("delivery-approach", "technical-design", "distribution-map",
                     "verification-report")


def _ready_to_ship(root, cli=CLI):
    """Every gate passed, one changed file traced and staged, a green on record
    and every document approved: the state `ship-commit` lands from."""
    for kind in REGULAR_DOCUMENTS:
        register(root, kind, "approved", cli=cli)
    body = manifest(root)
    for gate in body["gates"]:
        gate["status"] = "pass"
    body["changed_files"] = [{"path": "src/new.py", "scenarios": ["S-1"]}]
    write_manifest(root, body)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "new.py").write_text("y = 1\n")
    done = run(root, "tdd-green", "--issue", SLUG, "--", sys.executable, "-c", "pass", cli=cli)
    assert done.returncode == 0, done
    git(root, "add", "src/new.py")


def _tree(root):
    """The bytes of every file under .compass and docs/compass."""
    found = {}
    for top in (".compass", "docs/compass"):
        for path in sorted((Path(root) / top).rglob("*")):
            if path.is_file():
                found[str(path.relative_to(root))] = path.read_bytes()
    return found


def _masked(text):
    import re
    return re.sub(r"\b[0-9a-f]{8,40}\b", "<sha>", text)


def test_arc_5_landing_refuses_a_checkpoint_with_no_outcome(tmp_path, monkeypatch):
    root = project(tmp_path)
    register(root, "acceptance-criteria", "approved")
    assert approve(root, "define").returncode == 0
    _ready_to_ship(root)
    head, before = git(root, "rev-parse", "HEAD"), _tree(root)

    done = run(root, "ship-commit", "-m", "Ship it")
    assert done.returncode == 2, done
    lines = done.stderr.strip().splitlines()
    assert lines == [
        f"compass: Blocked: landing of issue '{SLUG}'",
        "Why: plan is listed in checkpoints with no outcome recorded, so nothing shows a "
        "person answered it.",
        "Fix: the person who answers runs compass evidence approve --checkpoint plan "
        "--approver <you> --role <role>, for each stage named, then ship again. "
        "[checkpoint-no-outcome]"], done.stderr
    assert git(root, "rev-parse", "HEAD") == head
    assert "land_timestamp" not in manifest(root)
    assert _tree(root) == before

    # The refusal is the first entry of an ordered list; an entry appended
    # after it runs after it, and only when it does not refuse.
    from compass_pkg import checkpoint_outcomes, core, manifest as manifest_module
    assert manifest_module.LANDING_REFUSALS[0] is checkpoint_outcomes.landing_refusal
    seen = []
    monkeypatch.setattr(manifest_module, "LANDING_REFUSALS", [
        *manifest_module.LANDING_REFUSALS, lambda task, task_dir: seen.append("stub")])
    task = manifest(root)
    with pytest.raises(core.CompassError):
        manifest_module.run_landing_refusals(task, str(manifest_file(root).parent))
    assert seen == []
    task["checkpoint_outcomes"].append({"stage": "plan", "outcome": "skipped",
                                        "by": "planner", "at": "2026-10-13T00:00:00Z"})
    manifest_module.run_landing_refusals(task, str(manifest_file(root).parent))
    assert seen == ["stub"]

    register(root, "technical-design", "approved")
    assert approve(root, "plan").returncode == 0
    git(root, "add", "src/new.py")
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode == 0, done
    assert manifest(root).get("land_timestamp") and git(root, "rev-parse", "HEAD") != head
    assert_no_gh_call(root)

    # An issue that is not judged lands exactly as the base commit lands it.
    captured = json.loads((FIXTURES / "base-ship-commit-not-judged.json").read_text())
    assert ship_not_judged(tmp_path / "not-judged") == captured
    _quick_fix_refused(tmp_path / "quick-fix")


def ship_not_judged(tmp_path, cli=CLI):
    """`ship-commit` on a regular issue with `checkpoints: []` and no
    `checkpoint_outcomes` key: its exit code and output, hashes masked."""
    root = project(tmp_path, compass_yml=dict(BALANCED, autonomy="autonomous"), cli=cli)
    body = manifest(root)
    assert body["checkpoints"] == []
    body.pop("checkpoint_outcomes", None)
    write_manifest(root, body)
    register(root, "acceptance-criteria", "approved", cli=cli)
    _ready_to_ship(root, cli=cli)
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG, cli=cli)
    assert manifest(root).get("land_timestamp"), done
    assert_no_gh_call(root)
    return {"exit": done.returncode, "stdout": _masked(done.stdout),
            "stderr": _masked(done.stderr)}


def _quick_fix_refused(tmp_path):
    root = project(tmp_path, compass_yml=dict(BALANCED, autonomy="controlled"))
    slug = quick_fix(root)
    body = manifest(root, slug)
    assert body["checkpoints"] == ["assess"] and body["checkpoint_outcomes"] == []
    head = git(root, "rev-parse", "HEAD")
    done = run(root, "quick-fix", "finish", "--issue", slug, "-m", "Fix it", *GREET_CMD)
    assert done.returncode == 2, done
    assert "assess is listed in checkpoints with no outcome recorded" in done.stderr, done
    assert git(root, "rev-parse", "HEAD") == head
    assert "land_timestamp" not in manifest(root, slug)
    assert_no_gh_call(root)
