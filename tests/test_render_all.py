"""Whole-archive render, and the guard that no test touches this checkout's archive
(issue `documents-carry-judgement`, DCJ-63).

`NEW_TEST_MODULES` lists the test modules the issue adds. Each later unit adds
its own to the list, so the guard runs every module that renders or migrates.
This module is not in the list: it would run itself.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "cli"))

import archive  # noqa: E402
import pages_support as ps  # noqa: E402
import parse_speed_support as speed  # noqa: E402
import rendered_blocks_support as sup  # noqa: E402
from rendered_blocks_support import tracked_digest  # noqa: E402

#: The modules this issue adds that render or migrate. Later units extend it.
NEW_TEST_MODULES = ["tests/test_render_blocks.py", "tests/test_rendered_blocks_check.py",
                    "tests/test_dod_from_manifest.py", "tests/test_verification_note.py",
                    "tests/test_issue_page.py", "tests/test_issue_index.py",
                    "tests/test_migrate_rendered_blocks.py"]


def _archive_digest():
    return tracked_digest(*[p for p in (ROOT / ".compass" / "work", ROOT / "docs" / "compass")
                            if p.is_dir()])


@pytest.mark.serial
def test_dcj_63_no_test_touches_own_archive():
    before = _archive_digest()
    env = dict(os.environ, PYTEST_ADDOPTS="", PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x",
         "-o", "addopts=", *NEW_TEST_MODULES],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1500)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert _archive_digest() == before
    # Every render and migrate those tests run targets a temporary folder: no
    # module builds a path from this checkout's archive.
    for name in NEW_TEST_MODULES + ["tests/rendered_blocks_support.py"]:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert 'ROOT / ".compass"' not in text and "ROOT / 'docs'" not in text, name
        assert 'ROOT / "docs" / "compass"' not in text, name


# --- the whole archive (DCJ-58 to DCJ-61, DCJ-77, DCJ-78) ---------------------------------

def _sample_project(tmp_path, count=None):
    """A copy of the archive sample as a project; with `count`, its issue folders
    are copied under new slugs until the work folder holds that many."""
    project = Path(tmp_path) / "proj"
    shutil.copytree(archive.sample_root(), project)
    if count:
        work = project / ".compass" / "work"
        sources = sorted(p for p in work.iterdir() if p.is_dir())
        index = 0
        while len(list(work.iterdir())) < count:
            source = sources[index % len(sources)]
            shutil.copytree(source, work / f"copy-{index:03d}-{source.name}")
            index += 1
    return project


def _all(project, *extra):
    code, out, err = sup.run(project, "issue", "render", "--all", "--json", *extra, timeout=900)
    data = json.loads(out) if out.strip().startswith("{") else {}
    return code, data, out + err


def _tree(project):
    return tracked_digest(project / "docs"), tracked_digest(project / ".compass" / "work")


def _isolated(project, count=2):
    """Slugs of issues that no other issue links to and that link to none."""
    from compass_pkg import render_after
    work = project / ".compass" / "work"
    manifests = {p.name: yaml.safe_load((p / "manifest.yml").read_text(encoding="utf-8"))
                 for p in work.iterdir() if (p / "manifest.yml").is_file()}
    linked = set()
    for slug, body in manifests.items():
        names = render_after.links_of(body)
        if names:
            linked.add(slug)
            linked |= names
    free = sorted(s for s in manifests if s not in linked)
    assert len(free) >= count, free
    return free[:count]


def test_dcj_58_render_all_skips_unchanged_issues(tmp_path):
    project = _sample_project(tmp_path)
    code, first, text = _all(project)
    assert code in (0, 1), text
    total = len(list((project / ".compass" / "work").iterdir()))
    failed = len(first["failed"])
    assert len(first["rendered"]) == total - failed and not first["skipped"]
    before = _tree(project)
    index_before = (project / "docs" / "compass" / "README.md").read_bytes()

    code, again, text = _all(project)
    assert code in (0, 1), text
    assert again["rendered"] == [] and len(again["skipped"]) == total - failed
    assert _tree(project) == before
    assert (project / "docs" / "compass" / "README.md").read_bytes() == index_before

    one, other = _isolated(project)
    manifest = project / ".compass" / "work" / one / "manifest.yml"
    manifest.write_text(manifest.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    code, run1, text = _all(project)
    assert run1["rendered"] == [one], text

    folder = project / ".compass" / "work" / other / "evidence"
    folder.mkdir(exist_ok=True)
    (folder / "extra-note.txt").write_text("a new file\n", encoding="utf-8")
    code, run2, text = _all(project)
    assert run2["rendered"] == [other], text

    settled = _tree(project)
    skip = project / ".compass" / "cache" / "render-skip.json"
    assert skip.is_file()
    skip.unlink()
    code, run3, text = _all(project)
    assert len(run3["rendered"]) == total - failed
    assert _tree(project) == settled


def test_dcj_59_linked_change_re_renders_both(tmp_path):
    root = sup.project(tmp_path)
    ps.add_issue(root, "target")
    ps.add_issue(root, "source")
    assert ps.render_all(root)[0] == 0
    assert "source" not in "\n".join(ps.block(ps.page(root, "target"), "related"))

    ps.set_fields(root, "source", follow_ups=[
        {"id": "FU-1", "status": "outstanding", "summary": "later", "target_task": "target"}])
    code, data, text = _all(root)
    assert code == 0, text
    assert {"source", "target"} <= set(data["rendered"]), data
    assert "feature" not in data["rendered"]
    assert "source" in "\n".join(ps.block(ps.page(root, "target"), "related"))

    ledger = Path(root) / "governance" / "decisions"
    ledger.mkdir(parents=True)
    (ledger / "2026-10-09-about-target.md").write_text(
        "# about-target\n\n## Decided by\n\nsomeone\n\n## Decision\n\nA rule for target.\n\n"
        "## Evidence\n\nIssue target.\n", encoding="utf-8")
    code, data, text = _all(root)
    assert code == 0 and "target" in data["rendered"], text
    assert "about-target" in "\n".join(ps.block(ps.page(root, "target"), "decisions"))
    for slug in ("target", "source"):
        done, out, err = sup.run(root, "check", "--issue", slug, "--verbose")
        assert "PASS rendered-blocks-current" in out, out


@pytest.mark.serial
def test_dcj_61_render_all_490_issues_within_bound(tmp_path):
    project = _sample_project(tmp_path, count=490)
    code, warm, text = _all(project)
    assert code in (0, 1), text
    skip = project / ".compass" / "cache" / "render-skip.json"
    times = []
    for _ in range(3):
        skip.unlink(missing_ok=True)
        started = time.perf_counter()
        code, data, text = _all(project)
        times.append(time.perf_counter() - started)
        assert code in (0, 1), text
        assert len(data["rendered"]) + len(data["failed"]) == 490
    median = sorted(times)[1]
    assert median < 5.0, f"render --all took {times} s over 490 issues; median {median:.2f} s"


def _plant(cache_folder, source_path, change):
    """Rewrite the stored parse of `source_path` so it names something the file
    does not. The key (the file's digest) stays valid."""
    from compass_pkg import parse_cache
    digest = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    entry = Path(cache_folder) / f"{digest}.json"
    assert entry.is_file(), sorted(os.listdir(cache_folder))[:3]
    raw = entry.read_text(encoding="utf-8")
    entry.write_text(change(raw), encoding="utf-8")
    return entry


def test_dcj_77_cache_cannot_decide_blocking_verdict(tmp_path):
    root = sup.rich_issue(tmp_path)
    from pages_support import SLUG
    # Past the plan stage, so a stale own-record block fails the check instead of being advisory.
    sup.base.edit(root, current_phase="verify")
    assert sup.render(root)[0] == 0
    assert ps.render_all(root)[0] == 0           # warms the parse cache
    manifest = ps.work_of(root, SLUG) / "manifest.yml"
    folder = Path(root) / ".compass" / "cache" / "parsed_yaml"
    assert folder.is_dir()
    # The stored parse now claims every gate passed; the file says seven of nine.
    entry = _plant(folder, manifest, lambda raw: raw.replace('"pending"', '"pass"'))
    assert '"pending"' not in entry.read_text(encoding="utf-8")

    code, out, err = sup.run(root, "check", "--issue", SLUG, "--verbose")
    assert "PASS rendered-blocks-current" in out, out
    assert "gates 7/9" in "\n".join(ps.block(ps.page(root), "header"))

    # Only the named readers name the cache; any other module that does fails the test.
    users = speed.parse_cache_users(ROOT / "cli" / "compass_pkg")
    assert users == ["flow.py", "project_scan.py"], users
    planted = tmp_path / "pkg"
    shutil.copytree(ROOT / "cli" / "compass_pkg", planted, ignore=shutil.ignore_patterns("__pycache__"))
    (planted / "other_reader.py").write_text("from compass_pkg import parse_cache\n")
    assert speed.parse_cache_users(planted) == ["flow.py", "other_reader.py", "project_scan.py"]


def test_dcj_101_render_all_reads_each_issues_own_manifest_not_the_cache(tmp_path):
    """DCJ-101: `render --all` plans from the manifest file, so a planted cache entry
    cannot write an own-record block (ADR-052)."""
    root = sup.rich_issue(tmp_path)
    from pages_support import SLUG
    sup.base.edit(root, current_phase="verify")
    assert sup.render(root)[0] == 0
    assert ps.render_all(root)[0] == 0           # warms the parse cache
    manifest = ps.work_of(root, SLUG) / "manifest.yml"
    folder = Path(root) / ".compass" / "cache" / "parsed_yaml"
    _plant(folder, manifest, lambda raw: raw.replace('"pending"', '"pass"'))
    (Path(root) / ".compass" / "cache" / "render-skip.json").unlink(missing_ok=True)

    assert ps.render_all(root)[0] == 0
    assert "gates 7/9" in "\n".join(ps.block(ps.page(root), "header"))


def test_dcj_78_render_all_dry_run_writes_nothing(tmp_path):
    project = _sample_project(tmp_path)
    before = _tree(project)
    listing = sorted(str(p.relative_to(project)) for p in project.rglob("*") if p.is_file())
    code, data, text = _all(project, "--dry-run")
    assert code in (0, 1), text
    assert code == (1 if data["failed"] else 0)
    assert data["dry_run"] is True
    assert data["would_write"], text
    assert all(item["kinds"] for item in data["would_write"])
    assert "skipped" in data
    assert _tree(project) == before
    assert sorted(str(p.relative_to(project)) for p in project.rglob("*") if p.is_file()) == listing
    assert not (project / ".compass" / "cache" / "render-skip.json").exists()


# --- the archive sample after migration (DCJ-62) -------------------------------------------

def test_dcj_62_archive_sample_meets_measures(tmp_path):
    from compass_pkg import status_words
    from compass_pkg.core import canonical_shape, docs_dir
    project = _sample_project(tmp_path)
    work = project / ".compass" / "work"
    code, out, err = sup.run(project, "issue", "migrate", str(work), "--apply",
                             "--i-have-a-copy", timeout=900)
    assert code == 0, out + err
    code, data, text = _all(project)
    assert code == 0, text[-2000:]
    index = (project / "docs" / "compass" / "README.md").read_text("utf-8")
    slugs = sorted(p.name for p in work.iterdir() if (p / "manifest.yml").is_file())
    assert len(slugs) >= 15
    for slug in slugs:
        task_dir = work / slug
        task = yaml.safe_load((task_dir / "manifest.yml").read_text("utf-8"))
        # `compass check` is run on the issue and the new check passes, whatever the generation
        # it was stored under.
        done = sup.run(project, "check", "--issue", slug, "--json")
        rows = {c["name"]: c for c in json.loads(done[1])["checks"]}
        if "rendered-blocks-current" in rows:
            assert rows["rendered-blocks-current"]["status"] == "pass", (slug, rows)
        else:
            # A spike owes none of the gate that holds the check.
            assert canonical_shape(task.get("delivery_approach")) == "spike", (slug, sorted(rows))
        folder = project / docs_dir(str(task_dir))
        # The issue page opens with the ask.
        page = (folder / "README.md").read_text("utf-8").splitlines()
        opening = [i for i, line in enumerate(page) if line == "<!-- compass:render ask -->"]
        assert opening and opening[0] < 20, (slug, opening)
        # The index lists the issue once.
        assert index.count("[%s](" % slug) == 1, slug
        # A quick fix closed as completed has its note.
        if status_words.is_completed(task) and canonical_shape(task.get("delivery_approach")) \
                == "quick-fix":
            assert (folder / "verification-note.md").is_file(), slug
        # A done issue with a Definition of Done block reads n of n met, or names what it carries.
        report = folder / "verification-report.md"
        if status_words.is_closed(task) and report.is_file():
            block = re.search(r"<!-- compass:render dod -->\n(.*?)<!-- /compass:render -->",
                              report.read_text("utf-8"), re.S)
            if block is None:
                continue
            first = block.group(1).splitlines()[0]
            outstanding = [f["id"] for f in task.get("follow_ups") or []
                           if f.get("status") == "outstanding" and f.get("defers")]
            if outstanding:
                assert "carried to ship" in first and all(i in first for i in outstanding), (slug, first)
            else:
                assert re.fullmatch(r"Definition of Done: (\d+) of \1 met", first), (slug, first)
