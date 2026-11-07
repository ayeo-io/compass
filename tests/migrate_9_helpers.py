"""Fixtures for the tests of `compass migrate` on issues (#359).

Each builds a git repository on the live default (no `compass.yml`) with 8.x
issues: manifests holding the keys the 8.0.4 evaluator wrote
(`test_next_stage.assessed_before_the_path`), and real red and green records
from `compass tdd-red` and `compass tdd-green`, so the stage the records give
is the one `compass next` reads.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
import compass_pkg  # noqa: E402,F401  - resolves the bundled yaml first
import yaml  # noqa: E402

from test_next_stage import assessed_before_the_path  # noqa: E402

ASSESSMENT = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
              "goal": "delivery", "urgency": "none", "labels": []}
SPIKE = dict(ASSESSMENT, goal="exploration")
PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts="]


def run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True, timeout=120)


def ok(root, *args):
    done = run(root, *args)
    assert done.returncode == 0, (args, done.stdout + done.stderr)
    return done


def git(root, *args):
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def project(tmp_path):
    """A git repository with two failing tests, and `compass init` run."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "src" / "__init__.py").write_text("")
    (root / "src" / "f.py").write_text("def f():\n    return 1\n\n\ndef g():\n    return 1\n")
    (root / "tests" / "test_f.py").write_text(
        "from src.f import f\n\n\ndef test_f():\n    assert f() == 2\n")
    (root / "tests" / "test_g.py").write_text(
        "from src.f import g\n\n\ndef test_g():\n    assert g() == 2\n")
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    ok(root, "init")
    return root


def task_dir(root, slug):
    return root / ".compass" / "work" / slug


def manifest(root, slug):
    return yaml.safe_load((task_dir(root, slug) / "manifest.yml").read_text())


def write_manifest(root, slug, body):
    (task_dir(root, slug) / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))


def scenario(sid, test):
    return {"id": sid, "title": f"{sid} holds", "intent": "INT-1", "tests": [test]}


def old_issue(root, slug, *, assessment=ASSESSMENT, scenarios=(), **extra):
    """An open 8.x issue: the 8.0.4 keys, the given scenarios and `extra` keys."""
    folder = task_dir(root, slug)
    folder.mkdir(parents=True)
    body = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
            "assessment": dict(assessment)}
    body.update(assessed_before_the_path(assessment))
    body["scenarios"] = [dict(s) for s in scenarios]
    body.update(extra)
    write_manifest(root, slug, body)
    return folder


def red(root, slug, sid, test):
    ok(root, "tdd-red", "--issue", slug, "--scenario", sid, "--", *PYTEST, test)


def green(root, slug, sid, test):
    ok(root, "tdd-green", "--issue", slug, "--scenario", sid, "--", *PYTEST, test)


def fix(root):
    (root / "src" / "f.py").write_text("def f():\n    return 2\n\n\ndef g():\n    return 2\n")


def snapshot(folder):
    """Every file under `folder`, as {relative path: bytes}."""
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in sorted(Path(folder).rglob("*")) if p.is_file()}
