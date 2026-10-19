"""`compass init` - make a directory a Compass project.

`compass init` is the one owner of initialisation, so every entry point can
make sure the project exists before it writes into it.

The split this verb keeps:

  compass init      creates .compass/ and its state file. Nothing else. Safe
                    to run twice, which is what lets the entry-point commands
                    call it unconditionally rather than each testing for the
                    directory.
  /compass:init     the slash command - writes a minimal compass.yml, or runs
                    `compass policy migrate` on a project with a
                    .compass/config.yml or copied governance. It copies nothing.
                    It then runs `compass init --readiness`, which is the only
                    caller that measures the repository.
  compass init --readiness
                    as `compass init`, then runs `compass readiness` when a
                    compass.yml exists and prints the absent signals. It exits 0
                    whatever happens: a failure prints that readiness was not
                    measured and why.

Auto-initialisation must never write configuration. Being initialised for you
is small and reversible; having a compass.yml written into your repository
because you ran /compass:intent is not, and it would arrive without the
conversation that is the whole point of choosing a configuration.

DEPENDENCY: none beyond the standard library and this package (the readiness modules
are imported only when `--readiness` is passed). It runs before
a project exists, so it must not reach for anything that assumes one - in
particular not core.find_compass_dir(), which raises when there is no
.compass/ and is exactly the case this verb handles.
"""
import datetime
import os

from compass_pkg import project_settings
from compass_pkg.terminal import say

# State the CLI writes, not settings a person edits (ADR-043). Written on
# creation only - never over an existing file. Settings live in `compass.yml`
# at the project root, which only `/compass:init` or `compass policy migrate`
# creates. A project that has run neither uses the shipped defaults, which are
# in force: that is a complete, valid state.
STATE_TEMPLATE = """\
# Compass - state the CLI wrote. Do not edit. Settings go in compass.yml; see
# docs/configuration.md in the Compass documentation.
#
# What created this project, and when. The pre-tool hook's first refusal uses
# this to say where Compass came from - a user who never ran `init` themselves
# should not meet an unexplained block.
initialized:
  by: "{by}"
  at: "{at}"

# From this date, a red record must carry the identity `compass tdd-red`
# stamps on it (record_id and content_digest) before it unlocks a code edit.
# A record with no identity counts only if its own timestamp is earlier.
# Delete the line to accept unstamped records again.
records_signed_since: '{at}'
"""


def resolve_project_root():
    """Where a project would be, for a verb that runs before one exists.

    Deliberately NOT core.find_compass_dir(): that raises when there is no
    .compass/, and this is the one verb whose job is that case.

    CLAUDE_PROJECT_DIR is the runtime stating where the project is, so it wins.
    Otherwise the nearest ancestor holding .git - a repository is the unit a
    person means by "this project". Failing that, the working directory.

    This is not the pre-tool hook's walk and must not be confused with it. The
    hook stops at a .git boundary to avoid READING a stranger's issue state;
    the risk here is the opposite - CREATING state somewhere the user did not
    mean - so the nearest repository is the answer, not the furthest.
    """
    explicit = os.environ.get("CLAUDE_PROJECT_DIR")
    if explicit:
        return os.path.abspath(explicit)

    search = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(search, ".git")):
            return search
        parent = os.path.dirname(search)
        if parent == search:
            return os.path.abspath(os.getcwd())
        search = parent


def ensure_initialised(project_root, by="compass init"):
    """Create .compass/ if it is not there. Returns (created, compass_dir).

    Idempotent on purpose. Every entry-point command calls this without
    checking first, so a second run must not touch a state or config file or
    anything under work/.

    `by` names what did the initialising - the verb itself, or the entry-point
    command that called it. It is written into the state file so the hook's
    first refusal can explain where Compass came from.
    """
    compass_dir = os.path.join(project_root, ".compass")
    work_dir = os.path.join(compass_dir, "work")
    state = os.path.join(project_root, project_settings.STATE_YML)
    old_config = os.path.join(project_root, project_settings.OLD_CONFIG)

    created = not os.path.isdir(compass_dir)

    os.makedirs(work_dir, exist_ok=True)
    stamp = datetime.date.today().isoformat()
    # A project from before ADR-043 has the values in its old settings file
    # already, which `project_settings.state` still reads, so init adds
    # nothing to it.
    if not os.path.exists(state) and not os.path.exists(old_config):
        with open(state, "w", encoding="utf-8") as fh:
            fh.write(STATE_TEMPLATE.format(by=by, at=stamp))

    return created, compass_dir


def _state_path(root, compass_dir):
    """The file that holds the project's state: the state file, or the old
    config for a project created before ADR-043."""
    return (project_settings.state_source(root)
            or os.path.join(compass_dir, "state.yml"))


def _measure_readiness(root):
    """Measure the repository for `compass init --readiness`.

    Returns `(lines, data)`: the lines to print after the files init wrote,
    and the `--json` fields. It never raises: any failure becomes the one
    "not measured" line, so init still completes. It measures only when the
    project has a settings file, because that is what `/compass:init` has
    just written."""
    if not os.path.isfile(os.path.join(root, project_settings.COMPASS_YML)):
        return [], {}
    try:
        from compass_pkg import readiness_cmd, readiness_record
        notes = []
        record = readiness_cmd.measure(root, notes)
        absent = readiness_cmd.fix_order(record["signals"])
        lines = ["Absent readiness signals (the floor first):"]
        for signal in absent:
            fix = signal.get("fix") or {}
            lines.append("- [ ] %s: %s (%s)" % (signal["id"], fix.get("change", signal["reason"]),
                                                fix.get("file", readiness_record.RECORD)))
        if not absent:
            lines.append("none - every readiness signal is present")
        lines += ["  " + note for note in notes]
        score_line, score, below = readiness_cmd._score_line(record)
        lines += [score_line, "wrote %s" % readiness_record.RECORD]
        return lines, {"readiness": {"measured": True, "score": score,
                                     "signals": len(record["signals"]),
                                     "floor_met": not below,
                                     "absent": [s["id"] for s in absent]}}
    except Exception as exc:                                # noqa: BLE001
        reason = " ".join(str(exc).split()) or type(exc).__name__
        return (["readiness was not measured: %s. Run `compass readiness` later." % reason],
                {"readiness": {"measured": False, "reason": reason}})


def cmd_init(args):
    root = resolve_project_root()
    created, compass_dir = ensure_initialised(
        root, by=getattr(args, "by", None) or "compass init")
    readiness_lines, readiness_data = (
        _measure_readiness(root) if getattr(args, "readiness", False) else ([], {}))

    if created:
        return say(
            args,
            "compass init: initialized Compass in %s." % root,
            detail=[
                "state    : %s" % _state_path(root, compass_dir),
                "work     : %s" % os.path.join(compass_dir, "work"),
                "settings : defaults in force. /compass:init writes a compass.yml.",
            ] + readiness_lines,
            decision=True,
            created=True, path=compass_dir, project_root=root, **readiness_data,
        )

    return say(
        args,
        "compass init: %s is already a Compass project - nothing changed." % root,
        detail=["state : %s" % _state_path(root, compass_dir)] + readiness_lines,
        created=False, path=compass_dir, project_root=root, **readiness_data,
    )
