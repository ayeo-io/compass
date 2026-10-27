"""What both hook drivers share: building the install, the project and the
machine, and checking what the hook did.

Everything that knows how Compass is laid out, how a fault is planted and
what a refusal looks like lives here, so a change to any of them changes
this file and not the specifications or the DSL. A subclass only knows how
its client sends a call to the hook.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

#: Where each part of the install lives, by the name a scenario gives it.
INSTALL_PARTS = {
    "compass-python.sh": "scripts/lib/compass-python.sh",
    "settings-files.sh": "scripts/lib/settings-files.sh",
    "pre-tool-project.sh": "hooks/lib/pre-tool-project.sh",
    "pre-tool-guards.sh": "hooks/lib/pre-tool-guards.sh",
    "pre-tool-targets.sh": "hooks/lib/pre-tool-targets.sh",
    "pre-tool-bash-writes.sh": "hooks/lib/pre-tool-bash-writes.sh",
    "pre-tool-issue.sh": "hooks/lib/pre-tool-issue.sh",
    "pre-tool-checks.sh": "hooks/lib/pre-tool-checks.sh",
}
#: The parts of the hook itself, which the hook checks before it sources any.
HOOK_PARTS = tuple(name for name in INSTALL_PARTS if name.startswith("pre-tool-"))

#: Each check whose Python can fail on its own: a line only its program holds,
#: and the words its refusal names it by.
CHECKS = {
    "code globs": ("fnmatch.fnmatch(path, g)", "enforcement.code_globs reader"),
    "delivery approach": ("resolve_artifact(sys.argv[1]", "delivery-approach reader"),
    "acceptance criteria": ('weight = stages.get("define"', "acceptance-criteria reader"),
    "red record": ("verdict_line(sys.argv[1]", "red-record reader"),
}

#: Other things a refusal can be checked to name, and the words that name them.
NAMES = {"the settings file": "fix .compass/config.yml and retry"}

MANIFEST = """schema_version: '2.0'
issue: {issue}
created: '2026-09-24'
status: active
stages: {{assess: full, define: full, implement: full}}
scenarios:
- id: M-1
  intent: INT-1
  tests: [t]
"""


def _red_record():
    import hashlib
    payload = {"command": "pytest -q", "scenario": None, "exit_code": 1,
               "passed": False, "timestamp": "2026-09-24T00:00:00+00:00",
               "record_id": "fixture0000000000"}
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    return payload


class HookDriverBase:
    """Builds one scenario's folders and checks one hook call."""

    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.install = self.workspace / "install"
        self.project = self.workspace / "project"
        self.fakebin = self.workspace / "fakebin"
        self.path = os.environ["PATH"]
        self.result = None
        self.project.mkdir(parents=True, exist_ok=True)

    # --- the install --------------------------------------------------------------------

    def hasCompleteInstall(self):
        if not self.install.exists():
            for part in ("hooks", "scripts", "cli", "adapters"):
                shutil.copytree(ROOT / part, self.install / part,
                                ignore=shutil.ignore_patterns("__pycache__"))
            (self.install / "compass-contract.md").write_text(
                (ROOT / "compass-contract.md").read_text(encoding="utf-8"), encoding="utf-8")

    def _part(self, part):
        if part not in INSTALL_PARTS:
            raise ValueError(f"no install part named {part!r}; known: {sorted(INSTALL_PARTS)}")
        return self.install / INSTALL_PARTS[part]

    def hasInstallMissing(self, part):
        self.hasCompleteInstall()
        self._part(part).unlink()

    def hasInstallWithUnreadable(self, part):
        self.hasCompleteInstall()
        self._part(part).chmod(0)

    # --- the project --------------------------------------------------------------------

    def hasOptedInProject(self, issue, code_globs):
        compass = self.project / ".compass"
        task = compass / "work" / issue
        (task / "evidence").mkdir(parents=True, exist_ok=True)
        (compass / "current-task").write_text(issue)
        globs = ", ".join(f"'{g}'" for g in code_globs)
        (compass / "config.yml").write_text(
            f"version: 1.0.0\nmode: enforced\nenforcement:\n  code_globs: [{globs}]\n")
        (task / "manifest.yml").write_text(MANIFEST.format(issue=issue))
        (task / "delivery-approach.md").write_text("# Approach\n")
        (task / "evidence" / "red.json").write_text(json.dumps(_red_record()))
        (task / ".red").write_text("")

    def hasGuestRepository(self):
        shutil.rmtree(self.project / ".compass", ignore_errors=True)

    def hasProjectWithNoIssues(self):
        shutil.rmtree(self.project / ".compass" / "work", ignore_errors=True)

    def hasSettingsThatDoNotParse(self):
        (self.project / ".compass" / "config.yml").write_text(
            "enforcement:\n  code_globs: [unclosed\n")

    def hasSettingsWithCodeGlobs(self, value):
        (self.project / ".compass" / "config.yml").write_text(
            f"version: 1.0.0\nmode: enforced\nenforcement:\n  code_globs: {value}\n")

    def hasUnreadableSettings(self):
        (self.project / ".compass" / "config.yml").chmod(0)

    def hasIssueWithNoApproachRecord(self, issue):
        (self.project / ".compass" / "work" / issue / "delivery-approach.md").unlink()

    # --- the machine --------------------------------------------------------------------

    def _fake(self, name, text):
        self.fakebin.mkdir(exist_ok=True)
        tool = self.fakebin / name
        tool.write_text(text)
        tool.chmod(0o755)
        if not self.path.startswith(f"{self.fakebin}:"):
            self.path = f"{self.fakebin}:{self.path}"

    def hasNoPython(self):
        bare = self.workspace / "barebin"
        bare.mkdir(exist_ok=True)
        for folder in ("/usr/bin", "/bin"):
            for name in os.listdir(folder):
                if name.startswith("python") or (bare / name).exists():
                    continue
                (bare / name).symlink_to(os.path.join(folder, name))
        self.path = str(bare)

    def hasPythonThatFailsFor(self, check, status):
        line = CHECKS[check][0].replace("'", "'\\''")
        self._fake("python3", f"""#!/usr/bin/env bash
# Fails only for the check whose program holds one line; otherwise the real python3.
if [ -f "${{1:-}}" ] && grep -qF -- '{line}' "$1"; then
  echo "fake python3: failing on purpose" >&2
  exit {int(status)}
fi
exec {sys.executable} "$@"
""")

    def cannotMakeTemporaryFile(self, attempt):
        counter = self.workspace / "mktemp-count"
        self._fake("mktemp", f"""#!/usr/bin/env bash
# Fails on call {int(attempt)}; otherwise the real mktemp.
n=$(( $(cat '{counter}' 2>/dev/null || echo 0) + 1 ))
echo "$n" > '{counter}'
if [ "$n" -eq {int(attempt)} ]; then
  echo "fake mktemp: failing on purpose" >&2
  exit 1
fi
exec /usr/bin/mktemp "$@"
""")

    # --- what the agent does: each client sends these its own way ----------------------

    def edits(self, path):
        self.result = self._send_edit(str(self.project / path))

    def reads(self, path):
        self.result = self._send_read(str(self.project / path))

    def runs(self, command):
        self.result = self._send_shell(command)

    def _env(self):
        return {**os.environ, "PATH": self.path, "CLAUDE_PROJECT_DIR": str(self.project)}

    def _run(self, argv, payload):
        return subprocess.run(argv, input=json.dumps(payload), capture_output=True,
                              text=True, cwd=self.project, env=self._env(), timeout=120)

    # --- what the person sees -----------------------------------------------------------

    def _said(self):
        if self.result is None:
            raise AssertionError("Expected a hook call before a check, found none")
        return " ".join(self.result.stderr.split())

    def confirmAllowed(self, silently):
        if self.result.returncode != 0:
            raise AssertionError(
                f"Expected the call allowed (exit 0), found exit {self.result.returncode}: "
                f"{self._said()}")
        if silently and self.result.stderr:
            raise AssertionError(f"Expected no output, found: {self._said()}")

    def confirmRefused(self, code, naming):
        said = self._said()
        # Claude Code blocks a tool call only on exit 2. Any other non-zero exit
        # is reported and the call goes ahead, so a hook that refuses with
        # exit 1 has allowed the call.
        if self.result.returncode != 2:
            raise AssertionError(
                f"Expected the call refused (exit 2), found exit {self.result.returncode}: {said}")
        if f"[{code}]" not in said:
            raise AssertionError(f"Expected refusal code [{code}], found: {said}")
        if naming:
            words = CHECKS[naming][1] if naming in CHECKS else NAMES.get(naming, naming)
            if words not in said:
                raise AssertionError(f"Expected the refusal to name {words!r}, found: {said}")

    def confirmRefusalSays(self, text):
        if text not in self._said():
            raise AssertionError(f"Expected the refusal to say {text!r}, found: {self._said()}")

    def confirmRefusalDoesNotSay(self, text):
        if text in self._said():
            raise AssertionError(f"Expected the refusal not to say {text!r}, found: {self._said()}")
