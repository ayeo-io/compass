#!/usr/bin/env python3
# =============================================================================
# compass_pkg.readiness_floor - why `approach evaluate --write` refuses an
# `autonomy: autonomous` issue, split out of routing.py to keep it under the
# module line cap. routing.py imports from here; this module imports nothing
# from routing.
#
# DEPENDENCY: standard library (os) only; no third-party package.
# =============================================================================

import os

from compass_pkg.core import CompassError


def _readiness_root(task_dir):
    """The project root whose readiness record applies: the issue's project,
    else the one around the working directory, else None."""
    if task_dir is not None:
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))
    from compass_pkg.core import find_compass_dir
    try:
        return os.path.dirname(find_compass_dir())
    except CompassError:
        return None


def _autonomy_setting(root, task):
    """Where a person changes `autonomy` for this issue."""
    if isinstance(task, dict) and isinstance(task.get("config"), dict) \
            and task["config"].get("autonomy"):
        return "the issue's `config:`"
    from compass_pkg import project_settings
    return project_settings.settings_file(root)


#: How every readiness refusal starts; the default view of `approach evaluate`
#: shows the rest of the first line as a concern.
FLOOR_REFUSED = ("approach evaluate --write refused: this issue runs `autonomy: autonomous`, "
                 "and ")


def _floor_refusal(root, task, autonomy, summary):
    """Why `approach evaluate --write` refuses this issue, or None.

    Only `autonomous` is judged. Trust is read from the environment before the
    record, so a record that a contribution committed cannot clear the floor
    on a CI runner. Every message names `autonomy` as the setting to change;
    only the untrusted one does not send the reader back to `compass
    readiness`, because measuring again cannot help there."""
    if autonomy != "autonomous":
        return None
    from compass_pkg import project_commands, readiness_record
    setting = (f"set `autonomy` to balanced or controlled in "
               f"{_autonomy_setting(root, task)}; those are never refused")
    head = FLOOR_REFUSED
    untrusted = project_commands.untrusted_reason(root)
    if untrusted is not None:
        return (head + f"readiness cannot be measured for an untrusted contribution "
                f"({untrusted}). That is not the same as below the readiness floor: no "
                f"setting lets an untrusted contribution run unattended. To run this "
                f"issue, {setting}.")
    if summary["status"] != "measured":
        if summary["reason"] == "missing":
            return (head + f"readiness is not measured in this checkout. The readiness "
                    f"record, {readiness_record.RECORD}, is per checkout and not committed, "
                    f"so a fresh clone has none. Run `compass readiness` here; a CI job "
                    f"runs it as a step before assess. Or {setting}.")
        if summary["reason"] == "stale":
            return (head + f"the readiness record is stale: {summary['detail']}. Run "
                    f"`compass readiness` again, or {setting}.")
        return (head + f"the readiness record is unreadable: {summary['detail']}. Or "
                f"{setting}.")
    record = readiness_record.read(root).record
    unmeasured = [s["id"] for s in record["signals"] if s.get("not_run") == "untrusted"]
    if unmeasured:
        return (head + f"the readiness record was measured for an untrusted contribution, "
                f"so these readiness signals did not run: {', '.join(unmeasured)}. Run "
                f"`compass readiness` in a trusted run, or {setting}.")
    absent = readiness_record.floor_absent(record)
    if not absent:
        return None
    fixes = []
    for signal in record["signals"]:
        if signal["id"] in absent:
            fix = signal.get("fix") or {}
            change = fix.get("change") or signal.get("reason") or "make it present"
            where = f" ({fix['file']})" if fix.get("file") else ""
            fixes.append(f"  - {signal['id']}: {change}{where}")
    return (head + "the repository is below the readiness floor. These readiness "
            "signals the floor requires are absent:\n" + "\n".join(fixes) +
            f"\nMake each present and run `compass readiness` again, or {setting}.")


def _readiness_floor(task_dir, task, autonomy):
    """`{**summary, would_refuse}` for the project, or None outside one.
    `summary` is what `--write` records in the manifest's `readiness:` key;
    `would_refuse` is the refusal message, or None."""
    root = _readiness_root(task_dir)
    if root is None:
        return None
    from compass_pkg import readiness_record
    summary = readiness_record.summary(root)
    return {**summary, "would_refuse": _floor_refusal(root, task, autonomy, summary)}
