# compass_pkg.preset_test - `compass policy test`: run a preset's fixtures
"""Run a preset's fixture assessments and report how each one went.

A preset is a folder with a `compass.yml` and a `compass-fixtures/` folder.
Each `.yml` file in the fixture folder is one fixture: an assessment and what
it is expected to compute. This module loads the preset, evaluates every
fixture over the shipped default, the preset's git parents and the preset,
and builds the one report that the text and `--json` views both render.
`docs/policy-test.md` owns the fixture format and the report.

It reads files and, through `policy_lint.load_layers`, may fetch a pinned git
parent. It writes no file of the preset and runs nothing the preset carries.
"""
# DEPENDENCY: standard library (dataclasses, os, re); compass_pkg.atomic_io,
# core (CompassError), layers, merge, obligations, policy_lint.
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from compass_pkg import layers, merge, obligations, policy_lint
from compass_pkg.atomic_io import StrictYamlError, load_yaml_strict
from compass_pkg.core import CompassError

JSON_SCHEMA_VERSION = 1

FIXTURE_DIR = "compass-fixtures"
FIXTURE_SUFFIX = ".yml"
FIXTURE_KEYS = ("name", "assessment", "expect")
EXPECT_KEYS = ("approach", "gates", "stages", "checks")
# A group folder is one path segment of this shape, at most this many deep.
GROUP_SEGMENT = re.compile(r"[a-z0-9][a-z0-9-]*")
GROUP_DEPTH = 3


@dataclass
class FixtureResult:
    file: str
    name: str
    status: str                 # "pass", "fail" or "error"
    mismatches: list = field(default_factory=list)
    message: object = None
    group: object = None        # the folder below compass-fixtures/, or None


@dataclass
class Result:
    preset: str
    lint: object = None
    fixtures_run: bool = False
    fixtures: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def shown(path):
    """`path` as a person sees it: from the working folder when it is below
    it, otherwise the folder's own name. An absolute path is machine-specific,
    so it never reaches a report."""
    absolute, base = os.path.abspath(path), os.getcwd()
    if absolute.startswith(base + os.sep):
        return os.path.relpath(absolute, base).replace(os.sep, "/")
    return os.path.basename(absolute)


def _lint(folder, fetch):
    """`(report, chain)`: the lint of the preset read as a parent over the
    shipped default, and the layers it ran over. A parent may not carry
    `unlock:`, a settings key or an `impl` outside the registry, and may not
    loosen a locked entry, so the lint is what checks the framework locks.
    The chain is None when the lint failed."""
    loaded = policy_lint.load_layers(folder, read_project=True, fetch=fetch)
    project, loaded.project = loaded.project, None
    if loaded.findings or project is None:
        return policy_lint.lint_loaded(loaded), None
    doc = project.doc
    preset = layers.Layer("preset", "parent", doc, layers.layer_digest(doc, "parent")
                          if isinstance(doc, dict) else "")
    chain = [loaded.parent, *[p.layer for p in loaded.git_parents], preset]
    report = policy_lint.lint_chain(loaded.parent, None, extra_parents=chain[1:])
    return report, chain if report.ok else None


def _relabel(report):
    """Name the preset's layer `preset` in every finding. The loader and the
    waiver checks call the layer they read `project`; in a preset there is no
    project layer, and a finding that says so points at the wrong file."""
    for f in report.findings:
        if f.layer == "project":
            f.layer = "preset"
        if f.path.startswith("project:"):
            f.path = "preset:" + f.path[len("project:"):]


def resolve(chain):
    """`(config, capabilities)` after the chain is merged, root first."""
    config, provenance, on = {}, {}, {}
    for layer in chain:
        config, provenance = merge.apply(config, layer.doc, layer.kind, layer.name, provenance)
        on.update(layer.doc.get("capabilities") or {})
    return config, tuple(sorted(k for k, v in on.items() if v is True))


def _walk(base, rel, found, problems):
    """Collect `(group, file)` pairs from the folder `rel` below `base`, and
    walk the folders in it. A folder is a group named by its path below
    `compass-fixtures/`; a fixture directly in `compass-fixtures/` has no
    group. What cannot be read as a fixture is a problem, so a fixture that was
    never run cannot pass unseen: a `.yaml` file, a linked folder (not followed,
    so a link cannot lead outside the preset) and a folder with nothing in it."""
    here = os.path.join(base, rel) if rel else base
    shown = f"{FIXTURE_DIR}/{rel}" if rel else FIXTURE_DIR
    holds = False
    for name in sorted(os.listdir(here)):
        if name.startswith("."):
            continue
        path = os.path.join(here, name)
        inside = f"{rel}/{name}" if rel else name
        where = f"{FIXTURE_DIR}/{inside}"
        holds = True
        if os.path.islink(path):
            # Whatever the link names (a file, a folder, nothing, a place outside
            # the preset) is neither read nor printed.
            problems.append(f"{where}: a link, not a file, so it is not followed; put the "
                            f"fixture itself in {FIXTURE_DIR}/")
        elif os.path.isdir(path):
            depth = len(inside.split("/"))
            if not GROUP_SEGMENT.fullmatch(name):
                problems.append(f"{where}: not read; a group folder is named with lower-case "
                                f"letters, digits and hyphens, starting with a letter or digit")
            elif depth > GROUP_DEPTH:
                problems.append(f"{where}: not read; groups go {GROUP_DEPTH} folders deep at most")
            else:
                _walk(base, inside, found, problems)
        elif os.path.splitext(name)[1].lower() in (FIXTURE_SUFFIX, ".yaml") \
                and not name.endswith(FIXTURE_SUFFIX):
            problems.append(f"{where}: not read; fixture files end in {FIXTURE_SUFFIX}, "
                            f"in lower case")
        elif name.endswith(FIXTURE_SUFFIX):
            if os.path.isfile(path):
                found.append((rel or None, inside))
            else:
                problems.append(f"{where}: not a regular file, so it is not run")
    if rel and not holds:
        problems.append(f"{shown}: a group with no fixture file, so nothing in it runs")


def _fixture_files(folder, problems):
    """`(group, file)` pairs in order: the fixtures directly in
    `compass-fixtures/` first, then each group by name, each by file name.
    `file` is the path below `compass-fixtures/`."""
    base = os.path.join(folder, FIXTURE_DIR)
    if not os.path.isdir(base):
        return []
    found = []
    _walk(base, "", found, problems)
    return sorted(found, key=lambda pair: (pair[0] or "", pair[1]))


def _format_problem(doc, dimensions):
    """What is wrong with a fixture's shape, or None. `dimensions` are the
    names the configuration's assessment may hold, besides `labels`."""
    if not isinstance(doc, dict):
        return "a fixture is a mapping with an assessment and an expect"
    unknown = sorted(str(k) for k in doc if k not in FIXTURE_KEYS)
    if unknown:
        return (f"unknown key '{unknown[0]}'; a fixture holds {', '.join(FIXTURE_KEYS)}")
    if "name" in doc and not (isinstance(doc["name"], str) and doc["name"].strip()):
        return "'name' must be text"
    for key in ("assessment", "expect"):
        if not isinstance(doc.get(key), dict) or not doc[key]:
            return f"'{key}' is missing or is not a mapping with something in it"
    unknown = sorted(str(k) for k in doc["assessment"] if k != "labels" and k not in dimensions)
    if unknown:
        return (f"unknown assessment key '{unknown[0]}'; an assessment holds labels and "
                f"the dimensions {', '.join(sorted(dimensions))}")
    labels = doc["assessment"].get("labels", [])
    if not (isinstance(labels, list) and all(isinstance(i, str) for i in labels)):
        return "assessment.labels must be a list of text"
    unknown = sorted(str(k) for k in doc["expect"] if k not in EXPECT_KEYS)
    if unknown:
        return (f"unknown expect key '{unknown[0]}'; expect holds {', '.join(EXPECT_KEYS)}")
    expect = doc["expect"]
    if "approach" in expect and not isinstance(expect["approach"], str):
        return "expect.approach must be a name"
    for key in ("gates", "checks"):
        if key in expect and not (isinstance(expect[key], list)
                                  and all(isinstance(i, str) for i in expect[key])):
            return f"expect.{key} must be a list of ids"
    if "stages" in expect:
        stages = expect["stages"]
        if not (isinstance(stages, dict) and stages and all(
                isinstance(k, str) and isinstance(v, str) for k, v in stages.items())):
            return "expect.stages must map at least one stage to a mode"
    return None


def _run_fixture(folder, name, config, capabilities):
    path = os.path.join(folder, FIXTURE_DIR, name)
    stem = os.path.basename(name)[:-len(FIXTURE_SUFFIX)]
    where = f"{FIXTURE_DIR}/{name}"
    try:
        doc = load_yaml_strict(path)
    except StrictYamlError as exc:
        return FixtureResult(name, stem, "error", message=str(exc).replace(path, where))
    except (OSError, UnicodeDecodeError) as exc:
        return FixtureResult(name, stem, "error", message=f"{where} cannot be read: "
                             f"{getattr(exc, 'strerror', None) or 'not UTF-8 text'}")
    wrong = _format_problem(doc, set(config.get("dimensions") or {}))
    if wrong:
        return FixtureResult(name, stem, "error", message=wrong)
    stem = doc.get("name") or stem
    try:
        got = obligations.obligations(config, doc["assessment"], capabilities=capabilities)
    except (CompassError, ValueError, KeyError, TypeError) as exc:
        return FixtureResult(name, stem, "error", message=f"the assessment cannot run: {exc}")
    if isinstance(got, obligations.Refused):
        return FixtureResult(name, stem, "error",
                             message=f"the configuration refuses this assessment: {got.reason}")
    mismatches = _compare(doc["expect"], got)
    return FixtureResult(name, stem, "fail" if mismatches else "pass", mismatches)


def _mismatch(field_name, expected, actual):
    return {"field": field_name, "expected": expected, "actual": actual}


def _compare(expect, got):
    """The differences between what a fixture expects and what the evaluator
    computed, in the order approach, gates, stages, checks. A set (gates,
    checks) is compared as a sorted list, so its order in the file does not
    matter; only the stages a fixture names are compared."""
    found = []
    if "approach" in expect and expect["approach"] != got.approach:
        found.append(_mismatch("approach", expect["approach"], got.approach))
    if "gates" in expect and sorted(expect["gates"]) != sorted(got.gate_set):
        found.append(_mismatch("gates", sorted(expect["gates"]), sorted(got.gate_set)))
    for stage, mode in sorted((expect.get("stages") or {}).items()):
        if got.stage_mode.get(stage) != mode:
            found.append(_mismatch(f"stages.{stage}", mode, got.stage_mode.get(stage)))
    if "checks" in expect:
        owed = sorted({c for ids in got.gate_checks.values() for c in ids})
        if sorted(expect["checks"]) != owed:
            found.append(_mismatch("checks", sorted(expect["checks"]), owed))
    return found


def run(folder, fetch=False):
    """The `Result` of testing the preset in `folder`."""
    folder = os.fspath(folder)
    if not os.path.exists(folder):
        raise CompassError(f"{shown(folder)}: no such folder")
    if not os.path.isdir(folder):
        raise CompassError(f"{shown(folder)}: not a folder; give the folder that holds "
                           f"the preset's {layers.PROJECT_FILE}")
    path = os.path.join(folder, layers.PROJECT_FILE)
    if not os.path.isfile(path):
        raise CompassError(f"{shown(folder)}: no {layers.PROJECT_FILE} here; a preset is a "
                           f"folder that holds one")
    # A file that cannot be read is an input error. One that reads but is not
    # valid YAML is a lint error (`L-LOAD`), which the report can show.
    try:
        with open(path, "rb") as fh:
            fh.read().decode("utf-8")
    except OSError as exc:
        raise CompassError(f"{shown(folder)}: {layers.PROJECT_FILE} cannot be read: "
                           f"{exc.strerror}") from exc
    except UnicodeDecodeError as exc:
        raise CompassError(f"{shown(folder)}: {layers.PROJECT_FILE} cannot be read: it is "
                           f"not UTF-8 text") from exc
    result = Result(shown(folder))
    result.lint, chain = _lint(folder, fetch)
    _relabel(result.lint)
    if chain is None:
        return result
    config, capabilities = resolve(chain)
    for group, name in _fixture_files(folder, result.problems):
        ran = _run_fixture(folder, name, config, capabilities)
        ran.group, ran.file = group, os.path.basename(name)
        result.fixtures.append(ran)
    if not result.fixtures:
        result.problems.insert(0, f"no fixtures: {FIXTURE_DIR}/ holds no {FIXTURE_SUFFIX} "
                               f"file, so nothing shows what the preset computes")
    result.fixtures_run = True
    return result


def group_counts(result):
    """One `{group, fixtures, passed, failed, result}` object for each group that holds
    a fixture, by group name. A fixture outside every group is in `totals` only."""
    counts = {}
    for f in result.fixtures:
        if f.group is None:
            continue
        row = counts.setdefault(f.group, {"group": f.group, "fixtures": 0, "passed": 0,
                                          "failed": 0, "result": "pass"})
        row["fixtures"] += 1
        row["passed" if f.status == "pass" else "failed"] += 1
        row["result"] = "pass" if row["failed"] == 0 else "fail"
    return [counts[name] for name in sorted(counts)]


def passed(result):
    return result.lint.ok and result.fixtures_run and not result.problems \
        and all(f.status == "pass" for f in result.fixtures)


def text(result):
    ok = passed(result)
    count = len(result.fixtures)
    won = sum(1 for f in result.fixtures if f.status == "pass")
    lines = [f"compass policy test: {'PASS' if ok else 'FAIL'}", f"  preset: {result.preset}"]
    lines += policy_lint.lint_text(result.lint)[1:]
    if not result.fixtures_run:
        return lines + ["  fixtures: not run (the lint failed)"]
    lines.append(f"  fixtures: {count} run, {won} passed, {count - won} failed")
    for f in result.fixtures:
        where = f"{FIXTURE_DIR}/{f.group}/{f.file}" if f.group else f"{FIXTURE_DIR}/{f.file}"
        lines.append(f"  - {f.status.upper()} {f.name} ({where})")
        for m in f.mismatches:
            lines.append(f"      {m['field']}: expected {_show(m['expected'])}, "
                         f"actual {_show(m['actual'])}")
        for line in (f.message or "").splitlines():
            lines.append(f"      {line.strip()}")
    lines += [f"  group {g['group']}: {g['fixtures']} run, {g['passed']} passed, "
              f"{g['failed']} failed" for g in group_counts(result)]
    lines += [f"  problem: {p}" for p in result.problems]
    return lines


def _show(value):
    return value if isinstance(value, str) else json.dumps(value)


def report_json(result):
    """The report as the documented dictionary."""
    count = len(result.fixtures)
    won = sum(1 for f in result.fixtures if f.status == "pass")
    return {
        "schema": JSON_SCHEMA_VERSION,
        "preset": result.preset,
        "result": "pass" if passed(result) else "fail",
        "lint": {"ok": result.lint.ok, "stopped_after": result.lint.stopped_after,
                 "findings": policy_lint.lint_json(result.lint)["findings"]},
        "fixtures_run": result.fixtures_run,
        "totals": {"fixtures": count, "passed": won, "failed": count - won},
        "fixtures": [{"file": f.file, "name": f.name, "status": f.status,
                      "mismatches": f.mismatches, "message": f.message, "group": f.group}
                     for f in result.fixtures],
        "problems": result.problems,
        "groups": group_counts(result),
    }
