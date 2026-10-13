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
import shutil
import subprocess
import sys
from pathlib import Path

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


def compass(root, *args, cli_dir=CLI_DIR, clock=None, cwd=None, **extra):
    """Run `compass <args>` in `root`; with `clock`, under the fixed clock."""
    if clock:
        cmd = [sys.executable, str(FIXED_CLOCK), "--cli", str(cli_dir), "--at", clock,
               "--", *args]
    else:
        cmd = [sys.executable, str(Path(cli_dir) / "compass"), *args]
    return subprocess.run(cmd, cwd=str(cwd or root), env=env_for(root, **extra),
                          capture_output=True, text=True, timeout=120)


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


if __name__ == "__main__" and sys.argv[1:2] == ["--capture"]:
    _capture(sys.argv[2], sys.argv[3])
