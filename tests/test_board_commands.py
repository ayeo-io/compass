"""The board commands, run as a person runs them: `compass board render`,
`compass board refresh` and `compass flow --html`.

The library units (board data, page, board file, worktree reader) have their
own tests. These tests run the whole command in a subprocess, with a recorder
standing in for the browser and a private temporary folder standing in for the
system one, and check what the command wrote, printed and opened. A few tests
call `board_cmd.build_page` in the test process to watch the order of the
steps.

They cover the commands' own behaviour (render, refresh, the output file, the
path guard, the browser, worktrees) and the page-level checks of the notes and
header lines that the data and worktree units decide. Issue: `compass-board`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg.core import display_stage  # noqa: E402
from compass_pkg.stable_ids import STAGE_IDS  # noqa: E402

TODAY = datetime.date.today()
THIS = "this checkout"
DONE_LANE = "done, last 7 days"


# --- helpers -----------------------------------------------------------------

class Rig:
    """Runs the CLI with a private temp folder and a recording browser."""

    def __init__(self, tmp_path):
        self.tmp = tmp_path / "systmp"
        self.tmp.mkdir()
        self.log = tmp_path / "browser.log"
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.outs = tmp_path / "outs"
        self.outs.mkdir()
        self._n = 0
        self.set_browser(0)

    def set_browser(self, code):
        script = self.bin / "board-recorder"
        script.write_text(f'#!/bin/sh\necho "$1" >> "{self.log}"\nexit {code}\n')
        script.chmod(0o755)
        self.browser = f"{script} %s"

    def calls(self):
        return self.log.read_text().split() if self.log.exists() else []

    def run(self, cwd, *args):
        env = {**os.environ, "TMPDIR": str(self.tmp), "BROWSER": self.browser}
        env.pop("COMPASS_ISSUE", None)
        return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                              env=env, capture_output=True, text=True)

    def out_file(self, name=None):
        self._n += 1
        return self.outs / (name or f"page-{self._n}.html")

    def page(self, cwd, *args):
        """Render with --no-open to a fresh file outside the project; return the text."""
        target = self.out_file()
        done = self.run(cwd, "board", "render", "--no-open", "--out", str(target), *args)
        assert done.returncode == 0, done.stdout + done.stderr
        return target.read_text(encoding="utf-8")

    def default_path(self, cwd):
        done = self.run(cwd, "board", "render", "--no-open", "--json")
        assert done.returncode == 0, done.stdout + done.stderr
        return Path(json.loads(done.stdout)["path"])


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def _project(tmp_path, name="proj"):
    root = tmp_path / name
    (root / ".compass" / "work").mkdir(parents=True)
    return root


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), env=env, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _repo(tmp_path, name="main"):
    root = _project(tmp_path, name)
    _git(root, "init", "-q")
    _git(root, "commit", "-q", "--allow-empty", "-m", "start")
    return root


def _worktree(repo, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "--detach", str(path))
    return path


def _write(root, slug, mtime=None, **fields):
    folder = root / ".compass" / "work" / slug
    folder.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": "2.0", "issue": slug,
            "created": fields.pop("created", TODAY.isoformat())}
    data.update(fields)
    path = folder / "manifest.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return folder


def _stages(**over):
    stages = {stage: "thorough" for stage in STAGE_IDS}
    stages.update(over)
    return stages


def _assessed(**over):
    fields = {"delivery_approach": "full", "stages": _stages()}
    fields.update(over)
    return fields


def _days_ago(days):
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return when.isoformat()


GATES = [{"id": "verify.correctness", "status": "pass"},
         {"id": "verify.governance", "status": "pending"}]
ONE_SCENARIO = [{"id": "TRC-1", "intent": "INT-1", "title": "t", "tests": ["tests/t.py::t"]}]


def _one_of_each(root):
    """An issue in each state, and one done two days ago."""
    _write(root, "set-aside-one", status="backlog", **_assessed())
    _write(root, "ready-one", scenarios=ONE_SCENARIO,
           **_assessed(stages=_stages(refine="skipped")))
    _write(root, "going-one", current_phase="plan", **_assessed())
    _write(root, "reviewing-one", current_phase="verify", gates=GATES, **_assessed())
    _write(root, "finished-one", status="done", close_reason="completed",
           land_timestamp=_days_ago(2), **_assessed())


LANE = re.compile(r'<section class="lane" aria-label="([^"]*)">(.*?)</section>', re.S)
CARD = re.compile(r'<a class="card[^"]*" href="#(issue-\d+)">(.*?)</a>', re.S)
SLUG = re.compile(r'<span class="slug">(.*?)</span>')
GENERATED = re.compile(r'^<p class="generated">.*</p>$', re.M)


def _cards(page):
    """(slug, lane name, card html) for every card on the page, in page order."""
    found = []
    for lane, body in LANE.findall(page):
        for _, html in CARD.findall(body):
            found.append((SLUG.search(html).group(1), lane, html))
    return found


def _card(page, slug):
    mine = [c for c in _cards(page) if c[0] == slug]
    assert len(mine) == 1, (slug, [c[:2] for c in _cards(page)])
    return mine[0]


def _panel(page, slug):
    for chunk in page.split('<section class="panel" id=')[1:]:
        if f"<h2>{slug}</h2>" in chunk:
            return chunk
    raise AssertionError(f"no panel for {slug}")


def _note(page):
    """The unplaceable note's items as (slug, text)."""
    if '<section class="unplaceable">' not in page:
        return []
    chunk = page.split('<section class="unplaceable">')[1].split("</section>")[0]
    return [(SLUG.search(li).group(1), re.sub(r"<[^>]+>", "", li))
            for li in re.findall(r"<li>(.*?)</li>", chunk, re.S)]


def _lane(name):
    return DONE_LANE if name == "done" else display_stage(name)


# --- the commands and the browser ---------------------------------------------
# The recorder succeeds in the render test and fails in the no-browser test, so
# a reported "opened" and a reported "could not open" are both proven to occur.

def test_trc_e1_render_writes_prints_opens(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    done = rig.run(root, "board", "render")
    assert done.returncode == 0, done.stdout + done.stderr
    printed = re.search(r"\S*compass-board-proj-[0-9a-f]{8}\.html", done.stdout)
    assert printed, done.stdout
    path = Path(printed.group(0))
    assert path.is_file()
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert os.path.realpath(path.parent) == os.path.realpath(rig.tmp)
    # Asked exactly once, with the file URI of the resolved path.
    assert rig.calls() == [path.resolve().as_uri()]
    assert "could not open" not in done.stdout.lower()


def test_trc_e2_render_no_open(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    done = rig.run(root, "board", "render", "--no-open")
    assert done.returncode == 0, done.stdout + done.stderr
    printed = re.search(r"\S*compass-board-proj-[0-9a-f]{8}\.html", done.stdout)
    assert printed and Path(printed.group(0)).is_file(), done.stdout
    assert rig.calls() == []


def test_trc_e3_render_out(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    target = rig.outs / "team-board.html"
    done = rig.run(root, "board", "render", "--no-open", "--out", str(target))
    assert done.returncode == 0, done.stdout + done.stderr
    assert str(target.resolve()) in done.stdout
    assert target.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert list(rig.tmp.iterdir()) == []
    assert rig.calls() == []


def test_trc_e11_no_browser(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    rig.set_browser(1)
    done = rig.run(root, "board", "render")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "could not open a browser" in done.stdout.lower()
    printed = re.search(r"\S*compass-board-proj-[0-9a-f]{8}\.html", done.stdout)
    assert printed and Path(printed.group(0)).is_file(), done.stdout
    assert len(rig.calls()) == 1


def test_trc_e5_one_board_file(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    before = set(os.listdir(rig.tmp))
    for verb in (("render", "--no-open"), ("render", "--no-open"),
                 ("refresh",), ("refresh",)):
        done = rig.run(root, "board", *verb)
        assert done.returncode == 0, done.stdout + done.stderr
    new = set(os.listdir(rig.tmp)) - before
    assert len(new) == 1, new
    assert next(iter(new)).startswith("compass-board-proj-")
    assert rig.calls() == []


def test_trc_e6_refresh_in_place(rig, tmp_path):
    root = _project(tmp_path)
    _write(root, "mover", status="backlog", **_assessed())
    path = rig.default_path(root)
    assert _card(path.read_text(), "mover")[1] == _lane("backlog")
    _write(root, "mover", current_phase="plan", **_assessed())
    done = rig.run(root, "board", "refresh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert str(path) in done.stdout and "refreshed" in done.stdout
    slug, lane, html = _card(path.read_text(), "mover")
    assert lane == _lane("plan") and ">in-progress<" in html
    assert rig.calls() == []


def test_trc_e7_refresh_out(rig, tmp_path):
    root = _project(tmp_path)
    _write(root, "mover", status="backlog", **_assessed())
    target = rig.outs / "team-board.html"
    first = rig.run(root, "board", "render", "--no-open", "--out", str(target))
    assert first.returncode == 0, first.stdout + first.stderr
    _write(root, "mover", current_phase="plan", **_assessed())
    done = rig.run(root, "board", "refresh", "--out", str(target))
    assert done.returncode == 0, done.stdout + done.stderr
    assert _card(target.read_text(), "mover")[1] == _lane("plan")
    assert list(rig.tmp.iterdir()) == []
    assert rig.calls() == []


def test_trc_e8_refresh_creates(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    assert list(rig.tmp.iterdir()) == []
    done = rig.run(root, "board", "refresh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "created" in done.stdout
    assert len(list(rig.tmp.iterdir())) == 1
    assert rig.calls() == []


# --- the path guard (E9) ------------------------------------------------------

def _guard_targets(root):
    return {
        "inside .compass": root / ".compass" / "board.html",
        "inside docs/compass": root / "docs" / "compass" / "board.html",
        "a directory": root,
        "a missing folder": root / "no-such-folder" / "board.html",
    }


@pytest.mark.parametrize("command", [
    ("board", "render", "--no-open", "--out"),
    ("board", "refresh", "--out"),
    ("flow", "--html"),
])
def test_trc_e9_path_guard(rig, tmp_path, command):
    root = _project(tmp_path)
    _one_of_each(root)
    (root / "docs" / "compass").mkdir(parents=True)
    named = {"render": "compass board render", "refresh": "compass board refresh",
             "--html": "compass flow --html"}
    name = named[command[1] if command[0] == "board" else command[1]]
    for why, target in _guard_targets(root).items():
        done = rig.run(root, *command, str(target))
        out = done.stdout + done.stderr
        assert done.returncode != 0, (why, out)
        # The CLI prints a path under the project relative to it.
        assert name in out and target.name in out, (why, out)
    assert not (root / ".compass" / "board.html").exists()
    assert not (root / "docs" / "compass" / "board.html").exists()
    assert list(rig.tmp.iterdir()) == []


def test_trc_e9_refuses_before_reading_any_manifest(rig, tmp_path, monkeypatch):
    from compass_pkg import board_cmd, flow
    from compass_pkg.core import CompassError
    root = _project(tmp_path)
    _one_of_each(root)
    monkeypatch.chdir(root)

    def read(*args, **kwargs):
        raise AssertionError("a manifest was read before the target was checked")

    monkeypatch.setattr(flow, "read_checkout", read)
    monkeypatch.setattr(flow, "board", read)
    import argparse
    args = argparse.Namespace(out=str(root / ".compass" / "board.html"),
                              worktrees=False, no_open=True)
    with pytest.raises(CompassError):
        board_cmd.cmd_board_render(args)
    with pytest.raises(CompassError):
        board_cmd.cmd_board_refresh(args)


def test_trc_e12_naming_rule(rig, tmp_path):
    root = _project(tmp_path)
    done = rig.run(root, "board", "--help")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "render" in done.stdout and "refresh" in done.stdout
    import test_cli_renames as names
    problems = names.convention_problems(names._load_root())
    assert not [p for p in problems if p.startswith("board")], problems
    assert "board refresh" in names.EXCEPTIONS
    assert names.EXCEPTIONS["board refresh"].strip()
    assert "board render" not in names.EXCEPTIONS


def test_trc_e13_outside_project(rig, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    for verb in (("render", "--no-open"), ("refresh",)):
        done = rig.run(bare, "board", *verb)
        assert done.returncode != 0, done.stdout + done.stderr
        assert ".compass" in done.stdout + done.stderr
    assert list(rig.tmp.iterdir()) == []


# --- command-level checks for the board file (E4, E10, E14, E15) ---------------

def test_trc_e4_the_command_prints_one_stable_path_per_checkout(rig, tmp_path):
    first = _repo(tmp_path, "first")
    odd = _project(tmp_path, "my board;x")
    side = _worktree(first, tmp_path / "wt" / "second")
    (side / ".compass" / "work").mkdir(parents=True)
    printed = {}
    for name, checkout in (("first", first), ("odd", odd), ("side", side)):
        one, two = rig.default_path(checkout), rig.default_path(checkout)
        assert one == two
        printed[name] = one
    assert len(set(printed.values())) == 3
    for name, checkout in (("first", first), ("odd", odd), ("side", side)):
        path = printed[name]
        assert os.path.realpath(path.parent) == os.path.realpath(rig.tmp)
        digest = hashlib.sha256(os.path.realpath(checkout).encode()).hexdigest()[:8]
        folder = re.sub(r"[^A-Za-z0-9._-]", "-", checkout.name)
        assert path.name == f"compass-board-{folder}-{digest}.html"
    assert printed["odd"].name.startswith("compass-board-my-board-x-")


def test_trc_e10_the_command_refuses_a_link_at_the_default_path(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    path = rig.default_path(root)
    path.unlink()
    precious = tmp_path / "precious.txt"
    precious.write_text("keep me\n")
    path.symlink_to(precious)
    for verb in (("render", "--no-open"), ("refresh",)):
        done = rig.run(root, "board", *verb)
        out = done.stdout + done.stderr
        assert done.returncode != 0, out
        assert str(path) in out and "--out" in out, out
        assert path.is_symlink() and os.readlink(path) == str(precious)
        assert precious.read_text() == "keep me\n"


def test_trc_e14_the_default_file_is_private_and_an_out_file_is_not(rig, tmp_path):
    if not hasattr(os, "getuid"):
        pytest.skip("needs POSIX file permissions")
    root = _project(tmp_path)
    _one_of_each(root)
    path = rig.default_path(root)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    path.chmod(0o666)
    done = rig.run(root, "board", "refresh")
    assert done.returncode == 0, done.stdout + done.stderr
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    target = rig.outs / "shared.html"
    done = rig.run(root, "board", "render", "--no-open", "--out", str(target))
    assert done.returncode == 0, done.stdout + done.stderr
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_trc_e15_planted_temporary_names_are_never_followed(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    path = rig.default_path(root)
    path.unlink()
    planted = {}
    for suffix in (".tmp", ".part", ".new", "~"):
        victim = tmp_path / f"victim{abs(hash(suffix))}.txt"
        victim.write_text("untouched\n")
        link = Path(str(path) + suffix)
        link.symlink_to(victim)
        planted[link] = victim
    for _ in range(2):
        done = rig.run(root, "board", "render", "--no-open")
        assert done.returncode == 0, done.stdout + done.stderr
    for link, victim in planted.items():
        assert link.is_symlink() and victim.read_text() == "untouched\n"
    assert set(os.listdir(rig.tmp)) == {path.name} | {p.name for p in planted}


# --- A2, A3: the three views agree --------------------------------------------

TEXT_SECTIONS = (("IN PROGRESS", "in-progress"), ("IN REVIEW", "in-review"),
                 ("READY", "ready"), ("BACKLOG", "backlog"),
                 ("DONE THIS WEEK", "done"))


def _text_states(text):
    states, current = {}, None
    for line in text.splitlines():
        heading = re.match(r"^  ([A-Z][A-Z ]+)\b.*\(\d+\)$", line)
        if heading and not line.startswith("    "):
            current = next((s for h, s in TEXT_SECTIONS if line.strip().startswith(h)), None)
        elif line.startswith("    ") and current:
            states[line.split()[0]] = current
    return states


def test_trc_a2_outputs_agree_on_state(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    expected = {"set-aside-one": ("backlog", "backlog"), "ready-one": ("ready", "plan"),
                "going-one": ("in-progress", "plan"),
                "reviewing-one": ("in-review", "verify"),
                "finished-one": ("done", "done")}
    as_json = rig.run(root, "flow", "--json")
    assert as_json.returncode == 0, as_json.stdout + as_json.stderr
    board = json.loads(as_json.stdout)["board"]
    json_states = {r["slug"]: r["state"] for rows in board.values() for r in rows}
    text = rig.run(root, "flow")
    assert text.returncode == 0, text.stdout + text.stderr
    text_states = _text_states(text.stdout)
    page = rig.page(root)
    for slug, (state, lane) in expected.items():
        assert json_states[slug] == state, slug
        assert text_states[slug] == state, (slug, text.stdout)
        found, where, html = _card(page, slug)
        assert f">{state if state != 'done' else 'done (completed)'}<" in html, (slug, html)
        assert where == _lane(lane), slug


def test_trc_a3_flow_html_is_the_board_page(rig, tmp_path):
    root = _project(tmp_path)
    _one_of_each(root)
    first, second = rig.outs / "first.html", rig.outs / "second.html"
    one = rig.run(root, "flow", "--html", str(first))
    two = rig.run(root, "board", "render", "--no-open", "--out", str(second))
    assert one.returncode == 0, one.stdout + one.stderr
    assert two.returncode == 0, two.stdout + two.stderr
    a, b = first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8")
    assert len(GENERATED.findall(a)) == 1 and len(GENERATED.findall(b)) == 1
    assert GENERATED.sub("", a) == GENERATED.sub("", b)
    assert 'class="lane"' in a


# --- B13: the header counts ----------------------------------------------------

def test_trc_b13_the_header_counts_blocked_and_stale_issues(tmp_path, monkeypatch):
    from compass_pkg import binding, board_cmd
    root = _project(tmp_path)
    _write(root, "waiting-one", current_phase="implement",
           blocked={"reason": "waiting for the schema review", "at": "2026-10-01"},
           **_assessed())
    _write(root, "stale-one", current_phase="implement", **_assessed())
    _write(root, "fresh-one", current_phase="implement", **_assessed())
    _write(root, "parked-one", status="backlog",
           blocked={"reason": "ignored on a set-aside issue", "at": "2026-10-01"},
           **_assessed())
    monkeypatch.setattr(
        binding, "evidence_state",
        lambda m, task_dir: "stale" if task_dir.endswith("stale-one") else "fresh")
    page = board_cmd.build_page(str(root), str(root / ".compass" / "work"), False,
                                datetime.datetime.now())
    tiles = re.findall(r"<li>(.*?)</li>", page.split("<header>")[1].split("</header>")[0])
    assert "4 issues" in tiles
    assert "blocked 1" in tiles and "stale evidence 1" in tiles
    assert "in-progress 3" in tiles and "backlog 1" in tiles
    assert "blocked: waiting for the schema review" in page
    assert "ignored on a set-aside issue" not in page


# --- B14, B15, B17, D4, D5: the page over a built project ----------------------

RETIRED = re.compile(r"\b(held|queued|parked|landed|abandoned|active|route)\b", re.I)


def test_trc_b14_no_retired_status_words(rig, tmp_path):
    root = _project(tmp_path)
    _write(root, "was-one", status="queued", **_assessed())
    _write(root, "was-two", status="parked", parked_reason="waiting on a decision",
           **_assessed())
    _write(root, "was-three", status="active", current_phase="plan", **_assessed())
    _write(root, "was-four", status="landed", land_timestamp=_days_ago(1), **_assessed())
    _write(root, "was-five", status="abandoned", **_assessed())
    page = rig.page(root)
    text = rig.run(root, "flow")
    assert text.returncode == 0, text.stdout + text.stderr
    assert not RETIRED.search(page), RETIRED.search(page).group(0)
    assert not RETIRED.search(text.stdout), RETIRED.search(text.stdout).group(0)
    assert "set aside" in page and "reason: waiting on a decision" in page


def test_trc_b15_stage_depth_words(rig, tmp_path):
    root = _project(tmp_path)
    _write(root, "six-skipped", current_phase="implement",
           **_assessed(stages=_stages(breakdown="skipped")))
    _write(root, "six-multi", current_phase="implement",
           **_assessed(stages=_stages(breakdown="multiagent")))
    old = _stages(assess="full", refine="light", breakdown="swarm")
    _write(root, "old-one", current_phase="implement",
           assessment={"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery", "role": "engineer",
                       "labels": []},
           **_assessed(stages=old))
    _write(root, "old-pair", current_phase="implement",
           **_assessed(stages=_stages(breakdown="solo-or-pair")))
    _write(root, "old-solo", current_phase="implement",
           **_assessed(stages=_stages(breakdown="solo")))
    page = rig.page(root)

    def depths(slug):
        return re.findall(r'class="depth">([^<]*)<', _panel(page, slug))

    assert depths("six-skipped")[4] == "skipped"
    assert depths("six-multi")[4] == "multiagent"
    one = depths("old-one")
    assert (one[0], one[2], one[4]) == ("thorough", "lightweight", "multiagent")
    assert "<dd>medium</dd>" in _panel(page, "old-one")
    assert depths("old-pair")[4] == "solo-or-pair"
    assert depths("old-solo")[4] == "solo"
    for slug in ("old-pair", "old-solo"):
        assert _card(page, slug)[1] == _lane("implement")
    assert not _note(page)
    assert not re.search(r'class="depth">(full|light|swarm|standard)<', page)
    assert "<dd>standard</dd>" not in page


def test_trc_b17_one_lane_per_issue(rig, tmp_path):
    root = _project(tmp_path)
    _write(root, "unassessed-one", status="backlog")
    _write(root, "set-aside-one", status="backlog", **_assessed())
    _write(root, "early-one", **_assessed())
    _write(root, "ready-one", scenarios=ONE_SCENARIO,
           **_assessed(stages=_stages(refine="skipped")))
    _write(root, "going-one", current_phase="implement", **_assessed())
    _write(root, "reviewing-one", current_phase="verify", gates=GATES, **_assessed())
    _write(root, "done-completed", status="done", close_reason="completed",
           land_timestamp=_days_ago(2), **_assessed())
    _write(root, "done-old", status="done", close_reason="completed",
           land_timestamp=_days_ago(30), **_assessed())
    _write(root, "done-not-planned", status="done", close_reason="not-planned",
           **_assessed())
    _write(root, "done-duplicate", status="done", close_reason="duplicate",
           duplicate_of="going-one", **_assessed())
    bad = root / ".compass" / "work" / "unreadable-one"
    bad.mkdir()
    (bad / "manifest.yml").write_text("key: [unclosed\n  - : :\n")
    page = rig.page(root)
    slugs = [p.name for p in (root / ".compass" / "work").iterdir()]
    carded = [c[0] for c in _cards(page)]
    assert len(carded) == len(set(carded))
    noted = [s for s, _ in _note(page)]
    header = page.split("<header>")[1].split("</header>")[0]
    for slug in slugs:
        if slug in carded:
            continue
        if slug.startswith("done-"):
            assert "done (" in header, slug
        else:
            assert slug in noted, slug
    assert "done (completed) 2" in header
    assert "done (not-planned) 1" in header and "done (duplicate) 1" in header
    assert noted == ["unreadable-one"]


def test_trc_d4_the_note_lists_each_folder_the_page_cannot_place(rig, tmp_path):
    root = _project(tmp_path)
    work = root / ".compass" / "work"
    (work / "no-manifest").mkdir()
    (work / "bad-yaml").mkdir()
    (work / "bad-yaml" / "manifest.yml").write_text("key: [unclosed\n  - : :\n")
    _write(root, "wrong-type", gates=5,
           **_assessed(artifacts=[{"kind": "technical-design", "path": "d.md"}]))
    _write(root, "odd-status", status="wibble", **_assessed())
    _write(root, "done-bare", status="done", **_assessed())
    _write(root, "schema-4", schema_version="4.0", **_assessed())
    _write(root, "no-stage", current_phase="nonsense", **_assessed())
    readable = [f"readable-{n}" for n in range(5)]
    for slug in readable:
        _write(root, slug, **_assessed())
    page = rig.page(root)
    note = dict(_note(page))
    assert sorted(note) == ["bad-yaml", "done-bare", "no-manifest", "no-stage",
                            "odd-status", "schema-4", "wrong-type"]
    for slug, text in note.items():
        assert "tree this checkout" in text and len(text.split(" - ")[-1]) > 3, text
    assert "schema_version" in note["schema-4"]
    assert "current_phase" in note["no-stage"]
    assert "wibble" in note["odd-status"]
    carded = {c[0] for c in _cards(page)}
    assert carded == set(readable)


def test_trc_d5_empty_project(rig, tmp_path):
    root = _project(tmp_path)
    page = rig.page(root)
    assert len(LANE.findall(page)) == 10
    for name, body in LANE.findall(page):
        assert 'class="count">0<' in body, name
        assert not CARD.findall(body)
    assert "There are no issues yet" in page
    html = rig.outs / "flow-empty.html"
    done = rig.run(root, "flow", "--html", str(html))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "There are no issues yet" in html.read_text(encoding="utf-8")


# --- worktrees: W1, W2, W3, W4, W7, W8, W9, W10, W12 ----------------------------

def _two_trees(tmp_path):
    main = _repo(tmp_path)
    side = _worktree(main, tmp_path / "wt" / "side")
    (side / ".compass" / "work").mkdir(parents=True, exist_ok=True)
    return main, side


def test_trc_w1_other_worktree_issue(rig, tmp_path):
    main, side = _two_trees(tmp_path)
    _write(main, "here-one", current_phase="plan", **_assessed())
    _write(side, "side-only", current_phase="implement", **_assessed())
    page = rig.page(main, "--worktrees")
    slug, lane, html = _card(page, "side-only")
    assert lane == _lane("implement")
    assert "tree side" in html and "also in" not in html
    panel = _panel(page, "side-only")
    assert ".compass/work/side-only/manifest.yml" in panel and "Tree side" in panel
    assert _card(page, "here-one")[1] == _lane("plan")


def test_trc_w2_the_newest_copy_decides_on_the_page(rig, tmp_path):
    main = _repo(tmp_path)
    trees = {n: _worktree(main, tmp_path / "wt" / n) for n in ("a", "b", "c")}
    for tree, phase, when in ((trees["a"], "plan", 1_000), (trees["b"], "verify", 3_000),
                              (trees["c"], "implement", 2_000)):
        _write(tree, "shared", mtime=when, current_phase=phase, **_assessed())
    page = rig.page(main, "--worktrees")
    slug, lane, html = _card(page, "shared")
    assert lane == _lane("verify")
    assert "tree b" in html and "also in 2 trees" in html


def test_trc_w3_the_header_counts_trees_read_and_skipped(rig, tmp_path):
    main = _repo(tmp_path)
    ok = _worktree(main, tmp_path / "wt" / "ok")
    gone = _worktree(main, tmp_path / "wt" / "gone")
    locked = _worktree(main, tmp_path / "wt" / "locked")
    _write(ok, "from-ok", current_phase="plan", **_assessed())
    _write(gone, "from-gone", current_phase="plan", **_assessed())
    _write(locked, "from-locked", current_phase="plan", **_assessed())
    _git(main, "worktree", "lock", str(locked))
    shutil.rmtree(gone)
    shutil.rmtree(locked)
    page = rig.page(main, "--worktrees")
    assert "Trees read: 2 (this checkout, ok)" in page
    assert "Trees skipped: 2" in page
    assert [c[0] for c in _cards(page)] == ["from-ok"]


def test_trc_w4_one_checkout_by_default(rig, tmp_path):
    main, side = _two_trees(tmp_path)
    _write(main, "here-one", current_phase="plan", **_assessed())
    _write(side, "side-only", current_phase="implement", **_assessed())
    page = rig.page(main)
    assert [c[0] for c in _cards(page)] == ["here-one"]
    assert "Trees read: 1 (this checkout)" in page


def test_trc_w7_outside_git_the_header_says_the_worktrees_could_not_be_listed(rig, tmp_path):
    root = _project(tmp_path)
    _write(root, "only-one", current_phase="plan", **_assessed())
    page = rig.page(root, "--worktrees")
    assert [c[0] for c in _cards(page)] == ["only-one"]
    assert "worktrees could not be listed" in page
    assert "not a git repository" in page.lower()


def test_trc_w8_unreadable_in_other_tree(rig, tmp_path):
    main, side = _two_trees(tmp_path)
    _write(main, "broken", mtime=1_000, current_phase="plan", **_assessed())
    _write(main, "here-ok", current_phase="plan", **_assessed())
    broken = side / ".compass" / "work" / "broken"
    broken.mkdir(parents=True)
    (broken / "manifest.yml").write_text("key: [unclosed\n  - : :\n")
    os.utime(broken / "manifest.yml", (3_000, 3_000))
    _write(side, "future", schema_version="4.0", **_assessed())
    _write(side, "side-ok", current_phase="implement", **_assessed())
    page = rig.page(main, "--worktrees")
    note = dict(_note(page))
    assert sorted(note) == ["broken", "future"]
    for slug, text in note.items():
        assert "tree side" in text, text
    carded = {c[0] for c in _cards(page)}
    assert carded == {"here-ok", "side-ok"}


def _tree_state(*roots):
    seen = {}
    for root in roots:
        for sub in (".compass/work", "docs/compass"):
            for here, _, files in os.walk(root / sub):
                for name in files:
                    p = Path(here) / name
                    st = p.stat()
                    seen[str(p)] = (st.st_mtime_ns, p.read_bytes())
            for here, dirs, _ in os.walk(root / sub):
                for d in dirs:
                    seen[str(Path(here) / d) + "/"] = None
    return seen


def test_trc_w9_no_issue_state_changed(rig, tmp_path):
    main, side = _two_trees(tmp_path)
    _write(main, "here-one", current_phase="plan", **_assessed())
    _write(side, "side-only", current_phase="implement", **_assessed())
    for tree, slug in ((main, "here-one"), (side, "side-only")):
        docs = tree / "docs" / "compass" / f"2026-10-01-{slug}"
        docs.mkdir(parents=True)
        (docs / "notes.md").write_text("# Notes\n")
    before = _tree_state(main, side)
    assert before
    outside = rig.outs / "flow-copy.html"
    for args in (("board", "render", "--no-open", "--worktrees"),
                 ("board", "refresh", "--worktrees"),
                 ("flow", "--html", str(outside))):
        done = rig.run(main, *args)
        assert done.returncode == 0, done.stdout + done.stderr
    assert _tree_state(main, side) == before


def test_trc_w10_a_link_leading_out_of_a_tree_is_listed_not_followed(rig, tmp_path):
    main, side = _two_trees(tmp_path)
    _write(main, "here-one", current_phase="plan", **_assessed())
    outside = tmp_path / "outside"
    _write(tmp_path / "outside-root", "escape", current_phase="plan", **_assessed())
    shutil.move(str(tmp_path / "outside-root" / ".compass" / "work" / "escape"), str(outside))
    os.symlink(outside, side / ".compass" / "work" / "escape")
    page = rig.page(main, "--worktrees")
    note = dict(_note(page))
    assert list(note) == ["escape"]
    assert "tree side" in note["escape"] and "leads out of the tree" in note["escape"]
    assert [c[0] for c in _cards(page)] == ["here-one"]


def test_trc_w12_done_here_not_read_elsewhere(rig, tmp_path, monkeypatch):
    main, side = _two_trees(tmp_path)
    _write(main, "finished", mtime=1_000, status="done", close_reason="completed",
           land_timestamp=_days_ago(2), **_assessed())
    _write(side, "finished", mtime=9_000, current_phase="implement", **_assessed())
    _write(main, "elsewhere", mtime=1_000, current_phase="plan", **_assessed())
    _write(side, "elsewhere", mtime=9_000, status="done", close_reason="completed",
           land_timestamp=_days_ago(1), **_assessed())
    page = rig.page(main, "--worktrees")
    slug, lane, html = _card(page, "finished")
    assert lane == DONE_LANE and "tree side" not in html
    slug, lane, html = _card(page, "elsewhere")
    assert lane == DONE_LANE and "tree side" in html
    # The command hands the reader only the slugs done in this checkout.
    from compass_pkg import board_cmd, board_trees
    seen = {}
    real = board_trees.list_sources

    def watch(project_root, worktrees, skip_slugs=frozenset()):
        seen["skip"] = set(skip_slugs)
        return real(project_root, worktrees, skip_slugs)

    monkeypatch.setattr(board_trees, "list_sources", watch)
    board_cmd.build_page(str(main), str(main / ".compass" / "work"), True,
                         datetime.datetime.now())
    assert seen["skip"] == {"finished"}


# --- review round 1 -------------------------------------------------------------

def _count_parses(monkeypatch, twice=False):
    """Record the manifest every `load_yaml` call in the package reads, through
    every module that imported the name. With `twice`, the board's own manifest
    parser is made to parse each manifest a second time."""
    from compass_pkg import core, flow
    seen = []
    real = core.load_yaml

    def counting(path, *args, **kwargs):
        if str(path) == core.manifest_path(os.path.dirname(str(path))):
            seen.append(os.path.realpath(str(path)))
        return real(path, *args, **kwargs)

    for name, module in list(sys.modules.items()):
        if name.startswith("compass_pkg") and getattr(module, "load_yaml", None) is real:
            monkeypatch.setattr(module, "load_yaml", counting)
    if twice:
        once = flow._parse_manifest

        def parse_twice(task_dir):
            once(task_dir)
            return once(task_dir)

        monkeypatch.setattr(flow, "_parse_manifest", parse_twice)
    return seen


def _three_trees_with_fifty_issues(tmp_path):
    main = _repo(tmp_path)
    trees = [_worktree(main, tmp_path / "wt" / name) for name in ("a", "b", "c")]
    newest = {}
    for i in range(50):
        slug = f"issue-{i:02d}"
        winner = i % 3
        for j, tree in enumerate(trees):
            _write(tree, slug, mtime=9_000 if j == winner else 1_000 + j,
                   current_phase="plan", **_assessed())
        newest[slug] = trees[winner]
    return main, newest


def _board_over_worktrees(main):
    from compass_pkg import board_trees, flow
    sources, _ = board_trees.list_sources(str(main), True)
    return flow.board(str(main / ".compass" / "work"), sources=sources)


def test_trc_w5_the_board_parses_one_manifest_per_distinct_slug(tmp_path, monkeypatch):
    main, newest = _three_trees_with_fifty_issues(tmp_path)
    seen = _count_parses(monkeypatch)
    data = _board_over_worktrees(main)
    assert len(data["in_progress"]) == 50
    assert len(seen) == 50 and len(set(seen)) == 50, len(seen)
    assert set(seen) == {os.path.realpath(str(t / ".compass" / "work" / slug / "manifest.yml"))
                         for slug, t in newest.items()}


def test_trc_w5_the_parse_counter_sees_a_second_parse(tmp_path, monkeypatch):
    main, _ = _three_trees_with_fifty_issues(tmp_path)
    seen = _count_parses(monkeypatch, twice=True)
    _board_over_worktrees(main)
    assert len(seen) != 50 and len(set(seen)) == 50


def test_a_tree_folder_named_like_this_checkout_is_not_this_checkout(rig, tmp_path):
    main = _repo(tmp_path)
    _write(main, "shared", mtime=1_000, current_phase="implement", **_assessed())
    lookalike = _worktree(main, tmp_path / "wt" / THIS)
    _write(lookalike, "shared", mtime=9_000, current_phase="verify", **_assessed())
    page = rig.page(main, "--worktrees")
    slug, lane, html = _card(page, "shared")
    assert lane == _lane("verify")
    assert "tree " in html and str(lookalike.name) in html
    assert "Trees read: 2" in page


def test_a_slug_with_a_card_is_not_also_listed_for_a_link_out_of_another_tree(rig, tmp_path):
    main, side = _two_trees(tmp_path)
    _write(main, "tc-only", current_phase="plan", **_assessed())
    outside = tmp_path / "outside"
    _write(tmp_path / "outside-root", "tc-only", current_phase="plan", **_assessed())
    shutil.move(str(tmp_path / "outside-root" / ".compass" / "work" / "tc-only"), str(outside))
    os.symlink(outside, side / ".compass" / "work" / "tc-only")
    page = rig.page(main, "--worktrees")
    assert [c[0] for c in _cards(page)] == ["tc-only"]
    assert _note(page) == []
    assert "<li>1 issue</li>" in page
