"""Dependencies between issues: the `depends_on` field, its verbs, the derived
block and every reader of it.

Scenario ids DBI-1 to DBI-20 are in the acceptance criteria of the issue
`dependencies-between-issues`; this file holds the ones the field, the
derivation, the hook and the deciding readers own.

Every test runs without a network: each fixture project leaves the GitHub
switches off and links no GitHub issue, a `gh` on PATH fails the test if
anything calls it, and the tests that need git use a local repository only.

Run as a script, this file writes the captures the backward-compatibility test
compares with:

    python3 tests/test_issue_dependencies.py --capture <cli folder> <out folder>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLI_DIR = ROOT / "cli"
FIXTURES = HERE / "fixtures" / "issue-dependencies"
FIXED_CLOCK = HERE / "fixed_clock.py"
#: Every command in the backward-compatibility comparison runs at this instant,
#: so ages and "done this week" read the same on any day.
FIXED_AT = "2026-10-13T12:00:00Z"

sys.path.insert(0, str(CLI_DIR))
import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
import yaml  # noqa: E402

GH_SHIM = """#!/bin/sh
echo "gh $*" >> "{log}"
echo "gh was called during a test that must make no network call" >&2
exit 1
"""


# --- running the CLI -----------------------------------------------------------

def _bin(root):
    """A folder on PATH holding a `gh` that records each call and fails."""
    folder = Path(root) / ".test-bin"
    if not (folder / "gh").exists():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "gh").write_text(GH_SHIM.format(log=Path(root) / ".gh-calls"))
        (folder / "gh").chmod(0o755)
    return folder


def env_for(root, **extra):
    (Path(root) / ".home").mkdir(parents=True, exist_ok=True)
    env = {"PATH": f"{_bin(root)}:{Path(sys.executable).parent}:/usr/bin:/bin",
           "HOME": str(Path(root) / ".home"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "NO_COLOR": "1", "COLUMNS": "100", "COMPASS_RENDER_AFTER": "0",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env.update(extra)
    return env


def compass(root, *args, cli_dir=CLI_DIR, clock=None, cwd=None, timeout=120, **extra):
    """Run `compass <args>` in `root`; with `clock`, under the fixed clock. A
    walk that does not end fails the test at `timeout` seconds."""
    if clock:
        cmd = [sys.executable, str(FIXED_CLOCK), "--cli", str(cli_dir), "--at", clock,
               "--", *args]
    else:
        cmd = [sys.executable, str(Path(cli_dir) / "compass"), *args]
    return subprocess.run(cmd, cwd=str(cwd or root), env=env_for(root, **extra),
                          capture_output=True, text=True, timeout=timeout)


def assert_no_gh_call(root):
    calls = Path(root) / ".gh-calls"
    assert not calls.exists(), calls.read_text()


# --- the backward-compatibility comparison -------------------------------------

#: Each command's output on the project `build_dbi5_project` writes, captured
#: from the code before `depends_on` existed.
DBI5_CAPTURES = FIXTURES / "captures.yml"
_DBI5_ASSESSMENT = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
                    "goal": "delivery", "role": "engineer", "labels": ["cli"]}
_DBI5_REASON = "every regular approach carries one"


def _dbi5_manifest(slug, **extra):
    m = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
         "assessment": dict(_DBI5_ASSESSMENT), "delivery_approach": "regular",
         "stages": dict(STAGES),
         "gates": [{"id": g, "status": "pending", "evidence": []} for g in GATES],
         "scenarios": [{"id": f"{slug.upper()}-1", "title": f"{slug} works", "intent": "INT-1",
                        "tests": [f"tests/test_{slug.replace('-', '_')}.py::test_it"]}]}
    m.update(extra)
    return m


def _dbi5_document(slug, kind, status):
    return {"id": "ART-" + kind.upper().replace("-", "_"), "kind": kind, "status": status,
            "reason": _DBI5_REASON, "path": f"docs/compass/2026-10-01-{slug}/{kind}.md"}


def _dbi5_issues():
    """One issue at each workflow state, none holding `depends_on`."""
    ac = lambda slug: _dbi5_document(slug, "acceptance-criteria", "approved")  # noqa: E731
    passed = [{"id": g, "status": "pass", "evidence": []} for g in GATES]
    return {
        # Not assessed: no delivery approach, so backlog at assess.
        "queued": {"schema_version": "3.0", "issue": "queued", "created": "2026-09-20"},
        # Assessed and held by a person.
        "held": _dbi5_manifest("held", status="backlog", parked_reason="waiting for a budget"),
        # A hold with a stored blocked flag left on it: readers ignore the flag.
        "held-flag": _dbi5_manifest("held-flag", status="backlog", blocked={
            "reason": "old flag", "at": "2026-10-02T00:00:00+00:00"}),
        # Refine runs and its review is not written: backlog at refine.
        "refining": _dbi5_manifest("refining", stages=dict(STAGES, refine="lightweight"),
                                   artifacts=[ac("refining")]),
        # Defined, refine skipped, work not started.
        "ready": _dbi5_manifest("ready", artifacts=[ac("ready")]),
        # A design registered and breakdown runs: in progress at breakdown.
        "planning": _dbi5_manifest("planning", stages=dict(STAGES, breakdown="lightweight"),
                                   artifacts=[ac("planning"),
                                              _dbi5_document("planning", "technical-design",
                                                             "draft")]),
        # A red on record: in progress at implement.
        "building": _dbi5_manifest("building"),
        # In progress with the stored blocked flag, which counts here.
        "flagged": _dbi5_manifest("flagged", blocked={"reason": "waits for the vendor",
                                                      "at": "2026-10-03T00:00:00+00:00"}),
        # Every scenario tested and a gate passed: in review at verify.
        "reviewing": _dbi5_manifest(
            "reviewing", evidence=[{"id": "EV-1", "type": "test-run", "scenario": "REVIEWING-1",
                                    "path": "evidence/green.json"}],
            gates=[passed[0], {"id": GATES[1], "status": "pending", "evidence": []}]),
        "shipped": _dbi5_manifest("shipped", status="done", close_reason="completed",
                                  land_timestamp="2026-10-12T10:00:00+00:00", gates=passed),
        "dropped": _dbi5_manifest("dropped", status="done", close_reason="not-planned"),
        "dup": _dbi5_manifest("dup", status="done", close_reason="duplicate",
                              duplicate_of="shipped"),
        # A stored status Compass does not set.
        "odd": _dbi5_manifest("odd", status="wibble"),
    }


def build_dbi5_project(root):
    """Write the backward-compatibility project under `root`. A folder with no
    manifest stands for an issue the board cannot place."""
    root = Path(root)
    work = root / ".compass" / "work"
    for slug, m in _dbi5_issues().items():
        d = work / slug
        d.mkdir(parents=True)
        (d / "manifest.yml").write_text(yaml.safe_dump(m, sort_keys=False), encoding="utf-8")
        if m.get("delivery_approach"):
            (d / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n\nregular\n")
        for art in m.get("artifacts") or []:
            doc = root / art["path"]
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(f"# {art['kind']} - {slug}\n")
        if slug in ("building", "flagged"):
            (d / "evidence").mkdir()
            sid = slug.upper() + "-1"
            (d / "evidence" / f"red-{sid}.json").write_text(
                json.dumps(red_payload(sid), indent=2))
    (work / "broken").mkdir(parents=True)
    return root


def _dbi5_slugs(root):
    return sorted(p.name for p in (Path(root) / ".compass" / "work").iterdir() if p.is_dir())


def _masked(text, root):
    """The output with the project's own path and the board page's Generated
    line replaced, so two runs in different folders compare."""
    for form in sorted({str(root), os.path.realpath(root)}, key=len, reverse=True):
        text = text.replace(form, "<ROOT>")
    return "\n".join("<GENERATED LINE>" if "Generated" in line else line
                     for line in text.split("\n"))


def _result(done, root):
    return _masked("exit %d\n--- stdout\n%s--- stderr\n%s" % (
        done.returncode, done.stdout, done.stderr), root)


def dbi5_outputs(root, cli_dir=CLI_DIR):
    """Every output the comparison reads, by capture file name, in the order
    the commands run. The commands that write (the board page and the issue
    pages) run after the ones that only read."""
    root = Path(root)
    out = {}
    run = lambda *a: compass(root, *a, cli_dir=cli_dir, clock=FIXED_AT)  # noqa: E731
    slugs = _dbi5_slugs(root)
    for slug in slugs:
        out[f"next-{slug}.txt"] = _result(run("next", "--issue", slug), root)
        out[f"lint-{slug}.txt"] = _result(run("issue", "lint", "--issue", slug), root)
    out["flow.txt"] = _result(run("flow"), root)
    out["flow-json.txt"] = _result(run("flow", "--json"), root)
    page = root / "board.html"
    out["board-render.txt"] = _result(run("board", "render", "--no-open", "--out", str(page)),
                                      root)
    out["board-page.html"] = _masked(page.read_text(encoding="utf-8"), root)
    for slug in slugs:
        out[f"render-{slug}.txt"] = _result(run("issue", "render", "--issue", slug), root)
        for doc in sorted((root / "docs" / "compass").glob(f"*-{slug}/README.md")):
            out[f"page-{slug}.md.txt"] = _masked(doc.read_text(encoding="utf-8"), root)
    index = root / "docs" / "compass" / "README.md"
    if index.exists():
        out["index.md.txt"] = _masked(index.read_text(encoding="utf-8"), root)
    return out


class _Block(str):
    """Text the capture file writes as a literal block, so a diff reads line by line."""


class _CaptureDumper(yaml.SafeDumper):
    pass


_CaptureDumper.add_representer(
    _Block, lambda dumper, text: dumper.represent_scalar(
        "tag:yaml.org,2002:str", str(text), style="|"))


def _capture(cli_dir, out_file):
    import tempfile
    root = build_dbi5_project(Path(tempfile.mkdtemp(prefix="dbi5-")) / "project")
    outputs = {name: _Block(text) for name, text in dbi5_outputs(root, cli_dir).items()}
    assert_no_gh_call(root)
    header = ("# What compass next, issue lint, flow, flow --json, board render and issue\n"
              "# render printed on the project that build_dbi5_project in\n"
              "# tests/test_issue_dependencies.py writes, captured from the code before\n"
              "# depends_on existed, under a fixed clock. The project's own folder reads\n"
              "# <ROOT> and the board page's Generated line is masked.\n")
    Path(out_file).write_text(
        header + yaml.dump(outputs, Dumper=_CaptureDumper, sort_keys=False, width=1000,
                           allow_unicode=True),
        encoding="utf-8")


def _split_result(text):
    head, rest = text.split("\n--- stdout\n", 1)
    stdout, stderr = rest.split("--- stderr\n", 1)
    return head, stdout, stderr


def test_dbi_5_manifest_without_key_reads_unchanged(tmp_path):
    captured = yaml.safe_load(DBI5_CAPTURES.read_text(encoding="utf-8"))
    root = build_dbi5_project(tmp_path / "project")
    manifests = {p: p.read_bytes() for p in (root / ".compass" / "work").glob("*/manifest.yml")}
    outputs = dbi5_outputs(root)
    assert list(outputs) == list(captured)
    for name, text in outputs.items():
        if name != "flow-json.txt":
            assert text == captured[name], name
    # The one difference: each --json row gains "depends_on": [].
    head, stdout, stderr = _split_result(outputs["flow-json.txt"])
    was_head, was_stdout, was_stderr = _split_result(captured["flow-json.txt"])
    assert (head, stderr) == (was_head, was_stderr)
    now, was = json.loads(stdout), json.loads(was_stdout)
    rows = [row for section in now["board"].values() for row in section]
    assert rows and all(row["depends_on"] == [] for row in rows), now

    def strip(node):
        # A row shows under `board` and again under `sections`.
        if isinstance(node, dict):
            if "slug" in node:
                assert node.pop("depends_on") == [], node
            for value in node.values():
                strip(value)
        elif isinstance(node, list):
            for value in node:
                strip(value)
    strip(now)
    assert json.dumps(now, indent=1) == json.dumps(was, indent=1)
    # No manifest is rewritten, so no migrate is needed or offered.
    assert {p: p.read_bytes() for p in manifests} == manifests
    assert not any("migrate" in text for text in outputs.values())
    assert_no_gh_call(root)


# --- fixture projects -----------------------------------------------------------

STAGES = {"assess": "thorough", "define": "thorough", "refine": "skipped",
          "plan": "thorough", "breakdown": "skipped", "implement": "thorough",
          "verify": "thorough", "ship": "thorough"}
GATES = ("verify.correctness", "verify.traceability")


def red_payload(scenario):
    payload = {"command": "pytest -q", "scenario": scenario, "exit_code": 1, "passed": False,
               "timestamp": "2026-10-05T00:00:00+00:00", "log_excerpt": "1 failed",
               "record_id": "fixture0000000000"}
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    return payload


class Project:
    """A Compass project under a temporary folder, with issues whose records
    put them at a chosen stage. No settings file, so every GitHub switch is off."""

    def __init__(self, root):
        self.root = Path(root)
        self.work = self.root / ".compass" / "work"
        self.work.mkdir(parents=True, exist_ok=True)
        (self.root / "src").mkdir(exist_ok=True)

    def dir(self, slug):
        return self.work / slug

    def manifest(self, slug):
        return yaml.safe_load((self.dir(slug) / "manifest.yml").read_text(encoding="utf-8"))

    def write(self, slug, manifest):
        (self.dir(slug) / "manifest.yml").write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    def bytes(self, slug):
        return (self.dir(slug) / "manifest.yml").read_bytes()

    def issue(self, slug, at="implement", *, close=None, hold=False, review=False,
              depends=None, marker=False, **extra):
        """Write issue `slug` with the records that put it at stage `at`.

        `close` closes it with that reason; `hold` sets it aside; `review`
        passes one gate, so an issue past implement reads as in review;
        `depends` is written as `depends_on` as given; `marker` adds the
        `.red` marker the hook looks for."""
        d = self.dir(slug)
        (d / "evidence").mkdir(parents=True, exist_ok=True)
        sid = slug.upper() + "-1"
        stages = dict(STAGES)
        m = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
             "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                            "size": "small", "goal": "delivery", "role": "engineer"},
             "delivery_approach": "regular", "stages": stages,
             "gates": [{"id": g, "status": "pending", "evidence": []} for g in GATES],
             "scenarios": [], "artifacts": [], "evidence": []}
        order = list(STAGES)
        index = order.index(at)
        if index >= order.index("refine"):
            m["scenarios"] = [{"id": sid, "title": f"{slug} works", "intent": "INT-1",
                               "tests": [f"tests/test_{slug.replace('-', '_')}.py::test_it"]}]
        if at == "refine":
            stages["refine"] = "lightweight"
        if at == "breakdown":
            stages["breakdown"] = "lightweight"
            m["artifacts"].append({"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
                                   "status": "draft", "reason": "every regular approach carries one",
                                   "path": f"docs/compass/2026-10-01-{slug}/technical-design.md"})
        if index >= order.index("implement"):
            (d / "evidence" / f"red-{sid}.json").write_text(json.dumps(red_payload(sid)))
        if index >= order.index("verify"):
            m["evidence"].append({"id": "EV-1", "type": "test-run", "scenario": sid,
                                  "path": "evidence/green.json"})
        if index >= order.index("ship"):
            for g in m["gates"]:
                g["status"] = "pass"
        elif review:
            m["gates"][0]["status"] = "pass"
        if close:
            m["status"] = "done"
            m["close_reason"] = close
            if close == "duplicate":
                m["duplicate_of"] = "other"
        if hold:
            m["status"] = "backlog"
        if depends is not None:
            m["depends_on"] = depends
        m.update(extra)
        self.write(slug, m)
        (d / "delivery-approach.md").write_text(f"# Delivery approach - {slug}\n")
        if marker:
            (d / ".red").write_text("")
        return d


def dep(issue, until="done", reason="needs it"):
    return {"issue": issue, "reason": reason, "until": until}


def next_line(project, slug):
    done = compass(project.root, "next", "--issue", slug)
    assert done.returncode == 0, done
    return done.stdout


def flow_rows(project):
    done = compass(project.root, "flow", "--json")
    assert done.returncode == 0, done
    board = json.loads(done.stdout)["board"]
    return {row["slug"]: row for rows in board.values() for row in rows}


# --- DBI-8: the until vocabulary --------------------------------------------------

#: (until, how the depended-on issue is set up, whether the waiting issue is blocked)
UNTIL_TABLE = [
    ("done", dict(at="verify", review=True), True),
    ("done", dict(at="ship", close="completed"), False),
    ("done", dict(at="ship", close="not-planned"), True),
    ("done", dict(at="ship", close="duplicate"), True),
    ("in-review", dict(at="implement"), True),
    ("in-review", dict(at="verify", review=True), False),
    ("plan", dict(at="refine"), True),
    ("plan", dict(at="plan"), False),
    ("plan", dict(at="implement"), False),
    ("plan", dict(at="breakdown", hold=True), False),
    ("breakdown", dict(at="implement"), False),
    ("ship", dict(at="verify"), True),
    ("ship", dict(at="ship", close="completed"), False),
]


def test_dbi_8_until_vocabulary(tmp_path):
    from compass_pkg import lifecycle
    project = Project(tmp_path)
    expected = {}
    for n, (until, setup, blocked) in enumerate(UNTIL_TABLE):
        waiting, other = f"a{n}", f"b{n}"
        project.issue(other, **setup)
        project.issue(waiting, "implement", depends=[dep(other, until)])
        close = setup.get("close")
        if not blocked:
            expected[waiting] = None
        elif close and close != "completed":
            expected[waiting] = f"waits for {other}, which was closed as {close}"
        else:
            expected[waiting] = f"waits for {other} to reach {until}"
    read = lifecycle.checkout_reader(str(project.work))
    rows = flow_rows(project)
    for n, row in enumerate(UNTIL_TABLE):
        waiting = f"a{n}"
        manifest = project.manifest(waiting)
        deps = lifecycle.judge(manifest, waiting, read)
        derived = lifecycle.dependency_block(manifest, str(project.dir(waiting)), deps)
        assert derived == expected[waiting], (row, derived)
        line = next_line(project, waiting)
        assert line.startswith("Implement"), (row, line)
        if expected[waiting]:
            assert line.rstrip("\n").endswith(" | blocked: " + expected[waiting]), (row, line)
        else:
            assert "blocked" not in line, (row, line)
        assert rows[waiting].get("blocked") == expected[waiting], (row, rows[waiting])
    assert_no_gh_call(project.root)


# --- DBI-1 to DBI-4: the verbs ----------------------------------------------------

def depends(project, *args, slug="a"):
    # The cycle walk ends in well under a second; a walk with no visited set
    # never does, so a short timeout turns it into a failure.
    return compass(project.root, "issue", "depends", *args, "--issue", slug, timeout=30)


def assert_schema_shape(entries):
    """`depends_on` against its schema node: with jsonschema when installed,
    and by its declared keys and values either way."""
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    node = schema["properties"]["depends_on"]
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        jsonschema.validate(entries, node)
    item = node["items"]
    for entry in entries:
        assert list(entry) == item["required"] == list(item["properties"]), entry
        assert entry["until"] in item["properties"]["until"]["enum"], entry
        assert entry["issue"].strip() and entry["reason"].strip(), entry


def test_dbi_1_depends_add_writes_the_shape(tmp_path):
    project = Project(tmp_path)
    for slug in ("a", "b", "c"):
        project.issue(slug, "define")
    assert "depends_on" not in project.manifest("a")
    done = depends(project, "add", "b", "--reason", "needs the parse cache")
    assert done.returncode == 0, done
    manifest = project.manifest("a")
    assert manifest["depends_on"] == [
        {"issue": "b", "reason": "needs the parse cache", "until": "done"}]
    assert list(manifest["depends_on"][0]) == ["issue", "reason", "until"]
    assert manifest["schema_version"] == "3.0"
    assert_schema_shape(manifest["depends_on"])
    assert "a now waits for b to reach done" in done.stdout, done
    done = depends(project, "add", "c", "--reason", "shares the hook", "--until", "in-review")
    assert done.returncode == 0, done
    manifest = project.manifest("a")
    assert [e["issue"] for e in manifest["depends_on"]] == ["b", "c"]
    assert manifest["depends_on"][1]["until"] == "in-review"
    assert_schema_shape(manifest["depends_on"])
    lint = compass(project.root, "issue", "lint", "--issue", "a")
    assert "depends_on" not in lint.stdout, lint
    assert_no_gh_call(project.root)


def test_dbi_2_depends_remove_removes_one_entry(tmp_path):
    project = Project(tmp_path)
    for slug in ("b", "c"):
        project.issue(slug, "define")
    project.issue("a", "define", depends=[dep("b"), dep("c")])
    done = depends(project, "remove", "b")
    assert done.returncode == 0, done
    assert [e["issue"] for e in project.manifest("a")["depends_on"]] == ["c"]
    done = depends(project, "remove", "c")
    assert done.returncode == 0, done
    assert "depends_on" not in project.manifest("a")
    before = project.bytes("a")
    done = depends(project, "remove", "b")
    assert done.returncode == 2, done
    assert "b is not a dependency of a" in done.stderr, done
    assert project.bytes("a") == before
    project.issue("a", "define", depends=[dep("gone")])
    done = depends(project, "remove", "gone")
    assert done.returncode == 0, done
    assert "depends_on" not in project.manifest("a")
    assert_no_gh_call(project.root)


def test_dbi_3_depends_add_input_checks(tmp_path):
    from compass_pkg import lifecycle
    project = Project(tmp_path)
    project.issue("a", "define")
    project.issue("b", "define")
    nine = ", ".join(lifecycle.UNTIL_VALUES)
    assert nine == "done, in-review, define, refine, plan, breakdown, implement, verify, ship"
    cases = [
        (["a", "--reason", "self"], "cannot depend on itself", False),
        (["b", "--reason", "x", "--until", "ready"], "'ready' is not an until value", True),
        (["b", "--reason", "x", "--until", "Done"], "'Done' is not an until value", True),
        (["b", "--reason", "   "], "--reason is empty", False),
        (["b"], "--reason", False),
        (["../b", "--reason", "x"], "not one path segment", False),
    ]
    before = project.bytes("a")
    for args, problem, lists_values in cases:
        done = depends(project, "add", *args)
        assert done.returncode == 2, (args, done)
        assert problem in done.stderr, (args, done)
        assert (nine in done.stderr) == lists_values, (args, done)
        assert project.bytes("a") == before, args
    project.issue("c", "define")
    project.issue("a", "define", depends=[dep("c"), dep("b"), dep("x-later")])
    done = depends(project, "add", "b", "--reason", "new reason", "--until", "plan")
    assert done.returncode == 0, done
    assert "updated the entry for b" in done.stdout, done
    assert project.manifest("a")["depends_on"] == [
        dep("c"), {"issue": "b", "reason": "new reason", "until": "plan"}, dep("x-later")]
    assert_no_gh_call(project.root)


def test_dbi_4_cycle_is_refused(tmp_path):
    project = Project(tmp_path)
    project.issue("a", "define")
    project.issue("b", "define", depends=[dep("a")])
    before = project.bytes("a")
    done = depends(project, "add", "b", "--reason", "x")
    assert done.returncode == 2, done
    assert "a -> b -> a" in done.stderr, done
    assert project.bytes("a") == before
    project.issue("b", "define", depends=[dep("c")])
    project.issue("c", "define", depends=[dep("a")])
    done = depends(project, "add", "b", "--reason", "x")
    assert done.returncode == 2, done
    assert "a -> b -> c -> a" in done.stderr, done
    assert project.bytes("a") == before
    project.issue("c", "define", depends=[dep("b")])
    done = depends(project, "add", "b", "--reason", "x")
    assert done.returncode == 0, done
    assert project.manifest("a")["depends_on"] == [dep("b", reason="x")]
    project.issue("a", "define")
    (project.dir("b") / "manifest.yml").write_text("issue: b\ndepends_on: [unclosed\n")
    done = depends(project, "add", "b", "--reason", "x")
    assert done.returncode == 0, done
    assert project.manifest("a")["depends_on"] == [dep("b", reason="x")]
    lines = [line for line in done.stderr.splitlines() if line.strip()]
    assert len(lines) == 1 and "b" in lines[0] and "could not be read" in lines[0] \
        and "no cycle check ran through it" in lines[0], done
    assert_no_gh_call(project.root)


# --- DBI-14 and DBI-15: lint ----------------------------------------------------------

def lint(project, slug="a"):
    # A cycle walk with no visited set never ends; the timeout makes it fail.
    return compass(project.root, "issue", "lint", "--issue", slug, timeout=30)


def dependency_lines(text):
    return [line for line in text.splitlines() if "depends_on" in line]


def test_dbi_14_missing_slug_is_a_lint_finding(tmp_path):
    project = Project(tmp_path)
    project.issue("a", "define", depends=[dep("speed-fix")])
    done = lint(project)
    assert done.returncode != 0, done
    finding = [line for line in dependency_lines(done.stdout) if "speed-fix" in line]
    assert finding and "depends on an issue that does not exist" in finding[0], done
    project.issue("fresh", "define")
    done = depends(project, "add", "speed-fix", "--reason", "x", slug="fresh")
    assert done.returncode == 0, done
    assert project.manifest("fresh")["depends_on"] == [dep("speed-fix", reason="x")]
    assert finding[0].strip().lstrip("- ") in done.stderr, (finding, done)
    project.issue("speed-fix", "define")
    done = lint(project)
    assert not dependency_lines(done.stdout), done
    assert done.returncode == 0, done
    assert_no_gh_call(project.root)


def test_dbi_15_lint_reports_hand_edited_faults(tmp_path):
    from compass_pkg import lifecycle
    nine = ", ".join(lifecycle.UNTIL_VALUES)
    shape = "the documented {issue, reason, until} shape"
    cases = [
        ([dep("b", until="soon")], ["until 'soon' is not a value", nine]),
        (["b"], [shape]),
        ([{"issue": "b", "until": "done"}], [shape]),
        ([dict(dep("b"), owner="sam")], [shape]),
        ([dep("b"), dep("b", until="plan")], ["names b twice"]),
        ([dep("b")], ["forms a cycle: a -> b -> c -> a"]),
        ([dep("closed")], ["closed", "not-planned"]),
    ]
    for number, (entries, names) in enumerate(cases):
        project = Project(tmp_path / str(number))
        project.issue("b", "define")
        project.issue("closed", "ship", close="not-planned")
        if names[0].startswith("forms a cycle"):
            # b also reaches a loop of its own, d and e, that never comes back
            # to a: the walk must end on it rather than go round it for ever.
            project.issue("b", "define", depends=[dep("d"), dep("c")])
            project.issue("c", "define", depends=[dep("a")])
            project.issue("d", "define", depends=[dep("e")])
            project.issue("e", "define", depends=[dep("d")])
        project.issue("a", "define", depends=entries)
        done = lint(project)
        assert done.returncode != 0, (entries, done)
        lines = dependency_lines(done.stdout)
        assert any(all(n in line for n in names) for line in lines), (entries, done)
        assert_no_gh_call(project.root)


# --- the pre-tool hook ------------------------------------------------------------------

HOOK = ROOT / "hooks" / "pre-tool.sh"


def hook(project, target, slug="a", path=None, hook_path=HOOK, **extra):
    """Run the pre-tool hook on an Edit of `target` for issue `slug`."""
    (project.root / ".compass" / "current-task").write_text(slug)
    env = env_for(project.root, CLAUDE_PROJECT_DIR=str(project.root), **extra)
    if path is not None:
        env["PATH"] = path
    event = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(target)}})
    return subprocess.run(["bash", str(hook_path)], input=event, capture_output=True,
                          text=True, env=env, timeout=120)


def code_file(project):
    return project.root / "src" / "app.py"


# --- DBI-6 and DBI-7: compass next and the implement-only scope ------------------------

def test_dbi_6_next_blocks_at_implement_until_done(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b")])
    before = project.bytes("a")
    line = next_line(project, "a")
    assert line.startswith("Implement"), line
    assert "blocked: waits for b to reach done" in line, line
    assert project.bytes("a") == before
    project.issue("c", "define")
    project.issue("a", "implement", depends=[dep("b"), dep("c", "plan")])
    before = project.bytes("a")
    line = next_line(project, "a")
    assert line.startswith("Implement"), line
    assert "blocked: waits for b to reach done; waits for c to reach plan" in line, line
    assert project.bytes("a") == before
    project.issue("b", "ship", close="completed")
    project.issue("c", "plan")
    line = next_line(project, "a")
    assert line.startswith("Implement") and "blocked" not in line, line
    assert project.bytes("a") == before
    assert_no_gh_call(project.root)


def _no_reader_blocks(project, slug="a"):
    """`compass next`, `issue_detail` and the board each report no dependency
    block for `slug`."""
    from compass_pkg import issue_detail, lifecycle
    from compass_pkg.core import load_manifest
    line = next_line(project, slug)
    assert "blocked" not in line, line
    manifest, _path = load_manifest(str(project.dir(slug)))
    facts = issue_detail.detail(manifest, str(project.dir(slug)),
                                read=lifecycle.checkout_reader(str(project.work)))
    assert facts.waits is None and facts.blocked is None, facts
    assert "blocked" not in flow_rows(project)[slug], flow_rows(project)[slug]
    return line


def test_dbi_7_stages_before_implement_not_blocked(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    for stage in ("define", "refine", "plan", "breakdown"):
        project.issue("a", stage, depends=[dep("b")])
        line = _no_reader_blocks(project)
        assert line.lower().startswith(stage), (stage, line)
        docs = project.root / "docs" / "compass" / "2026-10-01-a"
        for name in ("acceptance-criteria.md", "technical-design.md"):
            done = hook(project, docs / name)
            assert done.returncode == 0, (stage, name, done)
            assert "depends on" not in done.stderr, (stage, name, done)
    project.issue("a", "verify", depends=[dep("b")])
    assert _no_reader_blocks(project).startswith("Verify")
    for setup in (dict(hold=True), dict(close="not-planned")):
        project.issue("a", "implement", depends=[dep("b")], marker=True, **setup)
        _no_reader_blocks(project)
        done = hook(project, code_file(project))
        assert done.returncode == 0, (setup, done)
        assert "depends on" not in done.stderr and "waits-for-issue" not in done.stderr, done
    assert_no_gh_call(project.root)


# --- DBI-18 and DBI-13: the board data ----------------------------------------------------

def test_dbi_18_flow_json_gains_depends_on(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("d", "plan")
    project.issue("a", "plan", depends=[dep("b"), dep("gone", "plan", "a later issue")])
    rows = flow_rows(project)
    entries = rows["a"]["depends_on"]
    assert [list(e) for e in entries] == [["issue", "reason", "until", "state", "stage", "met"]] * 2
    assert entries[0] == {"issue": "b", "reason": "needs it", "until": "done",
                          "state": "in-progress", "stage": "implement", "met": False}
    assert entries[1] == {"issue": "gone", "reason": "a later issue", "until": "plan",
                          "state": None, "stage": None, "met": False}
    assert rows["d"]["depends_on"] == []
    assert all(row["depends_on"] == [] for slug, row in rows.items() if slug != "a")
    # Every key the rows held without depends_on is there with the same value.
    manifest = project.manifest("a")
    del manifest["depends_on"]
    project.write("a", manifest)
    before = flow_rows(project)
    for slug, row in rows.items():
        assert {k: v for k, v in row.items() if k != "depends_on"} == {
            k: v for k, v in before[slug].items() if k != "depends_on"}, slug
    assert_no_gh_call(project.root)


def test_dbi_13_derived_block_never_written(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    before = {slug: project.bytes(slug) for slug in ("a", "b")}
    assert "blocked: waits for b to reach done" in next_line(project, "a")
    assert flow_rows(project)["a"]["blocked"] == "waits for b to reach done"
    page = project.root / "board.html"
    for args in (("board", "render", "--no-open", "--out", str(page)),
                 ("issue", "render", "--issue", "a")):
        done = compass(project.root, *args)
        assert done.returncode == 0, done
    hook(project, code_file(project))
    assert {slug: project.bytes(slug) for slug in ("a", "b")} == before
    assert "blocked" not in project.manifest("a")
    done = compass(project.root, "issue", "blocked", "set", "--reason", "the vendor",
                   "--issue", "a")
    assert done.returncode == 0, done
    assert project.manifest("a")["blocked"]["reason"] == "the vendor"
    both = "the vendor; waits for b to reach done"
    assert flow_rows(project)["a"]["blocked"] == both
    done = compass(project.root, "flow")
    assert "BLOCKED: " + both in done.stdout, done
    done = compass(project.root, "board", "render", "--no-open", "--out", str(page))
    assert done.returncode == 0, done
    assert "blocked: " + both in page.read_text(encoding="utf-8")
    assert_no_gh_call(project.root)


# --- DBI-9 to DBI-12: the pre-tool hook ---------------------------------------------------

def _code(done):
    found = [code for code in ("waits-for-issue", "no-red-on-record", "reader-failed",
                               "red-marker-no-record") if f"[{code}]" in done.stderr]
    return found[0] if found else None


def test_dbi_9_hook_refuses_at_implement(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    done = hook(project, code_file(project))
    assert done.returncode == 2, done
    lines = done.stderr.strip().splitlines()
    assert lines[-1].endswith("[waits-for-issue]"), done
    assert "waits for b to reach done" in done.stderr, done
    assert "reads b as in-progress" in done.stderr, done
    assert "compass issue depends remove b" in done.stderr, done
    assert "`waits-for-issue`" in (ROOT / "docs" / "refusal-codes.md").read_text(encoding="utf-8")
    # A declared acceptance does not clear the wait.
    (project.dir("a") / ".red").unlink()
    (project.dir("a") / ".acceptance").write_text("")
    done = hook(project, code_file(project))
    assert done.returncode == 2 and _code(done) == "waits-for-issue", done
    project.issue("b", "ship", close="completed")
    done = hook(project, code_file(project))
    assert done.returncode == 0, done
    # A spike is never refused for a dependency.
    project.issue("b", "implement")
    (project.dir("a") / ".acceptance").unlink()
    (project.dir("a") / ".spike").write_text("")
    done = hook(project, code_file(project))
    assert done.returncode == 0, done
    # A hand-written cycle of three: the hook reads one level, so it refuses.
    project = Project(tmp_path / "three")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    project.issue("b", "implement", depends=[dep("c")])
    project.issue("c", "implement", depends=[dep("a")])
    done = hook(project, code_file(project))
    assert done.returncode == 2 and _code(done) == "waits-for-issue", done
    assert "compass issue depends remove b" in done.stderr, done
    assert_no_gh_call(project.root)


#: A `python3` that fails, as an install that cannot import compass_pkg does,
#: for the hook reader whose script holds the text in $FAKE_FAIL_ON, and runs
#: the real interpreter for every other call.
FAILING_PYTHON = """#!/usr/bin/env bash
if [ "${1:-}" = "-" ]; then
  body="$(cat)"
  if [ -n "${FAKE_FAIL_ON:-}" ] && printf '%s' "$body" | grep -qF -- "$FAKE_FAIL_ON"; then
    echo "ModuleNotFoundError: No module named 'compass_pkg'" >&2
    exit 1
  fi
  printf '%s\\n' "$body" | REALPY "$@"
  exit $?
fi
exec REALPY "$@"
"""


def test_dbi_10_hook_fails_safe(tmp_path):
    cases = [
        ("gone has no manifest", [dep("gone")], None, "gone",
         "depends on an issue that does not exist"),
        ("b does not parse", [dep("b")], "unparsable", "b", "cannot be read"),
        ("until soon", [dep("b", until="soon")], None, "b", "until 'soon' is not a value"),
        ("a bare string", ["b"], None, "b", "the documented {issue, reason, until} shape"),
        ("b depends on a", [dep("b")], "cycle", "b", "forms a cycle: a -> b -> a"),
    ]
    for number, (case, entries, b_setup, name, lint_text) in enumerate(cases):
        project = Project(tmp_path / str(number))
        project.issue("b", "implement", depends=[dep("a")] if b_setup == "cycle" else None)
        if b_setup == "unparsable":
            (project.dir("b") / "manifest.yml").write_text("issue: b\nstages: [unclosed\n")
        project.issue("a", "implement", depends=entries, marker=True)
        done = hook(project, code_file(project))
        assert done.returncode == 0, (case, done)
        warnings = [line for line in done.stderr.splitlines() if line.strip()]
        assert len(warnings) == 1, (case, done)
        assert f"'{name}'" in warnings[0] and "compass issue lint" in warnings[0], (case, done)
        assert "the edit is allowed" in warnings[0], (case, done)
        done = lint(project)
        assert done.returncode != 0, (case, done)
        assert any(lint_text in line for line in dependency_lines(done.stdout)), (case, done)
        assert_no_gh_call(project.root)
    # A reader that cannot run at all still refuses, as every hook reader does.
    project = Project(tmp_path / "broken")
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    fake = project.root / ".fake-bin"
    fake.mkdir()
    (fake / "python3").write_text(FAILING_PYTHON.replace("REALPY", sys.executable))
    (fake / "python3").chmod(0o755)
    done = hook(project, code_file(project), FAKE_FAIL_ON="hook_lines(",
                path=f"{fake}:{env_for(project.root)['PATH']}")
    assert done.returncode == 2, done
    assert _code(done) == "reader-failed" and "dependency reader" in done.stderr, done


def test_the_dependency_reader_runs_under_a_python3_older_than_3_10(tmp_path):
    """The hook's readers run under a python3 older than 3.10
    (docs/safety-contract.md), so the dependency reader must import there too:
    a reader that cannot import refuses every edit on an issue with a
    dependency."""
    old = shutil.which("python3", path="/usr/bin")
    if not old:
        pytest.skip("no /usr/bin/python3 on this machine")
    older = subprocess.run([old, "-c", "import sys; print(sys.version_info[:2] < (3, 10))"],
                           capture_output=True, text=True).stdout.strip()
    if older != "True":
        pytest.skip("/usr/bin/python3 is 3.10 or newer")
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    done = hook(project, code_file(project), path="/usr/bin:/bin")
    assert done.returncode == 2 and _code(done) == "waits-for-issue", done
    assert "Traceback" not in done.stderr, done


def _plant_cache_entry(project, slug, doc):
    """A parse-cache entry for `slug`'s manifest bytes that says `doc`."""
    from compass_pkg import parse_cache
    raw = (project.dir(slug) / "manifest.yml").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    folder = project.root / ".compass" / "cache" / "parsed_yaml"
    folder.mkdir(parents=True, exist_ok=True)
    entry = folder / f"{digest}.json"
    entry.write_text('{"format":%d,"pyyaml":%s,"source":"%s","doc":%s}' % (
        parse_cache.FORMAT, json.dumps(yaml.__version__), digest, parse_cache.encode(doc)))
    return entry


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


GIT_SHIM = """#!/bin/sh
echo "git $*" >> "{log}"
exec "{real}" "$@"
"""


def test_dbi_11_hook_reads_this_checkout_uncached(tmp_path):
    project = Project(tmp_path / "main")
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    _git(project.root, "init", "-q")
    _git(project.root, "add", "-A")
    _git(project.root, "commit", "-q", "-m", "fixture")
    other = tmp_path / "other"
    _git(project.root, "worktree", "add", "-q", str(other))
    Project(other).issue("b", "ship", close="completed")
    shim = project.root / ".git-shim"
    shim.mkdir()
    log = project.root / ".git-calls"
    (shim / "git").write_text(GIT_SHIM.format(log=log, real=shutil.which("git")))
    (shim / "git").chmod(0o755)
    path = f"{shim}:{env_for(project.root)['PATH']}"
    done = hook(project, code_file(project), path=path)
    assert done.returncode == 2 and _code(done) == "waits-for-issue", done
    assert not log.exists() or not log.read_text().strip(), log.read_text()
    done = depends(project, "remove", "b")
    assert done.returncode == 0, done
    done = hook(project, code_file(project), path=path)
    assert done.returncode == 0, done
    # A planted cache entry says b is in progress; b is done here.
    project.issue("b", "ship", close="completed")
    project.issue("a", "implement", depends=[dep("b")], marker=True)
    in_progress = dict(project.manifest("b"))
    for key in ("status", "close_reason"):
        in_progress.pop(key)
    entry = _plant_cache_entry(project, "b", in_progress)
    audit = _audit_dir(project.root)
    opened = project.root / ".audit.log"
    done = hook(project, code_file(project), PYTHONPATH=str(audit), DBI_AUDIT_LOG=str(opened))
    assert done.returncode == 0, done
    assert os.path.realpath(entry) not in _events(opened, "open"), "the cache entry was read"
    # Neither the dependency reader nor the derivation it calls names the cache.
    reader = HOOK.read_text(encoding="utf-8").split("hook_lines(", 1)[0].rsplit("<<'PYEOF'", 1)[1]
    assert "parse_cache" not in reader
    assert "parse_cache" not in (CLI_DIR / "compass_pkg" / "lifecycle.py").read_text(encoding="utf-8")
    assert_no_gh_call(project.root)


#: Logs every file a Python process opens and every folder it lists, to the
#: file $DBI_AUDIT_LOG names. Loaded at start-up as sitecustomize.
AUDIT_HOOK = """
import os
import sys

_log = os.environ.get("DBI_AUDIT_LOG")
if _log:
    _fd = os.open(_log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    _busy = []

    def _audit(event, args):
        if _busy or event not in ("open", "os.listdir", "os.scandir"):
            return
        path = args[0] if args else "."
        if path is None:
            path = "."
        if isinstance(path, int):
            return
        if isinstance(path, bytes):
            path = path.decode("utf-8", "replace")
        _busy.append(1)
        try:
            kind = "open" if event == "open" else "list"
            os.write(_fd, ("%s %s\\n" % (kind, os.path.realpath(str(path)))).encode())
        finally:
            _busy.pop()

    sys.addaudithook(_audit)
"""


def _audit_dir(root):
    folder = Path(root) / ".audit"
    folder.mkdir(exist_ok=True)
    (folder / "sitecustomize.py").write_text(AUDIT_HOOK)
    return folder


def _events(log, kind):
    if not Path(log).exists():
        return []
    return [line.split(" ", 1)[1] for line in Path(log).read_text().splitlines()
            if line.startswith(kind + " ")]


PYTHON_SHIM = """#!/bin/sh
echo "python3 $*" >> "{log}"
exec "{real}" "$@"
"""

#: python3 processes the hook starts for a production-code edit on an issue at
#: implement with a red on record, measured at fac8899e, before `depends_on`
#: existed: the delivery-approach reader, the acceptance-criteria reader and
#: the red-record reader.
BASE_PYTHON3 = 3

#: The added cost of 5 met dependencies over none, as a multiple of a
#: reference python3 process that imports compass_pkg and loads one manifest.
#: Measured on a development machine (Apple silicon, Python 3.11.9), 2026-10-13:
#: hook medians 0.181s with none, 0.247s with 1 and 0.254s with 5; reference
#: 0.045s; 5 over none 1.41; the marginal 0.073s is 1.63 references. The
#: reader is one more python3 process that imports `lifecycle`, so most of the
#: marginal is a process start, which the reference also measures. The limit
#: leaves about 50% for a runner whose bash and process start cost more, and a
#: second added process (about one reference more) fails it. The counts above
#: are the main check; they do not depend on timing.
MAX_MARGINAL_OVER_REFERENCE = 2.5


def _budget_project(root, deps):
    project = Project(root)
    for n in range(34):
        project.issue(f"other-{n:02d}", "implement")
    met = [f"met-{n}" for n in range(5)]
    for slug in met:
        project.issue(slug, "ship", close="completed")
    entries = {None: None, "empty": [], 1: [dep(met[0])], 5: [dep(s) for s in met]}[deps]
    project.issue("a", "implement", depends=entries, marker=True)
    if entries is None:
        manifest = project.manifest("a")
        manifest.pop("depends_on", None)
        project.write("a", manifest)
    return project, met[:len(entries or [])]


def _work_folders_listed(project, events, allowed):
    """The `.compass/work` folders listed, other than the waiting issue's and
    its dependencies' own: the work folder itself, or another issue's folder."""
    work = os.path.realpath(project.work)
    bad = []
    for path in events:
        if path == work:
            bad.append(path)
        elif path.startswith(work + os.sep):
            slug = path[len(work) + 1:].split(os.sep, 1)[0]
            if slug not in allowed:
                bad.append(path)
    return bad


@pytest.mark.serial
def test_dbi_12_hook_cost_budget(tmp_path):
    import statistics
    import time
    counts = {}
    projects = {}
    for deps in (None, "empty", 1, 5):
        project, met = _budget_project(tmp_path / str(deps), deps)
        projects[deps] = project
        shim = project.root / ".py-shim"
        shim.mkdir()
        log = project.root / ".python3-calls"
        (shim / "python3").write_text(PYTHON_SHIM.format(log=log, real=sys.executable))
        (shim / "python3").chmod(0o755)
        audit_log = project.root / ".audit.log"
        done = hook(project, code_file(project), path=f"{shim}:{env_for(project.root)['PATH']}",
                    PYTHONPATH=str(_audit_dir(project.root)), DBI_AUDIT_LOG=str(audit_log))
        assert done.returncode == 0, (deps, done)
        counts[deps] = len(log.read_text().splitlines())
        opened = _events(audit_log, "open")
        manifests = {s: opened.count(os.path.realpath(project.dir(s) / "manifest.yml"))
                     for s in (p.name for p in project.work.iterdir())}
        assert {s: n for s, n in manifests.items() if n and s != "a"} == {s: 1 for s in met}, \
            (deps, manifests)
        # Reading a dependency's own evidence folder for its stage is allowed;
        # listing the work folder, or any other issue's folder, is not.
        listed = _events(audit_log, "list")
        assert not _work_folders_listed(project, listed, {"a", *met}), (deps, listed)
    assert counts[None] == counts["empty"] == BASE_PYTHON3, counts
    assert counts[1] <= BASE_PYTHON3 + 1 and counts[5] <= BASE_PYTHON3 + 1, counts

    reference = [sys.executable, "-c",
                 "import sys; sys.path.insert(0, sys.argv[1]); import compass_pkg; "
                 "from compass_pkg.core import load_manifest; load_manifest(sys.argv[2])",
                 str(CLI_DIR), str(projects[5].dir("met-0"))]
    times = {0: [], 1: [], 5: [], "reference": []}
    for round_ in range(12):
        for deps, key in ((None, 0), (1, 1), (5, 5)):
            start = time.perf_counter()
            done = hook(projects[deps], code_file(projects[deps]))
            elapsed = time.perf_counter() - start
            assert done.returncode == 0, done
            if round_:
                times[key].append(elapsed)
        start = time.perf_counter()
        subprocess.run(reference, check=True, capture_output=True, timeout=60)
        if round_:
            times["reference"].append(time.perf_counter() - start)
    median = {k: statistics.median(v) for k, v in times.items()}
    ratio = median[5] / median[0]
    marginal = (median[5] - median[0]) / median["reference"]
    print("DBI-12 hook medians: 0 deps %.4fs, 1 dep %.4fs, 5 deps %.4fs; reference %.4fs; "
          "5 over 0 %.2f (limit 2.0); marginal over reference %.2f (limit %.1f)"
          % (median[0], median[1], median[5], median["reference"], ratio, marginal,
             MAX_MARGINAL_OVER_REFERENCE))
    assert ratio <= 2.0, median
    assert marginal < MAX_MARGINAL_OVER_REFERENCE, median


# --- DBI-16: ship-commit ----------------------------------------------------------------

WAITING = ["compass ship-commit: these issues were waiting for b:",
           "  a (until done)", "  c (until in-review)"]


def _ship_repo(root, waiting, gates_pass=True, at_head=False):
    """A local git repository where `b` is ready to ship. With `waiting`, `a`
    and `c` wait for it and a closed issue `e` names it too; without, the same
    issues name nothing. `d` waits for nothing either way."""
    root = Path(root)
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("hello\n")
    project = Project(root)
    project.issue("a", "implement", depends=[dep("b")] if waiting else None)
    project.issue("c", "implement", depends=[dep("b", "in-review")] if waiting else None)
    project.issue("e", "ship", close="not-planned", depends=[dep("b")] if waiting else None)
    project.issue("d", "implement")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    b = project.dir("b")
    b.mkdir(parents=True)
    (b / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "3.0", "issue": "b", "created": "2026-10-01",
        "assessment": {"risk": "contained", "familiarity": "greenfield", "size": "small",
                       "goal": "delivery", "role": "engineer", "labels": []},
        "delivery_approach": "regular", "stages": {}, "evidence": [],
        "gates": [{"id": "verify.correctness", "status": "pass" if gates_pass else "pending",
                   "evidence": []}],
        "scenarios": [{"id": "B-1", "title": "b works", "intent": "INT-1"}],
        "changed_files": [{"path": "feature.txt", "scenarios": ["B-1"]}],
    }, sort_keys=False))
    (root / "feature.txt").write_text("b's work\n")
    _git(root, "add", "--", "feature.txt", ".compass/work/b/manifest.yml")
    if at_head:
        _git(root, "commit", "-q", "-m", "integrate b")
    return project


def _ship(project):
    done = compass(project.root, "ship-commit", "-m", "Ship b", "--issue", "b")
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "<id>",
                  _masked(done.stdout + "\n--- stderr\n" + done.stderr, project.root))
    return done.returncode, text


def _without_waiting(text):
    return "\n".join(line for line in text.split("\n") if line not in WAITING)


def test_dbi_16_ship_commit_names_waiting_issues(tmp_path):
    for at_head in (False, True):
        waiting = _ship_repo(tmp_path / f"waiting-{at_head}", True, at_head=at_head)
        alone = _ship_repo(tmp_path / f"alone-{at_head}", False, at_head=at_head)
        code, text = _ship(waiting)
        alone_code, alone_text = _ship(alone)
        assert code == alone_code == 0, (text, alone_text)
        assert status_of(waiting, "b") == ("done", "completed"), text
        lines = text.split("\n")
        start = lines.index(WAITING[0])
        assert lines[start:start + 3] == WAITING, text
        assert not any(line.startswith(("  d ", "  e ")) for line in lines), text
        assert _without_waiting(text) == alone_text, (text, alone_text)
        assert not any(line in WAITING for line in alone_text.split("\n")), alone_text
        assert_no_gh_call(waiting.root)
    # A ship that does not land b prints no waiting line, and exits as it would.
    for at_head in (False, True):
        waiting = _ship_repo(tmp_path / f"refused-{at_head}", True, gates_pass=False,
                             at_head=at_head)
        alone = _ship_repo(tmp_path / f"refused-alone-{at_head}", False, gates_pass=False,
                           at_head=at_head)
        code, text = _ship(waiting)
        alone_code, alone_text = _ship(alone)
        assert status_of(waiting, "b")[0] != "done", text
        assert code == alone_code and text == alone_text, (text, alone_text)
        assert WAITING[0] not in text, text


def status_of(project, slug):
    manifest = project.manifest(slug)
    return manifest.get("status"), manifest.get("close_reason")


if __name__ == "__main__" and sys.argv[1:2] == ["--capture"]:
    _capture(sys.argv[2], sys.argv[3])
