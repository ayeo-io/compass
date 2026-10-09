# compass_pkg.board_cmd - the board commands and the one page builder
"""`compass board render`, `compass board refresh` and the page `compass flow
--html` writes.

This module is the only place that puts the board's parts in order:

1. find the project and check the target, so every refusal happens before a
   manifest is read;
2. read this checkout once (`flow.read_checkout`), which also tells which
   issues are done here;
3. with `--worktrees`, list the issue folders of the other trees, leaving out
   every slug that is done here;
4. build the board data (`flow.board`) and render it (`board_page`);
5. write the file (`board_file`), print its path and, for `render` only, ask
   the default browser to open it once.

Nothing here writes issue state.
"""
# DEPENDENCY: standard library (datetime, os, pathlib, webbrowser); compass_pkg.board_file, board_page, board_trees, flow, core, terminal.
from __future__ import annotations

import datetime
import os
import webbrowser
from pathlib import Path

from compass_pkg import board_file, board_page, board_trees, flow, status_words
from compass_pkg.core import find_compass_dir
from compass_pkg.terminal import Report


def build_page(project_root, work_root, worktrees, generated):
    """The board page as one HTML string. `compass flow --html` and
    `compass board render` both call this, so the two pages cannot differ."""
    parsed = flow.read_checkout(work_root)
    sources, trees = None, {"read": [board_trees.THIS_CHECKOUT], "skipped": 0,
                            "note": None}
    if worktrees:
        # An issue done here is read from this checkout only (it is not
        # listed in any other tree); an issue open here is still compared
        # with the copies elsewhere.
        done_here = {slug for slug, m in parsed.items()
                     if isinstance(m, dict) and status_words.is_closed(m)}
        sources, trees = board_trees.list_sources(project_root, True, done_here)
    data = flow.board(work_root, sources=sources, parsed=parsed)
    return board_page.render_page(data, generated, trees)


def _target(args, command):
    """Find the project and check where the page goes, before any read.
    Returns (project root, work root, path, file mode)."""
    compass_dir = find_compass_dir()
    root = os.path.dirname(compass_dir)
    if args.out:
        path = board_file.check_target(args.out, command, root)
        return root, os.path.join(compass_dir, "work"), path, board_file.OUT_MODE
    path = board_file.check_target(board_file.default_board_path(root), command, root)
    board_file.check_default_target(path, command)
    return root, os.path.join(compass_dir, "work"), path, board_file.PRIVATE_MODE


def _open_in_browser(path):
    """True when the browser call reports that it opened the file.

    The browser is asked once. `webbrowser.open` would, after a refusal, try
    each other browser the machine knows and so ask more than once; this asks
    the first one only, which is the one `BROWSER` names when it is set."""
    try:
        return bool(webbrowser.get().open(Path(path).resolve().as_uri()))
    except Exception:                                       # noqa: BLE001
        return False


def _run(args, command, open_browser):
    root, work_root, path, mode = _target(args, command)
    text = build_page(root, work_root, args.worktrees, datetime.datetime.now())
    action = board_file.write_page(path, text, mode)
    lines = ["%s: %s %s" % (command, action, path)]
    opened = None
    if open_browser:
        opened = _open_in_browser(path)
        lines.append("Opened it in the default browser." if opened else
                     "Could not open a browser; open the file yourself.")
    rep = Report(args, title=command)
    rep.summary(*lines)
    rep.data(path=path, action=action, opened=opened)
    return rep.emit()


def cmd_board_render(args):
    """Write the board page and ask the default browser to open it once."""
    return _run(args, "compass board render", not args.no_open)


def cmd_board_refresh(args):
    """Rewrite the board page in place. Never opens a browser."""
    return _run(args, "compass board refresh", False)


def _reading_options(parser):
    parser.add_argument(
        "--out", metavar="FILE", default=None,
        help="write the page to FILE instead of the checkout's board file "
             "(not inside .compass/ or docs/compass/)")
    parser.add_argument(
        "--worktrees", action="store_true",
        help="also read the issues in this repository's other git worktrees")


def register(sub):
    """Add `compass board render|refresh` to the top-level parser."""
    board = sub.add_parser(
        "board", help="the delivery board as one page - every issue by stage "
                      "(read-only; never modifies issue state)")
    verbs = board.add_subparsers(dest="subcmd", required=True)

    render = verbs.add_parser(
        "render", help="write the board page and open it in the browser")
    render.add_argument(
        "--no-open", action="store_true", dest="no_open",
        help="write the page and print its path, without opening a browser")
    _reading_options(render)
    render.set_defaults(func=cmd_board_render, output_kind="report")

    refresh = verbs.add_parser(
        "refresh", help="rewrite the board page in place (never opens a browser)")
    _reading_options(refresh)
    refresh.set_defaults(func=cmd_board_refresh, output_kind="report")
