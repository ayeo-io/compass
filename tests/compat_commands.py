"""Build the project states and run the entries of the contract 4 corpus.

The corpus in tests/fixtures/compat/contract-4-commands.yml records, for each
command, the exit code the CLI gave at 5.6.0. This module is the one place
that knows how to rebuild the project state an entry names and run the entry
the same way every time, so the test and the one-off capture cannot drift
apart.

Every run gets a scrubbed environment: HOME, CLAUDE_CONFIG_DIR and the cache
directory point into a temporary folder, git reads no global or system
configuration, and no Claude Code session variable leaks in. Without that,
an entry's exit code could depend on the machine that ran it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
CORPUS = ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml"

# A fixed date keeps hand-written manifests independent of the day the
# states are built.
FIXED_DATE = "2026-10-01"

QUICK_FIX_SLUG = "greet"
REGULAR_SLUG = "feature"

REGULAR_MANIFEST = f"""schema_version: '2.0'
issue: {REGULAR_SLUG}
created: '{FIXED_DATE}'
status: active
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: standard
  goal: delivery
  role: engineer
  labels: []
evidence: []
gates: []
scenarios: []
changed_files: []
follow_ups: []
"""

# Each key is one the 6.0.0 rewrite moves the reading of, so the corpus
# records what a project that sets them sees today.
CONFIG_WITH_SETTINGS = """version: 1.0.0
mode: advisory
autonomy: controlled
enforcement:
  code_globs: ["*.sh", "packaging/**"]
record:
  remote: ../record.git
  paths: [docs/decisions]
"""


@dataclass
class Outcome:
    exit: int
    stdout: str
    stderr: str


def environment(scratch: Path) -> dict:
    """The environment every CLI run gets, rooted in `scratch`."""
    home = scratch / "home"
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "COLUMNS": "100",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        # Background maintenance after a commit races the copy of a built
        # state, so every git process started here has it switched off.
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "maintenance.auto",
        "GIT_CONFIG_VALUE_0": "false",
        "GIT_CONFIG_KEY_1": "gc.auto",
        "GIT_CONFIG_VALUE_1": "0",
        "GIT_AUTHOR_NAME": "Compat Test",
        "GIT_AUTHOR_EMAIL": "compat@example.com",
        "GIT_COMMITTER_NAME": "Compat Test",
        "GIT_COMMITTER_EMAIL": "compat@example.com",
        "GIT_AUTHOR_DATE": f"{FIXED_DATE}T12:00:00+00:00",
        "GIT_COMMITTER_DATE": f"{FIXED_DATE}T12:00:00+00:00",
    }


def _cli(root: Path, env: dict, *argv: str) -> Outcome:
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=root, env=env,
                       capture_output=True, text=True, timeout=60)
    return Outcome(r.returncode, r.stdout, r.stderr)


def run_in(root: Path, env: dict, argv: list[str]) -> Outcome:
    """Run the CLI with `argv` in a project the caller has prepared."""
    return _cli(root, env, *argv)


def _must(root: Path, env: dict, *argv: str) -> None:
    r = _cli(root, env, *argv)
    if r.exit != 0:
        raise RuntimeError(f"building a state: compass {' '.join(argv)} "
                           f"exited {r.exit}\n{r.stdout}{r.stderr}")


def _git(root: Path, env: dict, *argv: str) -> None:
    subprocess.run(["git", *argv], cwd=root, env=env, check=True,
                   capture_output=True)


def _empty(root: Path, env: dict) -> None:
    root.mkdir(parents=True)
    _git(root, env, "init", "-q", "-b", "main")
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    _git(root, env, "add", "-A")
    _git(root, env, "commit", "-q", "-m", "base")


def _initialised(root: Path, env: dict) -> None:
    _empty(root, env)
    _must(root, env, "init")


def _quick_fix_started(root: Path, env: dict) -> None:
    _empty(root, env)
    _must(root, env, "quick-fix", "start", QUICK_FIX_SLUG,
          "--risk", "trivial - a one-line text change",
          "--familiarity", "brownfield-mapped - the file and its test exist",
          "--size", "atomic - one line",
          "--intent", "the greeting reads correctly",
          "--scenario", "Given the greeting, when read, then it says hello",
          "--test", "tests/test_greeting.py")
    # The note lets an `evidence add` entry succeed without registering it.
    _write_note(root)


# Evidence paths resolve against the issue's work directory, not the project.
NOTE = "evidence/note.md"


def _write_note(root: Path) -> None:
    note = root / ".compass" / "work" / QUICK_FIX_SLUG / NOTE
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("A reviewer read the change.\n", encoding="utf-8")


def _quick_fix_with_note(root: Path, env: dict) -> None:
    _quick_fix_started(root, env)
    _must(root, env, "evidence", "add", "EV-1", "--type", "artifact",
          "--path", NOTE)


def _regular_issue(root: Path, env: dict) -> None:
    # Built on the quick fix so that `issue raised-by` has a parent to name.
    _quick_fix_started(root, env)
    work = root / ".compass" / "work" / REGULAR_SLUG
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(REGULAR_MANIFEST, encoding="utf-8")
    _must(root, env, "approach", "evaluate", "--issue", REGULAR_SLUG,
          "--write")
    _must(root, env, "issue", "use", REGULAR_SLUG)


def _with_copied_governance(root: Path, env: dict) -> None:
    _initialised(root, env)
    governance = root / "governance"
    governance.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copyfile(ROOT / "governance" / name, governance / name)


def _outside_git(root: Path, env: dict) -> None:
    # A Compass project with no repository, so a command that needs git is
    # refused for that reason and not for a missing .compass folder.
    root.mkdir(parents=True)
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    _must(root, env, "init")


def _regular_issue_broken_compass_yml(root: Path, env: dict) -> None:
    _regular_issue(root, env)
    (root / "compass.yml").write_text("schema: 1\nstages: oops\n", encoding="utf-8")


def _with_broken_governance(root: Path, env: dict) -> None:
    _with_copied_governance(root, env)
    # A routing policy without its required top-level keys is the
    # structural fault `policy lint` exists to refuse.
    (root / "governance" / "routing-policy.yml").write_text(
        "version: 1\napproaches: 3\n", encoding="utf-8")


def _with_config(root: Path, env: dict) -> None:
    _quick_fix_started(root, env)
    (root / ".compass" / "config.yml").write_text(CONFIG_WITH_SETTINGS,
                                                  encoding="utf-8")


def _with_compass_yml(root: Path, env: dict) -> None:
    _initialised(root, env)
    (root / "compass.yml").write_text("schema: 1\n", encoding="utf-8")


def _with_default_extends(root: Path, env: dict) -> None:
    _initialised(root, env)
    (root / "compass.yml").write_text("schema: 1\nextends: compass:default@6\n",
                                      encoding="utf-8")


def _with_looser_compass_yml(root: Path, env: dict) -> None:
    _initialised(root, env)
    (root / "compass.yml").write_text(
        "schema: 1\nchecks:\n  suite-passed:\n    set:\n      severity: advisory\n",
        encoding="utf-8")


def _with_broken_compass_yml(root: Path, env: dict) -> None:
    _initialised(root, env)
    (root / "compass.yml").write_text("schema: 1\nstages: oops\n", encoding="utf-8")


def _with_git_parent_no_sha(root: Path, env: dict) -> None:
    _initialised(root, env)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: github:acme/compass-banking@1.2.0\n", encoding="utf-8")


def _with_git_parent_uncached(root: Path, env: dict) -> None:
    _initialised(root, env)
    (root / "compass.yml").write_text(
        f"schema: 1\nextends: github:acme/compass-banking@1.2.0#{'a' * 40}\n",
        encoding="utf-8")


STATES = {
    "with-git-parent-no-sha": _with_git_parent_no_sha,
    "with-git-parent-uncached": _with_git_parent_uncached,
    "empty": _empty,
    "initialised": _initialised,
    "quick-fix-started": _quick_fix_started,
    "quick-fix-with-note": _quick_fix_with_note,
    "regular-issue": _regular_issue,
    "regular-issue-broken-compass-yml": _regular_issue_broken_compass_yml,
    "with-copied-governance": _with_copied_governance,
    "with-broken-governance": _with_broken_governance,
    "with-config": _with_config,
    "with-compass-yml": _with_compass_yml,
    "with-default-extends": _with_default_extends,
    "with-looser-compass-yml": _with_looser_compass_yml,
    "with-broken-compass-yml": _with_broken_compass_yml,
    "outside-git": _outside_git,
}


class Projects:
    """Builds each named state once, then hands every entry its own copy.

    Copying a built state is much cheaper than rebuilding it, and a copy per
    entry keeps an entry that writes from changing what the next one sees.
    """

    def __init__(self, scratch: Path):
        self.scratch = scratch
        self.env = environment(scratch)
        self._templates: dict[str, Path] = {}
        self._count = 0

    def template(self, state: str) -> Path:
        if state not in self._templates:
            if state not in STATES:
                raise KeyError(f"unknown project state {state!r}")
            dest = self.scratch / "templates" / state
            STATES[state](dest, self.env)
            self._templates[state] = dest
        return self._templates[state]

    def fresh(self, state: str) -> Path:
        self._count += 1
        dest = self.scratch / "runs" / f"{self._count:03d}" / "project"
        shutil.copytree(self.template(state), dest, symlinks=True)
        return dest

    def run(self, entry: dict) -> Outcome:
        return _cli(self.fresh(entry["project"]), self.env, *entry["argv"])


def load(path: Path = CORPUS) -> list[dict]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["entries"]


def differences(entry: dict, outcome: Outcome) -> list[str]:
    """What the run did that the recorded entry says it should not."""
    found = []
    if outcome.exit != entry["exit"]:
        found.append(f"exit {outcome.exit}, recorded {entry['exit']}")
    phrase = entry.get("stdout_contains")
    if phrase and phrase not in outcome.stdout:
        found.append(f"stdout lacks {phrase!r}")
    return found


HEADER = """\
# Contract 4: the CLI's exit codes on a recorded command corpus.
#
# Each entry names a project state that tests/compat_commands.py builds, the
# arguments given to the CLI in it, and the exit code 5.6.0 gave. The exit
# codes were captured once by `capture()` and must never be regenerated by
# running newer code. A changed exit code is a change in behaviour to
# explain, not a fixture to refresh.
"""


def _dump(entries: list[dict]) -> str:
    # JSON strings and lists are valid YAML, and keep each entry on a few
    # readable lines with its arguments in one list.
    lines = [HEADER, "entries:"]
    for entry in entries:
        lines.append(f"- id: {entry['id']}")
        lines.append(f"  project: {entry['project']}")
        lines.append(f"  argv: {json.dumps(entry['argv'])}")
        if "exit" in entry:
            lines.append(f"  exit: {entry['exit']}")
        if entry.get("stdout_contains"):
            lines.append(
                f"  stdout_contains: {json.dumps(entry['stdout_contains'])}")
    return "\n".join(lines) + "\n"


def capture(path: Path = CORPUS, force: bool = False) -> None:
    """Run every entry and write the exit code it gave into the corpus.

    The baseline is captured once, from 5.6.0, and never regenerated by
    running newer code: a regenerated baseline would agree with whatever the
    code now does, which is the drift the contract exists to catch. So an
    entry that already has an exit code is refused unless `force` is given.
    """
    path = Path(path)
    entries = load(path)
    if not force and any("exit" in entry for entry in entries):
        raise RuntimeError(f"{path} already holds captured exit codes; "
                           f"pass force=True only to replace them on purpose")
    with tempfile.TemporaryDirectory() as tmp:
        projects = Projects(Path(tmp))
        for entry in entries:
            outcome = projects.run(entry)
            entry["exit"] = outcome.exit
            phrase = entry.get("stdout_contains")
            if phrase and phrase not in outcome.stdout:
                raise RuntimeError(f"{entry['id']}: stdout lacks {phrase!r}:"
                                   f"\n{outcome.stdout}")
    path.write_text(_dump(entries), encoding="utf-8")
