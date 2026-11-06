"""Local subprocess drivers over existing adapter entries and the shared kit."""
from __future__ import annotations

import json
import hashlib
import os
import shlex
import platform
import re
from datetime import date, datetime, timezone
from pathlib import Path
import subprocess
import sys
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DATE = date.today().isoformat()
LOCAL_CASES = {"route", "quick-fix", "feature-records", "local-handoff", "policy-and-evidence",
               "hook-payloads", "approval-scope", "git-isolation"}


def compare(expected, actual, path="observation"):
    """Reject semantic differences; callers get observations from the kit first."""
    assert type(expected) is type(actual), f"{path}: different value types"
    if isinstance(expected, dict):
        assert expected.keys() == actual.keys(), f"{path}: different fields"
        for key in expected:
            compare(expected[key], actual[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert len(expected) == len(actual), f"{path}: different item count"
        for index, (left, right) in enumerate(zip(expected, actual)):
            compare(left, right, f"{path}[{index}]")
    else:
        assert expected == actual, f"{path}: {expected!r} differs from {actual!r}"


class Adapter:
    """Observe an entry point in a scratch project; never launch a model."""

    slug = "reference-change"
    node = "tests/test_greeting.py::test_greeting"

    def __init__(self, name, project):
        self.name = name
        self.project = Path(project)
        self.project.mkdir(parents=True, exist_ok=True)
        self.calls = []
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("GIT_")}
        self.env.update(CLAUDE_PLUGIN_ROOT=str(ROOT), GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
                        COMPASS_OFFLINE="1")
        for key in ("COMPASS_ISSUE", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_DATA",
                    "CLAUDE_CODE_SESSION_ID"):
            self.env.pop(key, None)
        # 9.0.0 ships one adapter, Claude Code; the Codex adapter stays on 8.x.
        if name == "claude-code":
            self.entry = ["bash", str(ROOT / "bin/compass")]
        else:
            raise ValueError(f"No local driver for {name}")
        self.cli("init")

    def command(self, argv, *, check=True, input=None):
        result = subprocess.run(argv, cwd=self.project, env=self.env, input=input,
                                text=True, capture_output=True, timeout=30)
        self.calls.append({"argv": list(argv), "exit_code": result.returncode,
                           "stdout": result.stdout, "stderr": result.stderr})
        if check and result.returncode:
            raise AssertionError(f"{argv!r} exited {result.returncode}\n"
                                 f"{result.stdout}\n{result.stderr}")
        return result

    def cli(self, *argv, check=True):
        return self.command([*self.entry, *argv], check=check)

    def evaluate(self, **assessment):
        argv = ["approach", "evaluate", "--json"]
        for key, value in assessment.items():
            argv += ["--assessment", f"{key}={value}"]
        return json.loads(self.cli(*argv).stdout)

    @property
    def issue_dir(self):
        return self.project / ".compass/work" / self.slug

    @property
    def test_command(self):
        return [sys.executable, "-m", "pytest", "-q", self.node]

    def git(self, *argv):
        return self.command(["git", "-c", "core.fsmonitor=false", *argv])

    def seed(self, kind):
        assert kind in ("quick-fix", "feature")
        self.git("init", "-q")
        self.git("config", "user.name", "Conformance fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "maintenance.auto", "false")
        self.git("config", "gc.auto", "0")
        (self.project / ".gitignore").write_text(
            ".compass/\ndocs/compass/\n__pycache__/\n.pytest_cache/\n")
        tests = self.project / "tests"
        tests.mkdir()
        if kind == "quick-fix":
            self.source = "greeting.py"
            (self.project / self.source).write_text("def greet():\n    return 'Hi'\n")
            (tests / "test_greeting.py").write_text(
                "from greeting import greet\n\ndef test_greeting():\n    assert greet() == 'Hello'\n")
        else:
            self.source = "feature.py"
            self.node = "tests/test_feature.py::test_feature"
            (self.project / self.source).write_text("def clean_names(names):\n    return []\n")
            (tests / "test_feature.py").write_text(
                "from feature import clean_names\n\ndef test_feature():\n"
                "    assert clean_names([' Alice ', ' bob ']) == ['ALICE', 'BOB']\n"
                "    assert clean_names([]) == []\n")
        # The four-layer acceptance strategy applies to both fixtures. Their
        # project names its acceptance support code, as an adopter does, so
        # `compass check` gives no support-code advice to the issue.
        support = {"alias_helper": "tests/support/alias.py",
                   "driver_factory": "tests/support/drivers.py",
                   "dsl_root": "tests/support/dsl.py",
                   "layering_test": "tests/support/test_layering.py"}
        (tests / "support").mkdir()
        for path in support.values():
            (self.project / path).write_text("# acceptance support code\n")
        (self.project / ".compass/config.yml").write_text(
            yaml.safe_dump({"project": {"acceptance_support": support}}))
        self.git("add", ".gitignore", self.source, self.node.split("::")[0], *support.values())
        self.git("commit", "-q", "-m", "Seed the reference behaviour")

    def start_quick_fix(self):
        self.cli("quick-fix", "start", self.slug,
                 "--risk", "trivial - a reversible greeting correction",
                 "--familiarity", "brownfield-mapped - the seed test states the behaviour",
                 "--size", "atomic - one function returns the expected text",
                 "--intent", "The greeting says Hello",
                 "--scenario", "Given a greeting, when it is called, then it says Hello",
                 "--scenario-id", "CONF-1", "--test", self.node)

    # The fixture's one test is its scenario's acceptance test, so its red and green
    # are the outer loop of the four-layer acceptance strategy (ADR-080). A quick fix
    # records outer by default; the regular feature says so.
    def red(self):
        self.cli("tdd-red", "--issue", self.slug, "--scenario", "CONF-1",
                 "--loop", "outer", "--", *self.test_command)

    def fix(self, kind):
        if kind == "quick-fix":
            (self.project / "greeting.py").write_text("def greet():\n    return 'Hello'\n")
        else:
            assert kind == "feature"
            (self.project / "feature.py").write_text(
                "def clean_names(names):\n    return [name.strip().upper() for name in names]\n")

    def finish_quick_fix(self):
        self.cli("quick-fix", "finish", "--issue", self.slug, "--no-commit",
                 "-m", "Correct the reference greeting", "--candidate", "local",
                 "--client", "cli", "--", *self.test_command)

    def manifest(self):
        return yaml.safe_load((self.issue_dir / "manifest.yml").read_text())

    def _start_assessed(self, goal, *, labels=None):
        self.issue_dir.mkdir(parents=True)
        assessment = dict(risk="contained", familiarity="brownfield-mapped",
                          size="medium", goal=goal, role="engineer", labels=labels or [])
        manifest = dict(schema_version="3.0", issue=self.slug, created=FIXTURE_DATE,
                        assessment=assessment, scenarios=[], changed_files=[], evidence=[],
                        claims=[], follow_ups=[], reassessments=[])
        (self.issue_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
        argv = ["approach", "evaluate", "--issue", self.slug, "--write"]
        for key in ("risk", "familiarity", "size", "goal", "role"):
            argv += ["--justify", f"{key}=The fixed local fixture declares {assessment[key]}."]
        self.cli(*argv)
        self.cli("issue", "use", self.slug)

    def start_feature(self):
        self._start_assessed("delivery")
        self.cli("scenario", "add", "CONF-1", "--issue", self.slug,
                 "--title", "Trim and uppercase names", "--intent", "INT-1", "--test", self.node)
        self.cli("changed-file", "add", self.source, "--issue", self.slug, "--scenario", "CONF-1")
        docs = self.project / "docs/compass" / f"{FIXTURE_DATE}-{self.slug}"
        docs.mkdir(parents=True, exist_ok=True)
        spec = ("# Reference feature\n\n## Summary\n\nGoal: trim and uppercase names.\n"
                "Approach: one pure function.\nWhy now: a local conformance fixture.\n\n"
                "<!-- traceability id: CONF-1 · serves: INT-1 -->\n\n"
                "```gherkin\nScenario: Trim and uppercase names\n"
                "  Given 2 names with spaces\n  When they are cleaned\n"
                "  Then both names are uppercase without surrounding spaces and an empty list stays empty\n```\n"
                "\n## Non-functional requirements\n\n"
                "| Concern | Scenario | Reason it does not apply |\n|---|---|---|\n")
        for concern in ("performance", "capacity", "compatibility", "security", "privacy",
                        "operability", "accessibility"):
            spec += f"| {concern} | | Pure local fixture; no service or host guarantee is claimed. |\n"
        # The acceptance criteria are the one document Compass reads, at their
        # fixed path; nothing registers them (ADR-091).
        (docs / "acceptance-criteria.md").write_text(spec)

    def green_feature(self):
        self.cli("tdd-green", "--issue", self.slug, "--scenario", "CONF-1",
                 "--loop", "outer", "--candidate", "local", "--client", "cli",
                 "--", *self.test_command)
        # The regular approach also needs the isolation proof and the layering
        # record of the four-layer acceptance strategy (ADR-086).
        pytest = " ".join(shlex.quote(word) for word in self.test_command[:-1])
        self.cli("isolation", "record", "--issue", self.slug, "--candidate", "local",
                 "--client", "cli", "--parallel", f"{pytest} {shlex.quote(self.node)}",
                 "--repeat", pytest + " {tests}")
        self.cli("layering", "record", "--issue", self.slug, "--", *self.test_command)

    def start_spike(self):
        self._start_assessed("exploration")
        (self.issue_dir / ".spike").touch()

    def payload_decision(self, action):
        payload = {"cwd": str(self.project), "session_id": "local-" + self.name,
                   "hook_event_name": "PreToolUse"}
        if action == "shell":
            payload.update(tool_name="Bash", tool_input={"command": "printf x > greeting.py"})
        else:
            assert action in ("file", "move")
            payload.update(tool_name="Write", tool_input={
                "file_path": str(self.project / "greeting.py"), "content": "new"})
        result = self.command(["bash", str(ROOT / "hooks/pre-tool.sh")],
                              input=json.dumps(payload), check=False)
        codes = re.findall(r"\[([a-z][a-z0-9-]*)\]\s*$", result.stderr, re.MULTILINE)
        return {"exit_code": result.returncode,
                "reason": codes[-1] if result.returncode and codes else None}

    def start_approval_fixture(self):
        self._start_assessed("delivery", labels=["payments"])

    def approval_decision(self, subject):
        manifest = self.manifest()
        manifest["evidence"] = []
        if subject:
            record = {"id": "EV-SYNTHETIC-SCOPE", "type": "human-approval",
                      "issue": self.slug, "generation": manifest["generation"],
                      "approver": "synthetic fixture; no human signed", "role": "fixture",
                      "decision": "approved", "scope": "synthetic subject-check input only",
                      "timestamp": FIXTURE_DATE + "T00:00:00Z", "synthetic": True}
            record[subject] = "G5" if subject == "guardrail" else "dod-reviewed"
            manifest["evidence"].append(record)
        (self.issue_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
        result = self.cli("check", "--issue", self.slug, "--json", check=False)
        checked = json.loads(result.stdout)
        approval = next(row for row in checked["checks"] if row["name"] == "human-approval-present")
        return {"check": approval["name"], "status": approval["status"],
                "synthetic": True, "whole_issue_passed": result.returncode == 0}

    def capture(self, case_id, observation, expected):
        if case_id not in LOCAL_CASES:
            raise ValueError(f"{case_id} is not a local capture case")
        if observation.get("evidence_class") != "local" or expected.get("evidence_class") != "local":
            raise ValueError("A local capture needs local observations")
        differences = []
        try:
            compare(expected, observation)
        except AssertionError as error:
            differences.append(str(error))
        revision = self.command(["git", "-c", "core.fsmonitor=false", "-C", str(ROOT),
                                 "rev-parse", "HEAD"]).stdout.strip()
        return {"format_version": 1, "capture_id": uuid.uuid4().hex,
                "captured_at": datetime.now(timezone.utc).isoformat(), "case_id": case_id,
                "evidence_class": "local", "adapter": self.name, "entry": list(self.entry),
                "framework_revision": revision,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "environment": {"os": platform.system(), "python": platform.python_version()},
                "calls": list(self.calls), "observation": observation, "expected": expected,
                "result": {"status": "failed" if differences else "passed", "differences": differences},
                "native": {"status": "unmeasured"}, "independent": {"status": "unmeasured"}}

    def observe(self):
        self.cli("issue", "lint", "--issue", self.slug)
        result = self.cli("check", "--issue", self.slug, "--json", check=False)
        checked = json.loads(result.stdout)
        failures = {row["name"]: row["detail"] for row in checked["checks"]
                    if row["status"] not in ("pass", "nothing-to-check")}
        assert result.returncode == 0 and not failures, failures
        manifest = self.manifest()
        projected = {key: value for key, value in manifest.items()
                     if key not in ("evidence", "artifacts")}
        for key in ("claims", "follow_ups"):
            projected[key] = manifest.get(key, [])
        projected["gates"] = manifest["gates"]
        projected["artifacts"] = [{key: value for key, value in artifact.items()
                                   if key != "approved_at"}
                                  for artifact in manifest.get("artifacts", [])]
        evidence = []
        for entry in manifest["evidence"]:
            meaning = {key: value for key, value in entry.items()
                       if key not in ("record_id", "content_digest")}
            if entry.get("path"):
                path = (self.issue_dir / entry["path"]).resolve()
                assert path.is_relative_to(self.project.resolve()), "Evidence left the scratch project"
                contents = path.read_text()
                try:
                    record = json.loads(contents)
                except json.JSONDecodeError:
                    meaning["contents"] = contents
                else:
                    if entry["type"] in ("test-run", "isolation-proof", "layering"):
                        record = {key: value for key, value in record.items() if key not in (
                            "record_id", "content_digest", "timestamp", "first_timestamp", "_full_log",
                            "log_excerpt")}
                    meaning["record"] = record
                    if entry["type"] == "test-run":
                        meaning["passed"] = record["passed"]
            evidence.append(meaning)
        generation = self.issue_dir / "generations" / str(manifest["generation"])
        return {"format_version": 1, "evidence_class": "local",
                "unmeasured_classes": ["native", "independent"],
                "manifest": projected, "policy": yaml.safe_load((generation / "resolved.yml").read_text()),
                "evidence": evidence,
                "checks": [{key: check[key] for key in ("guardrail", "name", "status")}
                           for check in checked["checks"]]}
