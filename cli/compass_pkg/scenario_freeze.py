# compass_pkg.scenario_freeze - the scenario sign-off before code, and the freeze
"""What the code of a path issue was written against (ADR-095 decisions 9 to 11).

Three rules, each for a path issue (ADR-092) only, so an issue assessed before
9.0.0 keeps the records and the verdicts it had:

- **Sign-off before code.** An issue that owes `scenario-approval` (a `G5`
  label, a `signoff_labels` label or critical risk) needs a person's answer at
  the `specify` checkpoint before its first red. `compass tdd-red` asks
  `refusal` before the test runs, because the `.red` marker unlocks code edits.
  `controlled` autonomy waits at specify on every change; that is the
  project's choice, not this rule, so it is not read here.
- **The approval names what was approved.** The `checkpoint-approval` record
  for `specify`, and the request for it, hold `spec` and `spec_sha256`
  (`fields`).
- **The freeze.** The first red of a delivery issue writes `scenario_freeze`
  into the manifest: the time, the red record, the spec's path, its digest and
  the scenario ids. A later `compass tdd-red` never rewrites it. `compass
  quick-fix finish` writes it again each time it proves the red again, so it
  names the red that stands now (ADR-099). Each red record holds `spec_sha256`
  too, inside its `content_digest`. `compass check` prints `check_line`: a note,
  not a row, so no verdict moves.

The digest is the `sha256sum` digest of the spec file's bytes, so a reader can
check it with the standard tool. It is None when the issue has no spec file.
"""
# DEPENDENCY: standard library (hashlib, os); compass_pkg.core, path_stages,
# spec_location, stable_ids, and inside functions checkpoint_outcomes and refusals.
from __future__ import annotations

import hashlib
import os

from compass_pkg.core import load_manifest, now_iso, save_manifest
from compass_pkg.path_stages import is_path_issue
from compass_pkg.stable_ids import APPROACH_SPIKE, STAGE_SPECIFY

KEY = "scenario_freeze"
TOKEN = "scenario-approval"


def _project_root(task_dir):
    # <root>/.compass/work/<slug>
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(task_dir))))


def delivery(task) -> bool:
    """True for a path issue that ships code: a spike has no red and no freeze."""
    return is_path_issue(task) and task.get("delivery_approach") != APPROACH_SPIKE


def owes_signoff(task) -> bool:
    """True when the issue's stored `evidence_required` lists `scenario-approval`."""
    listed = task.get("evidence_required") if is_path_issue(task) else None
    return isinstance(listed, list) and TOKEN in listed


def signed_off(task) -> bool:
    """True when the `specify` checkpoint has a person's answer (`waited`)."""
    from compass_pkg import checkpoint_outcomes
    entry = checkpoint_outcomes.outcomes(task).get(STAGE_SPECIFY) or {}
    return entry.get("outcome") == checkpoint_outcomes.WAITED


def refusal(task, task_dir):
    """The refusal text when the red must wait for the scenario sign-off, or None."""
    if not owes_signoff(task) or signed_off(task):
        return None
    from compass_pkg import refusals
    return refusals.render("scenarios-not-approved", slug=os.path.basename(os.path.normpath(task_dir)))


def spec_digest(task_dir):
    """`(spec, sha256)`: the spec's path relative to the project, and the
    `sha256sum` digest of its bytes, or None when there is no file."""
    from compass_pkg.spec_location import spec_path
    path = spec_path(task_dir)
    rel = os.path.relpath(os.path.abspath(path), _project_root(task_dir))
    try:
        with open(path, "rb") as fh:
            return rel, hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return rel, None


def fields(task, task_dir, stage):
    """`{spec, spec_sha256}` for the `specify` approval of a path issue, else {}."""
    if stage != STAGE_SPECIFY or not is_path_issue(task):
        return {}
    spec, sha = spec_digest(task_dir)
    return {"spec": spec, "spec_sha256": sha}


def red_payload(task, task_dir):
    """`{spec_sha256}` for a red record of a delivery issue, else {}. The caller
    adds it before the record is stamped, so `content_digest` covers it."""
    return {"spec_sha256": spec_digest(task_dir)[1]} if delivery(task) else {}


def freeze(task_dir, red_path):
    """Write `scenario_freeze` on the issue's first red, and return it; None when
    the issue is not a delivery issue or is already frozen. `red_path` is the
    red record just written."""
    task, task_path = load_manifest(task_dir)
    if not delivery(task) or isinstance(task.get(KEY), dict):
        return None
    spec, sha = spec_digest(task_dir)
    task[KEY] = {
        "at": now_iso().replace("+00:00", "Z"),
        "red": os.path.relpath(os.path.abspath(red_path), os.path.abspath(task_dir)),
        "spec": spec,
        "spec_sha256": sha,
        "scenarios": [s["id"] for s in task.get("scenarios") or []
                      if isinstance(s, dict) and isinstance(s.get("id"), str)],
    }
    save_manifest(task, task_path)
    return task[KEY]


def short(sha):
    """A digest as a line shows it: its first 12 characters, so the line fits."""
    return sha[:12] if sha else "none: no spec file"


def check_line(task, task_dir):
    """`(text, changed)` for `compass check`, or None when the issue has no freeze.
    `changed` is True when the spec's digest now differs from the frozen one."""
    held = task.get(KEY) if isinstance(task, dict) else None
    if not isinstance(held, dict):
        return None
    frozen = held.get("spec_sha256")
    text = f"Scenarios: frozen at the red on record (sha256 {short(frozen)})"
    changed = spec_digest(task_dir)[1] != frozen
    if changed:
        text += "; the spec has changed since"
    return text, changed
