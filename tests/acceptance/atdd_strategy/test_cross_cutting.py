"""Failure-mode scenarios of the four-layer acceptance strategy that cross groups.

The scenario `TRC-X2` guards every later item of the strategy: an issue assessed by compass
8.0.4, before the strategy shipped, gives the result 8.0.4 gives. `TRC-X3` runs one in-scope
issue end to end on the TypeScript reference example (ayeo-io/compass-delivery#330): every
record comes from the project's own commands, and it skips without Node (`typescript.py`).
"""
from __future__ import annotations

import json

from tests.acceptance.atdd_strategy import support, typescript
from tests.acceptance.atdd_strategy.test_isolation_layering import (
    STRATEGY_MODULES, parser_imports)


def test_trc_x2(tmp_path):
    """An issue created before the major version keeps passing."""
    project = support.older_issue_project(tmp_path / "repo")
    issue = support.Issue(project, "older")
    assert "acceptance_strategy" not in issue.manifest()
    code, document = issue.check()
    assert support.summary(code, document) == support.recorded("older-issue")
    assert not [r for r in support.rows(document) if r[0] in support.STRATEGY_CHECKS]
    notices = " ".join(document["notices"])
    notice = ("four-layer acceptance strategy (`S17`): does not apply - this issue was "
              "assessed before the strategy shipped")
    assert notice in notices, notices
    # The default view keeps the line budget of compass 8.0.4: the notice shows in
    # the full view and the JSON document only.
    assert "four-layer acceptance strategy" not in issue.run("check", "--issue", "older")[1]
    assert notice in issue.run("check", "--issue", "older", "--verbose")[1]


# --- `TRC-X3` ------------------------------------------------------------------------------

TS_TEST = "tests/acceptance/todos.spec.ts::a completed todo can be archived"
TS_DRIVER = "tests/acceptance/drivers/api.ts"
#: The project's commands, as its README gives them.
RUN = " ".join(typescript.RUN)
LAYERING = " ".join(typescript.LAYERING)
#: Parsers of TypeScript or JavaScript source, beside the Python parsers the
#: no-parser scan of `TRC-F13` looks for.
TS_PARSERS = {"typescript", "esprima", "acorn", "babel", "swc", "esbuild", "tree_sitter",
              "tree_sitter_typescript", "pyjsparser", "js2py"}


def _commit(project, message):
    support.git(project.root, "add", "-A", ":!.compass", ":!compass.yml")
    support.git(project.root, "commit", "-q", "-m", message)


def _record(issue, name):
    return json.loads((issue.dir / "evidence" / name).read_text(encoding="utf-8"))


def test_trc_x3(tmp_path):
    """Another language."""
    typescript.need(packages=True)
    project = support.Project(tmp_path / "repo")
    typescript.copy(project.root)
    (project.root / ".gitignore").write_text("node_modules\n", encoding="utf-8")
    project.setting(None, project={
        "acceptance_support": {"alias_helper": "tests/acceptance/alias.ts",
                               "driver_factory": "tests/acceptance/driverFactory.ts",
                               "dsl_root": "tests/acceptance/dsl.ts",
                               "layering_test": "tests/acceptance/layering.test.ts"},
        "layering_command": LAYERING})
    driver = (project.root / TS_DRIVER).read_text(encoding="utf-8")
    (project.root / TS_DRIVER).unlink()
    _commit(project, "the specifications, the DSL and no API driver yet")

    issue = project.issue("archive")
    code, out, err = issue.assess()
    assert code == 0, out + err
    issue.must("scenario", "add", "TRC-1", "--issue", issue.slug, "--intent", "INT-1",
               "--title", "Archive a completed todo", "--test", TS_TEST)
    # Stage 1: the suite fails because the API driver is not written yet.
    issue.must("tdd-red", "--issue", issue.slug, "--loop", "outer", "--scenario", "TRC-1",
               "--", *typescript.RUN, "--driver", "api")
    (project.root / TS_DRIVER).write_text(driver, encoding="utf-8")
    _commit(project, "the API driver")
    named = ("--candidate", "local", "--client", "api")
    issue.must("tdd-green", "--issue", issue.slug, "--loop", "outer", "--scenario", "TRC-1",
               *named, "--", *typescript.RUN, "--driver", "api", TS_TEST)
    issue.must("isolation", "record", "--issue", issue.slug, *named,
               "--parallel", f"{RUN} --driver api --workers 2",
               "--repeat", f"{RUN} --driver api {{tests}}")
    issue.must("layering", "record", "--issue", issue.slug)

    code, document = issue.check()
    assert support.strategy_findings(document) == [], document["checks"]
    rows = {c["name"]: c["status"] for c in document["checks"]}
    for name in ("outer-loop-recorded", "outer-loop-attempts-recorded", "isolation-proven",
                 "layering-test-passed", "acceptance-support-present"):
        assert rows.get(name) == "pass", (name, document["checks"])

    # Every record the strategy read was written by the project's own commands.
    red = _record(issue, "red-TRC-1.outer.json")
    assert red["argv"][-3:] == ["tests/acceptance/run.ts", "--driver", "api"], red
    assert (red["red_kind"], red["missing_modules"]) == ("import", [TS_DRIVER]), red
    green = _record(issue, "green-TRC-1.outer.json")
    assert green["argv"][3:] == ["tests/acceptance/run.ts", "--driver", "api", TS_TEST], green
    proof = _record(issue, "isolation-proof.json")
    assert proof["parallel"]["exit_code"] == 0, proof
    assert proof["repeat"][0]["runs"] == [0, 0] and proof["candidate"] == green["candidate"]
    layering = _record(issue, "layering.json")
    assert layering["command"] == LAYERING and layering["passed"] is True, layering
    # The count comes from node's JUnit report: the banned-term rule skips here,
    # because the fixture project has no governance/terminology.yml.
    assert layering["tests_ran"] == 3, layering
    types = {e.get("type") for e in issue.manifest()["evidence"]}
    assert {"isolation-proof", "layering"} <= types, types

    # The modules the strategy adds hold no TypeScript parser, and no more does
    # the JUnit reader they share.
    package = support.ROOT / "cli" / "compass_pkg"
    paths = [package / name for name in (*STRATEGY_MODULES, "pytest_report.py")]
    assert parser_imports(paths) == []
    found = [(path.name, n) for path in paths for n in TS_PARSERS
             if f"import {n}" in path.read_text(encoding="utf-8")]
    assert found == [], found
