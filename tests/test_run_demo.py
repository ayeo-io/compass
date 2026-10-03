"""The headless runner's demo runs in CI, started by hand.

`scripts/run-demo.sh` builds a small project with one known bug, records
its failing test as a quick fix, and runs `compass run` on it.
`.github/workflows/compass-run-demo.yml` runs that script on a manual start
only, and authenticates the `claude` CLI by identity federation, as the
review job does, so no key is stored.

Scenario id: RD-1, in the delivery approach of the issue `run-demo-in-ci`
(GitHub issue #302).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "run-demo.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "compass-run-demo.yml"

#: A stub `claude` that reports one session and changes nothing.
_STUB = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ["STUB_LOG"]).open("a").write(json.dumps(sys.argv[1:]) + "\n")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "stub session", "session_id": "s1",
                  "total_cost_usd": 0.0}))
'''


def test_rd_1_the_demo_script_runs_compass_run_on_a_fresh_project(tmp_path):
    stub = tmp_path / "claude"
    stub.write_text(_STUB)
    stub.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "COMPASS_ISSUE"}
    env.update({"STUB_LOG": str(tmp_path / "log"), "CLAUDE_BIN": str(stub),
                "DEMO_DIR": str(tmp_path / "demo"),
                "DEMO_MAX_CYCLES": "1",
                "PATH": f"{Path(sys.executable).parent}{os.pathsep}{env['PATH']}"})
    result = subprocess.run(["bash", str(SCRIPT)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=300)
    # The stub fixes nothing, so the run stops at its one cycle.
    assert result.returncode == 4, result.stdout + result.stderr
    calls = (tmp_path / "log").read_text().splitlines()
    assert len(calls) == 1 and "--max-budget-usd" in json.loads(calls[0])
    records = list((tmp_path / "demo").glob("docs/compass/*/run-1.md"))
    assert records and "Outcome:** stopped" in records[0].read_text()
    # The script prints the record, so the job log shows it.
    assert "# Run 1" in result.stdout


def test_rd_1_the_workflow_starts_by_hand_and_stores_no_key():
    text = WORKFLOW.read_text()
    flow = yaml.safe_load(text)
    assert list(flow[True]) == ["workflow_dispatch"]
    assert flow["permissions"] == {"contents": "read", "id-token": "write"}
    assert "secrets." not in text
    for var in ("ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID",
                "ANTHROPIC_SERVICE_ACCOUNT_ID", "ANTHROPIC_WORKSPACE_ID"):
        assert f"vars.{var}" in text, var
    for needed in ("ANTHROPIC_IDENTITY_TOKEN_FILE", "ANTHROPIC_CONFIG_DIR",
                   "ANTHROPIC_PROFILE", "oidc_federation",
                   "audience=https://api.anthropic.com", "scripts/run-demo.sh",
                   "upload-artifact"):
        assert needed in text, needed
    # Every action is pinned to a full commit id.
    for line in text.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert len(ref) == 40, line
