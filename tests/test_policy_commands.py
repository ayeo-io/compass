"""`compass policy lint` and `compass policy show` over the fixed check set
(ADR-094).

`policy lint` lints `compass.yml` as a file of settings, and `policy show`
names the check set, its sha256, the sha256 of `compass.yml` and the
tighten-only settings it applies. These tests run the real CLI in a scratch
project. They keep the guarantees the 8.x layered lint and view gave that
still hold: the exit codes, one line per finding, the JSON shape, no absolute
path in a finding, and a file that cannot be parsed reported as a finding, not
a traceback. `tests/test_settings_lint.py` tests the findings themselves, and
`tests/test_policy_digest.py` the issue's `policy:` block.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
CLI = ROOT / "cli" / "compass"

LINT_KEYS = ["schema", "mode", "result", "layers", "stopped_after", "counts", "findings"]
FINDING_KEYS = ["code", "level", "layer", "path", "group", "message", "detail"]
SHOW_KEYS = ["check_set", "check_set_sha256", "settings_sha256", "tightened"]


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "100", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=180)
    return r.returncode, r.stdout, r.stderr


def _project(tmp_path, compass_yml=None):
    """A scratch project root: `.compass/` makes it the root."""
    (tmp_path / ".compass").mkdir(exist_ok=True)
    if compass_yml is not None:
        (tmp_path / "compass.yml").write_text(compass_yml, encoding="utf-8")
    return tmp_path


def _lint_json(root, *argv):
    code, out, err = _run(root, "policy", "lint", "--json", *argv)
    assert "Traceback" not in err, err
    return code, json.loads(out)


def _no_absolute_path(document):
    assert str(Path("/").resolve()) + "private" not in json.dumps(document)
    for finding in document["findings"]:
        assert not finding["path"].startswith("/"), finding
        assert "/tmp" not in finding["message"] and "/private" not in finding["message"], finding


# --- policy lint: text output and exit codes ----------------------------------------

def test_a_fault_prints_fail_and_one_line_each_and_exits_1(tmp_path):
    root = _project(tmp_path, "schema: 1\nautonomy: sometimes\nfoo: 1\n")
    code, out, _ = _run(root, "policy", "lint")
    lines = out.splitlines()
    assert code == 1
    assert lines[0] == "compass policy lint: FAIL"
    assert len(lines) == 3, out
    assert sorted(line.split(" [project] ")[1].split(":")[0] for line in lines[1:]) == [
        "autonomy", "foo"]
    assert all(line.startswith("  - L-SETTING-") for line in lines[1:]), out


def test_a_warning_is_printed_and_never_fails(tmp_path):
    root = _project(tmp_path, "schema: 1\nchecks: {}\n")
    code, out, _ = _run(root, "policy", "lint")
    lines = out.splitlines()
    assert code == 0
    assert lines[0] == "compass policy lint: PASS"
    assert lines[1].startswith("  - warning L-SETTING-REMOVED [project] checks: ")


def test_file_lints_one_compass_yml_over_the_check_set(tmp_path):
    bad = tmp_path / "other.yml"
    bad.write_text("schema: 1\nautonomy: sometimes\n", encoding="utf-8")
    code, out, _ = _run(tmp_path, "policy", "lint", "--file", str(bad))
    assert code == 1 and "L-SETTING-INVALID [project] autonomy" in out
    good = tmp_path / "good.yml"
    good.write_text("schema: 1\nsignoff_labels: [billing]\n", encoding="utf-8")
    assert _run(tmp_path, "policy", "lint", "--file", str(good))[0] == 0


def test_a_file_that_is_not_there_exits_2(tmp_path):
    code, _, err = _run(tmp_path, "policy", "lint", "--file", str(tmp_path / "none.yml"))
    assert code == 2
    assert "no such file" in err


def test_a_yaml_error_is_one_line_in_the_text_output(tmp_path):
    root = _project(tmp_path, "a: [1, 2\nb: 3\n")
    code, out, err = _run(root, "policy", "lint")
    assert "Traceback" not in err, err
    assert code == 1
    assert len(out.splitlines()) == 2, out
    assert out.splitlines()[1].startswith(
        "  - L-SETTING-INVALID [project] compass.yml: cannot be read: compass.yml:")


def test_a_non_text_key_in_a_setting_is_a_finding_not_a_traceback(tmp_path):
    code, document = _lint_json(_project(tmp_path, "schema: 1\napprovers:\n  2: [a]\n"))
    assert code == 1
    (finding,) = document["findings"]
    assert (finding["code"], finding["level"], finding["path"]) == (
        "L-SETTING-INVALID", "error", "approvers.2")


# --- policy lint --json -------------------------------------------------------------

def test_a_passing_project_has_the_pinned_envelope(tmp_path):
    code, document = _lint_json(_project(tmp_path, "schema: 1\n"))
    assert code == 0
    assert list(document) == LINT_KEYS
    assert (document["schema"], document["mode"], document["result"]) == (
        1, "settings", "pass")
    assert document["layers"] == [{"name": "project", "kind": "project"}]
    assert document["stopped_after"] is None
    assert document["counts"] == {"errors": 0, "warnings": 0}
    assert document["findings"] == []


def test_each_finding_has_the_pinned_keys_in_order(tmp_path):
    code, document = _lint_json(_project(tmp_path, "schema: 1\nautonomy: sometimes\n"))
    assert code == 1
    assert document["result"] == "fail"
    assert document["counts"] == {"errors": 1, "warnings": 0}
    (finding,) = document["findings"]
    assert list(finding) == FINDING_KEYS
    assert (finding["code"], finding["level"], finding["layer"], finding["path"],
            finding["group"], finding["detail"]) == (
        "L-SETTING-INVALID", "error", "project", "autonomy", "settings", None)
    assert isinstance(finding["message"], str) and finding["message"]


def test_a_load_finding_names_the_file_from_the_project_root(tmp_path):
    code, document = _lint_json(_project(tmp_path, "schema: 1\nowner: a\nowner: b\n"))
    assert code == 1
    _no_absolute_path(document)
    (finding,) = document["findings"]
    assert finding["path"] == "compass.yml"
    assert finding["message"].startswith("cannot be read: compass.yml:3: duplicate key")


def test_a_file_outside_the_project_is_named_by_its_basename(tmp_path):
    bad = tmp_path / "other.yml"
    bad.write_text("schema: 1\nowner: a\nowner: b\n", encoding="utf-8")
    elsewhere = tmp_path / "work"
    elsewhere.mkdir()
    code, document = _lint_json(_project(elsewhere), "--file", str(bad))
    _no_absolute_path(document)
    (finding,) = document["findings"]
    assert finding["path"] == "other.yml"
    assert finding["message"].startswith("cannot be read: other.yml:3: duplicate key")


def test_a_file_inside_the_project_is_named_from_its_root(tmp_path):
    root = _project(tmp_path)
    (root / "sub").mkdir()
    (root / "sub" / "x.yml").write_text("a: [1\n", encoding="utf-8")
    code, document = _lint_json(root, "--file", str(root / "sub" / "x.yml"))
    _no_absolute_path(document)
    assert document["findings"][0]["path"] == "sub/x.yml"


# --- policy show ------------------------------------------------------------------------

def _sha256(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_show_names_the_check_set_its_digest_and_the_settings(tmp_path):
    from compass_pkg import check_set
    root = _project(tmp_path, "schema: 1\nsignoff_labels: [billing]\n")
    code, out, _ = _run(root, "policy", "show")
    assert code == 0, out
    lines = out.splitlines()
    assert lines[0] == f"Policy: {check_set.ref()} (sha256 {check_set.sha256()})"
    assert lines[1] == f"Settings: compass.yml (sha256 {_sha256(root / 'compass.yml')})"
    assert lines[2:] == ["Tightened:", '  signoff_labels: ["billing"]']


def test_show_without_a_compass_yml_says_so(tmp_path):
    code, out, _ = _run(_project(tmp_path), "policy", "show")
    assert code == 0, out
    assert out.splitlines()[1:] == ["Settings: no compass.yml", "Tightened: nothing"]


def test_show_json_has_the_pinned_keys(tmp_path):
    root = _project(tmp_path, "schema: 1\nagent_review: on\n")
    code, out, _ = _run(root, "policy", "show", "--json")
    assert code == 0, out
    document = json.loads(out)
    assert list(document) == SHOW_KEYS
    assert document["settings_sha256"] == _sha256(root / "compass.yml")
    assert document["tightened"] == {"agent_review": True}


def test_show_refuses_a_file_that_cannot_be_read(tmp_path):
    code, out, err = _run(_project(tmp_path, "schema: 1\nowner: a\nowner: b\n"),
                          "policy", "show", "--json")
    assert "Traceback" not in err, err
    assert code == 2
    assert out.strip() == ""
    assert "duplicate key" in err


# --- help and the owning doc ---------------------------------------------------------

def test_both_verbs_describe_themselves(tmp_path):
    root = _project(tmp_path)
    out = _run(root, "policy", "show", "--help")[1]
    assert "check set" in out and "--issue" in out and "--json" in out
    assert "COMPASS_ISSUE" in out and "current-task" in out
    out = _run(root, "policy", "lint", "--help")[1]
    for option in ("--file", "--json"):
        assert option in out
    for removed in ("--exhaustive", "--issue", "--offline"):
        assert removed not in out


def test_the_owning_doc_documents_the_json_shape_and_every_code():
    from compass_pkg import settings_lint
    text = (ROOT / "docs" / "policy-lint.md").read_text(encoding="utf-8")
    for key in LINT_KEYS + FINDING_KEYS + SHOW_KEYS:
        assert f"`{key}`" in text, key
    for code in settings_lint.CODES:
        assert f"`{code}`" in text, code


@pytest.mark.parametrize("argv", [("policy", "lint", "--offline"),
                                  ("policy", "lint", "--exhaustive"),
                                  ("policy", "lint", "--issue", "demo")])
def test_a_removed_flag_fails_to_parse_and_names_the_adr(tmp_path, argv):
    code, _, err = _run(_project(tmp_path), *argv)
    assert code == 2
    assert "ADR-094" in err
