"""The board file: its default path in the system temp folder and the safe write.

Scenario ids: `TRC-E4` (one stable file per checkout), `TRC-E10` (a link or
another user's file is refused), `TRC-E14` (the default file is private) and
`TRC-E15` (the page goes through a new, exclusively created temporary file).
The module under test is imported inside each test so a missing module fails
the test and not the collection.
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

POSIX = hasattr(os, "getuid")


def _need_posix():
    """Skip inside the body: a skip mark makes the scenario's declared test
    count as one that never runs."""
    if not POSIX:
        pytest.skip("needs POSIX owners, links and permissions")


def _board_file():
    from compass_pkg import board_file
    return board_file


@pytest.fixture
def temp_folder(tmp_path, monkeypatch):
    """A private system temp folder, so a test never touches the real one."""
    folder = tmp_path / "systmp"
    folder.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(folder))
    return folder


def _project(tmp_path, name):
    root = tmp_path / name
    (root / ".compass").mkdir(parents=True)
    return root


# ---- TRC-E4 -------------------------------------------------------------

def test_trc_e4_default_board_file(tmp_path, temp_folder):
    bf = _board_file()
    one = _project(tmp_path, "alpha")
    two = _project(tmp_path, "beta")
    odd = _project(tmp_path, "my board;x")
    paths = {n: bf.default_board_path(str(r)) for n, r in
             (("one", one), ("two", two), ("odd", odd))}
    # The same checkout gives the same path every time.
    assert bf.default_board_path(str(one)) == paths["one"]
    assert len(set(paths.values())) == 3
    for path in paths.values():
        assert os.path.dirname(path) == str(temp_folder)
    digest = hashlib.sha256(str(one.resolve()).encode("utf-8")).hexdigest()[:8]
    assert os.path.basename(paths["one"]) == f"compass-board-alpha-{digest}.html"
    assert os.path.basename(paths["odd"]).startswith("compass-board-my-board-x-")
    assert re.fullmatch(r"compass-board-[A-Za-z0-9._-]+-[0-9a-f]{8}\.html",
                        os.path.basename(paths["odd"]))
    # The name comes from the resolved root: a link to the checkout agrees.
    link = tmp_path / "linked"
    link.symlink_to(one)
    assert bf.default_board_path(str(link)) == paths["one"]


# ---- TRC-E10 ------------------------------------------------------------

def test_trc_e10_a_link_is_refused(tmp_path):
    _need_posix()
    bf = _board_file()
    victim = tmp_path / "victim.txt"
    victim.write_text("keep\n")
    board = tmp_path / "board.html"
    board.symlink_to(victim)
    with pytest.raises(Exception) as err:
        bf.check_default_target(str(board), "compass board render")
    assert str(board) in str(err.value) and "--out" in str(err.value)
    assert board.is_symlink() and os.readlink(board) == str(victim)
    assert victim.read_text() == "keep\n"


def test_trc_e10_a_dangling_link_is_refused(tmp_path):
    _need_posix()
    bf = _board_file()
    board = tmp_path / "board.html"
    board.symlink_to(tmp_path / "nowhere")
    with pytest.raises(Exception) as err:
        bf.check_default_target(str(board), "compass board refresh")
    assert "--out" in str(err.value)
    assert not (tmp_path / "nowhere").exists()


def test_trc_e10_another_users_file_is_refused(tmp_path, monkeypatch):
    _need_posix()
    bf = _board_file()
    board = tmp_path / "board.html"
    board.write_text("theirs\n")
    mine = os.lstat(board).st_uid
    monkeypatch.setattr(os, "getuid", lambda: mine + 1)
    with pytest.raises(Exception) as err:
        bf.check_default_target(str(board), "compass board render")
    assert str(board) in str(err.value) and "--out" in str(err.value)
    assert board.read_text() == "theirs\n"


def test_trc_e10_a_file_of_the_current_user_and_a_missing_file_pass(tmp_path):
    _need_posix()
    bf = _board_file()
    board = tmp_path / "board.html"
    bf.check_default_target(str(board), "compass board render")  # missing
    board.write_text("mine\n")
    bf.check_default_target(str(board), "compass board render")


def test_trc_e10_a_folder_is_refused(tmp_path):
    bf = _board_file()
    board = tmp_path / "board.html"
    board.mkdir()
    with pytest.raises(Exception) as err:
        bf.check_default_target(str(board), "compass board render")
    assert "--out" in str(err.value)


def test_trc_e10_a_named_pipe_is_refused(tmp_path):
    _need_posix()
    bf = _board_file()
    board = tmp_path / "board.html"
    os.mkfifo(board)
    with pytest.raises(Exception):
        bf.check_default_target(str(board), "compass board render")


def test_trc_e10_without_owners_the_link_check_still_runs(tmp_path, monkeypatch):
    bf = _board_file()
    victim = tmp_path / "victim.txt"
    victim.write_text("keep\n")
    board = tmp_path / "board.html"
    try:
        board.symlink_to(victim)
    except (OSError, NotImplementedError):
        pytest.skip("no symbolic links here")
    monkeypatch.delattr(os, "getuid", raising=False)
    with pytest.raises(Exception):
        bf.check_default_target(str(board), "compass board render")
    board.unlink()
    board.write_text("mine\n")
    bf.check_default_target(str(board), "compass board render")


def test_trc_e10_check_target_guards_every_target(tmp_path, monkeypatch):
    bf = _board_file()
    root = _project(tmp_path, "proj")
    (root / "docs" / "compass").mkdir(parents=True)
    out = tmp_path / "outside"
    out.mkdir()
    assert bf.check_target(str(out / "b.html"), "compass board render", str(root)) \
        == os.path.join(os.path.realpath(out), "b.html")
    for bad in (root / ".compass" / "b.html", root / "docs" / "compass" / "b.html"):
        with pytest.raises(Exception) as err:
            bf.check_target(str(bad), "compass flow --html", str(root))
        assert "compass flow --html" in str(err.value) and "issue state" in str(err.value)
    with pytest.raises(Exception) as err:
        bf.check_target(str(out), "compass board render", str(root))
    assert "directory" in str(err.value)
    with pytest.raises(Exception) as err:
        bf.check_target(str(out / "no" / "b.html"), "compass board render", str(root))
    assert "does not exist" in str(err.value)


# ---- TRC-E14 ------------------------------------------------------------

def test_trc_e14_the_default_file_is_private(tmp_path):
    _need_posix()
    bf = _board_file()
    board = str(tmp_path / "default.html")
    old = os.umask(0)  # a loose umask must not widen the file
    try:
        assert bf.write_page(board, "<p>one</p>", 0o600) == "created"
        assert stat.S_IMODE(os.stat(board).st_mode) == 0o600
        assert bf.write_page(board, "<p>two</p>", 0o600) == "refreshed"
        assert stat.S_IMODE(os.stat(board).st_mode) == 0o600
        out = str(tmp_path / "team.html")
        os.umask(0o077)  # a tight umask must not narrow an --out file
        bf.write_page(out, "<p>x</p>", 0o644)
        assert stat.S_IMODE(os.stat(out).st_mode) == 0o644
    finally:
        os.umask(old)
    assert Path(board).read_text() == "<p>two</p>"


def test_trc_e14_a_refresh_narrows_a_wider_old_file(tmp_path):
    _need_posix()
    bf = _board_file()
    board = tmp_path / "default.html"
    board.write_text("old")
    os.chmod(board, 0o666)
    bf.write_page(str(board), "new", 0o600)
    assert stat.S_IMODE(os.stat(board).st_mode) == 0o600


# ---- TRC-E15 ------------------------------------------------------------

def test_trc_e15_the_page_goes_through_a_new_temporary_file(tmp_path, monkeypatch):
    bf = _board_file()
    folder = tmp_path / "shared"
    folder.mkdir()
    board = folder / "compass-board-x-12345678.html"
    victims = {}
    for suffix in (".tmp", ".part", ".new", "~"):
        victim = tmp_path / f"victim{abs(hash(suffix))}.txt"
        victim.write_text("keep\n")
        link = folder / (board.name + suffix)
        try:
            link.symlink_to(victim)
        except (OSError, NotImplementedError):
            pytest.skip("no symbolic links here")
        victims[link] = victim
    sources = []
    real_replace = os.replace

    def spy(src, dst, *a, **k):
        sources.append((str(src), str(dst), Path(src).exists()))
        return real_replace(src, dst, *a, **k)

    monkeypatch.setattr(os, "replace", spy)
    bf.write_page(str(board), "<p>1</p>", 0o600)
    bf.write_page(str(board), "<p>2</p>", 0o600)
    assert len(sources) == 2
    for src, dst, existed in sources:
        assert existed and dst == str(board)
        assert os.path.dirname(src) == str(folder)
        name = os.path.basename(src)
        assert name.startswith(".compass-tmp-")
        assert board.name not in name
    assert sources[0][0] != sources[1][0]
    for link, victim in victims.items():
        assert link.is_symlink() and victim.read_text() == "keep\n"
    assert sorted(p.name for p in folder.iterdir() if not p.is_symlink()) == [board.name]
    assert board.read_text() == "<p>2</p>"


def test_trc_e15_a_failed_write_leaves_no_temporary_file(tmp_path, monkeypatch):
    bf = _board_file()
    board = tmp_path / "b.html"
    board.write_text("old")

    def boom(*a, **k):
        raise OSError("disk went away")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        bf.write_page(str(board), "new", 0o600)
    assert board.read_text() == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["b.html"]
