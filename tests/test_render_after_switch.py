"""The after-command render can be switched off, and a command that never
renders does not load the render modules (DCJ-88, DCJ-89)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import rendered_blocks_support as sup
from rendered_blocks_support import SLUG, run

CLI = Path(__file__).resolve().parent.parent / "cli" / "compass"


def _blocked_header(root):
    page = Path(root) / sup.DOCS / "README.md"
    return page.read_text("utf-8").split("<!-- /compass:render -->")[0]


def test_dcj_88_the_environment_variable_switches_the_after_command_render_off(tmp_path):
    root = sup.rich_issue(tmp_path)
    assert sup.render(root)[0] == 0
    code, out, err = run(root, "issue", "blocked", "set", "--reason", "waiting on a review",
                         "--issue", SLUG, extra_env={"COMPASS_RENDER_AFTER": "0"})
    assert code == 0, out + err
    assert "Blocked" not in _blocked_header(root)
    # Any other value renders, as before.
    code, out, err = run(root, "issue", "blocked", "set", "--reason", "waiting on a review",
                         "--issue", SLUG, extra_env={"COMPASS_RENDER_AFTER": "1"})
    assert code == 0, out + err
    assert "Blocked: waiting on a review" in _blocked_header(root)
    # An explicit render is not affected by the switch.
    code, out, err = run(root, "issue", "blocked", "remove", "--issue", SLUG,
                         extra_env={"COMPASS_RENDER_AFTER": "0"})
    assert code == 0, out + err
    assert "Blocked: waiting on a review" in _blocked_header(root)
    code, out, err = run(root, "issue", "render", "--issue", SLUG,
                         extra_env={"COMPASS_RENDER_AFTER": "0"})
    assert code == 0, out + err
    assert "Blocked" not in _blocked_header(root)


def test_dcj_89_a_command_outside_the_render_triggers_does_not_load_the_render_modules(tmp_path):
    done = subprocess.run([sys.executable, "-X", "importtime", str(CLI), "next"],
                          cwd=tmp_path, capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL)
    loaded = {line.rsplit("|", 1)[-1].strip() for line in done.stderr.splitlines()
              if line.startswith("import time:")}
    assert "compass_pkg.core" in loaded, done.stderr[-500:]
    for name in ("compass_pkg.render_after", "compass_pkg.render_cmd",
                 "compass_pkg.render_check", "compass_pkg.block_renderers"):
        assert name not in loaded, name


def test_dcj_90_the_lazy_check_entry_still_goes_red_when_the_check_is_broken():
    runner = Path(__file__).resolve().parent.parent / ".github" / "scripts" / "check_mutation_runner.py"
    done = subprocess.run([sys.executable, str(runner), "--check", "rendered-blocks-current"],
                          capture_output=True, text=True, timeout=300,
                          env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert done.returncode == 0, done.stdout[-800:] + done.stderr[-400:]


def test_dcj_91_compass_next_loads_no_rendered_blocks_module(tmp_path):
    done = subprocess.run([sys.executable, "-X", "importtime", str(CLI), "next"],
                          cwd=tmp_path, capture_output=True, text=True, timeout=60,
                          stdin=subprocess.DEVNULL)
    loaded = {line.rsplit("|", 1)[-1].strip() for line in done.stderr.splitlines()
              if line.startswith("import time:")}
    assert "compass_pkg.core" in loaded, done.stderr[-500:]
    added = ("rendered_blocks", "block_renderers", "render_check", "render_cmd", "render_after",
             "render_inputs", "render_skip", "issue_page", "issue_detail", "project_index",
             "project_scan", "migrate_blocks")
    found = sorted(n for n in added if "compass_pkg." + n in loaded)
    assert not found, found
