"""Local subprocess drivers over existing adapter entries and the shared kit."""
from __future__ import annotations

import json
import hashlib
import os
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
               "hook-payloads", "approval-scope", "subtask-cap", "git-isolation"}


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
                        COMPASS_RENDER_AFTER="1", COMPASS_OFFLINE="1")
        for key in ("COMPASS_ISSUE", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_DATA",
                    "CLAUDE_CODE_SESSION_ID"):
            self.env.pop(key, None)
        if name == "codex":
            context = self.command([sys.executable,
                                    str(ROOT / "adapters/codex/runtime.py"), "context"])
            source = Path(json.loads(context.stdout)["root"])
            assert source == ROOT
            self.entry = [sys.executable, str(source / "cli/compass")]
        elif name == "claude-code":
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
        self.git("add", ".gitignore", self.source, self.node.split("::")[0])
        self.git("commit", "-q", "-m", "Seed the reference behaviour")

    def start_quick_fix(self):
        self.cli("quick-fix", "start", self.slug,
                 "--risk", "trivial - a reversible greeting correction",
                 "--familiarity", "brownfield-mapped - the seed test states the behaviour",
                 "--size", "atomic - one function returns the expected text",
                 "--intent", "The greeting says Hello",
                 "--scenario", "Given a greeting, when it is called, then it says Hello",
                 "--scenario-id", "CONF-1", "--test", self.node)

    def red(self):
        self.cli("tdd-red", "--issue", self.slug, "--scenario", "CONF-1",
                 "--", *self.test_command)

    def fix(self, kind):
        if kind == "quick-fix":
            (self.project / "greeting.py").write_text("def greet():\n    return 'Hello'\n")
        else:
            assert kind == "feature"
            (self.project / "feature.py").write_text(
                "def clean_names(names):\n    return [name.strip().upper() for name in names]\n")

    def finish_quick_fix(self):
        self.cli("quick-fix", "finish", "--issue", self.slug, "--no-commit",
                 "-m", "Correct the reference greeting", "--", *self.test_command)

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
        contents = {
            "acceptance-criteria": spec,
            "technical-design": "# Reference design\n\nUse a pure names function and two observable behaviours.\n",
            "distribution-map": "# Reference distribution\n\nunits: 2\n\nLocal fixture state only; no native agents are dispatched.\n",
        }
        for kind, text in contents.items():
            path = docs / f"{kind}.md"
            path.write_text(text)
            self.cli("issue", "artifact", "set", kind, "--issue", self.slug,
                     "--status", "draft", "--path", str(path.relative_to(self.project)))

    def green_feature(self):
        self.cli("tdd-green", "--issue", self.slug, "--scenario", "CONF-1",
                 "--", *self.test_command)
        self.cli("issue", "render", "--issue", self.slug)

    def start_spike(self):
        self._start_assessed("exploration")
        (self.issue_dir / ".spike").touch()
        docs = self.project / "docs/compass" / f"{FIXTURE_DATE}-{self.slug}"
        docs.mkdir(parents=True, exist_ok=True)
        path = docs / "delivery-approach.md"
        path.write_text("# Local spike\n\nExplore the isolated fixture. No production change ships.\n")
        self.cli("issue", "artifact", "set", "delivery-approach", "--issue", self.slug,
                 "--status", "draft", "--path", str(path.relative_to(self.project)))

    def payload_decision(self, action):
        payload = {"cwd": str(self.project), "session_id": "local-" + self.name,
                   "hook_event_name": "PreToolUse"}
        if action == "shell":
            command = "printf x > greeting.py"
            payload.update(tool_name="exec_command" if self.name == "codex" else "Bash",
                           tool_input={"cmd" if self.name == "codex" else "command": command})
        elif self.name == "codex":
            assert action in ("file", "move")
            body = ("*** Update File: greeting.py\n@@\n-old\n+new" if action == "file" else
                    "*** Update File: tests/test_greeting.py\n*** Move to: greeting.py\n@@\n-old\n+new")
            payload.update(tool_name="apply_patch", tool_input={
                "command": "*** Begin Patch\n" + body + "\n*** End Patch"})
        else:
            assert action in ("file", "move")
            payload.update(tool_name="Write", tool_input={
                "file_path": str(self.project / "greeting.py"), "content": "new"})
        argv = ([sys.executable, str(ROOT / "adapters/codex/runtime.py"), "hook"]
                if self.name == "codex" else ["bash", str(ROOT / "hooks/pre-tool.sh")])
        result = self.command(argv, input=json.dumps(payload), check=False)
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

    def cap_observation(self, requested):
        manifest = self.manifest()
        ceiling = manifest["subtask_ceiling"]
        docs = self.project / "docs/compass" / f"{FIXTURE_DATE}-{self.slug}"
        approach = docs / "delivery-approach.md"
        approach.write_text("# Local fixture approach\n\n" + yaml.safe_dump({
            key: manifest[key] for key in ("assessment", "delivery_approach", "stages", "subtask_ceiling")}))
        distribution = docs / "distribution-map.md"
        text = (f"# Local fixture distribution\n\nunits: {requested}\n\n"
                "| Subtask id | Task | Acceptance criteria | Branch name |\n|---|---|---|---|\n")
        for index in range(1, requested + 1):
            text += f"| subtask-{index} | Local fixture | CONF-1 | compass/{self.slug}/subtask-{index} |\n"
        distribution.write_text(text)
        for kind, path in (("delivery-approach", approach), ("distribution-map", distribution)):
            self.cli("issue", "artifact", "set", kind, "--issue", self.slug,
                     "--status", "draft", "--path", str(path.relative_to(self.project)))
        result = self.command(["bash", str(ROOT / "scripts/multiagent.sh"), self.slug, "--dry-run"],
                              check=False)
        # multiagent.sh prints "approach cap N", because "route" is a verb only (ADR-044).
        reported = re.search(r"(?:approach cap |cap is )(\d+)", result.stdout + result.stderr)
        reported_cap = int(reported[1]) if reported else None
        if result.returncode == 0 and "WOULD create worktree" in result.stdout:
            actual = "allow"
        elif result.returncode and "subtasks but the cap is" in result.stderr and reported_cap == ceiling:
            actual = "block"
        else:
            actual = "error"
        expected = "allow" if requested <= ceiling else "block"
        return {"ceiling": ceiling, "requested": requested, "reported_cap": reported_cap,
                "expected": expected, "actual": actual, "conforming": actual == expected}

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
                                  for artifact in manifest["artifacts"]]
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
                    if entry["type"] == "test-run":
                        record = {key: value for key, value in record.items() if key not in (
                            "record_id", "content_digest", "timestamp", "_full_log", "log_excerpt")}
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
