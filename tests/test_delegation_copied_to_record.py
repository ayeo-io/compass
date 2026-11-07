"""Each delegation used is copied into the issue record (#355, ADR-095
decision 12).

When an agent records an approval under a delegation, the manifest's
`delegations_used:` gets a copy of the delegation in the same save as the
record. The copy leaves out the nonce, the use count, the index of other
issues' records and the session ids, and carries the sha256 of the fields it
keeps. A second use of the same delegation adds nothing; a delegation whose
kept fields changed is added again as `<id>@2`. The issue's `devlog.md` gets
no line.

The delegation files are written into each test's own temporary project.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

from approval_support import (CHECK, OWNER, SLUG, manifest_of, project,  # noqa: E402
                              run, save_manifest, task_dir)
from delegation_support import delegated  # noqa: E402
from test_delegation_limits import _store, _write_dl  # noqa: E402

from compass_pkg import approvals, delegations  # noqa: E402

ARCHITECT = "compass:architect"
LEFT_OUT = ("nonce", "uses", "records", "session_id", "requested_prompt_id", "revoked_at",
            "revoked_by", "id")


def _approve(root):
    code, out, err = delegated(root, ARCHITECT, "--check", CHECK, "--scope", "s",
                               "--issue", SLUG)
    assert code == 0, out + err


def _digest(copy):
    body = {k: v for k, v in copy.items() if k != "sha256"}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file(root, number=1):
    return yaml.safe_load((_store(root) / f"DL-{number}.yml").read_text(encoding="utf-8"))


def test_a_delegated_approval_copies_the_delegation_into_the_manifest(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, until=None, format=2, requested_prompt_id="p-0")
    _approve(root)
    manifest = manifest_of(root)
    record = manifest["evidence"][-1]
    assert record["delegation"] == "DL-1" and record["via"] == "delegation"
    copy = manifest["delegations_used"]["DL-1"]
    assert copy == {"format": 2, "delegated_by": OWNER, "role": "owner",
                    "approver_source": "owner", "created_at": "2026-10-23T08:00:00Z",
                    "agent": ARCHITECT, "issues": {SLUG: 1},
                    "forms": ["checks", "documents", "checkpoints", "decisions"],
                    "created_via": "prompt", "prompt_id": "p-1",
                    "sha256": _digest(copy)}
    # The delegation file still counts the use and indexes the record.
    held = _file(root)
    assert held["uses"] == 1 and held["records"][0]["ids"] == [record["id"]]


def test_the_copy_leaves_out_the_nonce_the_count_the_index_and_the_session_ids(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, agent=None, covers_session="sess-1", requested_prompt_id="p-0")
    body = _file(root)
    body.update(uses=3, records=[{"issue": "other", "folder": "/elsewhere/other",
                                  "ids": ["EV-1"], "at": "2026-10-23T09:00:00Z"}])
    delegation_id, copy = delegations.copy_of(body)
    assert delegation_id == "DL-1"
    for name in LEFT_OUT:
        assert name not in copy, name
    assert copy["covers_session"] is True and "sess-1" not in json.dumps(copy)
    assert "/elsewhere" not in json.dumps(copy)
    assert copy["sha256"] == _digest(copy)


def test_the_copy_is_written_in_the_same_save_as_the_record(tmp_path, monkeypatch):
    root = project(tmp_path)
    body = _write_dl(root, 1, until=None, format=2)
    saved = []
    real = approvals.save_manifest

    def spy(task, path):
        saved.append((len(task.get("evidence") or []),
                      dict(task.get(delegations.USED_KEY) or {})))
        real(task, path)

    monkeypatch.setattr(approvals, "save_manifest", spy)
    before = len(manifest_of(root).get("evidence") or [])
    answer = approvals.checked(approvals.Answer(
        "check", CHECK, "approved", OWNER, "owner", "s",
        {"via": "delegation", "approved_by_agent": ARCHITECT, "delegation": "DL-1"},
        delegations.copy_of(body)))
    approvals.record(str(task_dir(root)), answer)
    assert len(saved) == 1
    count, used = saved[0]
    assert count == before + 1 and list(used) == ["DL-1"]


def test_a_refused_approval_writes_no_copy(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, until=None, format=2, forms=["documents"])
    code, out, err = delegated(root, ARCHITECT, "--check", CHECK, "--scope", "s",
                               "--issue", SLUG)
    assert code != 0 and "not human checks" in out + err, out + err
    assert delegations.USED_KEY not in manifest_of(root)


def test_a_second_use_keeps_one_copy(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, until=None, format=2)
    _approve(root)
    first = manifest_of(root)["delegations_used"]
    _approve(root)
    manifest = manifest_of(root)
    assert manifest["delegations_used"] == first
    assert [e["delegation"] for e in manifest["evidence"] if e.get("delegation")] == [
        "DL-1", "DL-1"]
    assert _file(root)["uses"] == 2


def test_a_revoke_does_not_change_the_copy():
    body = {"id": "DL-1", "delegated_by": OWNER, "forms": ["checks"], "uses": 1}
    revoked = dict(body, revoked_by=OWNER, revoked_at="2026-10-23T10:00:00Z", uses=2)
    assert delegations.copy_of(body) == delegations.copy_of(revoked)


def test_a_changed_delegation_is_added_under_the_next_number(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, until=None, format=2)
    _approve(root)
    # The same id now holds other fields, as when the delegation folder was cleared
    # and DL-1 was typed again.
    _write_dl(root, 1, until=None, format=2, forms=["checks"], prompt_id="p-again", uses=1)
    _approve(root)
    _write_dl(root, 1, until=None, format=2, forms=["checks"], prompt_id="p-third", uses=2)
    _approve(root)
    used = manifest_of(root)["delegations_used"]
    assert list(used) == ["DL-1", "DL-1@2", "DL-1@3"]
    assert used["DL-1@2"]["forms"] == ["checks"] and used["DL-1@2"]["prompt_id"] == "p-again"
    assert len({c["sha256"] for c in used.values()}) == 3
    # A use under the first fields again finds its copy and adds nothing.
    task = {"delegations_used": dict(used)}
    first = delegations.copy_of(dict(_file(root), forms=["checks", "documents",
                                                         "checkpoints", "decisions"],
                                      prompt_id="p-1"))
    assert delegations.keep_copy(task, first) == "DL-1"
    assert list(task["delegations_used"]) == ["DL-1", "DL-1@2", "DL-1@3"]


def test_a_delegated_approval_writes_no_devlog_line(tmp_path):
    root = project(tmp_path)
    devlog = task_dir(root) / "devlog.md"
    before = devlog.read_bytes() if devlog.is_file() else None
    _write_dl(root, 1, until=None, format=2)
    _approve(root)
    assert (devlog.read_bytes() if devlog.is_file() else None) == before


def test_the_copy_matches_the_manifest_schema(tmp_path):
    root = project(tmp_path)
    _write_dl(root, 1, until=None, format=2)
    _write_dl(root, 2, agent=None, covers_session="sess-1", labels=["auth"], max_uses=4,
              until="2999-01-01T00:00:00Z")
    task = {}
    for number in (1, 2):
        delegations.keep_copy(task, delegations.copy_of(_file(root, number)))
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    jsonschema.validate(task["delegations_used"], schema["properties"]["delegations_used"])


def test_an_old_manifest_without_the_key_keeps_its_check_verdict(tmp_path):
    """The key holds the authority only; `compass check` reads nothing from it."""
    root = project(tmp_path)
    before = run(root, "check", "--json", "--issue", SLUG)
    body = manifest_of(root)
    assert delegations.USED_KEY not in body
    _write_dl(root, 1, until=None, format=2)
    delegations.keep_copy(body, delegations.copy_of(_file(root)))
    save_manifest(root, body)
    after = run(root, "check", "--json", "--issue", SLUG)
    assert after[0] == before[0]
    assert json.loads(after[1]) == json.loads(before[1])


def test_a_delegated_ship_approval_copies_the_delegation(tmp_path):
    """The typed ship approval is a writer too; its delegation needs the
    typed-back code."""
    import re

    from test_ship_approval_typed import AGENT, _hook, _owing
    root = _owing(tmp_path)
    first = _hook(root, f"--agent {AGENT} --for ship", command="compass:delegate")
    code_text = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    assert not _hook(root, f"confirm {code_text}", command="compass:delegate").block
    code, out, err = delegated(root, AGENT, "--ship", "--issue", SLUG)
    assert code == 0, out + err
    manifest = manifest_of(root)
    assert manifest["evidence"][-1]["delegation"] == "DL-1"
    copy = manifest["delegations_used"]["DL-1"]
    assert copy["forms"] == ["ship"] and copy["agent"] == AGENT
    assert "requested_prompt_id" not in copy and copy["sha256"] == _digest(copy)
