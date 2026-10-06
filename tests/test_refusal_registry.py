"""One registry, one shape, for every hook and CLI refusal.

Spec D38: refusals used to be hand-written at each call site, so nothing
checked them together, and each drift - a retired word, an advertised
bypass, a raw machine key - was fixed one at a time.
`cli/compass_pkg/refusals.py` is now the one place a refusal's wording
lives; `render(code, **params)` is the only thing that turns a reason code
into text, and hooks/pre-tool.sh calls it (directly, or through the private
`compass _refusal` verb) at every refusal site.

Scenario ids: RTP-1 to RTP-4, in the acceptance criteria of the issue
`refusal-template`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
HOOK = ROOT / "hooks" / "pre-tool.sh"

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.refusals import REFUSALS, codes, render          # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from test_terminology import _scan_text                          # noqa: E402

# ---------------------------------------------------------------------------
# One set of fixture parameters per code - what RTP-1 and RTP-2 render with.
# Keeping this in sync with the registry is itself checked below.
# ---------------------------------------------------------------------------
FIXTURES = {
    "python-missing": dict(target="src/app.py", tool="Edit"),
    "reader-failed": dict(target="src/app.py", tool="Edit",
                          reader="delivery-approach reader",
                          cause="It exited 1.", detail=""),
    "config-invalid": dict(
        target="packaging/app.cfg", tool="Edit", file=".compass/config.yml",
        detail="enforcement.code_globs must be a list of strings, "
               "not ['packaging/**']"),
    "not-initialised": dict(detail="no .compass/work/ exists in this project"),
    "bad-current-task": dict(slug="../side"),
    "bad-session-issue": dict(slug="missing"),
    "pointer-moved": dict(slug="why", previous="ex"),
    "no-delivery-approach": dict(slug="demo"),
    "no-acceptance-criteria": dict(target="src/app.py", tool="Edit"),
    "red-unsigned": dict(slug="demo", since_date="2026-09-01"),
    "red-marker-no-record": dict(slug="demo"),
    "no-red-on-record": dict(slug="demo", target="src/app.py", tool="Edit",
                             guard="the built-in production-code set"),
}


def test_fixtures_cover_every_registered_code():
    """A code with no fixture would sail through RTP-1/RTP-2 unchecked."""
    assert set(FIXTURES) == set(codes())


# ---------------------------------------------------------------------------
# RTP-1 - the three-line shape, the code in brackets, the vocabulary scan,
# the 60-word cap.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", sorted(FIXTURES))
def test_rtp_1_the_template_shape(code):
    text = render(code, **FIXTURES[code])
    lines = text.split("\n")
    assert len(lines) == 3, (code, text)
    assert lines[0].startswith("Blocked: "), (code, text)
    assert lines[1].startswith("Why: "), (code, text)
    assert lines[2].startswith("Fix: "), (code, text)
    assert lines[2].rstrip().endswith(f"[{code}]"), (code, text)


@pytest.mark.parametrize("code", sorted(FIXTURES))
def test_rtp_1_passes_the_vocabulary_scan(code):
    text = render(code, **FIXTURES[code])
    hits = _scan_text(text, name=f"{code}.md")
    assert not hits, (code, hits, text)


@pytest.mark.parametrize("code", sorted(FIXTURES))
def test_rtp_1_stays_under_sixty_words(code):
    text = render(code, **FIXTURES[code])
    words = len(text.split())
    assert words < 60, (code, words, text)


# ---------------------------------------------------------------------------
# RTP-2 - no Fix line advertises the unbound-green side door or a skipped
# gate.
# ---------------------------------------------------------------------------

BANNED_FIX_PHRASES = (
    "drop --scenario", "without --scenario", "remove --scenario",
    "skip --scenario", "skip the gate", "skip a gate", "bypass the",
)


@pytest.mark.parametrize("code", sorted(FIXTURES))
def test_rtp_2_no_fix_line_suggests_a_bypass(code):
    text = render(code, **FIXTURES[code])
    fix_line = text.split("\n")[2].lower()
    for phrase in BANNED_FIX_PHRASES:
        assert phrase not in fix_line, (code, fix_line, phrase)


# ---------------------------------------------------------------------------
# RTP-3 - the hook prints the registry's refusal for exactly one code per
# failure-matrix cell, and the no-python3 case is honest.
# ---------------------------------------------------------------------------

MANIFEST = """schema_version: '2.0'
issue: matrix
created: '2026-09-29'
status: active
stages: {assess: full, define: full, implement: full}
scenarios:
- id: M-1
  intent: INT-1
  tests: [t]
"""

RED_RECORD = {"command": "pytest -q", "scenario": None, "exit_code": 1,
             "passed": False, "timestamp": "2026-09-24T00:00:00+00:00",
             "record_id": "fixture0000000000"}


def _red_record():
    import hashlib
    payload = dict(RED_RECORD)
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    return payload


FAKE_PY = """#!/usr/bin/env bash
# Fails only for the reader whose script holds $FAKE_FAIL_ON.
if [ "${1:-}" = "-" ]; then
  body="$(cat)"
  if [ -n "${FAKE_FAIL_ON:-}" ] && printf '%s' "$body" | grep -qF -- "$FAKE_FAIL_ON"; then
    echo "fake python3: failing on purpose" >&2
    exit "${FAKE_EXIT:-1}"
  fi
  printf '%s\\n' "$body" | REALPY "$@"
  exit $?
fi
exec REALPY "$@"
"""

READERS = {
    "code_globs": "fnmatch.fnmatch(path, g)",
    "approach": "resolve_artifact(sys.argv[1]",
    "acceptance": 'weight = stages.get("define"',
    "red": "verdict_line(sys.argv[1]",
}


@pytest.fixture
def install():
    """A copy of the hooks, their shell helper and the CLI package, with an
    issue whose every check passes."""
    root = Path(tempfile.mkdtemp(prefix="compass-rtp-"))
    for part in ("hooks", "scripts", "cli"):
        shutil.copytree(ROOT / part, root / part,
                        ignore=shutil.ignore_patterns("__pycache__"))
    compass = root / ".compass"
    task = compass / "work" / "matrix"
    (task / "evidence").mkdir(parents=True)
    (compass / "current-task").write_text("matrix")
    (compass / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n"
        "enforcement:\n  code_globs: ['packaging/**']\n")
    (task / "manifest.yml").write_text(MANIFEST)
    (task / "delivery-approach.md").write_text("# Approach\n")
    (task / "evidence" / "red.json").write_text(json.dumps(_red_record()))
    (task / ".red").write_text("")
    fake_bin = root / "fakebin"
    fake_bin.mkdir()
    fake = fake_bin / "python3"
    fake.write_text(FAKE_PY.replace("REALPY", sys.executable))
    fake.chmod(0o755)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _target(reader):
    return "packaging/app.cfg" if reader == "code_globs" else "src/app.py"


def _hook(root, target, *, fail_on=None, status=1, path=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root),
           "PATH": path or f"{root / 'fakebin'}:{os.environ['PATH']}"}
    if fail_on:
        env["FAKE_FAIL_ON"] = READERS[fail_on]
        env["FAKE_EXIT"] = str(status)
    event = json.dumps({"tool_name": "Edit",
                        "tool_input": {"file_path": str(root / target)}})
    return subprocess.run(["bash", str(root / "hooks" / "pre-tool.sh")],
                          input=event, capture_output=True, text=True,
                          timeout=120, env=env)


@pytest.mark.parametrize("reader", sorted(READERS))
def test_rtp_3_each_failing_reader_prints_exactly_one_code(install, reader):
    result = _hook(install, _target(reader), fail_on=reader, status=1)
    assert result.returncode == 2, (result.returncode, result.stderr)
    hits = [c for c in codes() if f"[{c}]" in result.stderr]
    assert hits == ["reader-failed"], (reader, result.stderr)


def test_rtp_3_a_config_of_the_wrong_shape_prints_config_invalid(install):
    (install / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n"
        "enforcement:\n  code_globs: [1, 2]\n")
    result = _hook(install, "packaging/app.cfg")
    assert result.returncode == 2, (result.returncode, result.stderr)
    hits = [c for c in codes() if f"[{c}]" in result.stderr]
    assert hits == ["config-invalid"], result.stderr


def _no_python_path(root):
    """A PATH holding every tool in /usr/bin and /bin except python."""
    bare = root / "barebin"
    bare.mkdir(exist_ok=True)
    for d in ("/usr/bin", "/bin"):
        for name in os.listdir(d):
            if name.startswith("python") or (bare / name).exists():
                continue
            (bare / name).symlink_to(os.path.join(d, name))
    return str(bare)


@pytest.mark.parametrize("target", ["src/app.py", "packaging/app.cfg"])
def test_rtp_3_no_python3_names_python_missing_and_matches_the_registry(
        install, target):
    result = _hook(install, target, path=_no_python_path(install))
    assert result.returncode == 2, (result.returncode, result.stderr)
    expected = render("python-missing", target=str(install / target), tool="Edit")
    assert result.stderr.strip() == expected.strip(), (
        result.stderr, expected)


# ---------------------------------------------------------------------------
# RTP-4 - the generated docs page, and every code has a call site.
# ---------------------------------------------------------------------------

def test_rtp_4_docs_page_is_not_stale():
    result = subprocess.run(
        [sys.executable, str(CLI), "_refusal", "--list"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    generated = result.stdout.strip()
    page = (ROOT / "docs" / "refusal-codes.md").read_text(encoding="utf-8")
    marker = "<!-- generated by `compass _refusal --list` -->"
    assert marker in page, "docs/refusal-codes.md has no generated marker"
    body = page.split(marker, 1)[1].strip()
    assert body == generated, (
        "docs/refusal-codes.md is stale - regenerate it with "
        "`compass _refusal --list`")


def test_rtp_4_every_code_has_a_call_site():
    """A code counts as used only where it is passed to the hook's refusal
    functions or to render() - a mention in a comment does not count."""
    text = ""
    for p in (ROOT / "hooks").glob("*.sh"):
        text += p.read_text(encoding="utf-8")
    for p in (ROOT / "cli" / "compass_pkg").glob("*.py"):
        if p.name == "refusals.py":
            continue
        text += p.read_text(encoding="utf-8")
    text += (ROOT / "cli" / "compass").read_text(encoding="utf-8")
    missing = [c for c in codes() if not _called(c, text)]
    assert not missing, f"codes with no call site outside the registry: {missing}"


def _called(code, text):
    code_lines = "\n".join(line for line in text.splitlines()
                           if not line.lstrip().startswith("#"))
    return bool(re.search(
        rf"(emit_refusal|compass_block)\s+{re.escape(code)}\b"
        rf"|render\(\s*[\"']{re.escape(code)}[\"']"
        rf"|printf .*\[{re.escape(code)}\]", code_lines))


def test_rtf_4_a_code_named_only_in_a_comment_is_not_a_call_site():
    assert not _called("no-red-on-record", "# no-red-on-record is handled\n")
    assert not _called("python-missing",
                       '    # render("python-missing", target=..., tool=...)\n')
    assert _called("no-red-on-record", 'compass_block no-red-on-record "x=1"')


# ---------------------------------------------------------------------------
# RTF - D45: the fallback keeps its shape, and the texts are exact.
# ---------------------------------------------------------------------------

def test_rtf_1_a_python3_that_fails_with_output_keeps_the_refusal_shape(install):
    broken = install / "brokenbin"
    broken.mkdir()
    (broken / "python3").write_text(
        "#!/bin/sh\necho 'broken python: dyld error' >&2\nexit 1\n")
    (broken / "python3").chmod(0o755)
    result = _hook(install, "src/app.py",
                   path=f"{broken}:{os.environ['PATH']}")
    assert result.returncode == 2, (result.returncode, result.stderr)
    lines = result.stderr.splitlines()
    starts = [i for i, l in enumerate(lines)
              if l.startswith(("Blocked:", "Why:", "Fix:"))]
    assert [lines[i].split(":")[0] for i in starts] == ["Blocked", "Why", "Fix"], lines
    assert "src/app.py" in lines[starts[0]], lines
    assert re.search(r"\[[a-z-]+\]$", lines[starts[2]]), lines
    assert "    broken python: dyld error" in lines[starts[2] + 1:], lines


def test_rtf_2_the_fix_lines_are_exact():
    fixes = {c: REFUSALS[c]["fix"] for c in codes()}
    assert "3.10+" in fixes["python-missing"]
    for code in ("red-unsigned", "red-marker-no-record", "no-red-on-record"):
        assert "--scenario <id>" in fixes[code], (code, fixes[code])
    assert "/compass:assess --reassess" in fixes["no-acceptance-criteria"]
    assert not any("re-try" in f for f in fixes.values()), fixes


def test_rtf_3_a_long_parameter_is_cut_and_the_refusal_stays_short():
    long_detail = " ".join(["word"] * 200)
    text = render("config-invalid", target="src/app.py", tool="Edit",
                  file="compass.yml", detail=long_detail)
    assert len(text.split()) < 60, len(text.split())


def test_rtf_4_the_registry_comment_claims_only_what_render_checks():
    """The comment says an extra field is ignored and a missing one
    raises; render() must behave that way."""
    render("config-invalid", target="a", tool="Edit", file="f", detail="d",
           extra="x")
    with pytest.raises(KeyError):
        render("config-invalid", target="a", tool="Edit", file="f")
    source = (ROOT / "cli" / "compass_pkg" / "refusals.py").read_text()
    assert "An extra field is ignored" in source


def test_rtf_4_the_hook_runs_under_a_python3_older_than_3_10(install):
    old = shutil.which("python3", path="/usr/bin")
    if not old:
        pytest.skip("no /usr/bin/python3 on this machine")
    version = subprocess.run([old, "-c", "import sys; print(sys.version_info[:2] < (3, 10))"],
                             capture_output=True, text=True).stdout.strip()
    if version != "True":
        pytest.skip("/usr/bin/python3 is 3.10 or newer")
    for red in install.glob(".compass/work/*/.red"):
        red.unlink()
    result = _hook(install, "src/app.py", path=f"/usr/bin:{os.environ['PATH']}")
    assert result.returncode == 2, result.stderr
    assert "[no-red-on-record]" in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr


def test_rtf_6_the_docs_page_does_not_claim_cli_refusals():
    page = (ROOT / "docs" / "refusal-codes.md").read_text()
    assert "the CLI can refuse" not in page, page[:400]


def test_rtf_6_no_fixture_renders_a_doubled_word():
    doubled = {c: m.group(0) for c in codes()
               for m in [re.search(r"\b(\w+) \1\b", render(c, **FIXTURES[c]))]
               if m}
    assert not doubled, doubled


# SH-5: the refusal for a settings file the hook cannot read names the file
# it read.

@pytest.mark.parametrize("name", ["compass.yml", ".compass/config.yml"])
def test_sh5_config_invalid_names_the_file_it_was_given(name):
    text = " ".join(render("config-invalid", target="a", tool="Edit",
                          file=name, detail="d").split())
    assert f"'{name}' could not be read" in text, text
    assert f"fix {name} and retry" in text, text
    other = ".compass/config.yml" if name == "compass.yml" else "compass.yml"
    assert other not in text.replace(name, ""), text


def test_sh5_the_registry_and_its_doc_hold_no_fixed_settings_file():
    template = REFUSALS["config-invalid"]
    assert ".compass/config.yml" not in " ".join(template.values())
    page = (ROOT / "docs" / "refusal-codes.md").read_text(encoding="utf-8")
    section = page.split("### `config-invalid`", 1)[1].split("###", 1)[0]
    assert "{file}" in section and ".compass/config.yml" not in section
