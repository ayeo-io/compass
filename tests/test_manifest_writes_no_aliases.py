"""The manifest writer writes no YAML anchors or aliases.

A manifest that holds one object under two keys, such as the assessment's
`labels` list copied to `evaluated_assessment`, was written as
`labels: &id001 []` and `labels: *id001`. A reader of the committed record
then has to know YAML anchors to read it. `manifest_store.dump` writes each
value in full.

A manifest written before this change can still hold anchors, so the
readers must keep reading one: the second half of this file runs each
reader over such a manifest.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

import yaml  # noqa: E402  (the bundled copy, once compass_pkg is on the path)

from compass_pkg import manifest_store  # noqa: E402

SLUG = "fix-f"


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def _compass(cwd, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          capture_output=True, text=True)


def _ok(cwd, *args):
    done = _compass(cwd, *args)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


def _anchored(text):
    return any(token in text for token in ("&id0", "*id0"))


def _started(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "f.py").write_text("def f():\n    return 1\n")
    (root / "tests" / "test_f.py").write_text("def test_f():\n    assert True\n")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _ok(root, "quick-fix", "start", SLUG,
        "--risk", "contained - one line", "--familiarity",
        "brownfield-mapped - the file and its test exist",
        "--size", "atomic - one line", "--intent", "f returns 2",
        "--scenario", "Given f, when called, then it returns 2.",
        "--scenario-id", "TRC-001", "--test", "tests/test_f.py",
        "--request", "https://example.com/tickets/1", "--requester", "Dana Smith")
    return root


def _manifest(root):
    return root / ".compass" / "work" / SLUG / "manifest.yml"


# --- the writer ------------------------------------------------------------------------------

def test_dump_writes_a_shared_value_in_full():
    shared = []
    data = {"assessment": {"labels": shared}, "evaluated_assessment": {"labels": shared}}
    text = manifest_store.dump(data)
    assert not _anchored(text), text
    assert yaml.safe_load(text) == data


def test_a_started_issue_has_no_anchor_in_its_manifest(tmp_path):
    """`quick-fix start` copies the assessment to `evaluated_assessment`, the
    case that wrote `labels: &id001 []`."""
    root = _started(tmp_path)
    text = _manifest(root).read_text()
    held = yaml.safe_load(text)
    assert held["assessment"].get("labels") == held["evaluated_assessment"].get("labels")
    assert not _anchored(text), text


# --- the readers, over a manifest written with anchors ---------------------------------------

def _with_anchors(root):
    """Write the started issue's manifest again as the old writer did: one list
    object under both assessments, so the dump holds an anchor and an alias."""
    path = _manifest(root)
    data = yaml.safe_load(path.read_text())
    shared = ["a-label"]
    data["assessment"]["labels"] = shared
    data["evaluated_assessment"]["labels"] = shared
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    assert "&id001" in text and "*id001" in text, text
    path.write_text(text)
    return path


def test_the_library_readers_read_an_anchored_manifest(tmp_path):
    from compass_pkg import atomic_io, core
    from compass_pkg import parse_cache
    root = _started(tmp_path)
    path = _with_anchors(root)
    task, _ = core.load_manifest(str(path.parent))
    assert task["evaluated_assessment"]["labels"] == ["a-label"]
    assert core.load_yaml(str(path))["evaluated_assessment"]["labels"] == ["a-label"]
    assert atomic_io.load_yaml_strict(path)["evaluated_assessment"]["labels"] == ["a-label"]
    # The second read comes from the stored parse.
    for _ in range(2):
        cache = parse_cache.for_work_root(str(root / ".compass" / "work"))
        assert cache.load_yaml(str(path))["evaluated_assessment"]["labels"] == ["a-label"]


def test_the_commands_read_an_anchored_manifest_and_write_it_without(tmp_path):
    root = _started(tmp_path)
    path = _with_anchors(root)
    for args in (["next"], ["check", "--issue", SLUG, "--json"], ["flow"],
                 ["approach", "show", "--issue", SLUG], ["trail", "--issue", SLUG]):
        done = _compass(root, *args)
        assert "Traceback" not in done.stderr, (args, done.stderr)
        assert done.returncode in (0, 1), (args, done.stdout + done.stderr)
    # A command that saves the manifest writes the values in full.
    _ok(root, "issue", "link", "set", "--issue", SLUG, "--requester", "Dana Lee")
    text = path.read_text()
    assert not _anchored(text), text
    held = yaml.safe_load(text)
    assert held["assessment"]["labels"] == held["evaluated_assessment"]["labels"] == ["a-label"]
