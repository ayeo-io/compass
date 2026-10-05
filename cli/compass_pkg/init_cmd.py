"""`compass init` - make a directory a Compass project.

`compass init` is the one owner of initialisation, so every entry point can
make sure the project exists before it writes into it.

The split this verb keeps:

  compass init      creates .compass/. Nothing else. Safe to run twice, which
                    is what lets the entry-point commands call it
                    unconditionally rather than each testing for the directory.
  /compass:init     the slash command - calls this, then offers the governance
                    conversation that copies governance/ into the project.

Auto-initialisation must never adopt governance. Being initialised for you is
small and reversible; having a governance directory copied into your
repository because you ran /compass:intent is not, and it would arrive without
the conversation that is the whole point of adopting it.

DEPENDENCY: none beyond the standard library and this package. It runs before
a project exists, so it must not reach for anything that assumes one - in
particular not core.find_compass_dir(), which raises when there is no
.compass/ and is exactly the case this verb handles.
"""
import datetime
import os

from compass_pkg.terminal import say

# Written on creation only - never over an existing file. Deliberately small:
# authoritative governance lives in governance/, and a value in two places can
# come to disagree. `/compass:init` is where a project fills these in.
CONFIG_TEMPLATE = """\
# Compass - per-project configuration
#
# Created by `compass init`. Authoritative governance lives in governance/,
# not here: governance/routing-policy.yml decides how a delivery approach is
# composed, and governance/guardrails.yml is what `compass check` runs. This
# file holds only project knobs those files have no opinion on.
#
# A project that has not run `/compass:init` uses the shipped governance
# defaults, which are active and in force. That is a complete, valid state.

version: 1.0.0

# advisory : checks report every failure clearly but exit 0 - nothing blocks.
# enforced : checks exit non-zero on any failure - the gate is real.
mode: enforced

# How often a session stops to wait for you at a stage hand-off (confirming
# the approach, and approving the acceptance criteria, the requirements review
# and the technical design). The routing policy's `autonomy_checkpoints:` table
# says which hand-offs wait for each value and route; `compass approach
# summary` shows the answer for an issue. No value changes a gate, evidence,
# the hook or `compass check`.
#   controlled : wait at every hand-off the table lists: all four on the
#                regular or full approach, assess and define on a hotfix,
#                assess on a quick fix or spike.
#   balanced   : a quick fix does not stop; the regular approach waits at
#                define and plan; the full approach waits at all four.
#                (The default.)
#   autonomous : never wait; every hand-off is shown and logged instead.
autonomy: balanced

# What created this project, and when. The hook reads these so that its first
# refusal in a project somebody's entry point initialised can say where Compass
# came from - a user who never ran `init` themselves should not meet an
# unexplained block.
initialised:
  by: "{by}"
  at: "{at}"

# From this date, a red record must carry the identity `compass tdd-red`
# stamps on it (record_id and content_digest) before it unlocks a code edit.
# A record with no identity counts only if its own timestamp is earlier.
# Delete the line to accept unstamped records again.
records_signed_since: '{at}'

project:
  # Shown in artifact headers and the devlog.
  name: ""

  # The command Compass runs to execute the test suite, passed to
  # `compass tdd-red` and `compass tdd-green`. Left empty, the hooks fall back
  # to detecting npm, Make and pytest conventions.
  test_command: ""
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
    checking first, so a second run must not touch a config the project has
    edited or anything under work/.

    `by` names what did the initialising - the verb itself, or the entry-point
    command that called it. It is written into the config so the hook's first
    refusal can explain where Compass came from.
    """
    compass_dir = os.path.join(project_root, ".compass")
    work_dir = os.path.join(compass_dir, "work")
    config = os.path.join(compass_dir, "config.yml")

    created = not os.path.isdir(compass_dir)

    os.makedirs(work_dir, exist_ok=True)
    if not os.path.exists(config):
        stamp = datetime.date.today().isoformat()
        with open(config, "w", encoding="utf-8") as fh:
            fh.write(CONFIG_TEMPLATE.format(by=by, at=stamp))

    return created, compass_dir


def cmd_init(args):
    root = resolve_project_root()
    created, compass_dir = ensure_initialised(
        root, by=getattr(args, "by", None) or "compass init")

    if created:
        return say(
            args,
            "compass init: initialised Compass in %s." % root,
            detail=[
                "config   : %s" % os.path.join(compass_dir, "config.yml"),
                "work     : %s" % os.path.join(compass_dir, "work"),
                "governance: the shipped defaults are in force. Run "
                "/compass:init to adopt your own.",
            ],
            decision=True,
            created=True, path=compass_dir, project_root=root,
        )

    return say(
        args,
        "compass init: %s is already a Compass project - nothing changed." % root,
        detail=["config : %s" % os.path.join(compass_dir, "config.yml")],
        created=False, path=compass_dir, project_root=root,
    )
