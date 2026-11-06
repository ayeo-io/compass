"""Checkpoint outcomes: a record of each stage hand-off, and the landing refusal.

A stage hand-off that can wait for a person (assess, define, refine, plan,
`implement` or `verify`)
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
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
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
        # A multiagent breakdown refuses a map with no `units:` line (ADR-071);
        # two units record nothing, so the stage records stay as they were.
        units = "\nunits: 2\n" if kind == "distribution-map" else ""
        path.write_text(f"# {kind}\n\nFirst version.\n{units}")
    # 9.0.0 removed `compass issue artifact set` (ADR-091), so the entry is written as an
    # older release wrote it.
    del cli
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import document_registry
    return document_registry.register(Path(root) / ".compass" / "work" / slug, kind,
                                      f"{DOCS}/{kind}.md", status)


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
    """The records show refine complete on an issue assessed before the path: its
    review written and registered. Other test files call it."""
    register(root, "acceptance-criteria")
    register(root, "requirements-review")


#: On the four-stage path balanced autonomy lists a checkpoint only where the
#: scenarios owe a person's approval, which critical risk owes (ADR-092 open
#: question 7). The tests that need a listed checkpoint beside an unlisted one
#: assess at that risk: `specify` is listed, and assess, build and ship are not.
CRITICAL = {"risk": "critical"}


def specify_done(root, slug=SLUG):
    """The records show specify complete on the path: one scenario with an id, an
    intent and a declared test (ADR-092)."""
    done = run(root, "scenario", "add", "TRC-001", "--issue", slug, "--intent", "INT-1",
               "--title", "one", "--test", "tests/test_one.py::test_one")
    assert done.returncode == 0, done


# --- ARC-3 ------------------------------------------------------------------------

def test_arc_3_agent_records_a_skipped_outcome(tmp_path):
    root = project(tmp_path, assessment=CRITICAL)
    assert manifest(root)["checkpoints"] == ["specify"]
    specify_done(root)
    devlog = manifest_file(root).parent / "devlog.md"
    devlog.write_text("# Devlog\n")
    generations = generation_files(root)
    assert generations, "the issue holds no stored generation to compare"
    evidence_before = manifest(root).get("evidence")

    # The path's assess hand-off is not listed under balanced autonomy, so an
    # agent records that it passed.
    before = _now()
    done = skip(root, "assess", "router")
    after = _now()
    assert done.returncode == 0, done
    assert done.stdout.strip() == (
        "compass issue checkpoint add: assess recorded as skipped by router."), done
    entries = outcomes(root)
    assert len(entries) == 1, entries
    entry = entries[0]
    assert {k: v for k, v in entry.items() if k != "at"} == {
        "stage": "assess", "outcome": "skipped", "by": "router"}, entry
    assert before <= _utc(entry["at"]) <= after, entry
    assert manifest(root).get("evidence") == evidence_before
    assert devlog.read_text() == "# Devlog\n"
    assert not schema_errors(manifest(root)), schema_errors(manifest(root))

    same = manifest_file(root).read_bytes()
    done = skip(root, "assess", "router")
    assert done.returncode == 0, done
    assert "already recorded as skipped; nothing was written" in done.stdout, done
    assert manifest_file(root).read_bytes() == same

    done = approve(root, "assess")
    assert done.returncode == 0, done
    assess = [e for e in outcomes(root) if e["stage"] == "assess"]
    assert len(assess) == 1, outcomes(root)
    assert assess[0]["outcome"] == "waited" and assess[0]["by"] == "jed72", assess
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
    root = project(tmp_path, assessment=CRITICAL)
    specify_done(root)
    assert approve(root, "assess").returncode == 0
    cases = [
        (("specify", "spec-author", "skipped"),
         "specify is a listed checkpoint, so it waits for a person"),
        (("assess", "router", "skipped"), "assess already holds a waited outcome"),
        (("breakdown", "builder", "skipped"), "'breakdown' is not a checkpoint stage"),
        (("build", "jed72", "skipped"), "--by must name an agent"),
        (("build", "builder", "waited"), "only a person's approval records waited"),
    ]
    for (stage, by, outcome), cause in cases:
        before = manifest_file(root).read_bytes()
        done = run(root, "issue", "checkpoint", "add", stage, "--outcome", outcome,
                   "--by", by, "--issue", SLUG)
        assert done.returncode == 2, (stage, done)
        assert cause in done.stderr, (stage, done.stderr)
        assert manifest_file(root).read_bytes() == before, stage
        if stage == "specify" or outcome == "waited":
            assert f"compass evidence approve --checkpoint {stage}" in done.stderr, done.stderr

    # Every path stage runs: the path has no stage modes (ADR-092 decision 1), so no
    # path issue has a stage whose hand-off its approach skips. A legacy stage is not
    # a stage of a path issue, and the quick fix refuses it by that name instead.
    slug = quick_fix(root)
    before = manifest_file(root, slug).read_bytes()
    done = run(root, "issue", "checkpoint", "add", "refine", "--outcome", "skipped",
               "--by", "builder", "--issue", slug)
    assert done.returncode == 2, done
    assert "'refine' is not a stage of the four-stage path" in done.stderr, done.stderr
    assert manifest_file(root, slug).read_bytes() == before

    # An issue assessed before outcomes were recorded is not judged: the verb
    # refuses it and does not add the key.
    body = manifest(root)
    body.pop("checkpoint_outcomes")
    write_manifest(root, body)
    before = manifest_file(root).read_bytes()
    done = skip(root, "build", "builder")
    assert done.returncode == 2, done
    assert "is not judged and takes no outcome; nothing was written" in done.stderr, done
    assert manifest_file(root).read_bytes() == before
    assert_no_gh_call(root)


# --- ARC-1 ------------------------------------------------------------------------

def _define_done(root):
    """The records show define complete and refine not started."""
    register(root, "acceptance-criteria")


def test_arc_1_person_answers_a_checkpoint(tmp_path):
    root = project(tmp_path, assessment=CRITICAL)
    specify_done(root)
    body = manifest(root)
    assert body["checkpoints"] == ["specify"] and body["checkpoint_outcomes"] == []
    before = manifest(root)

    done = approve(root, "specify")
    assert done.returncode == 0, done
    after = manifest(root)
    added = after["evidence"][len(before["evidence"]):]
    assert after["evidence"][:len(before["evidence"])] == before["evidence"]
    assert len(added) == 1, added
    record = added[0]
    assert record["type"] == "checkpoint-approval", record
    assert {k: v for k, v in record.items() if k not in ("id", "timestamp")} == {
        "type": "checkpoint-approval", "checkpoint": "specify", "approver": "jed72",
        "role": "product-owner", "scope": "the specify hand-off", "decision": "approved",
        "issue": SLUG, "generation": before["generation"], "via": "terminal"}, record
    assert "check" not in record
    _utc(record["timestamp"])
    assert not [e for e in after["evidence"] if e.get("type") == "human-approval"]
    assert after["checkpoint_outcomes"] == [{
        "stage": "specify", "outcome": "waited", "by": "jed72",
        "at": record["timestamp"], "evidence": record["id"]}]
    unchanged = {k: v for k, v in before.items() if k not in ("evidence", "checkpoint_outcomes")}
    assert {k: v for k, v in after.items() if k in unchanged} == unchanged
    assert set(after) == set(before)
    assert not schema_errors(after), schema_errors(after)
    assert_no_gh_call(root)


# --- ARC-2 ------------------------------------------------------------------------

def test_arc_2_approve_checkpoint_refusals(tmp_path):
    root = project(tmp_path, assessment=CRITICAL)
    specify_done(root)
    slug = quick_fix(root)
    cases = [
        ("no terminal", dict(stage="specify", terminal=False), "needs a terminal"),
        ("agent", dict(stage="specify", approver="agent"), "an agent cannot approve"),
        ("not listed", dict(stage="specify", approver="sam"),
         "sam is not an approver of this project"),
        ("not a checkpoint", dict(stage="breakdown"), "'breakdown' is not a checkpoint stage"),
        # Every path stage runs (ADR-092 decision 1), so the quick fix refuses a legacy
        # stage as a stage it does not have, not as a hand-off its approach skips.
        ("quick fix refine", dict(stage="refine", slug=slug),
         "'refine' is not a stage of the four-stage path"),
        ("build not run", dict(stage="build"), "build has not run"),
        ("rejected", dict(stage="specify", extra=("--decision", "rejected")),
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
    done = approve(root, "specify")
    assert done.returncode == 2, done
    assert "is not judged and takes no outcome; nothing was written" in done.stderr, done
    assert manifest_file(root).read_bytes() == before
    assert_no_gh_call(root)

    # A project that declares neither approvers nor an owner: any person answers.
    root = project(tmp_path / "open", compass_yml={"schema": 1, "autonomy": "balanced"},
                   assessment=CRITICAL)
    specify_done(root)
    done = approve(root, "specify", approver="sam", role="engineer")
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
    root = project(tmp_path, compass_yml=HUMAN_DESIGN,
                   assessment={"risk": "critical", "labels": ["migrations"]})
    specify_done(root)
    assert "specify" in manifest(root)["checkpoints"]
    without = _check_lines(root, "human-approval-present", "design-review")
    assert any("FAIL human-approval-present" in line for line in without[1]), without
    assert any("what: no human-approval evidence" in line for line in without[1]), without

    done = approve(root, "specify")
    assert done.returncode == 0, done
    with_record = _check_lines(root, "human-approval-present", "design-review")
    assert with_record == without, (with_record, without)
    body = manifest(root)
    approvals = [e for e in body["evidence"] if e.get("type") in (
        "human-approval", "artifact-approval", "checkpoint-approval")]
    assert [e["type"] for e in approvals] == ["checkpoint-approval"], approvals
    record = approvals[0]

    # The locked check, the gate of guardrail `G5` and the hard locks are as the base
    # commit has them; the `G5` entry is as g5-irreversible-labels left it.
    base = json.loads((FIXTURES / "base-locked-entries.json").read_text())["entries"]
    assert _entry_text("governance/presets/default/checks.yml", "human-approval-present", 2) \
        == base["governance/presets/default/checks.yml#human-approval-present"]
    assert _entry_text("governance/presets/default/gates.yml", "G5", 2) \
        == base["governance/presets/default/gates.yml#G5"]
    assert _entry_text("governance/presets/default/preset.yml", "hard", 2) \
        == base["governance/presets/default/preset.yml#locks.hard"]

    # An issue waiver whose approval names the checkpoint answer is refused with
    # W-APPROVAL-TYPE by the configuration lint, as a waiver naming any record that
    # is not a human-approval is. The write does not read the issue's `config:`
    # (ADR-094), so it takes nothing into effect, and compass check still fails the
    # sign-off.
    body["config"] = {"checks": {"backfills-paid": {
        "set": {"severity": "advisory"},
        "waiver": {"reason": "A one-line fix.", "approved_by": record["id"]}}}}
    write_manifest(root, body)
    fault = f"W-APPROVAL-TYPE issue:checks.backfills-paid: {record['id']} is a " \
            f"checkpoint-approval record, not a human-approval"
    done = run(root, "approach", "evaluate", "--issue", SLUG, "--write", "--reason", "waive")
    assert done.returncode == 0, done
    assert "W-APPROVAL-TYPE" not in done.stdout + done.stderr, done
    done = run(root, "policy", "lint", "--issue", SLUG)
    assert done.returncode != 0, done
    assert "W-APPROVAL-TYPE" in done.stdout and fault.split(": ", 1)[1] in done.stdout, done
    assert _check_lines(root, "human-approval-present", "design-review") == without
    assert_no_gh_call(root)


# --- ARC-5 ------------------------------------------------------------------------

REGULAR_DOCUMENTS = ("delivery-approach", "intent", "requirements-review", "technical-design",
                     "distribution-map", "verification-report")

#: The release line a regular issue on the shipped default owes before it lands (ADR-065).
RELEASE_NOTE = "Each stage hand-off is on record."


def meet_definition_of_done(body, root, slug=SLUG):
    """Add to `body` one review note that meets every item of the issue's Definition of
    Done. `compass ship-commit` refuses to land while `dod-evidence-typed` fails
    (ADR-091), so the state it lands from has the Definition of Done met."""
    from compass_pkg import effective, item_records
    folder = manifest_file(root, slug).parent
    ids = [check for check, _ in item_records.listed_checks(
        effective.view_or_legacy(str(folder)), "dod")]
    (folder / "evidence").mkdir(exist_ok=True)
    (folder / "evidence" / "dod-review.txt").write_text("reviewed\n")
    body["evidence"] = (body.get("evidence") or []) + [
        {"id": "EV-DOD", "type": "manual-review", "path": "evidence/dod-review.txt",
         "meets": ids}]


def _ready_to_ship(root, cli=CLI):
    """Every gate passed, one changed file traced and staged, a green on record,
    every document approved, the Definition of Done met and the release line
    recorded: the state `ship-commit` lands from."""
    for kind in REGULAR_DOCUMENTS:
        register(root, kind, "approved", cli=cli)
    body = manifest(root)
    meet_definition_of_done(body, root)
    for gate in body["gates"]:
        gate["status"] = "pass"
    body["changed_files"] = [{"path": "src/new.py", "scenarios": ["S-1"]}]
    body["release_note"] = RELEASE_NOTE
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
    # On the path balanced autonomy lists only `specify`, where critical risk owes a
    # person's approval of the scenarios (ADR-092 open question 7): the landing is
    # refused for that one listed hand-off, as it was for `plan` before.
    root = project(tmp_path, assessment=CRITICAL)
    # A new issue's first assessment makes it judged.
    assert manifest(root)["checkpoint_outcomes"] == []
    assert manifest(root)["checkpoints"] == ["specify"]
    specify_done(root)
    _ready_to_ship(root)
    head, before = git(root, "rev-parse", "HEAD"), _tree(root)

    done = run(root, "ship-commit", "-m", "Ship it")
    assert done.returncode == 2, done
    lines = done.stderr.strip().splitlines()
    assert lines == [
        f"compass: Blocked: landing of issue '{SLUG}'",
        "Why: specify is listed in checkpoints with no outcome recorded, so nothing shows "
        "a person answered it.",
        "Fix: the person who answers runs compass evidence approve --checkpoint specify "
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
    task["checkpoint_outcomes"].append({"stage": "specify", "outcome": "skipped",
                                        "by": "spec-author", "at": "2026-10-13T00:00:00Z"})
    manifest_module.run_landing_refusals(task, str(manifest_file(root).parent))
    assert seen == ["stub"]

    assert approve(root, "specify").returncode == 0
    git(root, "add", "src/new.py")
    done = run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG)
    assert done.returncode == 0, done
    assert manifest(root).get("land_timestamp") and git(root, "rev-parse", "HEAD") != head
    assert_no_gh_call(root)

    # An issue that is not judged lands exactly as the base commit lands it.
    # The captured stdout says "issue marked done.", because the status word
    # "landed" is retired (ADR-044). The capture was edited to match, word for word, and again when 9.0.0 stopped
    # deriving the living spec at landing (ADR-091).
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
    # Controlled autonomy lists every path stage where `S17` applies, as it does to
    # the light row (ADR-092 open question 7).
    assert body["checkpoints"] == ["assess", "specify", "build", "ship"], body
    assert body["checkpoint_outcomes"] == []
    head = git(root, "rev-parse", "HEAD")
    done = run(root, "quick-fix", "finish", "--issue", slug, "-m", "Fix it",
               "--candidate", "local", "--client", "cli", *GREET_CMD)
    assert done.returncode == 2, done
    assert ("assess, specify, build and ship are listed in checkpoints with no outcome "
            "recorded") in done.stderr, done
    assert git(root, "rev-parse", "HEAD") == head
    assert "land_timestamp" not in manifest(root, slug)
    assert_no_gh_call(root)


# --- ARC-8 ------------------------------------------------------------------------

#: Each hand-off text, the stage it hands off and the agent that runs it.
# The six stage commands went with the four-stage path (ADR-092). Ship holds
# the stage 2 and 3 review hand-offs, at build and at ship; the specify
# checkpoint is named by the `next:` line where it is listed.
HAND_OFFS = (("commands/ship.md", "build", "builder"),
             ("commands/ship.md", "ship", "verifier"),
             ("approaches/assess-procedure.md", "assess", "router"))


def test_arc_8_hand_off_texts_name_the_commands():
    import re
    for path, stage, agent in HAND_OFFS:
        text = (ROOT / path).read_text(encoding="utf-8")
        flat = " ".join(text.split())
        assert (f"compass issue checkpoint add {stage} --outcome skipped --by {agent}"
                in flat), path
        assert f"compass evidence approve --checkpoint {stage}" in flat, path
        assert not re.search(r"skipped checkpoint to `?devlog", flat, re.I), path
        assert not re.search(r"log the skip\w* (checkpoint|hand-off)", flat, re.I), path
    policy = " ".join((ROOT / "governance" / "routing-policy.md").read_text().split())
    assert not re.search(r"skipped checkpoint to `?devlog", policy, re.I)
    assert "compass issue checkpoint add" in policy
