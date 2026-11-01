"""The fixture projects the four-layer acceptance strategy tests run on.

A test states what a project and its issues hold and what Compass reports;
this module builds the project in a temporary folder and runs the CLI on it
in a subprocess. It also builds the same project with compass 8.0.4, so the
scenarios that compare with 8.0.4 (`TRC-A3`, `TRC-A9`, `TRC-X2`) have recorded
output to compare with (`record_fixtures.py`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "cli" / "compass"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
CREATED = "2026-10-29"

#: An assessment the shipped routing policy computes each approach from.
ASSESSMENTS = {
    "regular": {"risk": "contained", "size": "medium", "goal": "delivery"},
    "full": {"risk": "critical", "size": "medium", "goal": "delivery"},
    "quick-fix": {"risk": "trivial", "size": "atomic", "goal": "delivery"},
    "hotfix": {"risk": "contained", "size": "small", "goal": "delivery",
               "urgency": "live-defect"},
    "spike": {"risk": "contained", "size": "small", "goal": "exploration"},
}

#: The ids of the strategy's checks. Rows with these names are the strategy's
#: own findings; every other row is compared with compass 8.0.4.
STRATEGY_CHECKS = ("acceptance-applicability-agrees", "outer-loop-recorded",
                   "outer-loop-attempts-recorded", "isolation-proven",
                   "layering-test-passed")


def env(root):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "COMPASS_RENDER_AFTER": "0",
            "CLAUDE_PROJECT_DIR": str(root),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
            "GIT_AUTHOR_DATE": "2026-10-29T09:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-10-29T09:00:00+00:00"}


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, env=env(root), check=True,
                   capture_output=True, text=True)


class Project:
    """A git repository with `.compass/`, run by one CLI."""

    def __init__(self, root, cli=CLI, init=True):
        self.root = Path(root)
        self.cli = Path(cli)
        if init:
            self.root.mkdir(parents=True)
            (self.root / "README.md").write_text("base\n", encoding="utf-8")
            git(self.root, "init", "-q", "-b", "main")
            git(self.root, "add", "-A")
            git(self.root, "commit", "-q", "-m", "base")
            code, out, err = self.run("init")
            assert code == 0, out + err

    def run(self, *argv):
        r = subprocess.run([sys.executable, str(self.cli), *argv], cwd=self.root,
                           env=env(self.root), capture_output=True, text=True,
                           timeout=300, stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout, r.stderr

    def setting(self, value, where="compass.yml", **more):
        """Write the strategy setting into `compass.yml` or `.compass/config.yml`.
        `value` None writes the file without the key."""
        doc = {"schema": 1, **more} if where == "compass.yml" else dict(more)
        if value is not None:
            doc["acceptance_strategy"] = value
        path = self.root / where
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    def issue(self, slug, approach="regular"):
        task_dir = self.root / ".compass" / "work" / slug
        task_dir.mkdir(parents=True)
        assessment = {"familiarity": "brownfield-mapped", "labels": [],
                      **ASSESSMENTS[approach]}
        (task_dir / "manifest.yml").write_text(yaml.safe_dump({
            "schema_version": "3.0", "issue": slug, "created": CREATED,
            "assessment": assessment, "evidence": []}, sort_keys=False), encoding="utf-8")
        return Issue(self, slug)


class Issue:
    def __init__(self, project, slug):
        self.project, self.slug = project, slug
        self.dir = project.root / ".compass" / "work" / slug

    def run(self, *argv):
        return self.project.run(*argv)

    def assess(self, expected=None, reason=None):
        """`compass approach evaluate --write`, with a reason for every assessed value."""
        argv = ["approach", "evaluate", "--issue", self.slug, "--write"]
        for name in ("risk", "familiarity", "size", "goal", "urgency"):
            if name in self.manifest()["assessment"]:
                argv += ["--justify", f"{name}=Test fixture: the {name} was judged."]
        if expected is not None:
            argv += ["--expected-acceptance", expected]
        if reason is not None:
            argv += ["--reason", reason]
        return self.run(*argv)

    def must(self, *argv):
        code, out, err = self.run(*argv)
        assert code == 0, f"{argv}: {out}{err}"
        return out

    def acceptance_start(self, kind):
        return self.must("acceptance", "start", "--kind", kind, "--issue", self.slug,
                         "--", "true")

    def red(self):
        return self.must("tdd-red", "--issue", self.slug, "--", "sh", "-c",
                         "echo 'test_one FAILED'; exit 1")

    def green(self):
        return self.must("tdd-green", "--issue", self.slug, "--", "sh", "-c",
                         "echo 'test_one PASSED'")

    def check(self):
        """`(exit code, the --json document)` of `compass check`, or the text of
        stderr in place of the document when the command wrote no JSON."""
        code, out, err = self.run("check", "--issue", self.slug, "--json")
        try:
            return code, json.loads(out)
        except ValueError:
            return code, out + err

    def manifest(self):
        return yaml.safe_load((self.dir / "manifest.yml").read_text(encoding="utf-8"))

    def write_manifest(self, body):
        (self.dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                               encoding="utf-8")

    def close(self):
        body = self.manifest()
        body["land_timestamp"] = "2026-10-29T12:00:00Z"
        self.write_manifest(body)

    def approach_record(self):
        """The delivery-approach record written from the shipped template,
        registered and rendered, as the assess stage writes it."""
        rel = f"docs/compass/{CREATED}-{self.slug}/delivery-approach.md"
        path = self.project.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        template = (ROOT / "templates" / "delivery-approach.md").read_text(encoding="utf-8")
        path.write_text(template.replace("{{ISSUE_SLUG}}", self.slug), encoding="utf-8")
        self.must("issue", "artifact", "set", "delivery-approach", "--status", "draft",
                  "--path", rel, "--issue", self.slug)
        self.must("issue", "render", "--issue", self.slug)
        return path.read_text(encoding="utf-8")


def rows(document):
    """`[(name, status)]` of a `compass check --json` document."""
    return [(c["name"], c["status"]) for c in document["checks"]]


def findings(document):
    """The rows that are a finding: a failure or an advisory failure."""
    return [r for r in rows(document) if r[1] in ("fail", "advisory")]


def strategy_findings(document):
    return [r for r in findings(document) if r[0] in STRATEGY_CHECKS]


def without_strategy(document):
    return [r for r in rows(document) if r[0] not in STRATEGY_CHECKS]


def recorded(name):
    """The compass 8.0.4 output recorded for fixture `name`."""
    return json.loads((FIXTURES / "compass-8.0.4" / f"{name}.json").read_text(encoding="utf-8"))


def summary(code, document):
    """What a comparison with compass 8.0.4 reads: the exit code and the rows
    that are not the strategy's."""
    return {"exit": code, "rows": [list(r) for r in without_strategy(document)]}


# --- the projects the comparisons run on -------------------------------------------------

def out_of_scope_issue(project, kind, new_cli=True):
    """An issue whose acceptance is of kind `kind`, recorded with `compass
    acceptance start`, with nothing else (scenario `TRC-A3`)."""
    issue = project.issue("docs-" + kind)
    code, out, err = issue.assess(expected=kind if new_cli else None)
    assert code == 0, out + err
    issue.acceptance_start(kind)
    return issue


def spike_issue(project, new_cli=True):
    """An issue assessed as a spike, with no record of the strategy (scenario `TRC-A9`)."""
    issue = project.issue("explore", approach="spike")
    code, out, err = issue.assess()
    assert code == 0, out + err
    return issue


#: The project an issue assessed by compass 8.0.4 lives in (scenario `TRC-X2`), committed
#: as files. `older_issue_project` copies it and commits its README, so the tree
#: the records were written on is the tree they are judged on.
OLDER_PROJECT = FIXTURES / "assessed-by-8.0.4"


def older_issue_project(dest, cli=CLI):
    shutil.copytree(OLDER_PROJECT, dest)
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "README.md")
    git(dest, "commit", "-q", "-m", "base")
    return Project(dest, cli=cli, init=False)


def build_older_issue_project(dest, cli):
    """Write the `TRC-X2` project with `cli` (compass 8.0.4): a regular issue in
    scope, with an unbound red and green that carry no loop, candidate, client
    or attempts. Only `record_fixtures.py` calls this."""
    project = Project(dest, cli=cli)
    issue = project.issue("older")
    code, out, err = issue.assess()
    assert code == 0, out + err
    issue.red()
    issue.green()
    shutil.rmtree(dest / ".git")
    # This repository's .gitignore leaves out logs and lock files, so the
    # fixture holds none: the recorded output is the output of what CI checks out.
    for path in list(dest.rglob("*.log")) + list(dest.rglob("*.lock")):
        path.unlink()
    return project
