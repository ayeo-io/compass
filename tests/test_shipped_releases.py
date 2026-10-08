"""The table of shipped governance releases (`compass policy migrate` base).

`compass policy migrate` finds which shipped release a project's copied
governance came from, so it can tell a local edit from a default that moved
since. The table and the archive of the files are data in `governance/`. The
installed plugin has no git tags, so nothing reads a tag at run time; this
test is where the tags and the table are held together.

Scenario ids: `PM-12` (issue `policy-migrate`).
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

TABLE = ROOT / "governance" / "shipped-releases.yml"
ARCHIVE = ROOT / "governance" / "shipped-releases.tar.xz"
FILES = ("routing-policy.yml", "guardrails.yml")


def _api():
    from compass_pkg import shipped_releases
    return shipped_releases


def _content_hash(text):
    """The way `tests/test_governance_drift.py` hashes a governance file."""
    data = yaml.safe_load(text)
    data.pop("version", None)
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _tags():
    out = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT, capture_output=True,
                         text=True)
    return out.stdout.split() if out.returncode == 0 else []


def _tag_text(tag, name):
    return subprocess.run(["git", "show", f"{tag}:governance/{name}"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout


def test_PM_12_the_table_and_the_archive_exist_and_agree():
    assert TABLE.is_file() and ARCHIVE.is_file()
    api = _api()
    releases = api.table()
    assert releases and releases[0]["tag"] == "v1.0.0"
    for release in releases:
        policy_text, guardrails_text = api.texts(release["tag"])
        assert _content_hash(policy_text) == release["routing_policy"]["digest"]
        assert _content_hash(guardrails_text) == release["guardrails"]["digest"]
        assert str(yaml.safe_load(policy_text)["version"]) == release["routing_policy"]["version"]


def test_PM_12_the_table_holds_every_tagged_release_and_matches_its_files():
    tags = _tags()
    if not tags:
        pytest.skip("this checkout has no release tags (a shallow clone)")
    api = _api()
    by_tag = {r["tag"]: r for r in api.table()}
    assert api.missing_tags(list(by_tag.values()), tags) == []
    for tag in tags:
        assert _content_hash(_tag_text(tag, "routing-policy.yml")) \
            == by_tag[tag]["routing_policy"]["digest"], tag
        assert _content_hash(_tag_text(tag, "guardrails.yml")) \
            == by_tag[tag]["guardrails"]["digest"], tag


def test_PM_12_a_table_without_one_release_is_reported():
    api = _api()
    releases = api.table()
    smaller = [r for r in copy.deepcopy(releases) if r["tag"] != "v5.3.0"]
    assert api.missing_tags(smaller, [r["tag"] for r in releases]) == ["v5.3.0"]


def test_PM_12_the_current_shipped_files_are_a_candidate_after_the_newest_release():
    api = _api()
    current = api.current()
    assert current["tag"] == "current"
    assert current["routing_policy"]["version"] == str(
        yaml.safe_load((ROOT / "governance" / "routing-policy.yml").read_text(
            encoding="utf-8"))["version"])


# --- the rival-name gate reads inside the archive (PM-19) --------------------------
#
# `scripts/rival-name-gate.py --tree` reads tracked files as bytes and scans
# their text. A compressed archive has no readable text, so the gate cannot see
# its members. This test unpacks the archive and gives every member to the
# gate's own text scan.

GATE = ROOT / "scripts" / "rival-name-gate.py"
REAL_HASHES = ROOT / "scripts" / "rival-name-hashes.txt"


def _members(archive_path):
    with tarfile.open(archive_path, "r:xz") as archive:
        return {m.name: archive.extractfile(m).read().decode("utf-8")
                for m in archive.getmembers() if m.isfile()}


def _gate_findings(archive_path, hashes_path):
    """The gate's findings (its stdout lines) for each member of an archive,
    scanned through `rival-name-gate.py --text -`."""
    found = []
    for name, text in sorted(_members(archive_path).items()):
        run = subprocess.run([sys.executable, str(GATE), "--text", "-", "--hashes",
                              str(hashes_path)], input=text, capture_output=True,
                             text=True, timeout=120)
        if run.returncode != 0:
            found.append((name, run.returncode, run.stdout.strip()))
    return found


def test_PM_19_no_member_of_the_archive_holds_a_rival_name():
    assert len(_members(ARCHIVE)) >= 2, "the archive holds no members to scan"
    assert _gate_findings(ARCHIVE, REAL_HASHES) == []


def test_PM_19_the_member_scan_fails_on_a_planted_name(tmp_path):
    # An invented product under a fake key, as tests/test_rival_names_never_committed.py
    # does: no real name is written anywhere.
    key = tmp_path / "key.yml"
    key.write_text(yaml.safe_dump({"rivals": {"R0": {"name": "Zorblax Kit"}}}),
                   encoding="utf-8")
    hashes = tmp_path / "hashes.txt"
    done = subprocess.run([sys.executable, str(GATE), "--write-hashes", str(key),
                           "--hashes", str(hashes)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    planted = tmp_path / "planted.tar.xz"
    with tarfile.open(planted, "w:xz") as archive:
        for name, text in (("routing-policy/clean.yml", "version: 1\n"),
                           ("guardrails/dirty.yml", "# built on Zorblax Kit\nversion: 1\n")):
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    found = _gate_findings(planted, hashes)
    assert [name for name, _, _ in found] == ["guardrails/dirty.yml"]
    assert "zorblax" not in found[0][2].lower(), "the gate printed the name"
