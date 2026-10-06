"""Every Python reader of project settings goes through one module.

`cli/compass_pkg/project_settings.py` reads the settings keys from
`compass.yml` at the project root when it exists, and from
`.compass/config.yml` otherwise. CLI-written state (`initialised`,
`records_signed_since`) comes from the state file in `.compass/`, falling back to
`.compass/config.yml` (ADR-043). A reader that still opens the old file
itself would ignore `compass.yml`, so this test fails for it.

Scenario ids: SR-1 to SR-5, in the acceptance criteria of the issue
`settings-reader-python`.
"""
from __future__ import annotations

import ast
import datetime
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_sr2_compass_yml_wins_when_both_exist(root):
    (root / ".compass" / "config.yml").write_text("mode: advisory\n")
    (root / "compass.yml").write_text("adoption: enforced\n")
    assert core.load_mode() == "enforced"


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
    # The hook still reads `initialised` from the old file, so init writes
    # that one block there and no setting.
    import yaml
    old = yaml.safe_load((proj / ".compass" / "config.yml").read_text())
    assert set(old) == {"initialised"}
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
