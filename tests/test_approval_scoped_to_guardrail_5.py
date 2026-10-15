"""`human-approval-present` counts only an approval given for guardrail `G5`
(issue `approval-scoped-to-guardrail-5`, ADR-066).

Guardrail `G5` ("a human signs off on the irreversible") has one check,
`human-approval-present`. It used to count every approved `human-approval`
record, so `compass evidence approve --check dod-reviewed` on an issue that
touches payments also cleared the payments sign-off. A record that names
another subject - a check, a waiver, a checkpoint, a document or a set of
decisions, or a guardrail other than exactly `G5` - is now set aside. A
record with no subject key, the form every earlier sign-off uses, still
counts. `compass evidence approve --guardrail`, with the value `G5`, records
the sign-off at a terminal. A landed issue that the earlier rule passes is reported, never
failed.

Scenario ids: `AGF-1` to `AGF-18`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pty
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg import checks, status_words  # noqa: E402

SLUG = "feature"
CHECK = "human-approval-present"
COMMAND = "compass evidence approve --guardrail G5"
NOT_FOR_G5 = "not for guardrail `G5`"


def _record(evidence_id, **fields):
    """An approved `human-approval` record holding all four required fields."""
    body = {"id": evidence_id, "type": "human-approval", "decision": "approved",
            "approver": "alice", "role": "owner", "scope": "the definition of done",
            "timestamp": "2026-10-14T09:00:00Z"}
    body.update(fields)
    return {k: v for k, v in body.items() if v is not None}


DOD = _record("EV-APPROVAL-dod-reviewed-1", check="dod-reviewed")
G5 = _record("EV-G5", guardrail="G5", approver="jed72", role="maintainer",
             scope="refund path change")
# A sign-off recorded the earlier way, as EV-HUMAN-APPROVAL in the archived
# issue `vocabulary-and-cli-renames` is: a path and no subject key.
NO_SUBJECT = _record("EV-HUMAN-APPROVAL", path="evidence/approval.md", approver="jed72",
                     role="maintainer", scope="the renames")


def _task(evidence, status=None):
    """A manifest that guardrail `G5` applies to: labelled payments."""
    task = {"schema_version": "2.0", "issue": SLUG, "created": "2026-10-14",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "medium", "goal": "delivery", "role": "engineer",
                           "labels": ["payments"]},
            "evidence": [dict(e) for e in evidence]}
    if status:
        task["status"] = status
        if status == "done":
            task["close_reason"] = "completed"
    return task


def _judge(evidence, status=None, tmp_path=Path("/nonexistent")):
    return checks._check_human_approval(_task(evidence, status), str(tmp_path))


# --- a scratch project, for the runs of `compass` itself ---------------------------------

def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(root, *argv, terminal=False):
    """Run the CLI. With `terminal` its stdin is a pseudo-terminal, as it is
    when a person types the command; without, stdin is empty, as in an agent
    session."""
    master = slave = None
    if terminal:
        master, slave = pty.openpty()
    try:
        r = subprocess.run([sys.executable, str(CLI), *argv], cwd=root, env=_env(root),
                           capture_output=True, text=True, timeout=180,
                           stdin=slave if terminal else subprocess.DEVNULL)
    finally:
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
    return r.returncode, r.stdout, r.stderr


def _manifest_path(root):
    return root / ".compass" / "work" / SLUG / "manifest.yml"


def _manifest(root):
    return yaml.safe_load(_manifest_path(root).read_text(encoding="utf-8"))


def _project(tmp_path, evidence=()):
    """An in-flight issue labelled payments, at generation 1, holding `evidence`."""
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    _manifest_path(root).write_text(yaml.safe_dump(_task([]), sort_keys=False),
                                    encoding="utf-8")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write",
                          *[f"--justify={dim}=test" for dim in
                            ("risk", "familiarity", "size", "goal", "role")])
    assert code == 0, out + err
    body = _manifest(root)
    assert body["generation"] == 1
    body["evidence"] = [dict(e) for e in evidence]
    _manifest_path(root).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return root


def _check_row(root):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    rows = [r for r in json.loads(out)["checks"] if r["name"] == CHECK]
    assert len(rows) == 1, out + err
    return code, rows[0]


def _approve(root, *argv, terminal=True):
    return _run(root, "evidence", "approve", "--issue", SLUG, *argv, terminal=terminal)


# --- AGF-1: an approval of another human check does not clear guardrail `G5` ------------------------

def test_agf_1_an_unrelated_check_approval_does_not_clear_g5(tmp_path):
    root = _project(tmp_path, [DOD])
    code, row = _check_row(root)
    assert row["status"] == "fail", row
    assert "EV-APPROVAL-dod-reviewed-1" in row["detail"] and "dod-reviewed" in row["detail"]
    assert "given for check 'dod-reviewed'" in row["detail"], row
    assert NOT_FOR_G5 in row["detail"], row
    assert COMMAND in row["detail"], row
    assert code != 0


# --- AGF-2: an approval given for guardrail `G5` clears it -------------------------------------------

def test_agf_2_a_g5_approval_clears_it(tmp_path):
    root = _project(tmp_path, [DOD, G5])
    _, row = _check_row(root)
    assert row["status"] == "pass", row
    for needle in ("EV-G5", "jed72", "maintainer", "refund path change"):
        assert needle in row["detail"], row


# --- AGF-3: a sign-off with no subject key still clears guardrail `G5` -------------------------------

def test_agf_3_a_sign_off_with_no_subject_key_still_counts():
    ok, detail = _judge([NO_SUBJECT])
    assert ok, detail
    assert "EV-HUMAN-APPROVAL" in detail and "jed72" in detail


# --- AGF-4: approvals for a waiver, a checkpoint or another guardrail are set aside -----

@pytest.mark.parametrize("subject, shown", [
    ({"waiver": {"scope": "issue", "entry": "G1"}}, "given for waiver"),
    ({"checkpoint": "define"}, "given for checkpoint 'define'"),
    ({"guardrail": "G3"}, "given for guardrail 'G3'"),
])
def test_agf_4_approvals_with_another_subject_are_set_aside(subject, shown):
    ok, detail = _judge([_record("EV-OTHER", **subject)])
    assert not ok, detail
    assert "EV-OTHER" in detail and shown in detail and NOT_FOR_G5 in detail, detail
    assert COMMAND in detail


# --- AGF-5: an unrelated approval recorded first does not hide a sign-off of guardrail `G5` ------------

def test_agf_5_an_earlier_unrelated_approval_does_not_hide_a_g5_approval():
    ok, detail = _judge([DOD, G5])
    assert ok, detail
    assert "EV-G5" in detail and "EV-APPROVAL-dod-reviewed-1" not in detail, detail
    incomplete = {k: v for k, v in DOD.items() if k != "role"}
    ok, detail = _judge([incomplete, G5])
    assert ok, detail
    assert "EV-G5" in detail and "EV-APPROVAL-dod-reviewed-1" not in detail, detail


# --- AGF-6: a sign-off of guardrail `G5` with a missing field still fails ------------------------------

def test_agf_6_an_incomplete_g5_approval_fails():
    incomplete = {k: v for k, v in G5.items() if k != "role"}
    ok, detail = _judge([DOD, incomplete])
    assert not ok, detail
    assert "EV-G5" in detail and "role" in detail, detail


# --- AGF-7: a landed issue whose only approval names another check is reported ----------

@pytest.mark.parametrize("status", ["done", "landed"])
def test_agf_7_a_landed_issue_is_reported_not_failed(status):
    assert not status_words.is_in_flight(_task([], status))
    ok, detail = _judge([DOD], status)
    assert ok, detail
    assert "no approval was given for guardrail `G5`" in detail, detail
    assert "landed" in detail and "reported only" in detail, detail


# --- AGF-8: a person records a sign-off of guardrail `G5` at a terminal ---------------------------------

def test_agf_8_approve_guardrail_g5_writes_the_record(tmp_path):
    root = _project(tmp_path, [DOD])
    code, out, err = _approve(root, "--guardrail", "G5", "--approver", "jed72",
                              "--role", "maintainer", "--scope", "refund path change")
    assert code == 0, out + err
    new = [e for e in _manifest(root)["evidence"] if e["id"] != DOD["id"]]
    assert len(new) == 1, new
    record = new[0]
    assert record["id"] == "EV-APPROVAL-G5-1"
    assert {k: record[k] for k in ("type", "guardrail", "decision", "approver", "role",
                                   "scope", "issue", "generation")} == {
        "type": "human-approval", "guardrail": "G5", "decision": "approved",
        "approver": "jed72", "role": "maintainer", "scope": "refund path change",
        "issue": SLUG, "generation": 1}
    assert record["timestamp"]
    assert "check" not in record
    _, row = _check_row(root)
    assert row["status"] == "pass", row
    assert "EV-APPROVAL-G5-1" in row["detail"]


def test_agf_8_a_second_sign_off_takes_the_next_number(tmp_path):
    root = _project(tmp_path, [DOD, _record("EV-APPROVAL-G5-1", guardrail="G5")])
    code, out, err = _approve(root, "--guardrail", "G5", "--approver", "jed72",
                              "--role", "maintainer", "--scope", "x")
    assert code == 0, out + err
    assert _manifest(root)["evidence"][-1]["id"] == "EV-APPROVAL-G5-2"


# --- AGF-9: refusals of the form for guardrail `G5` ------------------------------------------------------

@pytest.mark.parametrize("argv, terminal, cause", [
    (["--guardrail", "G3", "--approver", "jed72", "--role", "maintainer", "--scope", "x"],
     True, "`G5` is the only guardrail with a sign-off"),
    (["--guardrail", "G5", "--approver", "agent", "--role", "maintainer", "--scope", "x"],
     True, "an agent cannot approve"),
    (["--guardrail", "G5", "--approver", "jed72", "--role", "maintainer"],
     True, "--scope must not be empty"),
    (["--guardrail", "G5", "--check", "dod-reviewed", "--approver", "jed72", "--role",
      "maintainer", "--scope", "x"], True, "not allowed with argument"),
    (["--guardrail", "G5", "--approver", "jed72", "--role", "maintainer", "--scope", "x"],
     False, "needs a terminal"),
], ids=["g3", "agent", "no-scope", "two-forms", "no-terminal"])
def test_agf_9_approve_guardrail_refusals(tmp_path, argv, terminal, cause):
    root = _project(tmp_path, [DOD])
    before = _manifest_path(root).read_bytes()
    code, out, err = _approve(root, *argv, terminal=terminal)
    assert code != 0, out + err
    assert cause in out + err, out + err
    assert _manifest_path(root).read_bytes() == before


# --- TRC-D7: the agent runs the terminal verb from its shell ------------------------------

def test_d7_terminal_refusal_names_request(tmp_path):
    root = _project(tmp_path, [DOD])
    before = _manifest_path(root).read_bytes()
    code, out, err = _approve(root, "--guardrail", "G5", "--approver", "jed72",
                              "--role", "owner", "--scope", "x", terminal=False)
    assert code != 0, out + err
    assert "needs a terminal" in out + err, out + err
    assert "compass evidence request" in out + err, out + err
    assert _manifest_path(root).read_bytes() == before


# --- AGF-10: no landed issue in the archive newly fails ----------------------------------

def _rule_1_0_0(task):
    """The verdict of `human-approval-present` 1.0.0, frozen as the oracle: the
    first approved `human-approval` record, whatever it names, must hold all
    four fields; a landed issue with no approved record is reported."""
    approved = [e for e in task.get("evidence") or [] if isinstance(e, dict)
                and e.get("type") == "human-approval" and e.get("decision") == "approved"]
    if not approved:
        return not status_words.is_in_flight(task)
    return all(approved[0].get(k) for k in ("approver", "role", "scope", "timestamp"))


def _archive_verdicts(work=ROOT / ".compass" / "work"):
    """(slug, landed, before, after) for every manifest of the local archive.
    The archive is not tracked, so in a fresh checkout the list is empty and
    contract 3's sample is the half of AGF-10 that runs."""
    rows = []
    for task_dir in sorted(work.iterdir()) if work.is_dir() else []:
        path = task_dir / "manifest.yml"
        if not path.is_file():
            continue
        try:
            task = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(task, dict):
            continue
        after, _ = checks._check_human_approval(task, str(task_dir))
        rows.append((task_dir.name, not status_words.is_in_flight(task),
                     _rule_1_0_0(task), bool(after)))
    return rows


def test_agf_10_no_landed_issue_newly_fails():
    rows = _archive_verdicts()
    moved = [(slug, landed, before, after) for slug, landed, before, after in rows
             if before != after]
    print(f"judged {len(rows)} manifests; verdicts that moved: {len(moved)}")
    for slug, landed, before, after in moved:
        print(f"  {slug}: {'landed' if landed else 'in flight'}, "
              f"{'pass' if before else 'fail'} -> {'pass' if after else 'fail'}")
    newly_failed = [slug for slug, landed, before, after in moved
                    if landed and before and not after]
    assert not newly_failed, f"landed issues that newly fail: {newly_failed}"


# --- AGF-11: major version 1 and the locked catalogue entries ----------------------------

# The sha256 of each locked entry as JSON with sorted keys, read at main 5079cef6
# before this change. They must not move: the change is to the implementation only.
LOCKED = {
    ("checks.yml", "checks", CHECK):
        "0e3e2224bc64929a923573284b7590543b134e743e6b74eb273ea4c2737f0572",
    ("gates.yml", "gates", "G5"):
        "e33c524704a884fd1fbd81227f52de0fabb8d1af0dbeb458b353f2b94fcd0292",
}


def test_agf_11_major_1_and_locked_entries_unchanged():
    from compass_pkg.check_registry import REGISTRY
    assert REGISTRY[CHECK].version.split(".")[0] == "1"
    lock = yaml.safe_load((ROOT / "tests" / "fixtures" / "impls" / "versions.lock.yml")
                          .read_text(encoding="utf-8"))["implementations"][CHECK]
    assert str(lock["version"]).split(".")[0] == "1"
    preset = ROOT / "governance" / "presets" / "default"
    for (name, section, key), digest in LOCKED.items():
        entry = yaml.safe_load((preset / name).read_text(encoding="utf-8"))[section][key]
        assert hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest() \
            == digest, f"{section}.{key} changed"


# --- AGF-17: version 1.1.0, and a generation that recorded 1.0.0 is judged ---------------

def test_agf_17_version_1_1_0_within_major_1(tmp_path):
    from compass_pkg.check_registry import REGISTRY
    from impl_versions_support import record_versions
    assert REGISTRY[CHECK].version == "1.1.0"
    lock = yaml.safe_load((ROOT / "tests" / "fixtures" / "impls" / "versions.lock.yml")
                          .read_text(encoding="utf-8"))["implementations"][CHECK]
    assert str(lock["version"]) == "1.1.0"
    page = (ROOT / "docs" / "check-implementations.md").read_text(encoding="utf-8")
    assert f"### `{CHECK}` (version 1.1.0)" in page
    root = _project(tmp_path, [G5])
    record_versions(root / ".compass" / "work" / SLUG, implementations={CHECK: "1.0.0"})
    _, row = _check_row(root)
    assert row["status"] == "pass", row
    assert "refused" not in row["detail"], row


# --- AGF-12: the docs and the decision entry state the rule ------------------------------

NAMES_COMMAND = re.compile(r"compass evidence approve --guardrail,?( (and|with) the value)? G5")


def _flat(text):
    return " ".join(text.replace("`", "").split())


def test_agf_12_docs_and_decision_entry_state_the_rule():
    from compass_pkg.check_cmd import CHECK_GUIDANCE
    guardrails = yaml.safe_load((ROOT / "governance" / "guardrails.yml")
                                .read_text(encoding="utf-8"))
    evidence_type = json.dumps(guardrails["evidence_types"]["human-approval"])
    for name, text in [
        ("docs/safety-contract.md", (ROOT / "docs" / "safety-contract.md").read_text()),
        ("docs/entry-exit-evaluation.md",
         (ROOT / "docs" / "entry-exit-evaluation.md").read_text()),
        ("governance/guardrails.md", (ROOT / "governance" / "guardrails.md").read_text()),
        ("governance/guardrails.yml evidence_types.human-approval", evidence_type),
        ("docs/upgrade-7-0-0.md", (ROOT / "docs" / "upgrade-7-0-0.md").read_text()),
    ]:
        flat = _flat(text)
        # In prose the value sits in its own code span, as in "--guardrail and the
        # value `G5`", because the house style keeps a guardrail code in backticks.
        assert NAMES_COMMAND.search(flat), f"{name} does not name {COMMAND}"
        assert "given for guardrail G5" in flat, f"{name} does not state the rule"
    guidance = CHECK_GUIDANCE[CHECK]
    assert COMMAND in guidance["do"] and COMMAND in guidance["fix"]
    assert "--check" not in guidance["do"] + guidance["fix"]
    from compass_pkg.verb_help import VERB_DESCRIPTIONS
    assert "--guardrail G5" in VERB_DESCRIPTIONS["evidence approve"]

    # No doc or code comment still says the check accepts any approval. Merged
    # decision records keep the text that was true when they were written.
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split()
    stale = re.compile(r"accepts\s+any\s+approved\s+`?human-approval")
    found = []
    for rel in tracked:
        if rel.startswith(("architecture/decisions/", "governance/decisions/", "tests/")):
            continue
        path = ROOT / rel
        if path.suffix not in (".py", ".md", ".yml", ".yaml", ".json") or not path.is_file():
            continue
        if stale.search(" ".join(path.read_text(encoding="utf-8", errors="replace").split())):
            found.append(rel)
    assert not found, f"still say the check accepts any approval: {found}"

    entry = ROOT / "governance" / "decisions" / \
        "2026-10-14-guardrail-5-counts-only-an-approval-given-for-it.md"
    flat = _flat(entry.read_text(encoding="utf-8"))
    for needle in ("given for guardrail G5", "major version 1", "from fail to pass"):
        assert needle in flat, f"the decision entry does not say {needle!r}"

    adrs = sorted((ROOT / "architecture" / "decisions").glob("ADR-066-*.md"))
    assert len(adrs) == 1, adrs
    adr = _flat(adrs[0].read_text(encoding="utf-8"))
    for needle in ("status: accepted", "SUBJECT_KEYS", "landed", "1.1.0", "ADR-038",
                   "ADR-063"):
        assert needle in adr, f"ADR-066 does not say {needle!r}"
    index = (ROOT / "architecture" / "decisions" / "README.md").read_text(encoding="utf-8")
    assert adrs[0].name in index

    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    props = schema["properties"]["evidence"]["items"]["properties"]
    assert props["guardrail"]["type"] == "string"
    assert props["waiver"]["type"] == "object"
    reference = (ROOT / "schemas" / "manifest.reference.yml").read_text(encoding="utf-8")
    assert re.search(r"^\s+guardrail:\s+#", reference, re.M)
    assert re.search(r"^\s+waiver:\s+#", reference, re.M)


# --- AGF-13: the landed floor ------------------------------------------------------------

def test_agf_13_landed_floor_reports_not_fails():
    no_role = {k: v for k, v in NO_SUBJECT.items() if k != "role"}
    ok, detail = _judge([DOD, no_role], "done")
    assert ok, detail
    assert "role" in detail and "landed" in detail, detail
    assert "earlier rule passes it" in detail and "reported only" in detail, detail
    ok, detail = _judge([DOD, no_role])
    assert not ok, detail
    assert "EV-HUMAN-APPROVAL" in detail and "role" in detail, detail


def test_agf_13_a_landed_issue_the_earlier_rule_fails_still_fails():
    no_role = {k: v for k, v in DOD.items() if k != "role"}
    ok, detail = _judge([no_role], "done")
    assert not ok, detail


# --- AGF-14: artifact and decisions keys are set aside -----------------------------------

@pytest.mark.parametrize("subject, shown", [
    ({"artifact": "technical-design"}, "given for artifact 'technical-design'"),
    ({"decisions": ["Q1"]}, "given for decisions ['Q1']"),
])
def test_agf_14_artifact_and_decisions_keys_set_aside(subject, shown):
    ok, detail = _judge([_record("EV-OTHER", **subject)])
    assert not ok, detail
    assert "EV-OTHER" in detail and shown in detail and NOT_FOR_G5 in detail, detail


# --- AGF-15: the guardrail value must be exactly `G5` --------------------------------------

@pytest.mark.parametrize("value", ["g5", "5", "guardrail-5", ["G5"], None])
def test_agf_15_guardrail_must_be_exactly_g5(value):
    ok, detail = _judge([_record("EV-OTHER", guardrail=value)
                         if value is not None else
                         dict(_record("EV-OTHER"), guardrail=None)])
    assert not ok, detail
    shown = "none" if value is None else repr(value)
    assert "EV-OTHER" in detail and f"given for guardrail {shown}" in detail, detail


# --- AGF-16: the form for guardrail `G5` records an approval only ----------------------------------------

def test_agf_16_guardrail_form_refuses_rejected(tmp_path):
    root = _project(tmp_path, [DOD])
    before = _manifest_path(root).read_bytes()
    code, out, err = _approve(root, "--guardrail", "G5", "--decision", "rejected",
                              "--approver", "jed72", "--role", "maintainer", "--scope", "x")
    assert code != 0, out + err
    assert "`--guardrail G5` records an approval only" in out + err, out + err
    assert _manifest_path(root).read_bytes() == before


# --- AGF-18: every CLI writer of a human-approval record names its subject --------------

# The functions under cli/ that build a `human-approval` record holding a
# decision. A new one must be added here, so its test is written with it.
KNOWN_WRITERS = {("compass_pkg/approvals.py", "_record_check"),
                 ("compass_pkg/approvals.py", "_record_guardrail")}


def _writers():
    """Each (file, function) under cli/ that builds a dict literal whose
    `type` is `human-approval`."""
    found = set()
    for path in sorted((ROOT / "cli").rglob("*.py")):
        if "vendor" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Dict):
                    continue
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, ast.Constant) and key.value == "type"
                            and isinstance(value, ast.Constant)
                            and value.value == "human-approval"):
                        found.add((path.relative_to(ROOT / "cli").as_posix(), fn.name))
    return found


def test_agf_18_every_writer_names_a_subject(tmp_path):
    from compass_pkg import approval_records, approve_cmd
    assert approval_records.SUBJECT_KEYS == (
        "check", "waiver", "checkpoint", "artifact", "decisions")
    assert checks.approval_records is approval_records
    from compass_pkg import approvals
    assert approve_cmd.approval_records is approval_records
    assert approvals.approval_records is approval_records
    for module in (checks, approvals):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "approval_records.gives_g5" in source, module.__name__
    assert _writers() == KNOWN_WRITERS

    def subject_named(record):
        return (any(k in record for k in approval_records.SUBJECT_KEYS)
                or record.get("guardrail") == "G5")

    # _record_guardrail
    root = _project(tmp_path / "g5")
    code, out, err = _approve(root, "--guardrail", "G5", "--approver", "jed72",
                              "--role", "maintainer", "--scope", "x")
    assert code == 0, out + err
    assert subject_named(_manifest(root)["evidence"][-1])

    # _record_check
    from test_human_checks import SIGN_OFF, _approve as approve_check, _cli_project
    from test_generation_store import _manifest as manifest_of
    (tmp_path / "check").mkdir()
    croot, task_dir = _cli_project(tmp_path / "check")
    code, out, err = approve_check(croot, check=SIGN_OFF)
    assert code == 0, out + err
    record = manifest_of(task_dir)["evidence"][-1]
    assert record["type"] == "human-approval" and subject_named(record)

    # `compass evidence add --type human-approval` writes a record with no
    # decision, which no approval reader counts.
    (root / ".compass" / "work" / SLUG / "evidence").mkdir(exist_ok=True)
    (root / ".compass" / "work" / SLUG / "evidence" / "note.md").write_text("# note\n")
    code, out, err = _run(root, "evidence", "add", "--issue", SLUG, "EV-NOTE",
                          "--type", "human-approval", "--path", "evidence/note.md")
    assert code == 0, out + err
    added = [e for e in _manifest(root)["evidence"] if e["id"] == "EV-NOTE"]
    assert added and "decision" not in added[0]
