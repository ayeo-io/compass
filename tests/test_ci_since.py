"""`compass ci --since <ref>` fully checks only issues in flight and those
landed after the ref: the faster-suite-and-release issue, scenario FS-C in
`docs/system-spec.md`.

Each test builds a git repository with three commits and a tag on the
second, and a Compass project whose issues landed at different points.
`compass ci` prints one section per issue; a lint-only issue's section says
its gate checks were skipped.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
FEATURE = {"risk": "contained", "familiarity": "brownfield-mapped",
           "size": "standard", "goal": "delivery", "role": "engineer"}


def _git(cwd: Path, *args) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _commit(root: Path, name: str, date: str) -> str:
    (root / name).write_text(name)
    _git(root, "add", name)
    env_date = ["-c", "user.name=t"]
    subprocess.run(["git", *env_date, "commit", "-q", "-m", name], cwd=root, check=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    return _git(root, "rev-parse", "HEAD")


def _issue(root: Path, slug: str, **fields) -> None:
    import yaml
    task = root / ".compass" / "work" / slug
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-01-01",
        "status": "active", "assessment": FEATURE}, sort_keys=False))
    r = subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--issue", slug,
                        "--write"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    m = yaml.safe_load((task / "manifest.yml").read_text())
    m.update(fields)
    (task / "manifest.yml").write_text(yaml.safe_dump(m, sort_keys=False))
    (task / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q")
    first = _commit(root, "a", "2026-01-01T10:00:00+00:00")
    _commit(root, "b", "2026-02-01T10:00:00+00:00")
    _git(root, "tag", "v1")
    third = _commit(root, "c", "2026-03-01T10:00:00+00:00")
    (root / ".compass").mkdir()
    _issue(root, "landed-before", status="landed", land_commit=first)
    _issue(root, "landed-after", status="landed", land_commit=third)
    _issue(root, "stamped-before", status="landed", land_timestamp="2025-06-01T00:00:00+00:00")
    _issue(root, "stamped-after", status="landed", land_timestamp="2026-02-15T00:00:00+00:00")
    _issue(root, "unplaceable", status="landed", land_commit="0" * 40)
    _issue(root, "in-flight")
    return root


def _sections(out: str) -> dict:
    """Each issue's slug mapped to whether its gate checks were skipped."""
    parts = re.split(r"\n\[issue\] ", out)
    return {p.split("\n", 1)[0].strip(): "gate checks skipped" in p for p in parts[1:]}


def _ci(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), "ci", *args], cwd=root,
                          capture_output=True, text=True)


def test_since_lints_old_landings_and_checks_the_rest(tmp_path):
    """Issues landed before the ref are lint-only; issues landed after it,
    in flight, or unplaceable are fully checked (FS-C)."""
    root = _project(tmp_path)
    skipped = _sections(_ci(root, "--since", "v1").stdout)
    assert skipped == {"landed-before": True, "stamped-before": True,
                       "landed-after": False, "stamped-after": False,
                       "unplaceable": False, "in-flight": False}, skipped


def test_without_since_every_landed_issue_is_checked(tmp_path):
    """compass ci with no option checks exactly what it checked before
    (FS-C)."""
    root = _project(tmp_path)
    skipped = _sections(_ci(root).stdout)
    assert skipped and not any(skipped.values()), skipped


def test_a_ref_that_names_no_commit_fails_loudly(tmp_path):
    """--since with a ref git cannot resolve exits non-zero and names the
    ref, rather than checking less than it was asked to (FS-C)."""
    root = _project(tmp_path)
    r = _ci(root, "--since", "no-such-ref")
    assert r.returncode != 0
    assert "no-such-ref" in r.stdout + r.stderr
