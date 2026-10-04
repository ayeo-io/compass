"""Rival product names are never committed.

The maintainer's rule (2026-10-04): no rival product name, alias,
organisation, repository slug or URL goes into anything committed to GitHub
or synced to the delivery record. Committed text uses the codes R1 to R9;
the key that maps codes to names stays with the maintainer, untracked.

The gate compares hashes of every token n-gram against committed hashes of
the key's entries, so it can check text without naming what it looks for.
These tests plant an invented product, "Zorblax Kit" under the code `R0`,
never a real one.

Scenario ids: RN-1 to RN-8, in the acceptance criteria of the issue
`rival-names-never-committed` (#366).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "evals"))

try:
    from compass_pkg import rival_names  # noqa: E402
except ImportError:  # before the module exists, each test fails on its own
    rival_names = None

GATE = ROOT / "scripts" / "rival-name-gate.py"
HASHES = ROOT / "scripts" / "rival-name-hashes.txt"
KEY = ROOT / ".compass" / "private" / "rival-codes.yml"

FAKE_KEY = {"rivals": {"R0": {
    "name": "Zorblax Kit",
    "aliases": ["zorblax-kit", "acme/zorblax"],
    "urls": ["https://example.invalid/acme/zorblax"],
}}}


def _gate(*args, cwd=ROOT, stdin=None):
    return subprocess.run([sys.executable, str(GATE), *args], cwd=str(cwd),
                          input=stdin, capture_output=True, text=True,
                          timeout=300)


@pytest.fixture
def fake(tmp_path):
    """A fake key and the hash file the generator writes from it."""
    key = tmp_path / "key.yml"
    key.write_text(yaml.safe_dump(FAKE_KEY), encoding="utf-8")
    hashes = tmp_path / "hashes.txt"
    # Not asserted here: a fixture failure would show as an error, not as
    # the failing test that names what is missing.
    _gate("--write-hashes", str(key), "--hashes", str(hashes))
    return key, hashes


def _repo(root):
    root.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"],
                 ["config", "user.name", "t"]):
        subprocess.run(["git", *args], cwd=str(root), check=True)
    return root


def _commit_all(root):
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=str(root),
                   check=True)


# --- RN-1: the tracked tree names no rival -----------------------------------

def test_rn_1_the_tracked_tree_names_no_rival():
    result = _gate("--tree")
    assert result.returncode == 0, (
        "tracked text or paths name a rival product; replace each with its "
        "code:\n" + result.stdout[-4000:] + result.stderr[-2000:])


# --- RN-2: a planted name fails the gate, and the output names nothing -------

def _assert_reports_without_naming(result, where):
    output = (result.stdout + result.stderr).lower()
    assert result.returncode == 1, f"{where}: the gate passed a planted name"
    assert "zorblax" not in output, f"{where}: the gate printed the name"
    return output


def test_rn_2_a_name_in_a_tracked_file_fails_without_being_named(fake, tmp_path):
    _, hashes = fake
    repo = _repo(tmp_path / "repo")
    (repo / "notes.md").write_text("first line\nWe tried Zorblax Kit once.\n",
                                   encoding="utf-8")
    _commit_all(repo)
    output = _assert_reports_without_naming(
        _gate("--tree", "--hashes", str(hashes), cwd=repo), "file")
    assert "notes.md:2" in output


def test_rn_2_a_name_in_a_tracked_path_fails_without_being_named(fake, tmp_path):
    _, hashes = fake
    repo = _repo(tmp_path / "repo")
    (repo / "seed_zorblax_kit").mkdir()
    (repo / "seed_zorblax_kit" / "a.txt").write_text("nothing here\n",
                                                     encoding="utf-8")
    _commit_all(repo)
    output = _assert_reports_without_naming(
        _gate("--tree", "--hashes", str(hashes), cwd=repo), "path")
    assert "seed_" in output and "a.txt" in output, output


def test_rn_2_a_name_in_a_commit_message_fails_without_being_named(fake):
    _, hashes = fake
    _assert_reports_without_naming(
        _gate("--text", "-", "--hashes", str(hashes),
              stdin="Add a comparison\n\nCompared with acme/zorblax today.\n"),
        "commit message")


def test_rn_2_a_name_in_a_pull_request_body_fails_without_being_named(fake, tmp_path):
    _, hashes = fake
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {
        "title": "Add a comparison",
        "body": "See https://example.invalid/acme/zorblax for details."}}),
        encoding="utf-8")
    _assert_reports_without_naming(
        _gate("--github-event", str(event), "--hashes", str(hashes)),
        "pull request body")


def test_rn_2_a_name_in_both_path_and_text_is_masked_in_the_finding(fake, tmp_path):
    _, hashes = fake
    repo = _repo(tmp_path / "repo")
    (repo / "notes").mkdir()
    (repo / "notes" / "zorblax-kit.md").write_text("About Zorblax Kit.\n",
                                                    encoding="utf-8")
    _commit_all(repo)
    output = _assert_reports_without_naming(
        _gate("--tree", "--hashes", str(hashes), cwd=repo), "path and text")
    assert "notes/[name].md:1" in output, output


@pytest.mark.parametrize("text", [
    "implement-specs/acme/zorblax/b.md",  # an allowed compound before a name
    "seed_zorblax_kit/a.txt",            # a longer name containing a shorter
    "acme/zorblax-kit and acme zorblax",  # a long entry, then a short one
    "seed_zorblax_\u212ait/a.txt",        # a Kelvin sign standing for k
])
def test_rn_2_mask_never_shows_part_of_a_name(tmp_path, text):
    # A key in which one alias, the lone first word, is inside another,
    # so masking must merge overlapping hits.
    key = tmp_path / "key.yml"
    key.write_text(yaml.safe_dump({"rivals": {"R0": {
        "name": "Zorblax Kit", "aliases": ["zorblax", "acme/zorblax-kit"],
        "urls": []}}}), encoding="utf-8")
    hashes = rival_names.hashes_from_key(rival_names.load_key(str(key)))
    masked = rival_names.mask(text, hashes)
    survivors = {"zorblax", "kit"} & set(rival_names.tokens(masked))
    assert not survivors, masked
    assert "[name]" in masked


def test_rn_2_a_name_in_the_branch_name_fails(fake, tmp_path):
    _, hashes = fake
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {
        "title": "Add a comparison", "body": "",
        "head": {"ref": "compare-with-zorblax-kit"}}}), encoding="utf-8")
    output = _assert_reports_without_naming(
        _gate("--github-event", str(event), "--hashes", str(hashes)),
        "branch name")
    assert "branch name" in output


def test_rn_2_redaction_leaves_nothing_the_scan_finds(fake):
    key_path, hashes = fake
    key = rival_names.load_key(key_path)
    loaded = rival_names.load_hashes(hashes)
    for text in ("\u017fZorblax Kit", "zorblax implement-specs kit x",
                 "seed_zorblax_kit", "ACME/Zorblax", "zorblaxkit"):
        redacted = rival_names.redact_names(text, key)
        assert rival_names.scan(redacted, loaded) == [], (text, redacted)


def test_rn_2_clean_text_passes(fake):
    _, hashes = fake
    result = _gate("--text", "-", "--hashes", str(hashes),
                   stdin="Add a comparison with R0\n")
    assert result.returncode == 0, result.stdout + result.stderr


# --- RN-3: whole-token matching, with one allowed compound -------------------

def test_rn_3_the_order_file_name_passes_only_because_it_is_allowed():
    hashes = rival_names.load_hashes(HASHES)
    name = ".claude/commands/implement-specs.md"
    assert rival_names.scan(name, hashes) == []
    assert rival_names.scan(name, hashes, allowed=()) != [], (
        "without the allowed compound the order file's name must fail; "
        "otherwise the exemption is not what passes it")


def test_rn_3_a_name_inside_a_longer_word_does_not_match(fake):
    _, hashes = fake
    loaded = rival_names.load_hashes(hashes)
    assert rival_names.scan("zorblaxkitten", loaded) == []
    assert rival_names.scan("zorblax_kit", loaded) == [1]


# --- RN-4: rival eval conditions load from the key ---------------------------

def test_rn_4_a_rival_condition_without_the_key_is_skipped(tmp_path, capsys):
    import harness
    out = tmp_path / "out"
    code = harness.main(["--scenario", "cmp-edge-case", "--condition", "R1",
                         "--out", str(out),
                         "--frameworks-config", str(tmp_path / "absent.yml")])
    err = capsys.readouterr().err
    assert code == 0
    assert "skipped" in err and "key" in err, err
    assert not list(out.glob("*.json")) if out.exists() else True


def test_rn_4_the_conditions_are_codes():
    import harness
    choices = next(a for a in harness._build_arg_parser()._actions
                   if a.dest == "condition").choices
    assert sorted(choices) == ["R1", "R3", "bare", "compass"]


def test_rn_4_a_key_shaped_file_pins_the_rival_condition(tmp_path):
    import harness
    key = tmp_path / "key.yml"
    key.write_text(yaml.safe_dump({"rivals": {
        "R1": {"name": "x", "aliases": [], "urls": [],
               "eval": {"repo": "https://example.invalid/r1", "commit": "a" * 40}},
        "R2": {"name": "y", "aliases": [], "urls": []}}}), encoding="utf-8")
    config = harness.load_frameworks_config(key)
    assert config == {"R1": {"repo": "https://example.invalid/r1",
                             "commit": "a" * 40}}
    harness._check_framework_commit_pin("R1", "a" * 40, config)


# Hashes of each rival condition's command line before the sweep renamed the
# conditions, so the rename provably changed nothing a session runs.
_ARGS_BEFORE_THE_SWEEP = {
    "R1": "a95fd410f345ec6357acf2c544f0939b4c71c71c6ddaccc12a261a57ff6643a5",
    "R3": "588c1d39d5b268e72ebc9abd664af376fbab5b1e0a699e1916cbde451971eda3",
}


@pytest.mark.parametrize("code", sorted(_ARGS_BEFORE_THE_SWEEP))
def test_rn_4_the_rename_leaves_each_command_line_unchanged(code):
    import harness
    args = harness._common_claude_args(code, None, Path("/framework"),
                                       Path("/scripts"))
    digest = hashlib.sha256("\0".join(args).encode()).hexdigest()
    assert digest == _ARGS_BEFORE_THE_SWEEP[code]


def test_rn_4_the_seed_path_map_applies_to_the_overlay_only():
    import harness
    paths = {"docs/R1": "docs/real-folder"}
    assert harness._mapped("docs/R1/plans/p.md", paths) == "docs/real-folder/plans/p.md"
    assert harness._mapped("docs/R1", paths) == "docs/real-folder"
    assert harness._mapped("docs/R10/p.md", paths) == "docs/R10/p.md"
    assert harness._mapped("src/a.py", paths) == "src/a.py"


def test_rn_4_no_frameworks_file_is_tracked():
    tracked = subprocess.run(["git", "ls-files", "evals/frameworks.yml"],
                             cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.stdout.strip() == ""


# --- RN-5: record sync redacts, and refuses without the key ------------------

def _record_project(tmp_path, monkeypatch, key_source):
    """A project syncing `docs/analysis` with a names key configured under
    `.compass/private/`, copied there from `key_source` when one is given;
    without one the configured key is missing."""
    from test_delivery_record import _remote
    from test_ship_commit_derives import _init_repo
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "project"
    root.mkdir()
    _init_repo(root)
    (root / "docs" / "analysis").mkdir(parents=True)
    (root / "docs" / "analysis" / "zorblax-kit-notes.md").write_text(
        "We compared Compass with Zorblax Kit (acme/zorblax).\n",
        encoding="utf-8")
    remote = _remote(tmp_path)
    cfg = root / ".compass" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(f"record:\n  remote: {remote}\n  paths:\n"
                   f"    - docs/analysis\n"
                   f"  names_key: .compass/private/key.yml\n",
                   encoding="utf-8")
    if key_source is not None:
        (root / ".compass" / "private").mkdir()
        (root / ".compass" / "private" / "key.yml").write_text(
            Path(key_source).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.delenv("COMPASS_RIVALS_KEY", raising=False)
    return root, remote


def _cli(cwd, *args):
    return subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *args],
                          cwd=str(cwd), capture_output=True, text=True,
                          timeout=120)


def test_rn_5_record_sync_sends_codes_only(fake, tmp_path, monkeypatch):
    key, _ = fake
    root, remote = _record_project(tmp_path, monkeypatch, key)
    result = _cli(root, "record", "sync")
    assert result.returncode == 0, result.stdout + result.stderr
    clone = tmp_path / "check"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(clone)],
                   check=True)
    files = [p for p in clone.rglob("*") if p.is_file() and ".git" not in p.parts]
    assert files, "nothing was synced"
    for path in files:
        rel = str(path.relative_to(clone)).lower()
        assert "zorblax" not in rel, rel
        assert "zorblax" not in path.read_text(encoding="utf-8").lower()
    assert any("R0" in p.read_text(encoding="utf-8") for p in files)


def test_rn_5_record_sync_refuses_when_the_key_is_missing(tmp_path, monkeypatch):
    root, remote = _record_project(tmp_path, monkeypatch, None)
    result = _cli(root, "record", "sync")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "key" in result.stderr
    log = subprocess.run(["git", "log", "--oneline", "--all"], cwd=str(remote),
                         capture_output=True, text=True)
    assert log.stdout.strip() == "", "a refused sync still pushed"


def test_rn_5_a_linked_worktree_finds_the_key_in_the_main_checkout(
        tmp_path, monkeypatch):
    from compass_pkg import record
    from test_ship_commit_derives import _init_repo
    monkeypatch.delenv("COMPASS_RIVALS_KEY", raising=False)
    main = tmp_path / "main"
    main.mkdir()
    _init_repo(main)
    (main / ".compass").mkdir(exist_ok=True)
    (main / ".compass" / "config.yml").write_text(
        "record:\n  remote: x\n  paths: [docs]\n"
        "  names_key: .compass/private/key.yml\n", encoding="utf-8")
    (main / ".compass" / "private").mkdir()
    (main / ".compass" / "private" / "key.yml").write_text(
        yaml.safe_dump(FAKE_KEY), encoding="utf-8")
    worktree = tmp_path / "wt"
    subprocess.run(["git", "worktree", "add", "-q", "-b", "wt", str(worktree)],
                   cwd=str(main), check=True)
    (worktree / ".compass").mkdir(exist_ok=True)
    (worktree / ".compass" / "config.yml").write_text(
        (main / ".compass" / "config.yml").read_text(), encoding="utf-8")
    found = record.names_key(str(worktree))
    assert found and os.path.samefile(found, main / ".compass" / "private" / "key.yml")


@pytest.mark.parametrize("bad", ["../outside.yml", "/etc/key.yml",
                                 "a/../../outside.yml"])
def test_rn_5_a_key_outside_the_project_is_refused(tmp_path, bad):
    from compass_pkg import record
    from compass_pkg.core import CompassError
    from test_ship_commit_derives import _init_repo
    root = tmp_path / "p"
    root.mkdir()
    _init_repo(root)
    (root / ".compass").mkdir(exist_ok=True)
    (root / ".compass" / "config.yml").write_text(
        f"record:\n  remote: x\n  paths: [docs]\n  names_key: {bad}\n",
        encoding="utf-8")
    with pytest.raises(CompassError, match="inside the project"):
        record.names_key(str(root))


def test_rn_5_a_record_folder_named_for_a_rival_syncs_under_its_code(
        fake, tmp_path, monkeypatch):
    from compass_pkg import record
    key, _ = fake
    root, remote = _record_project(tmp_path, monkeypatch, key)
    folder = root / "docs" / "analysis" / "zorblax-kit-issue"
    folder.mkdir()
    (folder / "notes.md").write_text("plain\n", encoding="utf-8")
    record.sync(str(root), only=["docs/analysis/zorblax-kit-issue"])
    clone = tmp_path / "check2"
    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(clone)],
                   check=True)
    names = [str(p.relative_to(clone)).lower() for p in clone.rglob("*")
             if ".git" not in p.parts]
    assert names and not any("zorblax" in n for n in names), names


def test_rn_5_this_project_configures_its_key():
    config = yaml.safe_load((ROOT / ".compass" / "config.yml").read_text()
                            if (ROOT / ".compass" / "config.yml").exists()
                            else "{}") or {}
    record = config.get("record") or {}
    if not record:
        pytest.skip("this checkout has no delivery record configured")
    assert record.get("names_key") == ".compass/private/rival-codes.yml"


# --- RN-6: CI runs the gate over pull request text ---------------------------

def test_rn_6_ci_runs_the_gate_over_commits_title_and_body():
    workflow = (ROOT / ".github" / "workflows" / "compass.yml").read_text()
    steps = [step for job in yaml.safe_load(workflow)["jobs"].values()
             for step in job.get("steps", [])]
    runs = "\n".join(step.get("run", "") for step in steps)
    assert "rival-name-gate.py --github-event" in runs
    assert "git log --format=%B" in runs and "rival-name-gate.py --text -" in runs
    gate_step = next(step for step in steps
                     if "rival-name-gate.py" in step.get("run", ""))
    assert gate_step.get("shell") == "bash", "pipefail needs `shell: bash`"
    for expression in ("pull_request.title", "pull_request.body",
                       "head.ref", "head_ref"):
        assert expression not in workflow, (
            f"{expression} reaches the workflow text; the gate reads it "
            f"from the event file")
    triggers = yaml.safe_load(workflow)[True]["pull_request"]["types"]
    assert "edited" in triggers


# --- RN-7: the rule is stated where sessions read it -------------------------

@pytest.mark.parametrize("rel", ["CLAUDE.md",
                                 "skills/compass-runtime/writing-voice.md"])
def test_rn_7_the_rule_is_stated(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert "rival product" in text.lower(), rel
    assert "code" in text.lower() and "names key" in text.lower(), rel


# --- RN-8: the hash file is exactly what the key gives -----------------------

def test_rn_8_the_hash_file_matches_the_key():
    if not KEY.is_file():
        pytest.skip("the names key is held by the maintainer and is not in "
                    "this checkout (CI): the hash file cannot be compared")
    result = _gate("--check-hashes", str(KEY))
    assert result.returncode == 0, result.stdout + result.stderr


def test_rn_8_the_key_is_never_tracked():
    tracked = subprocess.run(["git", "ls-files", ".compass/private"],
                             cwd=str(ROOT), capture_output=True, text=True)
    assert tracked.stdout.strip() == ""


# --- RN-9: the sweep keeps every published number ----------------------------

# Each swept run document's numbers before the sweep, as a hash of the
# sequence of every number in it (a digit run not glued to a letter, so the
# codes' own digits are left out).
_NUMBERS_BEFORE_THE_SWEEP = {
    "docs/compass/2026-08-26-first-hour-intent.md": "a7600bb98ce43d1d",
    "docs/compass/2026-08-27-sdd-loop-spike.md": "3d6f34001ca91ddb",
    "docs/compass/2026-09-28-comparison-suite-run-3.md": "dc4d6338d311797a",
    "docs/compass/2026-09-28-eval-comparison.md": "e24eba21ed5da5ee",
    "docs/compass/2026-09-28-quick-fix-evaluation-cost.md": "fd9612c54be6d7e2",
    "docs/compass/2026-09-30-eval-comparison-discriminating.md": "fbd601094d460131",
}

KEY_NOTE = ("Rival products appear as codes R1 to R9; the maintainer holds "
            "the key.")


@pytest.mark.parametrize("rel", sorted(_NUMBERS_BEFORE_THE_SWEEP))
def test_rn_9_the_sweep_keeps_every_number(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    numbers = re.findall(r"(?<![A-Za-z0-9])\d[\d,.]*", text.replace(KEY_NOTE, ""))
    digest = hashlib.sha256(" ".join(numbers).encode()).hexdigest()[:16]
    assert digest == _NUMBERS_BEFORE_THE_SWEEP[rel]


@pytest.mark.parametrize("rel", sorted(_NUMBERS_BEFORE_THE_SWEEP))
def test_rn_9_each_swept_run_says_where_the_key_is(rel):
    assert KEY_NOTE in (ROOT / rel).read_text(encoding="utf-8")
