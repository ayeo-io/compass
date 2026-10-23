"""`archive_under()` copies a project without its own cache, and removes a
failed copy.

With `COMPASS_FULL_ARCHIVE=1` the project `archive_under()` copies is this
checkout, and the copy goes into `.compass/archive-sample-cache/` inside it.
Copying that folder too made the copy recurse into itself until the disk
filled. A copy that raised was never removed, because the caller records the
folder only after `archive_under()` returns.

Each test builds a small fake checkout in a temporary folder and points
`archive.CACHE` and `archive.checkable_root` at it. None of them copies this
checkout.

Scenario id: `AUC-1`.
"""
from __future__ import annotations

import pytest

import archive
import compat_baseline as cb


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    (root / ".compass" / "work" / "one").mkdir(parents=True)
    (root / ".compass" / "work" / "one" / "manifest.yml").write_text("issue: one\n")
    cache = root / ".compass" / "archive-sample-cache"
    (cache / "earlier").mkdir(parents=True)
    (cache / "earlier" / "kept.txt").write_text("an earlier unpacked sample\n")
    monkeypatch.setattr(archive, "CACHE", cache)
    monkeypatch.setattr(archive, "checkable_root", lambda: root)
    monkeypatch.setattr(cb, "build_configuration", lambda kind, root, fault=None: None)
    return root, cache


def _copies(cache):
    return sorted(p for p in cache.iterdir() if p.name.startswith("config-"))


def test_auc_1_the_copy_leaves_out_its_own_cache(checkout):
    root, cache = checkout
    copy = cb.archive_under("B")
    assert (copy / ".compass" / "work" / "one" / "manifest.yml").is_file()
    assert not (copy / ".compass" / "archive-sample-cache").exists()
    assert _copies(cache) == [copy]


def test_auc_1_a_failed_build_leaves_no_copy(checkout, monkeypatch):
    _root, cache = checkout

    def fail(kind, root, fault=None):
        raise RuntimeError("the configuration could not be built")
    monkeypatch.setattr(cb, "build_configuration", fail)
    with pytest.raises(RuntimeError):
        cb.archive_under("B")
    assert _copies(cache) == []
