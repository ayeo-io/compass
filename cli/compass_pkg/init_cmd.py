"""`compass init` - make a directory a Compass project.

`compass init` is the one owner of initialisation, so every entry point can
make sure the project exists before it writes into it.

The split this verb keeps:

  compass init      creates .compass/, its state file and the ignore lines
                    of the record (#356): `.compass/work/.gitignore` in every
                    project, and the per-machine lines of `.compass/.gitignore`
                    when the record is committed (`record_mode`). Nothing
                    else. Safe to run twice, which is what lets the
                    entry-point commands call it unconditionally rather than
                    each testing for the directory. A second run only adds an
                    ignore line that is missing; it keeps the person's own.
  /compass:init     the slash command - writes a minimal compass.yml. It
                    copies nothing.

Auto-initialisation must never write configuration. Being initialised for you
is small and reversible; having a compass.yml written into your repository
because you ran /compass:assess is not, and it would arrive without the
conversation that is the whole point of choosing a configuration.

DEPENDENCY: none beyond the standard library and this package. It runs before
a project exists, so it must not reach for anything that assumes one - in
particular not core.find_compass_dir(), which raises when there is no
.compass/ and is exactly the case this verb handles.
"""
import datetime
import os

from compass_pkg import project_settings, record_mode
from compass_pkg.core import CompassError
from compass_pkg.terminal import say

# State the CLI writes, not settings a person edits (ADR-043). Written on
# creation only - never over an existing file. Settings live in `compass.yml`
# at the project root, which only `/compass:init` or a person creates. A
# project without one uses the shipped defaults, which are
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


def write_ignore_files(project_root):
    """Write the record's ignore lines. Returns the files it changed.

    `.compass/work/.gitignore` is written in every project: in kept-out mode
    the project ignores the folder anyway, and a later switch to committed
    mode needs no second step. The lines of `.compass/.gitignore` are added
    only in committed mode, because a project that keeps its record out may
    track that file and must not see it change. A project whose settings
    cannot be read gets no committed-mode lines: `compass policy lint`
    names the fault, and init must not fail on it."""
    compass_dir = os.path.join(project_root, ".compass")
    changed = []
    work_ignore = os.path.join(compass_dir, "work", ".gitignore")
    if record_mode.add_ignore_lines(work_ignore, record_mode.WORK_IGNORE_LINES,
                                    record_mode.WORK_IGNORE_HEADER):
        changed.append(work_ignore)
    try:
        committed = record_mode.mode(project_root).mode == record_mode.COMMITTED
    except CompassError:
        committed = False
    if committed:
        compass_ignore = os.path.join(compass_dir, ".gitignore")
        if record_mode.add_ignore_lines(compass_ignore,
                                        record_mode.COMPASS_IGNORE_LINES,
                                        record_mode.COMPASS_IGNORE_HEADER):
            changed.append(compass_ignore)
    return changed


def ensure_initialised(project_root, by="compass init", changed=None):
    """Create .compass/ if it is not there. Returns (created, compass_dir).

    Idempotent on purpose. Every entry-point command calls this without
    checking first, so a second run must not touch a state or config file or
    anything under work/.

    `by` names what did the initialising - the verb itself, or the entry-point
    command that called it. It is written into the state file so the hook's
    first refusal can explain where Compass came from.

    `changed`, when given, is a list that receives each ignore file this run
    wrote to (`write_ignore_files`).
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
    written = write_ignore_files(project_root)
    if changed is not None:
        changed.extend(written)

    return created, compass_dir


def _state_path(root, compass_dir):
    """The file that holds the project's state: the state file, or the old
    config for a project created before ADR-043."""
    return (project_settings.state_source(root)
            or os.path.join(compass_dir, "state.yml"))


def cmd_init(args):
    root = resolve_project_root()
    changed = []
    created, compass_dir = ensure_initialised(
        root, by=getattr(args, "by", None) or "compass init", changed=changed)
    ignores = ["ignore   : %s" % path for path in changed]

    if created:
        return say(
            args,
            "compass init: initialized Compass in %s." % root,
            detail=[
                "state    : %s" % _state_path(root, compass_dir),
                "work     : %s" % os.path.join(compass_dir, "work"),
                *ignores,
                "settings : defaults in force. /compass:init writes a compass.yml.",
            ],
            decision=True,
            created=True, path=compass_dir, project_root=root,
        )

    if changed:
        return say(
            args,
            "compass init: %s is already a Compass project - added the missing "
            "ignore lines." % root,
            detail=["state    : %s" % _state_path(root, compass_dir), *ignores],
            created=False, path=compass_dir, project_root=root,
        )
    return say(
        args,
        "compass init: %s is already a Compass project - nothing changed." % root,
        detail=["state : %s" % _state_path(root, compass_dir)],
        created=False, path=compass_dir, project_root=root,
    )
