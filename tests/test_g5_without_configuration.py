"""The guardrail 5 sign-off with no project configuration (GitHub issue #571,
folded into issue `approve-inside-claude-code`).

A project with no `compass.yml` checks runs the shipped default preset. Each
approval path writes a record that `human-approval-present` counts, and no
Compass message tells a person to edit `manifest.yml` by hand.

Scenario ids: `TRC-G1`, `TRC-G3`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from test_approval_scoped_to_guardrail_5 import SLUG, _project, _run  # noqa: E402


# --- the fix text names the approval path (`TRC-G3`) --------------------------------------

def _in_order(text):
    first = text.index("/compass:approve")
    delegated = text.index("delegat", first)
    terminal = text.index("compass evidence approve --guardrail G5", delegated)
    return first < delegated < terminal


def test_g3_fix_text_names_approval_path(tmp_path):
    import json
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import check_cmd
    root = _project(tmp_path)
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    assert code != 0, out + err
    row = next(r for r in json.loads(out)["checks"] if r["name"] == "human-approval-present")
    assert row["status"] == "fail", row
    guidance = check_cmd.CHECK_GUIDANCE["human-approval-present"]
    for text in (row["detail"], guidance["do"], guidance["fix"]):
        assert _in_order(text), text
    for text in (row["detail"], *guidance.values()):
        lowered = text.lower()
        assert not ("manifest.yml" in lowered
                    and any(w in lowered for w in ("add ", "edit ", "append "))), text


# --- a project with no configuration records the sign-off (`TRC-G1`) -------------------------

def test_g1_each_path_passes_on_default_preset(tmp_path):
    import datetime
    import re
    from approval_support import event
    from compass_pkg import approval_requests, prompt_approval
    from test_approval_scoped_to_guardrail_5 import _approve, _check_row, _manifest

    env = {"COMPASS_APPROVER": "jed72"}

    def fresh(name):
        root = _project(tmp_path / name)
        assert not (root / "compass.yml").exists()
        (root / ".compass" / "current-task").write_text(SLUG + "\n")
        return root, root / ".compass" / "work" / SLUG

    def passes(root):
        code, row = _check_row(root)
        assert row["status"] == "pass", row
        assert _manifest(root)["generation"] == 1

    # A typed /compass:approve.
    root, task = fresh("prompt")
    req = approval_requests.write(str(task), "guardrail", "G5", "refund migration")
    approval_requests.mark_shown(str(task), req)
    result = prompt_approval.handle(event(root), env, plugin_root=str(ROOT))
    assert not result.block, result
    passes(root)

    # An agent under a delegation that covers g5.
    root, task = fresh("delegated")
    until = datetime.datetime.now().astimezone() + datetime.timedelta(hours=2)
    first = prompt_approval.handle(
        event(root, command="compass:delegate",
              args=f"--agent compass:architect --until {until:%H:%M} --for g5"), env,
        plugin_root=str(ROOT))
    code = re.search(r"confirm (\S+)", first.message).group(1)
    done = prompt_approval.handle(event(root, command="compass:delegate",
                                        args=f"confirm {code}"), env, plugin_root=str(ROOT))
    assert not done.block, done
    code, out, err = _run(root, "evidence", "approve", "--issue", SLUG, "--guardrail", "G5",
                          "--scope", "refund migration", "--delegated", "--as",
                          "compass:architect")
    assert code == 0, out + err
    passes(root)

    # A person at a terminal.
    root, _ = fresh("terminal")
    code, out, err = _approve(root, "--guardrail", "G5", "--approver", "jed72", "--role",
                              "owner", "--scope", "refund migration")
    assert code == 0, out + err
    passes(root)
