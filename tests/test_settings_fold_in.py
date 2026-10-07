"""Every Python reader of project settings goes through one module.

`cli/compass_pkg/project_settings.py` reads the settings keys from
`compass.yml` at the project root when it exists, and from
`.compass/config.yml` otherwise. CLI-written state (`initialised`,
`records_signed_since`) comes from the state file in `.compass/`, falling back to
`.compass/config.yml` (ADR-043). A reader that still opens the old file
itself would ignore `compass.yml`, so this test fails for it.

Scenario ids: SR-1 to SR-5, in the acceptance criteria of the issue
`settings-reader-python`; SH-4 and SH-6, in those of `settings-reader-hook`.
"""
from __future__ import annotations

import ast
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import compat_hook
from settings_helpers import (GLOBS, SETTINGS, hook_edit, make_project,
                              make_repo, run_script)

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import core, governance, project_settings, record  # noqa: E402
from compass_pkg import red_first  # noqa: E402
from compass_pkg.project_commands import _project_commands_allowed  # noqa: E402
from compass_pkg.tdd import _read_config  # noqa: E402

# One settings document, written as `.compass/config.yml` (adoption is `mode`)
# or as `compass.yml` (adoption is `adoption`).
BODY = """\
autonomy: autonomous
governance_drift: strict
allow_project_commands: true
project:
  name: demo
  test_command: make test
record:
  remote: ../rec
  paths: [docs]
prices:
  opus: {input: 1, output: 2}
"""

FILES = ("config", "compass")


def _write(root, kind, text=BODY, adoption="advisory"):
    """Write the settings in the named file, with the adoption setting under
    the key that file uses."""
    (root / ".compass" / "work").mkdir(parents=True, exist_ok=True)
    if kind == "config":
        (root / ".compass" / "config.yml").write_text(
            f"mode: {adoption}\n{text}")
    else:
        (root / "compass.yml").write_text(f"adoption: {adoption}\n{text}")


@pytest.fixture
def root(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".compass").mkdir()
    monkeypatch.chdir(proj)
    return proj


# SR-1: each reader gets the same value from `compass.yml` or `.compass/config.yml`.

@pytest.mark.parametrize("kind", FILES)
def test_sr1_adoption_mode(root, kind):
    _write(root, kind)
    assert core.load_mode() == "advisory"


@pytest.mark.parametrize("kind", FILES)
def test_sr1_autonomy(root, kind):
    _write(root, kind)
    assert core.load_autonomy() == "autonomous"


@pytest.mark.parametrize("kind", FILES)
def test_sr1_drift_strictness(root, kind):
    _write(root, kind)
    assert governance._drift_is_strict() is True


@pytest.mark.parametrize("kind", FILES)
def test_sr1_record_settings(root, kind):
    _write(root, kind)
    assert record.settings(root) == ("../rec", ["docs"])


@pytest.mark.parametrize("kind", FILES)
def test_sr1_record_names_key(root, kind):
    _write(root, kind, BODY.replace("paths: [docs]",
                                    "paths: [docs]\n  names_key: k.yml"))
    (root / "k.yml").write_text("R1: x\n")
    assert record.names_key(root) == str(root / "k.yml")


@pytest.mark.parametrize("kind", FILES)
def test_sr1_project_settings_and_opt_in(root, kind):
    _write(root, kind)
    cfg = _read_config(str(root / ".compass" / "work"))
    assert cfg["project"] == {"name": "demo", "test_command": "make test"}
    assert _project_commands_allowed(str(root / ".compass" / "work")) is True


@pytest.mark.parametrize("kind", FILES)
def test_sr1_prices(root, kind):
    _write(root, kind)
    assert project_settings.settings(str(root))["prices"] == {
        "opus": {"input": 1, "output": 2}}


@pytest.mark.parametrize("kind", FILES)
def test_sr1_adoption_key_is_the_same_in_both(root, kind):
    _write(root, kind)
    assert project_settings.settings(str(root))["adoption"] == "advisory"


def test_sr1_signed_cutoff_from_state_then_old_file(root):
    work = str(root / ".compass" / "work")
    (root / ".compass" / "config.yml").write_text(
        "records_signed_since: '2026-01-02'\n")
    assert red_first.signed_since(work) == datetime.date(2026, 1, 2)
    (root / ".compass" / "state.yml").write_text(
        "records_signed_since: '2026-03-04'\n")
    assert red_first.signed_since(work) == datetime.date(2026, 3, 4)


# SR-2: a missing or broken settings file behaves as it did at 5.6.0, and advice
# names the file actually read.

BROKEN = "key: [unclosed\n"


def _break(root, kind):
    (root / ".compass" / "work").mkdir(parents=True, exist_ok=True)
    path = (root / ".compass" / "config.yml" if kind == "config"
            else root / "compass.yml")
    path.write_text(BROKEN)


def test_sr2_missing_file_defaults(root):
    work = str(root / ".compass" / "work")
    assert core.load_mode() == "enforced"
    assert core.load_autonomy() == "balanced"
    assert governance._drift_is_strict() is False
    assert record.settings(root) is None
    assert _read_config(work) == {}
    assert _project_commands_allowed(work) is False
    assert red_first.signed_since(work) is None


@pytest.mark.parametrize("kind", FILES)
def test_sr2_broken_file_per_reader(root, kind):
    _break(root, kind)
    work = str(root / ".compass" / "work")
    assert core.load_mode() == "enforced"
    with pytest.raises(core.CompassError):
        core.load_autonomy()
    assert governance._drift_is_strict() is False
    with pytest.raises(core.CompassError):
        record.settings(root)
    assert _read_config(work) == {}
    assert _project_commands_allowed(work) is False


def test_sr2_broken_state_is_a_far_past_cutoff(root):
    (root / ".compass" / "state.yml").write_text(BROKEN)
    assert red_first.signed_since(
        str(root / ".compass" / "work")) == datetime.date.min


def test_sr2_broken_old_file_is_a_far_past_cutoff(root):
    (root / ".compass" / "config.yml").write_text(BROKEN)
    assert red_first.signed_since(
        str(root / ".compass" / "work")) == datetime.date.min


def test_sr2_duplicate_key_in_compass_yml_is_broken(root):
    (root / "compass.yml").write_text("autonomy: balanced\nautonomy: controlled\n")
    with pytest.raises(core.CompassError):
        core.load_autonomy()
    assert core.load_mode() == "enforced"


def test_sr2_unknown_autonomy_names_the_file_read(root):
    (root / "compass.yml").write_text("autonomy: sometimes\n")
    with pytest.raises(core.CompassError, match="compass.yml"):
        core.load_autonomy()
    (root / "compass.yml").unlink()
    (root / ".compass" / "config.yml").write_text("autonomy: sometimes\n")
    with pytest.raises(core.CompassError, match=r"\.compass/config\.yml"):
        core.load_autonomy()


def test_sr2_compass_yml_is_read_when_both_exist_and_the_old_file_has_only_state(
        root):
    # `schema:` makes it Compass's file, so it is the one read. A setting left
    # in the old file would be a conflict, so the old file holds state only.
    (root / ".compass" / "config.yml").write_text(
        "records_signed_since: '2026-09-24'\n")
    (root / "compass.yml").write_text("schema: 1\nadoption: advisory\n")
    assert core.load_mode() == "advisory"


# SR-3: `compass init` writes the state file and no settings.

def test_sr3_init_writes_state_and_no_settings_file(tmp_path):
    proj = tmp_path / "fresh"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    subprocess.run([sys.executable, str(CLI), "init"], cwd=proj, env=env,
                   check=True, capture_output=True)
    state = (proj / ".compass" / "state.yml").read_text()
    assert "initialised:" in state and "records_signed_since:" in state
    assert not (proj / "compass.yml").exists()
    # The hook reads `initialised` through project_settings, so init no longer
    # writes the interim `.compass/config.yml` that held it.
    assert not (proj / ".compass" / "config.yml").exists()
    # The cutoff reads from the state file.
    assert red_first.signed_since(str(proj / ".compass" / "work")) \
        == datetime.date.today()
    assert project_settings.state(str(proj))["initialised"]["by"] \
        == "compass init"


def test_sr3_hook_explanation_still_reads_from_a_new_project(tmp_path):
    proj = tmp_path / "fresh"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    subprocess.run([sys.executable, str(CLI), "init"], cwd=proj, env=env,
                   check=True, capture_output=True)
    import json
    payload = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": str(proj / "app.py"), "content": "x = 1\n"},
        "cwd": str(proj)})
    out = subprocess.run(["bash", str(ROOT / "hooks" / "pre-tool.sh")],
                         input=payload, text=True, capture_output=True,
                         env=env, cwd=proj)
    assert "initialised by compass init" in out.stderr, out.stderr


# SR-4: no reader is left on the old file.

def _joined(node):
    """The text of a string constant, an f-string's constant parts joined, or
    a `+` of those; None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "\0"
                       for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _joined(node.left), _joined(node.right)
        if left is not None or right is not None:
            return (left or "\0") + (right or "\0")
    return None


def _names_old_file(source):
    """Whether `source` names `.compass/config.yml`: a string, an f-string or a
    concatenation that equals or ends with it, or the bare `config.yml` as an
    argument of a path join."""
    for node in ast.walk(ast.parse(source)):
        text = _joined(node)
        if text is None:
            continue
        if text == "config.yml" or text.endswith(".compass/config.yml"):
            return True
    return False


PLANTED_FORMS = {
    "a path join": "import os\nx = os.path.join(d, 'config.yml')\n",
    "a whole string": "x = d + '/.compass/config.yml'\n",
    "a message ending with it": "x = 'set it in .compass/config.yml'\n",
    "an f-string": "x = f'{d}/.compass/config.yml'\n",
    "a concatenation": "x = d + '/.compass' + '/config.yml'\n",
    "a nested concatenation": "x = '.compass' + '/' + 'config.yml'\n",
}


@pytest.mark.parametrize("form", sorted(PLANTED_FORMS))
def test_sr4_the_scan_flags_each_planted_form(form):
    assert _names_old_file(PLANTED_FORMS[form]), form


def test_sr4_the_scan_passes_unrelated_code():
    assert not _names_old_file("def f():\n    return 'ok'\n")
    assert not _names_old_file("x = 'the .compass/config.yml file is read'\n")


def test_sr4_only_project_settings_names_the_old_file():
    offenders = []
    for path in sorted((ROOT / "cli").rglob("*.py")):
        if "vendor" in path.parts or path.name == "project_settings.py":
            continue
        if _names_old_file(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    cli_text = (ROOT / "cli" / "compass").read_text(encoding="utf-8")
    assert not offenders, offenders
    assert not _names_old_file(cli_text)


class _OldFileSettings:
    """`project_settings` with its `settings` replaced by a reader that opens
    `.compass/config.yml` itself, as a reader that was never moved would."""

    @staticmethod
    def settings(project_root):
        import yaml
        path = os.path.join(project_root, ".compass", "config.yml")
        if not os.path.isfile(path):
            return {}
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}


def _names_key_check(root, kind):
    """The SR-1 check for `record.names_key`, as a callable."""
    for stale in (root / "compass.yml", root / ".compass" / "config.yml"):
        stale.unlink(missing_ok=True)
    _write(root, kind, BODY.replace("paths: [docs]",
                                    "paths: [docs]\n  names_key: k.yml"))
    (root / "k.yml").write_text("R1: x\n")
    assert record.names_key(root) == str(root / "k.yml")


def test_sr4_a_reader_left_on_the_old_file_fails_the_sr1_check(root, monkeypatch):
    """Plant a reader on the old file: the check passes on the old file and
    fails on `compass.yml`, which that reader never opens."""
    monkeypatch.setattr(record, "project_settings", _OldFileSettings)
    _names_key_check(root, "config")
    with pytest.raises(AssertionError):
        _names_key_check(root, "compass")


# SR-1 and SR-2: the old file reads only `mode`, and advice names the file read.

def test_sr2_the_old_file_ignores_an_adoption_key(root):
    (root / ".compass" / "config.yml").write_text("adoption: advisory\n")
    assert core.load_mode() == "enforced"
    (root / ".compass" / "config.yml").write_text("mode: advisory\n")
    assert core.load_mode() == "advisory"


def test_sr2_advice_names_the_file_and_key_actually_read(root):
    (root / ".compass" / "config.yml").write_text("mode: advisory\n")
    assert "`mode: enforced` in .compass/config.yml" in core.mode_banner(
        "advisory")
    (root / ".compass" / "config.yml").unlink()
    (root / "compass.yml").write_text("record: {remote: ''}\n")
    assert "`adoption: enforced` in compass.yml" in core.mode_banner("advisory")
    with pytest.raises(core.CompassError, match="`record:` in compass.yml"):
        record.settings(root)


# SH-4: `compass init` writes the state file only, and leaves an old project
# alone.

def _init(proj):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    return subprocess.run([sys.executable, str(CLI), "init"], cwd=proj,
                          env=env, check=True, capture_output=True, text=True)


def _hook_says_initialised_by(proj, who):
    import json
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj)}
    payload = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": str(proj / "app.py"), "content": "x = 1\n"},
        "cwd": str(proj)})
    out = subprocess.run(["bash", str(ROOT / "hooks" / "pre-tool.sh")],
                         input=payload, text=True, capture_output=True,
                         env=env, cwd=proj)
    return f"initialised by {who}" in out.stderr, out.stderr


def test_sh4_init_writes_no_old_settings_file_in_a_new_project(tmp_path):
    proj = tmp_path / "fresh"
    proj.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    _init(proj)
    assert sorted(p.name for p in (proj / ".compass").iterdir()) == \
        ["state.yml", "work"]
    assert _hook_says_initialised_by(proj, "compass init")[0]


@pytest.mark.parametrize("old", [
    "mode: advisory\nautonomy: autonomous\ninitialised:\n  by: older\n  at: '2026-01-01'\n",
    "initialised:\n  by: older\n  at: '2026-01-01'\n",
])
def test_sh4_an_old_project_is_left_as_it_is(tmp_path, old):
    proj = tmp_path / "old"
    (proj / ".compass").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    (proj / ".compass" / "config.yml").write_text(old)
    _init(proj)
    assert (proj / ".compass" / "config.yml").read_text() == old
    assert not (proj / ".compass" / "state.yml").exists()
    assert _hook_says_initialised_by(proj, "older")[0]


# SH-6: the hook and the two scripts do not read the old file themselves.

#: The one shell file that names the settings files, so the hook can tell
#: whether any exists before it starts Python (SH-10). It only tests that a
#: file exists, and a test below pins its two names to `project_settings`.
SETTINGS_FILES_HELPER = ROOT / "scripts" / "lib" / "settings-files.sh"

SHELL_READERS = [p for p in (
    sorted((ROOT / "hooks").glob("*.sh"))
    + [ROOT / "scripts" / "integrate.sh", ROOT / "scripts" / "multiagent.sh"]
    + sorted((ROOT / "scripts" / "lib").glob("*.sh")))
    if p != SETTINGS_FILES_HELPER]


def _shell_names_old_file(source):
    """Whether shell source (or the Python inside its heredocs) names the old
    settings file in a line that is not a comment.

    A line is flattened first - quotes, backslashes, `$`, braces, `+`,
    parentheses and spaces removed - so `'.compass' + '/config.yml'`,
    `"$DIR/config"".yml"` and an f-string all read as the name they build. A
    quoted piece that is only the stem or only the extension is refused too:
    it is the half of a name built in two steps.
    """
    for line in source.splitlines():
        if line.lstrip().startswith("#"):
            continue
        flat = re.sub(r"""["'\\${}+\s()]""", "", line)
        if re.search(r"config\.?y(a)?ml|\.compass/config", flat, re.I):
            return True
        if re.search(r"""["']config\.?["']|["']\.?ya?ml["']""", line):
            return True
    return False


SHELL_PLANTED_FORMS = {
    "a whole path": 'CFG="$PROJECT_DIR/.compass/config.yml"\n',
    "a directory variable": 'f="$COMPASS_DIR/config.yml"\n',
    "a split string": "f=\"$d/config\"'.yml'\n",
    "a python concatenation": "p = d + '/.compass' + '/' + 'config' + '.yml'\n",
    "a python path join": "p = os.path.join(d, '.compass', 'config.yml')\n",
    "a stem built in a variable": "name='config'\nf=\"$d/${name}.suffix\"\n",
    "an extension built in a variable": "ext='.yml'\nf=\"$d/$stem$ext\"\n",
    "a yaml spelling": 'f="$d/config.yaml"\n',
    "a line with a trailing comment": 'f=".compass/config.yml" # read it\n',
}


@pytest.mark.parametrize("form", sorted(SHELL_PLANTED_FORMS))
def test_sh6_the_shell_scan_flags_each_planted_form(form):
    assert _shell_names_old_file(SHELL_PLANTED_FORMS[form]), form


def test_sh6_the_shell_scan_passes_comments_and_unrelated_code():
    assert not _shell_names_old_file(
        "# the old .compass/config.yml is read by project_settings\n"
        "echo \"configure the project\"\n"
        "compass_setting \"$PROJECT_DIR\" test_command ''\n")


def test_sh6_the_hook_and_the_scripts_name_no_settings_file():
    offenders = [str(p.relative_to(ROOT)) for p in SHELL_READERS
                 if _shell_names_old_file(p.read_text(encoding="utf-8"))]
    assert not offenders, offenders
    assert len(SHELL_READERS) >= 6


def _honoured(framework, base):
    """What a copy of the hook and the scripts do with `compass.yml` alone:
    the hook blocks the glob, `multiagent.sh` takes the root and cap, and
    `integrate.sh` takes the test command. A name that is True is honoured."""
    project = make_project(base, compass_yml=GLOBS)
    hook = hook_edit(framework, base, project, "packaging/a.cfg")[0] == 2
    repo = make_repo(base, compass=SETTINGS % ("new", 3, "new"))
    out = run_script(framework, repo, "multiagent.sh", "--dry-run")
    multi = "wt-new" in out.stdout and "config max 3" in out.stdout
    out = run_script(framework, repo, "integrate.sh")
    integ = "test command:  run-new" in out.stdout
    return {"hook": hook, "multiagent": multi, "integrate": integ}


def _planted(tmp_framework, name, old, new):
    path = tmp_framework / name
    text = path.read_text(encoding="utf-8")
    assert old in text, (name, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


@pytest.fixture
def copy():
    base = Path(tempfile.mkdtemp(prefix="shf-"))
    framework = compat_hook.install(base / "framework")
    yield framework, base
    shutil.rmtree(base, ignore_errors=True)


def test_sh6_the_real_hook_and_scripts_honour_compass_yml(copy):
    framework, base = copy
    assert _honoured(framework, base) == {
        "hook": True, "multiagent": True, "integrate": True}


# The old file named by a spelling the scan cannot see (the name is assembled
# at run time from pieces no line holds whole), so only a behaviour check
# can catch it.
_HIDDEN = ('OLD="$PROJECT_DIR/.$(printf comp)ass/$(printf con)fig.$(printf y)ml"\n'
           '_read() { grep -E "^[[:space:]]*$1:" "$OLD" 2>/dev/null | head -n1 '
           '| sed -E "s/^[^:]*:[[:space:]]*//"; }\n')


def test_sh6_a_script_left_on_the_old_file_fails_the_behaviour_check(copy):
    framework, base = copy
    _planted(framework, "scripts/multiagent.sh",
             'WORKTREE_ROOT_REL="$(compass_setting "$PROJECT_DIR" worktree_root'
             " '../.compass-worktrees')\"",
             _HIDDEN + 'WORKTREE_ROOT_REL="$(_read worktree_root)"; '
             'WORKTREE_ROOT_REL="${WORKTREE_ROOT_REL:-../.compass-worktrees}"')
    assert not _shell_names_old_file(
        (framework / "scripts" / "multiagent.sh").read_text())
    assert _honoured(framework, base)["multiagent"] is False


def test_sh6_the_other_script_left_on_the_old_file_fails_too(copy):
    framework, base = copy
    _planted(framework, "scripts/integrate.sh",
             'TEST_CMD="$(compass_setting "$PROJECT_DIR" test_command \'\')"',
             _HIDDEN + 'TEST_CMD="$(_read test_command)"')
    assert _honoured(framework, base)["integrate"] is False


def test_sh6_a_hook_left_on_the_old_file_fails_the_behaviour_check(copy):
    framework, base = copy
    _planted(framework, "hooks/pre-tool.sh",
             "cfg = project_settings.settings(sys.argv[1])",
             "import os, yaml\n"
             "    p = os.path.join(sys.argv[1], '.compass',\n"
             "                     ''.join(['con', 'fig', '.', 'y', 'ml']))\n"
             "    cfg = (yaml.safe_load(open(p)) or {}) if os.path.exists(p) else {}")
    assert not _shell_names_old_file(
        (framework / "hooks" / "pre-tool.sh").read_text())
    assert _honoured(framework, base)["hook"] is False


def test_sh6_the_scan_flags_a_hook_that_names_the_old_file_plainly(copy):
    framework, _base = copy
    _planted(framework, "hooks/pre-tool.sh",
             "cfg = project_settings.settings(sys.argv[1])",
             "cfg = open(sys.argv[1] + '/.compass/config.yml').read()")
    assert _shell_names_old_file(
        (framework / "hooks" / "pre-tool.sh").read_text())


# SH-10: the helper that names the two settings files is pinned to
# `project_settings`.

def _helper_names(text):
    """The paths the helper tests with `[ -f "$1/<path>" ]`, and any other
    non-comment line that is neither the function line, its closing brace nor
    such a test."""
    names, other = [], []
    for line in text.splitlines():
        stripped = line.strip().rstrip("|").strip()
        found = re.fullmatch(r'\[ -f "\$1/([^"]+)" \]', stripped)
        if found:
            names.append(found.group(1))
        elif (stripped and not stripped.startswith("#")
              and stripped not in ("}",)
              and not stripped.startswith("compass_has_settings_file()")):
            other.append(line)
    return names, other


def test_sh10_the_helper_names_exactly_the_files_project_settings_reads():
    assert SETTINGS_FILES_HELPER.is_file(), "the helper does not exist"
    names, other = _helper_names(
        SETTINGS_FILES_HELPER.read_text(encoding="utf-8"))
    assert sorted(names) == sorted([project_settings.COMPASS_YML,
                                    project_settings.OLD_CONFIG])
    assert not other, other


@pytest.mark.parametrize("planted", [
    'compass_has_settings_file() {\n  [ -f "$1/compass.yml" ]\n}\n',
    'compass_has_settings_file() {\n  [ -f "$1/compass.yml" ] || [ -f "$1/.compass/config.yaml" ]\n}\n',
    'compass_has_settings_file() {\n  [ -f "$1/compass.yml" ] || [ -f "$1/.compass/config.yml" ]\n'
    '  grep -q x "$1/.compass/config.yml"\n}\n',
])
def test_sh10_the_pin_fails_for_a_helper_that_drifts(planted):
    names, other = _helper_names(planted)
    assert (sorted(names) != sorted([project_settings.COMPASS_YML,
                                     project_settings.OLD_CONFIG])
            or other)
