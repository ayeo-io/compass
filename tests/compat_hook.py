"""Build project states and run the pre-tool hook against them, for contract 5.

Contract 5 records what the pre-tool hook decides for a fixed set of tool
calls, captured once from the 5.6.0 code. This module holds the three things
that recording needs:

- the inputs: each tool call, the project state it runs in, and any phrase
  whose presence in the output is part of the decision;
- the builder: one function per named state, each writing a fresh project
  into a temporary directory;
- the runner: the hook run on a copy of the framework, never on this
  repository, with the tool call as JSON on stdin.

`capture` writes the observed decisions into the corpus file once. The test
reads that file and never rewrites it, so a later change to the hook shows up
as a failing entry rather than as a new recording.

Scenario id: `TRC-001` (issue `compat-hook-corpus`).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# The bundled PyYAML must win over any copy on the machine, as in conftest.
sys.path.insert(0, str(ROOT / "cli"))
import compass_pkg  # noqa: E402,F401
import yaml  # noqa: E402

CORPUS = ROOT / "tests" / "fixtures" / "compat" / "contract-5-hook.yml"
SLUG = "corpus"

# The refusal registry ends every refusal with its code in brackets, and the
# shell fallback keeps that shape, so the last bracketed word is the code.
_CODE_RE = re.compile(r"\[([a-z][a-z0-9-]*)\]\s*$", re.MULTILINE)

_INITIALISED = 'initialised:\n  by: "compass init"\n  at: "2026-09-05"\n'
_GLOBS = "enforcement:\n  code_globs: ['packaging/**', '*.sh']\n"
CONFIG = "version: 1.0.0\nmode: enforced\n" + _GLOBS + _INITIALISED

MANIFEST = """schema_version: '2.0'
issue: corpus
created: '2026-10-06'
status: active
stages: {assess: full, define: full, implement: full}
scenarios:
- id: C5-1
  intent: INT-1
  tests: [t]
"""


def _signed_red(timestamp="2026-09-24T00:00:00+00:00", signed=True):
    payload = {"command": "pytest -q", "scenario": None, "exit_code": 1,
               "passed": False, "timestamp": timestamp,
               "record_id": "fixture0000000000"}
    if signed:
        body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    return payload


def _issue(project, *, config=CONFIG, pointer=SLUG, manifest=MANIFEST,
           approach=True, red=None, markers=()):
    """An opted-in project with one issue. `red` is a record to write, or
    "marker-only" for a `.red` with no record behind it."""
    compass = project / ".compass"
    task = compass / "work" / SLUG
    (task / "evidence").mkdir(parents=True)
    if config is not None:
        (compass / "config.yml").write_text(config)
    if pointer is not None:
        (compass / "current-task").write_text(pointer)
    (task / "manifest.yml").write_text(manifest)
    if approach:
        (task / "delivery-approach.md").write_text("# Approach\n")
    if red == "marker-only":
        (task / ".red").write_text("")
    elif red is not None:
        (task / "evidence" / "red.json").write_text(json.dumps(red))
        (task / ".red").write_text("")
    for marker in markers:
        (task / marker).write_text("")


def _bare(project, *, config, work):
    """An opted-in project with no issue: `.compass/` and its config, and an
    empty `work/` when `work` is true."""
    compass = project / ".compass"
    compass.mkdir()
    (compass / "config.yml").write_text(config)
    if work:
        (compass / "work").mkdir()


def _unreadable(project):
    _issue(project, red=_signed_red())
    (project / ".compass" / "config.yml").chmod(0)


#: Each named state and how to build it. A state is the project only; the
#: tool call comes from the entry.
STATES = {
    "red": lambda p: _issue(p, red=_signed_red()),
    "no-red": lambda p: _issue(p),
    "red-unsigned": lambda p: _issue(
        p, config=CONFIG + "records_signed_since: '2026-09-05'\n",
        red=_signed_red("2026-09-20T00:00:00+00:00", signed=False)),
    "red-marker-only": lambda p: _issue(p, red="marker-only"),
    "spike": lambda p: _issue(p, markers=(".spike",)),
    "acceptance": lambda p: _issue(p, markers=(".acceptance",)),
    "no-scenarios": lambda p: _issue(
        p, manifest=MANIFEST.split("scenarios:")[0] + "scenarios: []\n",
        red=_signed_red()),
    "no-approach": lambda p: _issue(p, approach=False, red=_signed_red()),
    "no-pointer": lambda p: _issue(p, pointer=None, red=_signed_red()),
    "bad-pointer": lambda p: _issue(p, pointer="../elsewhere", red=_signed_red()),
    "not-opted-in": lambda p: None,
    "no-work-initialised": lambda p: _bare(p, config=CONFIG, work=False),
    "no-work-plain": lambda p: _bare(
        p, config="version: 1.0.0\nmode: enforced\n" + _GLOBS, work=False),
    "no-issue-initialised": lambda p: _bare(p, config=CONFIG, work=True),
    "no-issue-plain": lambda p: _bare(
        p, config="version: 1.0.0\nmode: enforced\n" + _GLOBS, work=True),
    "config-malformed": lambda p: _issue(
        p, config="version: 1.0.0\nenforcement: [unclosed\n", red=_signed_red()),
    "config-unreadable": _unreadable,
    "config-globs-string": lambda p: _issue(
        p, config="version: 1.0.0\nenforcement:\n  code_globs: '*'\n",
        red=_signed_red()),
    "advisory": lambda p: _issue(
        p, config=CONFIG.replace("mode: enforced", "mode: advisory")),
}

#: Entries whose state relies on a file permission that the root user ignores.
NEEDS_NON_ROOT = {"config-unreadable"}


def _edit(path):
    return ("Edit", {"file_path": "{project}/" + path,
                     "old_string": "a", "new_string": "b"})


def _write(path):
    return ("Write", {"file_path": "{project}/" + path, "content": "x\n"})


def _bash(command):
    return ("Bash", {"command": command})


# Commands hold no double quote. Without jq the hook reads the JSON with
# grep, which stops at the first escaped quote, so a quote-free command reads
# the same under both parsers.
_PY_WRITE = "python3 - <<'PY'\nopen('src/app.py', 'w').write('x')\nPY"
_PY_READ = "python3 - <<'PY'\nprint(open('src/app.py').read())\nPY"
_PATHLIB = ("python3 - <<'PY'\nimport pathlib\n"
            "pathlib.Path('src/app.py').write_text('x')\nPY")

_OPTED_IN = "which is when it opted into Compass"

#: (id, state, (tool, tool_input), phrase or None). A phrase is recorded as
#: `stderr_contains` when the hook printed it and `stderr_excludes` when not.
INPUTS = [
    # Production code with and without a red on record.
    ("edit-code-with-red", "red", _edit("src/app.py"), None),
    ("write-new-code-with-red", "red", _write("src/pkg/fresh.py"), None),
    ("bash-redirect-with-red", "red", _bash("echo x > src/app.py"), None),
    ("edit-code-no-red", "no-red", _edit("src/app.py"), None),
    ("write-new-code-no-red", "no-red", _write("src/pkg/fresh.py"), None),
    ("edit-workflow-no-red", "no-red", _edit(".github/workflows/ci.yml"), None),
    ("edit-migration-no-red", "no-red", _edit("db/migrations/001.sql"), None),
    # Exempt paths.
    ("write-test-dir-no-red", "no-red", _write("tests/test_app.py"), None),
    ("edit-test-basename-no-red", "no-red", _edit("pkg/app_test.go"), None),
    ("edit-markdown-no-red", "no-red", _edit("README.md"), None),
    ("edit-issue-manifest-no-red", "no-red",
     _edit(".compass/work/corpus/manifest.yml"), None),
    ("edit-issue-document-no-red", "no-red",
     _edit("docs/compass/2026-10-06-corpus/intent.md"), None),
    ("edit-compass-config-no-red", "no-red", _edit(".compass/config.yml"), None),
    # The project's own enforcement.code_globs.
    ("edit-glob-dir-match-no-red", "no-red", _edit("packaging/build.cfg"), None),
    ("edit-glob-ext-match-no-red", "no-red", _edit("bin/deploy.sh"), None),
    ("edit-glob-miss-no-red", "no-red", _edit("docker-compose.yml"), None),
    ("bash-redirect-glob-match-no-red", "no-red",
     _bash("echo x > packaging/build.cfg"), None),
    # Bash commands that write a guarded path.
    ("bash-redirect-no-red", "no-red", _bash("echo x > src/app.py"), None),
    ("bash-append-no-red", "no-red", _bash("printf y >> src/app.py"), None),
    ("bash-sed-in-place-no-red", "no-red",
     _bash("sed -i '' 's/a/b/' src/app.py"), None),
    ("bash-tee-no-red", "no-red", _bash("echo x | tee src/app.py"), None),
    ("bash-python-open-write-no-red", "no-red", _bash(_PY_WRITE), None),
    ("bash-pathlib-write-no-red", "no-red", _bash(_PATHLIB), None),
    ("bash-copy-onto-code-no-red", "no-red",
     _bash("cp /tmp/draft.py src/app.py"), None),
    ("bash-git-apply-no-red", "no-red", _bash("git apply fix.diff"), None),
    # Bash commands that only read, or write somewhere unguarded.
    ("bash-cat-no-red", "no-red", _bash("cat src/app.py"), None),
    ("bash-grep-no-red", "no-red", _bash("grep -n main src/app.py"), None),
    ("bash-python-open-read-no-red", "no-red", _bash(_PY_READ), None),
    ("bash-stderr-duplicate-no-red", "no-red",
     _bash("pytest -q 2>&1 | tail -5"), None),
    ("bash-redirect-dev-null-no-red", "no-red", _bash("ls > /dev/null"), None),
    ("bash-redirect-test-file-no-red", "no-red",
     _bash("echo x > tests/test_app.py"), None),
    # Paths outside the project.
    ("edit-outside-project-no-red", "no-red",
     ("Edit", {"file_path": "{outside}/app.py",
               "old_string": "a", "new_string": "b"}), None),
    ("bash-redirect-outside-project-no-red", "no-red",
     _bash("echo x > {outside}/app.py"), None),
    # Not opted in, and opted in with no issue.
    ("edit-code-not-opted-in", "not-opted-in", _edit("src/app.py"), None),
    ("bash-redirect-not-opted-in", "not-opted-in",
     _bash("echo x > src/app.py"), None),
    ("edit-code-no-work-initialised", "no-work-initialised",
     _edit("src/app.py"), _OPTED_IN),
    ("edit-code-no-work-plain", "no-work-plain", _edit("src/app.py"), _OPTED_IN),
    ("edit-code-no-issue-initialised", "no-issue-initialised",
     _edit("src/app.py"), _OPTED_IN),
    ("edit-code-no-issue-plain", "no-issue-plain", _edit("src/app.py"), _OPTED_IN),
    ("edit-test-no-issue-initialised", "no-issue-initialised",
     _edit("tests/test_app.py"), None),
    # Issue state other than the red.
    ("edit-code-spike", "spike", _edit("src/app.py"), None),
    ("edit-code-acceptance", "acceptance", _edit("src/app.py"), None),
    ("edit-code-red-unsigned", "red-unsigned", _edit("src/app.py"), None),
    ("edit-code-red-marker-only", "red-marker-only", _edit("src/app.py"), None),
    ("edit-code-no-scenarios", "no-scenarios", _edit("src/app.py"), None),
    ("edit-code-no-approach", "no-approach", _edit("src/app.py"), None),
    ("edit-code-no-pointer", "no-pointer", _edit("src/app.py"),
     "falling back to the most recently modified issue"),
    ("edit-code-bad-pointer", "bad-pointer", _edit("src/app.py"), None),
    # A config file the hook cannot use.
    ("edit-code-config-malformed", "config-malformed", _edit("src/app.py"), None),
    ("edit-unlisted-config-malformed", "config-malformed",
     _edit("packaging/build.cfg"), None),
    ("edit-markdown-config-malformed", "config-malformed",
     _edit("README.md"), None),
    ("edit-code-config-unreadable", "config-unreadable",
     _edit("src/app.py"), None),
    ("edit-unlisted-config-unreadable", "config-unreadable",
     _edit("packaging/build.cfg"), None),
    ("edit-unlisted-globs-string", "config-globs-string",
     _edit("docker-compose.yml"), None),
    # Advisory mode.
    ("edit-code-advisory", "advisory", _edit("src/app.py"), None),
    ("bash-redirect-advisory", "advisory", _bash("echo x > src/app.py"), None),
]


def install(base):
    """Copy the parts of the framework the hook runs from into `base`, so
    no run reads or writes this repository."""
    for part in ("hooks", "scripts", "cli"):
        shutil.copytree(ROOT / part, base / part,
                        ignore=shutil.ignore_patterns("__pycache__"))
    return base


def build(state, base):
    """A fresh project for `state` under `base`, plus a sibling directory
    outside it. Neither path holds "test" or "spec", so the hook's test-file
    exemption cannot fire on the project's own location."""
    project = Path(tempfile.mkdtemp(prefix="c5proj-", dir=base))
    outside = Path(tempfile.mkdtemp(prefix="c5out-", dir=base))
    STATES[state](project)
    return project, outside


def _fill(value, project, outside):
    if isinstance(value, dict):
        return {k: _fill(v, project, outside) for k, v in value.items()}
    if isinstance(value, str):
        return value.replace("{project}", str(project)).replace(
            "{outside}", str(outside))
    return value


def run(hook_root, project, outside, tool, tool_input, base):
    """Run the copied hook once and return (exit, code, stdout, stderr)."""
    home = base / "home"
    config_dir = base / "claude-config"
    home.mkdir(exist_ok=True)
    config_dir.mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(config_dir),
        "CLAUDE_PROJECT_DIR": str(project),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "C.UTF-8",
    }
    event = json.dumps({"tool_name": tool,
                        "tool_input": _fill(tool_input, project, outside)})
    result = subprocess.run(
        ["bash", str(hook_root / "hooks" / "pre-tool.sh")], input=event,
        capture_output=True, text=True, timeout=60, env=env, cwd=project)
    codes = _CODE_RE.findall(result.stderr)
    return (result.returncode, codes[-1] if codes else None,
            result.stdout, result.stderr)


def run_entry(hook_root, base, entry, mutate=None):
    """Build the entry's state, apply `mutate(project)` if given, and run."""
    project, outside = build(entry["state"], base)
    if mutate is not None:
        mutate(project)
    try:
        return run(hook_root, project, outside, entry["tool"],
                   entry["tool_input"], base)
    finally:
        cfg = project / ".compass" / "config.yml"
        if cfg.exists():
            cfg.chmod(0o644)


def _observe(hook_root, base, item):
    entry_id, state, (tool, tool_input), phrase = item
    entry = {"id": entry_id, "state": state, "tool": tool,
             "tool_input": tool_input}
    exit_code, code, _out, err = run_entry(hook_root, base, entry)
    entry["exit"] = exit_code
    entry["decision"] = {0: "allow", 2: "block"}.get(exit_code, "error")
    entry["code"] = code
    if phrase is not None:
        key = "stderr_contains" if phrase in err else "stderr_excludes"
        entry[key] = phrase
    return entry


_HEADER = """\
# Contract 5: the pre-tool hook's decision on each tool call below, captured
# once from compass {version} (commit {commit}) by tests/compat_hook.py.
# Do not regenerate this file from newer code: it is the record a rewrite of
# the configuration must still match. `decision` follows the exit status
# (0 allows, 2 blocks); `code` is the bracketed refusal code, or null.
# `{{project}}` and `{{outside}}` stand for the project directory and a
# directory outside it, filled in when the entry runs.
"""


def capture(path=CORPUS, force=False):
    """Run every input twice, keep the entries whose two runs agree, and
    write them to `path`. Refuses to overwrite an existing corpus unless
    `force` is true, because the corpus is a record of the old code and a
    rewrite from new code would hide the change it exists to catch.

    Returns the ids dropped for giving different results on the two runs.
    """
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(
            "%s exists; pass force=True only to replace a corpus captured "
            "from the same code" % path)
    if os.geteuid() == 0:
        raise RuntimeError("capture as a normal user: the root user can read "
                           "an unreadable config, so one state would be wrong")
    version = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    base = Path(tempfile.mkdtemp(prefix="c5cap-"))
    try:
        hook_root = install(base / "framework")
        kept, dropped = [], []
        for item in INPUTS:
            first = _observe(hook_root, base, item)
            second = _observe(hook_root, base, item)
            (kept if first == second else dropped).append(first)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump({"contract": 5, "entries": kept}, sort_keys=False,
                          allow_unicode=True, width=1000)
    path.write_text(_HEADER.format(version=version, commit=commit) + body)
    return [entry["id"] for entry in dropped]


def load(path=CORPUS):
    return yaml.safe_load(Path(path).read_text())["entries"]


if __name__ == "__main__":
    print("dropped:", capture(force="--force" in sys.argv))
