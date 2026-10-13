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


def test_dcj_63_no_test_touches_own_archive(request, monkeypatch):
    """No test run writes into this checkout's archive. The check is the archive
    guard (tests/archive_guard.py), which takes a digest of `.compass/work` and
    `docs/compass` when the session starts and again when it ends, so it covers
    every test in the session. This test shows that the guard is registered, that
    it does not run as a serial test, and that no module which renders or
    migrates builds a path from this checkout's archive. It starts no process."""
    def no_process(*args, **kwargs):
        raise AssertionError("this test must not start a process")

    monkeypatch.setattr(subprocess, "Popen", no_process)
    assert request.node.get_closest_marker("serial") is None
    import archive_guard
    plugins = request.config.pluginmanager.get_plugins()
    for hook in ("pytest_sessionstart", "pytest_sessionfinish"):
        impl = getattr(archive_guard, hook)
        assert any(getattr(plugin, hook, None) is impl for plugin in plugins), (
            f"this session did not register the archive guard's {hook}")
    # Every render and migrate those tests run targets a temporary folder: no
    # module builds a path from this checkout's archive.
    for name in NEW_TEST_MODULES + ["tests/rendered_blocks_support.py"]:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert 'ROOT / ".compass"' not in text and "ROOT / 'docs'" not in text, name
        assert 'ROOT / "docs" / "compass"' not in text, name


# The planted module does one thing to one file in this checkout's .compass/work
# folder. The control does nothing to it.
_PLANTED_MODULE = '''\
from pathlib import Path


def test_changes_the_archive():
    target = Path({target!r})
    {action}
'''

#: What the planted module does, and whether the file exists before it runs.
_ACTIONS = {
    "added": ("target.parent.mkdir(parents=True, exist_ok=True); target.write_text('after')", False),
    "changed": ("target.write_text('after')", True),
    "removed": ("target.unlink()", True),
    "untouched": ("assert target.exists()", True),
}


def _run_archive_guard(tmp_path, action, parallel):
    """Run a planted module under the archive guard. Returns the run and the
    planted path. The planted file is removed afterwards, and so is `.compass/work`
    (and `.compass`) when this run made it."""
    import uuid
    work = ROOT / ".compass" / "work"
    made = [d for d in (ROOT / ".compass", work) if not d.exists()]
    planted = work / f".dcj-63-planted-{uuid.uuid4().hex}"
    code, exists_before = _ACTIONS[action]
    module = tmp_path / f"test_{action}_{'xdist' if parallel else 'alone'}.py"
    module.write_text(_PLANTED_MODULE.format(target=str(planted), action=code),
                      encoding="utf-8")
    env ={k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    env["PYTHONPATH"] = str(HERE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider",
               "-p", "archive_guard", "-q", str(module)]
    if parallel:
        command[3:3] = ["-p", "xdist.plugin", "-n", "2"]
    try:
        if exists_before:
            work.mkdir(parents=True, exist_ok=True)
            planted.write_text("before", encoding="utf-8")
        run = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True,
                             env=env, timeout=300)
    finally:
        planted.unlink(missing_ok=True)
        for folder in reversed(made):
            try:
                folder.rmdir()
            except OSError:
                pass          # something else is in it: leave it
    return run, planted


@pytest.mark.serial
def test_dcj_63_guard_fails_on_a_planted_archive_write(tmp_path):
    """Serial, because while the planted file exists a parallel test that asks
    whether this checkout has an archive would see one. A file is added, changed
    and removed in turn, alone and under xdist, where the write happens in a
    worker and only the controlling process sees the whole session. Changing a
    file keeps its name, so a guard that compared names alone would miss it."""
    for parallel in (False, True):
        how = "xdist" if parallel else "alone"
        for action in ("added", "changed", "removed"):
            run, planted = _run_archive_guard(tmp_path, action, parallel)
            output = run.stdout + run.stderr
            assert run.returncode != 0, (how, action, output[-2000:])
            assert f"{action}: .compass/work/{planted.name}" in output, (how, action, output[-2000:])
            assert not planted.exists()
        control, _ = _run_archive_guard(tmp_path, "untouched", parallel)
        assert control.returncode == 0, (how, control.stdout[-2000:] + control.stderr[-1000:])


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


def test_dcj_104_planted_render_all_fails_check_and_a_single_render_repairs(tmp_path):
    """DCJ-104: `render --all` plans from the scan, which reads the parse cache, so a
    planted entry can write a wrong own-record block. Check reads the manifest file,
    so the plant fails `rendered-blocks-current` and never passes a gate. The
    single-issue render reads the file and repairs the page (ADR-052)."""
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
    out = sup.run(root, "check", "--issue", SLUG, "--verbose")[1]
    assert "FAIL rendered-blocks-current" in out, out

    assert sup.render(root)[0] == 0
    out = sup.run(root, "check", "--issue", SLUG, "--verbose")[1]
    assert "PASS rendered-blocks-current" in out, out
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
