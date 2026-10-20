"""The `language` setting is checked by the tag rules in `compass_pkg.language`.

Each test runs the real CLI on a scratch project. Each test name ends with the
number of its scenario in the acceptance criteria of the issue
`language-key-and-us-english`. The test for the documented tag table belongs to
the documentation unit of that issue.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
HOOK = ROOT / "hooks" / "session-start.sh"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg import catalogue_check, language, project_settings  # noqa: E402
from parent_fixtures import issue_project  # noqa: E402

SENTENCE_START = "`language` in compass.yml"
GUIDE = "docs/configuration.md"

# The 17 values of the acceptance criteria that are not a language tag.
REFUSED = ["en_US", "en-", "-en", "en--US", "x-klingon", "e", "english", "zh-yue",
           "zh-cmn-Hans", "en-US-posix", "de-CH-1996", "en-1234", "en-USA", "en-U",
           "en US", "en-US,de", "en-Ü"]


def _env():
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _run(cwd, *argv):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(),
                          capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout + done.stderr


def _project(tmp_path, compass_yml, old=None, name="proj"):
    """A project whose compass.yml holds `compass_yml`, and an old settings
    file when `old` is given."""
    root = tmp_path / name
    (root / ".compass").mkdir(parents=True)
    if compass_yml is not None:
        (root / "compass.yml").write_text(compass_yml, encoding="utf-8")
    if old is not None:
        (root / ".compass" / "config.yml").write_text(old, encoding="utf-8")
    return root


def _with_language(tmp_path, yaml_value, name="proj"):
    """A project whose compass.yml holds `language: <yaml_value>`. A JSON
    string is a valid YAML double-quoted string."""
    return _project(tmp_path, f"schema: 1\nlanguage: {yaml_value}\n", name=name)


def _quoted(text):
    return json.dumps(text)


def _lint(root):
    return _run(root, "policy", "lint")


def _finding_lines(out):
    return [ln for ln in out.splitlines() if ln.lstrip().startswith("- ")]


def _sentence(out):
    """The text of the one language finding, after its `language: ` prefix."""
    lines = [ln for ln in _finding_lines(out) if "language:" in ln]
    assert len(lines) == 1, out
    return lines[0].split("language: ", 1)[1]


def test_trc_001(tmp_path):
    assert len(REFUSED) == 17 and "en_US" in REFUSED
    for i, value in enumerate(REFUSED):
        root = _with_language(tmp_path, _quoted(value), name=f"p{i}")
        code, out = _lint(root)
        assert code != 0, (value, out)
        assert len(_finding_lines(out)) == 1, (value, out)
        assert "[project]" in out and "language" in out, (value, out)
        assert SENTENCE_START in _sentence(out), (value, out)
    assert "Did you mean `en-US`?" in _sentence(_lint(_with_language(tmp_path, '"en_US"',
                                                                      name="again"))[1])
    # compass ci runs the same lint on every issue's configuration.
    ci_root, _task = issue_project(tmp_path / "ci", "compass:default@6")
    (ci_root / "compass.yml").write_text(
        'schema: 1\nextends: compass:default@6\nlanguage: "en_US"\n', encoding="utf-8")
    code, out = _run(ci_root, "ci")
    assert code != 0 and SENTENCE_START in out, out


def test_trc_002(tmp_path):
    code, out = _lint(_with_language(tmp_path, '"en_US"'))
    assert code != 0
    text = _sentence(out)
    assert len(text.split()) < 60, text
    for part in (SENTENCE_START, "`en_US`", "a language, an optional script and an "
                 "optional region, joined by hyphens", "`en-US`", "`de`", "`zh-Hans`", GUIDE):
        assert part in text, (part, text)


@pytest.mark.parametrize("yaml_value", ["5", "true", "no", "[en-US]", "{tag: en-US}",
                                        "2026-10-19"])
def test_trc_003(tmp_path, yaml_value):
    code, out = _lint(_with_language(tmp_path, yaml_value))
    assert code != 0, out
    text = _sentence(out)
    assert "must be text such as `en-US`" in text, text
    assert len(text.split()) < 60, text
    assert ("Norwegian is `nb`" in text) == (yaml_value == "no"), text


def test_trc_004(tmp_path):
    for value in ('""', '"   "'):
        code, out = _lint(_with_language(tmp_path, value, name="blank" + str(len(value))))
        assert code != 0, out
        assert "is empty" in _sentence(out), out
    for name, text in (("null", "schema: 1\nlanguage: null\n"),
                       ("bare", "schema: 1\nlanguage:\n"),
                       ("absent", "schema: 1\n")):
        code, out = _lint(_project(tmp_path, text, name=name))
        assert code == 0, (name, out)
        assert "language" not in out, (name, out)


def test_trc_005(tmp_path):
    value = "a" * 100_000
    root = _with_language(tmp_path, _quoted(value))
    started = time.monotonic()
    code, out = _lint(root)
    took = time.monotonic() - started
    assert code != 0, out
    text = _sentence(out)
    assert len(text.split()) < 60, text
    assert "a" * 20 + "..." in text and "a" * 21 not in text, text
    # The lint itself is fast; the rest of the 2 seconds is the process start.
    assert took < 2 + 8, took
    started = time.monotonic()
    assert language.problem(value) is not None
    assert time.monotonic() - started < 2


def test_trc_006(tmp_path):
    root = _project(tmp_path, "schema: 1\nlanguage: en-US\nlanguage: de\n")
    code, out = _lint(root)
    assert code != 0, out
    assert "language" in out and "duplicate" in out.lower(), out
    assert "is not a language tag" not in out and SENTENCE_START not in out, out


@pytest.mark.parametrize("written,expected", [
    ("en-US", "en-US"), ("EN-us", "en-US"), ("en-us", "en-US"), ("zh-hans", "zh-Hans"),
    (" en-US ", "en-US"), ("de", "de"), ("fil", "fil"), ("es-419", "es-419"),
    ("en-Latn-US", "en-Latn-US")])
def test_trc_007(tmp_path, written, expected):
    root = _with_language(tmp_path, _quoted(written))
    before = (root / "compass.yml").read_bytes()
    code, out = _lint(root)
    assert code == 0, out
    assert "language" not in out, out
    assert language.canonical(written) == expected
    assert (root / "compass.yml").read_bytes() == before


def _documented_tags():
    """The tags in the language table of the configuration guide."""
    import re

    text = (ROOT / GUIDE).read_text(encoding="utf-8")
    section = re.search(r"^### `language`\n(.*?)(?=^#{1,3} |\Z)", text,
                        flags=re.M | re.S).group(1)
    rows = re.findall(r"^\| ([^|]+?) \| `([^`]+)` \|$", section, flags=re.M)
    return [tag for name, tag in rows if name != "Language"]


def _rejected(tags):
    return [tag for tag in tags if language.canonical(tag) is None]


def test_trc_008():
    tags = _documented_tags()
    assert len(tags) == 39
    assert _rejected(tags) == []
    # A planted row with the wrong separator makes the check fail.
    assert _rejected(tags + ["en_US"]) == ["en_US"]


def test_trc_009(tmp_path, monkeypatch):
    def no_socket(*args, **kwargs):
        raise AssertionError("a network socket was opened")

    monkeypatch.setattr(socket, "socket", no_socket)
    assert catalogue_check.check_layer({"schema": 1, "language": "xx-ZZ"}, "project") == []
    assert language.canonical("xx-ZZ") == "xx-ZZ"
    monkeypatch.undo()
    code, out = _lint(_with_language(tmp_path, '"xx-ZZ"'))
    assert code == 0 and "language" not in out, out


def test_trc_010(tmp_path):
    only_old = _project(tmp_path, None, old="language: de\n", name="old")
    code, out = _lint(only_old)
    assert code == 0, out
    assert project_settings.settings(str(only_old)).get("language") == "de"
    both = _project(tmp_path, "schema: 1\n", old="language: de\n", name="both")
    # The lint reads compass.yml only; the commands that read the settings
    # name the conflict, as they do for any key left in the old file.
    code, out = _run(both, "approach", "evaluate", "--offline", "--assessment", "risk=low",
                     "--assessment", "familiarity=high", "--assessment", "size=small",
                     "--assessment", "goal=deliver")
    assert code != 0, out
    assert "settings-conflict" in out and "sets language," in out, out
    assert project_settings.settings_conflict(str(both)) == ["language"]


def test_trc_067(tmp_path):
    bad = _with_language(tmp_path, '"en_US"', name="bad")
    good = _project(tmp_path, "schema: 1\n", name="none")
    code, out = _lint(bad)
    assert code == 1 and SENTENCE_START in out, out
    sentence = _sentence(out)
    code, out = _run(bad, "approach", "evaluate", "--offline", "--assessment", "risk=low",
                     "--assessment", "familiarity=high", "--assessment", "size=small",
                     "--assessment", "goal=deliver")
    assert code == 2 and sentence in out, out
    ci_root, _task = issue_project(tmp_path / "ci", "compass:default@6")
    (ci_root / "compass.yml").write_text(
        'schema: 1\nextends: compass:default@6\nlanguage: "en_US"\n', encoding="utf-8")
    code, out = _run(ci_root, "ci")
    assert code != 0 and sentence in out, out
    # compass next gives the same exit code as a project with no language key.
    assert _run(bad, "next")[0] == _run(good, "next")[0]
    # The session-start hook exits 0 and adds no language line.
    done = subprocess.run(
        ["bash", str(HOOK)], input=json.dumps({"hook_event_name": "SessionStart",
                                               "source": "startup", "cwd": str(bad)}),
        capture_output=True, text=True, env=_env(), cwd=str(bad), timeout=60)
    assert done.returncode == 0, done.stderr
    assert "Write all prose in" not in done.stdout
