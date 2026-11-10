"""What each section of `trail.md` says, from fixture records.

Step 5 of #356 [Commit the issue record with the code and add trail.md]. Each
test starts one quick fix with `compass quick-fix start` in a git repository,
then writes the records a section reads straight into the issue folder, and
runs `compass trail`. The sections, in the issue's order: who asked, what was
agreed, the red for each scenario, the green, who approved and by what
authority, what shipped. `tests/test_trail_sha256sum.py` checks the sum lines
with the real `sha256sum`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "fix-f"
REQUEST = "https://example.com/tickets/1"


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout.strip()


def run(cwd, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          capture_output=True, text=True)


def _ok(cwd, *args):
    done = run(cwd, *args)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


def _start(root, *flags):
    _ok(root, "quick-fix", "start", SLUG,
        "--risk", "trivial - one line", "--familiarity",
        "brownfield-mapped - the file and its test exist",
        "--size", "atomic - one line", "--intent", "f returns 2",
        "--scenario", "Given f, when called, then it returns 2.",
        "--scenario-id", "TRC-001", "--test", "tests/test_f.py", *flags)


def _issue(tmp_path, *flags, sub=None, git=True):
    """A project with one started quick fix, in a git repository unless `git`
    is false; `sub` puts the project in a folder below the repository root.
    Returns the project root."""
    repo = tmp_path / "repo"
    root = repo / sub if sub else repo
    (root / "src").mkdir(parents=True)
    (root / "src" / "f.py").write_text("def f():\n    return 2\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_f.py").write_text("def test_f():\n    assert True\n")
    if sub or not git:
        # Started outside git, Compass makes its project here, not at a
        # repository root above.
        _start(root, *flags)
    if git:
        _git(repo, "init", "-q")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "t")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
    if not sub and git:
        _start(root, *flags)
    return root


def _dir(root):
    return root / ".compass" / "work" / SLUG


def manifest(root):
    return yaml.safe_load((_dir(root) / "manifest.yml").read_text())


def write_manifest(root, body):
    (_dir(root) / "manifest.yml").write_text(
        yaml.safe_dump(body, sort_keys=False, default_flow_style=False))


def _update(root, **keys):
    body = manifest(root)
    body.update(keys)
    write_manifest(root, body)


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _record(root, name, **fields):
    evidence = _dir(root) / "evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / name).write_text(json.dumps(fields, indent=2))
    (evidence / name.replace(".json", ".log")).write_text("log of " + name + "\n")


def _red(root, scenario="TRC-001", at="2026-11-07T10:00:00+00:00"):
    _record(root, f"red-{scenario}.outer.json", command="pytest tests/test_f.py",
            scenario=scenario, loop="outer", exit_code=1, passed=False, timestamp=at)


def _green(root, scenario="TRC-001", at="2026-11-07T10:05:00+00:00", files=None):
    _record(root, f"green-{scenario}.outer.json", command="pytest tests/test_f.py",
            scenario=scenario, loop="outer", exit_code=0, passed=True, timestamp=at,
            file_sha256=files or {})


def trail(root):
    _ok(root, "trail", "--issue", SLUG)
    return (_dir(root) / "trail.md").read_text()


def section(text, number):
    """The body of section `number`, without its heading."""
    start = text.index(f"\n## {number}. ")
    end = text.find("\n## ", start + 1)
    body = text[start:] if end < 0 else text[start:end]
    return body.split("\n", 2)[2]


def _sums(body):
    return [line.split("  ", 1)[1] for line in body.splitlines()
            if len(line) > 66 and line[64:66] == "  "]


# --- 1. who asked ---------------------------------------------------------------------------

def test_who_asked_names_the_requester_as_a_claim_and_hashes_the_manifest(tmp_path):
    root = _issue(tmp_path, "--request", REQUEST, "--requester", "Dana Smith")
    body = section(trail(root), 1)
    assert f"Dana Smith asked at {REQUEST}, recorded " in body
    assert "Compass does not check who the requester is." in body
    assert _sums(body) == [f".compass/work/{SLUG}/manifest.yml"]


def test_who_asked_names_quick_fix_start_when_it_recorded_the_request(tmp_path):
    root = _issue(tmp_path, "--request", REQUEST, "--requester", "Dana Smith")
    assert manifest(root)["request"]["recorded_by"] == "compass quick-fix start"
    body = section(trail(root), 1)
    assert " with `compass quick-fix start`. Compass does not check" in body, body
    assert "issue link set" not in body, body


def test_who_asked_names_issue_link_set_when_it_recorded_the_request(tmp_path):
    root = _issue(tmp_path)
    _ok(root, "issue", "link", "set", "--issue", SLUG, "--request", REQUEST,
        "--requester", "Dana Smith")
    assert manifest(root)["request"]["recorded_by"] == "compass issue link set"
    body = section(trail(root), 1)
    assert " with `compass issue link set`. Compass does not check" in body, body


def test_who_asked_names_no_command_when_the_record_names_none(tmp_path):
    """A request recorded before `recorded_by` existed names no command, rather
    than a command that may not have written it."""
    root = _issue(tmp_path, "--request", REQUEST, "--requester", "Dana Smith")
    body = manifest(root)
    body["request"] = {"link": REQUEST, "requester": "Dana Smith",
                       "recorded_at": "2026-11-07T10:00:00Z"}
    write_manifest(root, body)
    text = section(trail(root), 1)
    assert (f"Dana Smith asked at {REQUEST}, recorded 2026-11-07T10:00:00Z. "
            "Compass does not check") in text, text
    # The trail is written from the record alone, so a second write is the same.
    assert trail(root) == trail(root)


def test_who_asked_says_what_is_missing(tmp_path):
    # `start` records "not stated at start" when it gets a link and no
    # requester, so the missing requester is a record written another way.
    root = _issue(tmp_path, "--request", REQUEST)
    held = manifest(root)
    held["request"] = {"link": REQUEST, "recorded_at": "2026-11-07T10:00:00Z"}
    write_manifest(root, held)
    body = section(trail(root), 1)
    assert "The record holds no requester" in body and REQUEST in body


# --- 2. what was agreed ---------------------------------------------------------------------

def test_what_was_agreed_lists_the_scenarios_and_hashes_the_spec(tmp_path):
    root = _issue(tmp_path)
    body = section(trail(root), 2)
    assert "- TRC-001: Given f, when called, then it returns 2." in body
    named = _sums(body)
    assert len(named) == 1 and named[0].endswith(f"-{SLUG}/acceptance-criteria.md"), named


def test_a_frozen_spec_that_changed_says_so(tmp_path):
    root = _issue(tmp_path)
    spec = next((root / "docs" / "compass").glob(f"*-{SLUG}/acceptance-criteria.md"))
    frozen = hashlib.sha256(spec.read_bytes()).hexdigest()
    _update(root, scenario_freeze={"at": "2026-11-07T10:00:00Z",
                                   "red": "evidence/red-TRC-001.outer.json",
                                   "spec": str(spec.relative_to(root)),
                                   "spec_sha256": frozen, "scenarios": ["TRC-001"]})
    assert f"spec sha256 {frozen[:12]}; unchanged since." in section(trail(root), 2)
    spec.write_text(spec.read_text() + "\nA line added after the first red.\n")
    assert f"spec sha256 {frozen[:12]}; changed since." in section(trail(root), 2)


def test_a_quick_fix_with_no_spec_file_hashes_the_manifest(tmp_path):
    root = _issue(tmp_path)
    for spec in (root / "docs" / "compass").glob(f"*-{SLUG}/acceptance-criteria.md"):
        spec.unlink()
    body = section(trail(root), 2)
    assert "There is no spec file; the scenarios are in the manifest." in body
    assert _sums(body) == [f".compass/work/{SLUG}/manifest.yml"]


def test_an_owed_sign_off_names_the_approver_and_the_spec_digest(tmp_path):
    root = _issue(tmp_path)
    body = manifest(root)
    body["evidence_required"] = body["evidence_required"] + ["scenario-approval"]
    body["evidence"] = [{"id": "EV-CHECKPOINT-specify-1", "type": "checkpoint-approval",
                         "checkpoint": "specify", "approver": "jed72", "role": "owner",
                         "scope": "the specify hand-off", "decision": "approved",
                         "timestamp": "2026-11-07T09:00:00Z", "spec_sha256": "a" * 64,
                         "via": "prompt", "request": 1}]
    write_manifest(root, body)
    agreed = section(trail(root), 2)
    assert ("Scenarios signed off by jed72 at 2026-11-07T09:00:00Z "
            "(EV-CHECKPOINT-specify-1), spec sha256 aaaaaaaaaaaa.") in agreed


# --- 3 and 4. red and green -----------------------------------------------------------------

def test_a_scenario_with_no_red_says_so_and_has_no_sum_line(tmp_path):
    root = _issue(tmp_path)
    text = trail(root)
    assert "- TRC-001: no red on record." in section(text, 3)
    assert _sums(section(text, 3)) == []
    assert "- TRC-001: no green on record." in section(text, 4)


def test_red_and_green_name_their_records_and_logs(tmp_path):
    root = _issue(tmp_path)
    _red(root)
    _green(root)
    text = trail(root)
    red = section(text, 3)
    assert ("- TRC-001 failed at 2026-11-07T10:00:00+00:00, exit 1 (outer loop): "
            "`pytest tests/test_f.py`") in red
    evidence = f".compass/work/{SLUG}/evidence/"
    assert _sums(red) == [evidence + "red-TRC-001.outer.json", evidence + "red-TRC-001.outer.log"]
    assert "- TRC-001 passed at 2026-11-07T10:05:00+00:00, exit 0 (outer loop)" in section(text, 4)


def test_the_code_lines_hold_the_digests_of_the_newest_green_not_the_disk(tmp_path):
    root = _issue(tmp_path)
    _record(root, "green.json", command="pytest", exit_code=0, passed=True,
            timestamp="2026-11-07T10:01:00+00:00", file_sha256={"src/f.py": "1" * 64})
    _green(root, files={"src/f.py": "2" * 64, "tests/test_f.py": "3" * 64,
                        "bad": "not a digest"})
    green = section(trail(root), 4)
    assert "The files as the newest green tested them (green-TRC-001.outer.json)." in green
    assert f"{'2' * 64}  src/f.py" in green and f"{'3' * 64}  tests/test_f.py" in green
    assert "1" * 64 not in green and "bad" not in _sums(green)
    # The digest on disk is not the one named.
    disk = hashlib.sha256((root / "src" / "f.py").read_bytes()).hexdigest()
    assert disk not in green


# --- 5. who approved ------------------------------------------------------------------------

def _approvals(root):
    body = manifest(root)
    body["pull_request"] = {"repo": "acme/widgets", "number": 7,
                            "merged_at": "2026-11-07T12:00:00Z", "merge_commit": "c" * 40,
                            "author": "dev1"}
    body["delegations_used"] = {"DL-3": {"delegated_by": "jed72", "role": "owner",
                                         "sha256": "d" * 64}}
    body["waivers"] = [{"id": "W-1", "check": "layering-recorded", "reason": "no layers",
                        "requested_at": "2026-11-07T09:30:00Z", "requested_by": "agent"}]
    body["evidence"] = [
        {"id": "EV-APPROVAL-G5-1", "type": "human-approval", "guardrail": "G5",
         "approver": "jed72", "role": "owner", "scope": "the change",
         "decision": "approved", "timestamp": "2026-11-07T09:00:00Z", "via": "terminal"},
        {"id": "EV-CHECKPOINT-specify-1", "type": "checkpoint-approval",
         "checkpoint": "specify", "approver": "jed72", "role": "owner",
         "decision": "approved", "timestamp": "2026-11-07T09:10:00Z", "via": "prompt",
         "request": 2},
        {"id": "EV-APPROVAL-dod-reviewed-1", "type": "human-approval", "check": "dod-reviewed",
         "approver": "jed72", "role": "owner", "scope": "the review",
         "decision": "approved", "timestamp": "2026-11-07T09:20:00Z", "via": "delegation",
         "approved_by_agent": "compass:architect", "delegation": "DL-3"},
        {"id": "EV-WAIVER-W-1-1", "type": "human-approval", "waiver": "W-1",
         "waived_check": "layering-recorded", "waiver_reason": "no layers",
         "approver": "jed72", "role": "owner", "decision": "approved",
         "timestamp": "2026-11-07T09:40:00Z", "via": "terminal"},
        {"id": "EV-PR-APPROVAL-1", "type": "pr-approval",
         "pull_request": {"repo": "acme/widgets", "number": 7}, "review_id": 99,
         "url": "https://github.com/acme/widgets/pull/7#pullrequestreview-99",
         "approver": "rev2", "decision": "approved", "timestamp": "2026-11-07T11:00:00Z",
         "via": "github"},
        {"id": "EV-WITHDRAWAL-1", "type": "approval-withdrawal",
         "withdraws": "EV-APPROVAL-dod-reviewed-1", "by": "jed72",
         "at": "2026-11-07T09:50:00Z"},
    ]
    write_manifest(root, body)


def test_each_approval_names_who_when_and_by_what_authority(tmp_path):
    root = _issue(tmp_path, "--request", REQUEST, "--requester", "Dana Smith")
    _approvals(root)
    body = section(trail(root), 5)
    assert ("- EV-APPROVAL-G5-1: the guardrail `G5` sign-off, approved by jed72 (owner) at "
            "2026-11-07T09:00:00Z, typed at a terminal.") in body
    assert ("- EV-CHECKPOINT-specify-1: the specify checkpoint, approved by jed72 (owner) at "
            "2026-11-07T09:10:00Z, typed in Claude Code (`/compass:approve`) for request 2."
            ) in body
    assert ("- EV-APPROVAL-dod-reviewed-1: check dod-reviewed, approved by jed72 (owner) at "
            "2026-11-07T09:20:00Z, under delegation DL-3 given by jed72, copy sha256 "
            "dddddddddddd, used by compass:architect.") in body
    assert ("- EV-WAIVER-W-1-1: waiver W-1 of layering-recorded, approved by jed72 (owner)"
            ) in body
    assert ("- EV-PR-APPROVAL-1: pull request acme/widgets#7, approved by rev2 at "
            "2026-11-07T11:00:00Z, review 99 by rev2 on acme/widgets#7, "
            "https://github.com/acme/widgets/pull/7#pullrequestreview-99.") in body
    assert ("- EV-WITHDRAWAL-1: withdraws EV-APPROVAL-dod-reviewed-1, by jed72 at "
            "2026-11-07T09:50:00Z.") in body
    assert ("- Waiver W-1 of layering-recorded: no layers; approved in EV-WAIVER-W-1-1."
            ) in body
    # The requester is a claim, never an approval.
    assert "Dana Smith" not in body
    assert "Ship approval:" not in body
    assert _sums(body) == [f".compass/work/{SLUG}/manifest.yml"]


def test_a_ship_approval_not_on_record_says_when_it_is_due(tmp_path):
    root = _issue(tmp_path)
    assert "Ship approval: not on record yet." in section(trail(root), 5)
    _update(root, pull_request={"repo": "acme/widgets", "number": 7})
    assert ("Ship approval: read from pull request acme/widgets#7 after the merge."
            in section(trail(root), 5))


# --- 6. what shipped ------------------------------------------------------------------------

def test_a_stored_land_commit_is_named(tmp_path):
    root = _issue(tmp_path)
    _update(root, status="done", close_reason="completed", release_note="f returns 2",
            land_timestamp="2026-11-07T12:00:00+00:00", land_commit="e" * 40)
    body = section(trail(root), 6)
    assert f"Landed 2026-11-07T12:00:00+00:00 in {'e' * 40}." in body
    assert "Release line: f returns 2" in body
    assert _sums(body)[0] == f".compass/work/{SLUG}/manifest.yml"


def test_a_committed_landing_names_how_to_find_its_commit_not_an_id(tmp_path):
    root = _issue(tmp_path)
    _update(root, status="done", close_reason="completed", landed_with_record=True,
            land_timestamp="2026-11-07T12:00:00+00:00")
    body = section(trail(root), 6)
    assert "Landed 2026-11-07T12:00:00+00:00, with this record, in the commit that" in body
    assert f"-- .compass/work/{SLUG}/manifest.yml" in body


def test_an_issue_in_flight_has_not_landed(tmp_path):
    root = _issue(tmp_path)
    assert "Not landed yet." in section(trail(root), 6)


# --- the file -------------------------------------------------------------------------------

def test_the_same_record_gives_the_same_bytes(tmp_path):
    root = _issue(tmp_path, "--request", REQUEST, "--requester", "Dana Smith")
    _approvals(root)
    _red(root)
    _green(root, files={"src/f.py": "2" * 64})
    first = trail(root)
    assert trail(root) == first
    assert run(root, "trail", "--check", "--issue", SLUG).returncode == 0


def test_a_project_below_the_repository_root_names_paths_from_the_root(tmp_path):
    root = _issue(tmp_path, sub="app")
    _green(root, files={"src/f.py": "2" * 64})
    text = trail(root)
    assert f"grep -E '^[0-9a-f]{{64}}  ' app/.compass/work/{SLUG}/trail.md | sha256sum -c -" in text
    assert f"{'2' * 64}  app/src/f.py" in text
    assert _sums(section(text, 1)) == [f"app/.compass/work/{SLUG}/manifest.yml"]


def test_outside_git_the_paths_start_at_the_project_root(tmp_path):
    root = _issue(tmp_path, git=False)
    text = trail(root)
    assert "From the project root, check every file named below:" in text
    assert _sums(section(text, 1)) == [f".compass/work/{SLUG}/manifest.yml"]


def test_a_spike_gets_no_trail(tmp_path):
    root = _issue(tmp_path)
    _update(root, delivery_approach="spike")
    done = run(root, "trail", "--issue", SLUG)
    assert done.returncode != 0
    assert "is a spike" in done.stdout + done.stderr
    assert not (_dir(root) / "trail.md").exists()


def test_check_without_a_trail_reports_it_missing(tmp_path):
    root = _issue(tmp_path)
    done = run(root, "trail", "--check", "--issue", SLUG)
    assert done.returncode == 1 and "missing" in done.stdout, done.stdout


def test_compass_check_prints_a_trail_line_and_no_row(tmp_path):
    root = _issue(tmp_path, "--request", REQUEST, "--requester", "Dana Smith")
    before = json.loads(run(root, "check", "--issue", SLUG, "--json").stdout)
    assert not any(n.startswith("Trail:") for n in before["notices"]), before["notices"]
    trail(root)
    fresh = json.loads(run(root, "check", "--issue", SLUG, "--json").stdout)
    assert "Trail: up to date" in fresh["notices"], fresh["notices"]
    _ok(root, "issue", "link", "set", "--issue", SLUG, "--requester", "Lee Jones")
    stale = json.loads(run(root, "check", "--issue", SLUG, "--json").stdout)
    assert "Trail: out of date; run `compass trail`" in stale["notices"], stale["notices"]
    assert ([c["name"] for c in stale["checks"]] == [c["name"] for c in fresh["checks"]]
            == [c["name"] for c in before["checks"]])
    assert stale["failed"] == fresh["failed"]
    verbose = run(root, "check", "--issue", SLUG, "--verbose")
    assert "Trail: out of date; run `compass trail`" in verbose.stdout, verbose.stdout
