"""`compass next` shows the route as a rail to a person, and nothing new to
the model.

A person at a terminal sees a header, a rail of the route's stages (done,
current, pending, skipped by policy) and the next command. Claude Code runs
commands with stdout not a terminal and with `CLAUDECODE` set, so either
condition must keep today's output byte for byte: `tests/fixtures/next-golden.json`
holds that output, captured before the rail existed, for each route below.

Regenerate the golden file only for a deliberate change to `compass next`'s
plain output: `python3 tests/test_progress_rail.py --regen`.
"""
from __future__ import annotations

import ast
import json
import os
import pty
import re
import select
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOLDEN = ROOT / "tests" / "fixtures" / "next-golden.json"
ANSI = re.compile(r"\x1b\[[0-9;]*m")

ROUTES = {
    "quick-fix": {"risk": "trivial", "familiarity": "brownfield-mapped",
                  "size": "atomic", "goal": "delivery", "role": "engineer"},
    "feature": {"risk": "contained", "familiarity": "brownfield-mapped",
                "size": "standard", "goal": "delivery", "role": "engineer"},
    "initiative": {"risk": "cross-cutting", "familiarity": "brownfield-unmapped",
                   "size": "large", "goal": "delivery", "role": "engineer"},
    "spike": {"risk": "contained", "familiarity": "brownfield-unmapped",
              "size": "small", "goal": "exploration", "role": "engineer"},
}
STATES = {
    "fresh": {},
    "implementing": {"current_phase": "implement"},
    "verifying": {"current_phase": "verify"},
    "landed": {"status": "landed"},
    "gates-pass": {"gates": "all-pass"},
}


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "NO_COLOR", "COMPASS_COLOR", "COLUMNS")}
    env.update(extra)
    return env


def _project(root: Path, route: str, state: str, *, approach_record=True) -> Path:
    import yaml
    slug = f"{route}-{state}"
    task = root / ".compass" / "work" / slug
    task.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(slug + "\n")
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-10-01",
        "status": "active", "assessment": ROUTES[route]}, sort_keys=False))
    r = subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--issue", slug,
                        "--write"], cwd=root, capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stdout + r.stderr
    m = yaml.safe_load((task / "manifest.yml").read_text())
    for key, value in STATES[state].items():
        if value == "all-pass":
            for g in m["gates"]:
                g["status"] = "pass"
        else:
            m[key] = value
    (task / "manifest.yml").write_text(yaml.safe_dump(m, sort_keys=False))
    if approach_record:
        (task / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
    return task


def _cases():
    for route in ROUTES:
        for state in STATES:
            yield f"{route}/{state}"
    yield "feature/no-approach-record"


def _build(tmp: Path, case: str) -> Path:
    route, state = case.split("/")
    root = tmp / case.replace("/", "-")
    root.mkdir(parents=True)
    if state == "no-approach-record":
        _project(root, route, "fresh", approach_record=False)
    else:
        _project(root, route, state)
    return root


def _neutral(text: str, root: Path) -> str:
    """The project path as <ROOT>, so the golden file holds on any machine.
    macOS resolves the temporary directory through /private, so the resolved
    path is replaced first."""
    return text.replace(str(root.resolve()), "<ROOT>").replace(str(root), "<ROOT>")


def _piped(root: Path, *args, **env):
    r = subprocess.run([sys.executable, str(CLI), "next", *args], cwd=root,
                       capture_output=True, text=True, env=_env(**env))
    return {"exit": r.returncode, "stdout": _neutral(r.stdout, root)}


def _tty(root: Path, *args, columns=100, **env):
    """Run `compass next` with stdout a pseudo-terminal; return its output."""
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, str(CLI), "next", *args], cwd=root,
                            stdout=slave, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                            env=_env(COLUMNS=str(columns), TERM="xterm-256color", **env))
    os.close(slave)
    chunks = []
    while True:
        ready, _, _ = select.select([master], [], [], 30)
        if not ready:
            break
        try:
            data = os.read(master, 4096)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    proc.wait(timeout=30)
    os.close(master)
    return proc.returncode, b"".join(chunks).decode("utf-8").replace("\r\n", "\n")


@pytest.mark.parametrize("case", list(_cases()))
def test_piped_output_matches_the_golden_file(tmp_path, case):
    """RL-B: what the model sees does not change."""
    golden = json.loads(GOLDEN.read_text())
    assert _piped(_build(tmp_path, case)) == golden[case]


@pytest.mark.parametrize("case", ["feature/implementing", "quick-fix/fresh", "spike/verifying"])
def test_claudecode_keeps_todays_output_in_a_terminal(tmp_path, case):
    """RL-D: Claude Code sets CLAUDECODE; even in a terminal it gets plain output."""
    root = _build(tmp_path, case)
    code, out = _tty(root, CLAUDECODE="1")
    golden = json.loads(GOLDEN.read_text())[case]
    assert (code, _neutral(out, root)) == (golden["exit"], golden["stdout"])


@pytest.mark.parametrize("flag", ["--json", "--quiet"])
def test_machine_and_quiet_views_keep_todays_output(tmp_path, flag):
    """Only the default human view gets the rail."""
    root = _build(tmp_path, "feature/implementing")
    assert "●" in _tty(root)[1]
    plain = _piped(root, flag)["stdout"]
    assert _neutral(_tty(root, flag)[1], root) == plain


def _rail_lines(out: str) -> list[str]:
    lines = ANSI.sub("", out).split("\n")
    # header, then the rail up to the first blank line
    rail = []
    for line in lines[1:]:
        if not line.strip():
            break
        rail.append(line)
    return rail


def test_a_terminal_shows_a_rail_with_one_current_marker(tmp_path):
    """RL-A: at a terminal, the line after the header is a rail with exactly
    one current marker."""
    root = _build(tmp_path, "feature/implementing")
    code, out = _tty(root)
    assert code == 0, out
    plain = ANSI.sub("", out)
    assert plain.split("\n")[0] == "feature · feature-implementing", plain
    rail = " ".join(_rail_lines(out))
    assert rail.count("●") == 1, rail
    assert "Implement ●" in rail, rail
    assert "Assess ✓" in rail and "Verify ○" in rail and "Ship ○" in rail, rail
    assert "\x1b[" in out, "a terminal with no NO_COLOR gets colour"


def test_a_skipped_stage_is_shown_not_left_out(tmp_path):
    """RL-C: the quick fix collapses most stages; each still appears."""
    root = _build(tmp_path, "quick-fix/implementing")
    code, out = _tty(root)
    rail = " ".join(_rail_lines(out))
    for stage in ("Assess", "Define", "Refine", "Plan", "Breakdown", "Implement",
                  "Verify", "Ship"):
        assert stage in rail, (stage, rail)
    assert "–" in rail, rail


def test_no_color_drops_the_colour_codes(tmp_path):
    """RL-E: with NO_COLOR set, the rail has no colour codes."""
    root = _build(tmp_path, "feature/implementing")
    code, out = _tty(root, NO_COLOR="1")
    assert "●" in out and "\x1b[" not in out, repr(out)


def test_compass_color_never_uses_ascii_markers(tmp_path):
    """RL-E: with COMPASS_COLOR=never, the rail uses ASCII markers and no
    colour codes."""
    root = _build(tmp_path, "quick-fix/implementing")
    code, out = _tty(root, COMPASS_COLOR="never")
    rail = " ".join(_rail_lines(out))
    assert "\x1b[" not in out, repr(out)
    assert "[>]" in rail and "[-]" in rail and "[x]" in rail, rail
    assert out.isascii(), out


def test_compass_color_always_shows_the_rail_when_piped(tmp_path):
    """RL-E: always overrides the terminal check, but never CLAUDECODE."""
    root = _build(tmp_path, "feature/implementing")
    shown = _piped(root, COMPASS_COLOR="always")["stdout"]
    assert "●" in shown and "\x1b[" in shown, shown
    golden = json.loads(GOLDEN.read_text())["feature/implementing"]
    assert _piped(root, COMPASS_COLOR="always", CLAUDECODE="1") == golden


def test_no_color_wins_over_compass_color_always(tmp_path):
    """RL-E: NO_COLOR means no colour codes, whatever COMPASS_COLOR says."""
    root = _build(tmp_path, "feature/implementing")
    code, out = _tty(root, NO_COLOR="1", COMPASS_COLOR="always")
    assert "●" in out and "\x1b[" not in out, repr(out)
    shown = _piped(root, NO_COLOR="1", COMPASS_COLOR="always")["stdout"]
    assert "●" in shown and "\x1b[" not in shown, repr(shown)


@pytest.mark.parametrize("flag", ["--json", "--quiet", "--evidence-out"])
def test_machine_views_stay_plain_under_compass_color_always(tmp_path, flag):
    """`always` draws the rail on a pipe, but never into a machine view."""
    root = _build(tmp_path, "feature/implementing")
    args = [flag, str(tmp_path / "capture.txt")] if flag == "--evidence-out" else [flag]
    assert _piped(root, *args, COMPASS_COLOR="always") == _piped(root, *args)


def test_a_manifest_value_cannot_write_escape_codes(tmp_path):
    """The header prints the manifest's issue name. A control character in it
    must not reach the terminal, where it could set the window title or clear
    the screen."""
    root = _build(tmp_path, "feature/implementing")
    manifest = root / ".compass" / "work" / "feature-implementing" / "manifest.yml"
    manifest.write_text(manifest.read_text().replace(
        "issue: feature-implementing",
        'issue: "\\e]0;pwned\\a\\e[2Jevil"'))
    code, out = _tty(root, COMPASS_COLOR="never")
    assert code == 0, out
    assert "\x1b" not in out and "\x07" not in out, repr(out)
    assert out.split("\n")[0] == "feature - ]0;pwned[2Jevil", repr(out)


@pytest.mark.parametrize("colour", [None, "never"])
def test_a_terminal_that_cannot_encode_the_rail_gets_a_working_output(tmp_path, colour):
    """A stdout that cannot encode the glyphs must not crash `compass next`:
    ASCII markers draw the rail, and anything still unencodable falls back
    to today's line."""
    root = _build(tmp_path, "feature/implementing")
    env = {"PYTHONIOENCODING": "ascii"}
    if colour:
        env["COMPASS_COLOR"] = colour
    code, out = _tty(root, **env)
    assert code == 0, out
    assert out.isascii(), out
    assert "Implement [gate: verify.correctness]" in out, out
    if colour == "never":
        assert "[>]" in out, out


def test_a_long_slug_still_fits_a_narrow_terminal(tmp_path):
    """RL-F covers the header as well as the rail."""
    import shutil
    root = _build(tmp_path, "feature/implementing")
    long_slug = "devlog-logs-edits-outside-the-project"
    work = root / ".compass" / "work"
    shutil.move(str(work / "feature-implementing"), str(work / long_slug))
    (root / ".compass" / "current-task").write_text(long_slug + "\n")
    manifest = work / long_slug / "manifest.yml"
    manifest.write_text(manifest.read_text().replace(
        "issue: feature-implementing", f"issue: {long_slug}"))
    code, out = _tty(root, columns=40)
    assert code == 0, out
    for line in ANSI.sub("", out).split("\n"):
        assert len(line) <= 40, line


def test_an_unknown_current_stage_gets_no_next_command(tmp_path):
    """A stage outside the pipeline's order names no command, so there is
    no `Next:` line to print and no stage is marked done or current."""
    import yaml
    root = _build(tmp_path, "feature/fresh")
    path = root / ".compass" / "work" / "feature-fresh" / "manifest.yml"
    m = yaml.safe_load(path.read_text())
    m["current_phase"] = "conclude"
    path.write_text(yaml.safe_dump(m, sort_keys=False))
    code, out = _tty(root, NO_COLOR="1")
    plain = ANSI.sub("", out)
    assert code == 0 and "Next:" not in plain and "✓" not in plain, plain
    assert "Conclude [gate: verify.correctness]" in plain, plain


@pytest.mark.parametrize("case", ["feature/implementing", "quick-fix/implementing"])
def test_a_narrow_terminal_wraps_the_rail(tmp_path, case):
    """RL-F: every line fits, the plain line under the rail included. A
    quick-fix's plain line names its collapsed stages, so it is the longest."""
    root = _build(tmp_path, case)
    code, out = _tty(root, columns=40)
    rail = _rail_lines(out)
    assert len(rail) > 1, rail
    for line in ANSI.sub("", out).split("\n"):
        assert len(line) <= 40, line
    assert " ".join(rail).count("●") == 1, rail


@pytest.mark.parametrize("case, command", [
    ("feature/implementing", "/compass:implement"),
    ("feature/verifying", "/compass:verify"),
    ("quick-fix/implementing", "/compass:quick-fix"),
])
def test_the_next_line_names_the_command(tmp_path, case, command):
    """RL-G: a Next line names the command for the current stage."""
    code, out = _tty(_build(tmp_path, case))
    assert f"Next: {command}" in ANSI.sub("", out), out


def test_a_finished_issue_has_no_current_marker_and_no_next_line(tmp_path):
    code, out = _tty(_build(tmp_path, "feature/landed"))
    plain = ANSI.sub("", out)
    assert "●" not in plain and "Next:" not in plain, plain
    assert "all phases complete" in plain, plain


def test_the_renderer_imports_only_the_standard_library():
    """Constraint: one module, standard library only."""
    tree = ast.parse((ROOT / "cli" / "compass_pkg" / "render.py").read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    assert names <= set(sys.stdlib_module_names), names - set(sys.stdlib_module_names)



def test_the_status_line_fits_its_line_with_the_shared_renderer():
    """RL-H: one renderer for the rail and the status line, so width fitting
    is fixed in one place."""
    sys.path.insert(0, str(ROOT / "cli"))
    import compass_pkg.render as render
    import compass_pkg.statusline as statusline
    assert not hasattr(statusline, "_fit"), "the status line keeps its own fitting"
    assert statusline.fit is render.fit
    line = render.fit(["compass", "a-long-issue-slug", "feature", "Implement",
                       "gates 1/6"], 30, " · ")
    assert len(line) <= 30 and line.startswith("compass · a-long"), line

if __name__ == "__main__" and sys.argv[1:] == ["--regen"]:
    import tempfile
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for case in _cases():
            out[case] = _piped(_build(Path(tmp), case))
    GOLDEN.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} cases to {GOLDEN}")
