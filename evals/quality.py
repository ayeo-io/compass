"""Static code-quality signals for one eval run, with no model and no
third-party tool.

`measure(record, scenarios_dir)` rebuilds the run's final code: it copies the
scenario's seed, and the condition's `seed_<condition>` overlay where there is
one, into a temporary directory, commits it, and applies the run's recorded
diff. The diff is taken against a seed commit that also holds the condition's
install step output (`compass init`, `specify init`), which the rebuild does
not have, so only the diff sections for `.py` files outside `tests/` are
applied: those files come from the seed alone, and an edit to an install
file cannot stop the rebuild.

Each changed `.py` file outside `tests/` is then measured before and after
with the standard library's `ast`:

- complexity: one per function, nested ones included (a lambda is not
  counted); one per `if`, `for`,
  `while`, `except` handler, `with`, comprehension `if`, conditional
  expression and `match` case; and for each boolean operator, its operands
  minus one. A new file's before is 0; a deleted file is skipped.
- duplicated lines: lines stripped, blank and comment-only lines dropped;
  each four-line window counts once per extra occurrence; after minus
  before, floored at 0 per file.
- lint findings: an import bound to a name the module never reads (names in
  `__all__` and `__future__` imports count as used), a bare `except:`, a
  mutable default argument and `from x import *`, one each.

A file that does not parse, before or after, gives no measure and is named
in `skipped`. A run
whose diff will not apply, or that changes no `.py` file outside `tests/`,
gives no measure at all: the report then says "not recorded", never 0.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

GIT = ["git", "-c", "user.email=quality@example.com", "-c", "user.name=quality",
       "-c", "core.hooksPath=/dev/null"]

_SECTION_START_RE = re.compile(r"^diff --git ", re.M)


def _unquote(name: str) -> str:
    """A path as git prints it in a diff: plain, or in double quotes with
    C-style escapes (octal bytes for a non-ASCII name)."""
    name = name.split("\t", 1)[0]
    if len(name) >= 2 and name[0] == name[-1] == '"':
        raw = name[1:-1].encode("ascii", "backslashreplace").decode("unicode_escape")
        name = raw.encode("latin-1").decode("utf-8", "replace")
    return name


def _section_path(section: str) -> Optional[str]:
    """The file a diff section changes, from its `+++` line, or from its `---`
    line when the file was deleted. A section with neither (a binary file)
    has no path here and is not measured."""
    new = old = None
    for line in section.splitlines():
        if line.startswith("+++ "):
            new = line[4:]
        elif line.startswith("--- "):
            old = line[4:]
        if new is not None:
            break
    name = new if new and new != "/dev/null" else old
    if not name or name == "/dev/null":
        return None
    name = _unquote(name)
    return name[2:] if name[:2] in ("a/", "b/") else name


def complexity(source: str) -> Optional[int]:
    """Decision points in `source`, or None when it does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            count += 0 if isinstance(node, ast.Lambda) else 1
        elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While,
                               ast.ExceptHandler, ast.With, ast.AsyncWith,
                               ast.IfExp)):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            count += len(node.ifs)
        elif hasattr(ast, "match_case") and isinstance(node, ast.match_case):
            count += 1
    return count


def _code_lines(source: str) -> List[str]:
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)
    return lines


def duplicated_lines(source: str) -> int:
    """Four-line windows that occur more than once, counted once per extra
    occurrence."""
    lines = _code_lines(source)
    seen: Dict[tuple, int] = {}
    for i in range(len(lines) - 3):
        window = tuple(lines[i:i + 4])
        seen[window] = seen.get(window, 0) + 1
    return sum(n - 1 for n in seen.values() if n > 1)


def _mutable(default: ast.expr) -> bool:
    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
        return True
    return (isinstance(default, ast.Call) and isinstance(default.func, ast.Name)
            and default.func.id in ("list", "dict", "set"))


def lint_findings(source: str) -> Optional[int]:
    """Unused imports, bare excepts, mutable defaults and star imports, or None
    when `source` does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    findings = 0
    imported: Dict[str, int] = {}
    exported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split(".")[0]] = 1
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    findings += 1
                else:
                    imported[alias.asname or alias.name] = 1
        elif isinstance(node, ast.ExceptHandler) and node.type is None:
            findings += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defaults = node.args.defaults + [d for d in node.args.kw_defaults if d]
            findings += sum(1 for d in defaults if _mutable(d))
        elif isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets) \
                    and isinstance(node.value, (ast.List, ast.Tuple)):
                exported |= {e.value for e in node.value.elts
                             if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    read = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    read |= {n.value.id for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    findings += sum(1 for name in imported if name not in read and name not in exported)
    return findings


def _measured_path(path: str) -> bool:
    return path.endswith(".py") and not path.startswith("tests/") \
        and "/tests/" not in path


def _python_sections(diff: str) -> tuple[str, List[str]]:
    """The diff sections for `.py` files outside `tests/`, and their paths."""
    starts = [m.start() for m in _SECTION_START_RE.finditer(diff)]
    sections, paths = [], []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(diff)
        section = diff[start:end]
        path = _section_path(section)
        if path and _measured_path(path):
            sections.append(section)
            paths.append(path)
    return "".join(sections), paths


def _git(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    # No GIT_* variable from the caller: GIT_DIR or GIT_INDEX_FILE (which git
    # sets for a hook) would point these commands at another repository.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run([*GIT, *args], cwd=cwd, capture_output=True,
                          text=True, env=env)


def _overlay_dir(scenario_dir: Path, condition: str) -> Path:
    return scenario_dir / ("seed_" + condition.replace("-", "_"))


_CACHE: Dict[tuple, Optional[Dict[str, Any]]] = {}


def measure(record: Dict[str, Any], scenarios_dir: Path) -> Optional[Dict[str, Any]]:
    """The run's static signals, or None when there is nothing to measure.
    One rebuild per record: the report asks for three measures of each."""
    key = (str(scenarios_dir), record.get("scenario"), record.get("condition"),
           record.get("diff"))
    if key not in _CACHE:
        _CACHE[key] = _measure(record, scenarios_dir)
    return _CACHE[key]


def _measure(record: Dict[str, Any], scenarios_dir: Path) -> Optional[Dict[str, Any]]:
    diff = record.get("diff")
    scenario_dir = Path(scenarios_dir) / str(record.get("scenario", ""))
    if not isinstance(diff, str) or not (scenario_dir / "seed").is_dir():
        return None
    python_diff, paths = _python_sections(diff)
    if not paths:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copytree(scenario_dir / "seed", work, dirs_exist_ok=True)
        overlay = _overlay_dir(scenario_dir, str(record.get("condition", "")))
        if overlay.is_dir():
            shutil.copytree(overlay, work, dirs_exist_ok=True)
        before = {p: (work / p).read_text(encoding="utf-8") if (work / p).is_file() else ""
                  for p in paths}
        if _git(["init", "-q"], work).returncode != 0:
            return None
        _git(["add", "-A"], work)
        _git(["commit", "-q", "-m", "seed"], work)
        patch = work / ".quality.patch"
        patch.write_text(python_diff, encoding="utf-8")
        applied = _git(["apply", "--whitespace=nowarn", str(patch)], work)
        if applied.returncode != 0:
            return {"note": "the diff for " + ", ".join(paths) + " does not apply "
                            "to the seed: " + applied.stderr.strip()[:200]}
        totals = {"complexity_added": 0, "duplicated_lines": 0, "lint_findings": 0}
        measured, skipped = [], []
        for path in paths:
            target = work / path
            if not target.is_file():
                continue  # deleted: skipped, not measured
            after = target.read_text(encoding="utf-8")
            c_after, lint = complexity(after), lint_findings(after)
            c_before = complexity(before[path]) if before[path] else 0
            if c_after is None or lint is None or c_before is None:
                skipped.append(path)
                continue
            totals["complexity_added"] += c_after - c_before
            totals["duplicated_lines"] += max(
                0, duplicated_lines(after) - duplicated_lines(before[path]))
            totals["lint_findings"] += lint
            measured.append(path)
    if not measured:
        return {"note": "no changed Python file could be measured", "skipped": skipped}
    return {**totals, "files": measured, "skipped": skipped}


def _one(key: str):
    def extract(record: Dict[str, Any], scenarios_dir: Path) -> Optional[int]:
        m = measure(record, scenarios_dir)
        return m.get(key) if isinstance(m, dict) else None
    return extract


complexity_added_of = _one("complexity_added")
duplicated_lines_of = _one("duplicated_lines")
lint_findings_of = _one("lint_findings")
