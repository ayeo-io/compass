"""The shared table of calls the approval guard must refuse or allow, and the
helpers that run one call through the real pre-tool hook or `check` in process.

This file holds no test, so pytest does not collect it. The test files of issue
`hooks-stop-refusing-harmless-work` import it:

- `REFUSED` lists every call that must stay refused, for each protected thing,
  with the refusal code the hook must give (`TRC-033`).
- `EXEMPT_COMMANDS` and the `exempt` field show which exemption a row attacks,
  so a test can count at least three refused calls for each (`TRC-054`).
- `ALLOWED` lists the controls: harmless calls that must pass. A control has
  `code=None` and its `twin_of` names the loosening scenario it belongs to.
- `UNREFUSED_ON_BASE` holds rows the design lists as refused that the guard
  before this change does not refuse. They are findings for the orchestrator,
  kept here and not deleted.

A row holds placeholders, written `{name}` and replaced by `expand`:

| Placeholder | Stands for |
|---|---|
| `{request}` | request 1 of issue `issue-a`, in its folder of pending approval requests |
| `{requests_dir}` | the folder that holds the pending and closed requests |
| `{script}` | the prompt hook script in the hooks folder |
| `{transcript}` | the session transcript, in a `.claude/projects/-p` folder of the home |
| `{session}` | the session id, `s1` |
| `{home}` | the temporary home folder |
| `{memory}` | the `memory` folder beside the transcript |
| `{delegation}` | delegation `DL-1` in the project's delegations folder |
| `{project}` | the temporary project folder |

A tool row may carry the key `cwd` in `tool_input`: `payload` moves it to the
call's working folder, as a Claude Code event carries it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

HOOK_PATH = ROOT / "hooks" / "pre-tool.sh"

REQ = "approval-request-protected"
DEL = "delegation-protected"
TRN = "transcript-protected"
CALLER = "delegation-caller-mismatch"

THINGS = ("request-folder", "prompt-hook-script", "transcript",
          "delegation-folder", "memory-folder")
EXEMPT_COMMANDS = ("echo", "printf", "grep", "rg", "git commit", "gh",
                   "compass", "cat", "tee", "ls", "wc", "stat", "du", "test", "[")
MIN_PER_THING, MIN_PER_EXEMPT = 25, 3
PLACEHOLDERS = ("{request}", "{requests_dir}", "{script}", "{transcript}",
                "{session}", "{home}", "{memory}", "{delegation}", "{project}")


@dataclass(frozen=True)
class Case:
    id: str              # "REQ-07", "SCR-03", "TRN-12", "DEL-04", "MEM-20", "OK-01"
    thing: str           # one of THINGS
    code: str | None     # refusal code the hook must give; None for an allowed control
    tool: str            # "Bash", "Read", "Grep", "Edit" or "Write"
    command: str = ""    # Bash only; holds placeholders
    tool_input: dict = field(default_factory=dict)   # non-Bash only; holds placeholders
    exempt: str | None = None     # the exempt command this row attacks, else None
    twin_of: str | None = None    # the TRC id of the loosening it pairs with


def _bash(prefix, thing, code, rows):
    """Rows are `command` or `(command, exempt)` or `(command, exempt, twin)`."""
    out = []
    for n, row in enumerate(rows, 1):
        command, exempt, twin = (row, None, None) if isinstance(row, str) else (
            tuple(row) + (None,) * (3 - len(row)))
        out.append(Case(f"{prefix}-{n:02d}", thing, code, "Bash", command, {}, exempt, twin))
    return out


def _tools(prefix, thing, code, rows, start=1):
    """Rows are `(tool, tool_input)` or `(tool, tool_input, twin)`."""
    out = []
    for n, row in enumerate(rows, start):
        tool, tool_input, twin = tuple(row) + (None,) * (3 - len(row))
        out.append(Case(f"{prefix}-{n:02d}", thing, code, tool, "", dict(tool_input), None, twin))
    return out


# --- the request folder: 38 rows, then the exempt-command rows -------------------------------

_REQUEST_FOLDER = _bash("REQ", "request-folder", REQ, [
    # read the content (8)
    ("cat {request}", "cat", "TRC-014"), "head -3 {request}", "tail -n1 {request}",
    "sed -n p {request}", "awk '{print}' {request}", "less {request}", "xxd {request}",
    "base64 {request}",
    # write, copy, delete (7)
    ("echo x > {request}", "echo", "TRC-014"), "echo x >> {request}",
    ("cp /tmp/a {request}", None, "TRC-014"), "mv /tmp/a {request}", "rm {request}",
    ("sed -i '' s/a/b/ {request}", None, "TRC-014"), "touch {request}",
    # enter or walk the folder (4)
    ("cd {requests_dir}", None, "TRC-014"), ("rm -r {requests_dir}", None, "TRC-014"),
    "find {requests_dir} -type f -exec cat {} +", "pushd {requests_dir}",
    # a message or a wrapper hides it (7)
    ('git commit -m "$(cat {request})"', "git commit", "TRC-002"),
    'git commit -m "`cat {request}`"',
    ('bash -c "cat {request}"', None, "TRC-002"),
    ('echo "cat {request}" | sh', "echo", "TRC-002"),
    "bash <<'EOF'\ncat {request}\nEOF",
    'git commit -m "$(<{request})"',
    'eval "cat {request}"',
    # an exempt command misused (8)
    ("ls -d {requests_dir}/* | xargs cat", "ls", "TRC-037"),
    ("cat $(ls {requests_dir})", "ls", "TRC-038"),
    ("cat `<{request}`", None, "TRC-039"),
    ("cat <(wc -l {request})", None, "TRC-040"),
    ("grep -f {request} x", "grep", "TRC-041"),
    ("grep -e x {request}", "grep", "TRC-041"),
    ("wc --files0-from={request}", "wc", "TRC-042"),
    ("wc -l --files0-from=- < {request}", None, "TRC-042"),
    # an option whose value is a path (3)
    ("gh pr create --body-file {request}", "gh", "TRC-051"),
    ("git commit -F {request}", "git commit", "TRC-051"),
    ("git commit --file={request}", "git commit", "TRC-051"),
    # a script that reads it (1)
    ("cat > /tmp/s.sh <<'EOF'\ncat {request}\nEOF\nsh /tmp/s.sh", None, "TRC-044"),
])

# Each exempt command has at least three rows (TRC-054). The rows below add the
# ones of the design's table that the families above do not already hold.
_EXEMPT_REQUEST = _bash("EXM", "request-folder", REQ, [
    ('echo "$(<{request})"', "echo"), ("echo $(wc -l {request})", "echo"),
    ("printf x > {request}", "printf"), ("printf 'cat {request}' | bash", "printf"),
    ('printf "$(cat {request})"', "printf"),
    ("grep -rnf {request} x", "grep"),
    ("rg --file {request} x", "rg"), ("rg x {request}", "rg"),
    ("gh issue comment 5 --body-file {request}", "gh"),
    ("gh pr create --body-file={request}", "gh"),
    ('gh pr create --body "$(cat {request})"', "gh"),
    ('compass quick-fix start --title x --note "$(cat {request})"', "compass"),
    ('compass x --note "`cat {request}`"', "compass"),
    ("cat < {request}", "cat"),
    ("printf x | tee -a {request}", "tee"), ("echo x | tee {request}", "tee"),
    ("tee {request} < /dev/null", "tee"),
    ("wc -l {request} | cat", "wc"), ("echo $(wc -l {request})", "wc"),
    ("stat {request} | sh", "stat"), ("echo `stat {request}`", "stat"),
    ("diff <(stat {request}) /dev/null", "stat"),
    ("du --files0-from={request}", "du"), ("du {request} | xargs cat", "du"),
    ("cat <(du {request})", "du"),
    ("echo $(test -f {request})", "test"), ("test -f {request} | sh", "test"),
    ("cat <(test -f {request})", "test"),
    ("[ -f {request} ] | sh", "["), ("echo $([ -f {request} ])", "["),
    ("cat <([ -f {request} ])", "["),
])
# The code of a delegated approval is the caller rule, not a path rule.
_EXEMPT_CALLER = [Case("EXM-90", "delegation-folder", CALLER, "Bash",
                       "compass evidence approve --check c --delegated", {}, "compass", None)]
# The exempt `ls` and `cat` rows that reach other protected things.
_EXEMPT_OTHER = [
    Case("EXM-91", "transcript", TRN, "Bash", "ls -R {home}", {}, "ls", "TRC-006"),
    Case("EXM-92", "prompt-hook-script", REQ, "Bash", "cat {script} | bash", {}, "cat", "TRC-043"),
    Case("EXM-93", "prompt-hook-script", REQ, "Bash", "grep x > {script}", {}, "grep", "TRC-043"),
    Case("EXM-94", "prompt-hook-script", REQ, "Bash", "rg --pre {script} x .", {}, "rg", "TRC-043"),
]

# --- the prompt hook script: 27 rows ----------------------------------------------------------

_SCRIPT = _bash("SCR", "prompt-hook-script", REQ, [
    # run it (8)
    ("bash {script} < event.json", None, "TRC-016"), ("./{script}", None, "TRC-016"),
    "sh {script}", ("source {script}", None, "TRC-016"), ". {script}",
    ('sh -c "{script} < event.json"', None, "TRC-016"),
    ("echo '{}' | {script}", None, "TRC-016"), "xargs {script}",
    # copy or replace it (5)
    ("cp {script} /tmp/p.sh", None, "TRC-016"), "mv /tmp/p.sh {script}",
    "grep x > {script}", "echo x > {script}", "tee {script} < /dev/null",
    # an option or a variable runs or writes it (8)
    ("git log --output={script} --format=%B -1", None, "TRC-043"),
    ("git diff --output={script}", None, "TRC-043"),
    ("git show --output={script}", None, "TRC-043"),
    ("rg --pre {script} x .", None, "TRC-043"), ("rg --pre={script} x .", None, "TRC-043"),
    ("GIT_EXTERNAL_DIFF={script} git diff", None, "TRC-043"),
    ("git log --exec={script}", None, "TRC-043"),
    ("git -c alias.x='!{script}' x", None, "TRC-016"),
    # a reader piped on (3)
    ("cat {script} | bash", None, "TRC-043"), "cat {script} | sh", "cat {script} | xargs sh",
    # a reader in a pipe or a substitution: no exemption (3)
    ("cat {script} | head", None, "TRC-015"), "echo $(cat {script})", "cat <(cat {script})",
])

# --- the transcript: 33 rows -----------------------------------------------------------------

_TRANSCRIPT = _bash("TRN", "transcript", TRN, [
    # read the file by path (6)
    ("cat {transcript}", None, "TRC-004"),
    ('tail "$CLAUDE_CONFIG_DIR"/projects/x/y.jsonl', None, "TRC-004"),
    ("grep confirm {home}/.claude-ayeo/projects/*/*.jsonl", None, "TRC-004"),
    ('cat "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/-p/{session}.jsonl"', None, "TRC-004"),
    "jq . {transcript}", "strings {transcript}",
    # a message hides it (4)
    ('git commit -m "$(cat {transcript})"', None, "TRC-004"),
    ("echo x | tee {transcript}", None, "TRC-004"),
    'echo "`cat {transcript}`"', 'bash -c "cat {transcript}"',
    # a listing that reaches the folder (5)
    ("ls {home}/.claude/projects/-p", None, "TRC-006"), ("ls {home}/.claude", None, "TRC-006"),
    ("ls -R {home}", None, "TRC-006"), ("ls {home}/*", None, "TRC-006"),
    "ls -d {home}/.claude*",
    # a read or an entry above the folder (4)
    ("cd {home}", None, "TRC-006"), ("grep -r confirm {home}", None, "TRC-006"),
    ("cd {home} && grep -r confirm .", None, "TRC-006"),
    "find {home} -name '*.jsonl'",
    # a normalised path (8)
    ("ls {home}/dev/../.claude/projects/-p", None, "TRC-046"),
    ("ls {home}//.claude", None, "TRC-046"),
    ("ls ~ada/.claude/projects/-p", None, "TRC-046"),
    ("ls {home}/.CLAUDE/projects/-p", None, "TRC-046"),
    ("ls {home}/./.claude", None, "TRC-046"), ("ls {home}/.cl*", None, "TRC-046"),
    ("ls -aR {home}", None, "TRC-046"), ("ls $HOME/dev/../.claude", None, "TRC-046"),
    # the memory folder from Bash (4)
    ("cat {memory}/MEMORY.md", None, "TRC-019"), ("ls {memory}", None, "TRC-019"),
    ("grep -rn x {memory}", None, "TRC-019"), ("cd {memory}", None, "TRC-019"),
    # a script that reads it (2)
    ("cat > /tmp/s.sh <<'EOF'\ncat {transcript}\nEOF\n. /tmp/s.sh", None, "TRC-044"),
    ("cat > /tmp/s.sh <<'EOF'\ncat {transcript}\nEOF\nsh /tmp/s.sh", None, "TRC-044"),
])

# --- the delegation folder: 26 rows -----------------------------------------------------------

_DELEGATION = _bash("DEL", "delegation-folder", DEL, [
    # read (6)
    ("cat {delegation}", None, "TRC-012"), "head {delegation}", "grep x {delegation}",
    "jq . {delegation}", "cat .compass/delegations/*", ("cat .compass/deleg*/*", None, "TRC-012"),
    # write or delete (6)
    ("rm {delegation}", None, "TRC-012"),
    ("echo x > .compass/delegations/DL-2.yml", None, "TRC-012"),
    "cp /tmp/a {delegation}", "touch {delegation}", "rm -r .compass/delegations",
    "mv {delegation} /tmp",
    # a message or a wrapper hides it (5)
    ('git commit -m "$(cat {delegation})"', None, "TRC-012"),
    'bash -c "cat {delegation}"', 'echo "cat {delegation}" | sh',
    'echo "`cat {delegation}`"', "cat <(cat {delegation})",
    # a glob that reaches it (5)
    "cat .compass/d*/*", "cat .compass/deleg?tions/*", "ls .compass/deleg*",
    "cat **/DL-*.yml", "cat .compass/delegations/DL-?.yml",
    # a script that reads it (4)
    ("cat > /tmp/s.sh <<'EOF'\ncat {delegation}\nEOF\nsh /tmp/s.sh", None, "TRC-044"),
    ("cat > /tmp/s.sh <<'EOF'\ncat {delegation}\nEOF\nsource /tmp/s.sh", None, "TRC-044"),
    ("cat > /tmp/s.sh <<'EOF'\ncat {delegation}\nEOF\n. /tmp/s.sh", None, "TRC-044"),
    ("cat > ./s.sh <<'EOF'\ncat {delegation}\nEOF\n./s.sh", None, "TRC-044"),
    # no `ls` exemption for the delegation folder
    "ls .compass/delegations",
])

# --- the memory folder: 29 rows ---------------------------------------------------------------

_P = "{home}/.claude/projects"
_MEMORY = (
    # the transcript and lookalikes through a tool (8)
    _tools("MEM", "memory-folder", TRN, [
        ("Read", {"file_path": "{transcript}"}, "TRC-018"),
        ("Write", {"file_path": "{transcript}"}, "TRC-018"),
        ("Read", {"file_path": "{memory}/../{session}.jsonl"}, "TRC-018"),
        ("Grep", {"pattern": "x", "path": _P + "/-p"}, "TRC-018"),
        ("Read", {"file_path": _P + "/memory/{session}.jsonl"}, "TRC-018"),
        ("Read", {"file_path": _P + "/-p/memory.jsonl"}, "TRC-018"),
        ("Read", {"file_path": _P + "/-p/memory-old/x.md"}, "TRC-018"),
        ("Edit", {"file_path": _P + "/memory/x.md"}, "TRC-018"),
    ])
    # a climb out of the folder (8)
    + _tools("MEM", "memory-folder", TRN, [
        ("Grep", {"pattern": "x", "path": "{memory}", "glob": "../*.jsonl"}, "TRC-047"),
        ("Grep", {"pattern": "x", "path": "{memory}", "glob": "../**"}, "TRC-047"),
        ("Grep", {"pattern": "x", "path": "{memory}/.."}, "TRC-047"),
        ("Read", {"file_path": "{memory}/../{session}.jsonl"}, "TRC-047"),
        ("Write", {"file_path": "{memory}/./../{session}.jsonl"}, "TRC-047"),
        ("Read", {"file_path": "{memory}/link"}, "TRC-047"),
        ("Edit", {"file_path": "{memory}/link"}, "TRC-047"),
        ("Grep", {"pattern": "x", "path": "{memory}", "glob": "a/../../*.jsonl"}, "TRC-047"),
    ], start=9)
    # Bash on the folder (6)
    + [Case(f"MEM-{n:02d}", "memory-folder", TRN, "Bash", command, {}, None, "TRC-019")
       for n, command in enumerate([
           "cat {memory}/MEMORY.md", "ls {memory}", "grep -rn x {memory}", "cd {memory}",
           "rm {memory}/x.md", "echo x > {memory}/x.md"], 17)]
    # the wrong shape of path (the first five of the design's seven)
    + _tools("MEM", "memory-folder", TRN, [
        ("Write", {"file_path": _P + "/-p/q/memory/x.md"}, "TRC-018"),
        ("Write", {"file_path": _P + "/memory/x.md"}, "TRC-018"),
        ("Read", {"file_path": _P + "/-p/MEMORY.md"}, "TRC-018"),
        ("Write", {"file_path": _P + "/-p/memory"}, "TRC-018"),
        ("Read", {"file_path": _P + "/-p/memory.md"}, "TRC-018"),
    ], start=23)
)

# Two rows of the design's "wrong shape" family name a path that is not under a
# `.claude*/projects` folder. The guard before this change does not refuse them
# (a finding for the orchestrator, reported in result.md): a path in a
# configuration folder that holds no `projects` folder, and a `projects` folder
# whose parent is not a configuration folder.
UNREFUSED_ON_BASE = tuple(_tools("MEM", "memory-folder", TRN, [
    ("Read", {"file_path": "{home}/.claude/memory/x.md"}, "TRC-018"),
    ("Read", {"file_path": "{home}/projects/-p/memory/x.md"}, "TRC-018"),
], start=28))

REFUSED = tuple(_REQUEST_FOLDER + _EXEMPT_REQUEST + _EXEMPT_CALLER + _EXEMPT_OTHER
                + _SCRIPT + _TRANSCRIPT + _DELEGATION + _MEMORY)

# Text that pipes into a stage that could write or run it stays refused, as it is
# now: only `tee`, `cat`, `head`, `tail`, `wc`, `sort`, `uniq`, `cut`, `tr`, `less`,
# `more`, `grep`, `egrep`, `fgrep`, `rg`, `diff` and `pbcopy` read piped text as data.
# `git`, `gh` and `compass` can turn it into a write (`git apply`, `gh api --input -`),
# so they are not in that list. These rows name a protected word in the text.
_TEXT_TO_WRITER = _bash("PIP", "request-folder", REQ, [
    ('echo "see approval-requests" | git commit -F -', "echo", "TRC-001"),
    ('echo "see approval-requests" | gh api --input -', "echo", "TRC-001"),
    ('printf "see approval-requests" | compass quick-fix start --note -', "printf", "TRC-001"),
    ('echo "see approval-requests" | mystery', "echo", "TRC-001"),
])
REFUSED = REFUSED + tuple(_TEXT_TO_WRITER)

# --- the controls: calls that must pass -------------------------------------------------------

_OK = []


def _ok(twin, commands, thing="request-folder"):
    start = len(_OK) + 1
    for n, command in enumerate(commands, start):
        _OK.append(Case(f"OK-{n:02d}", thing, None, "Bash", command, {}, None, twin))


_ok("TRC-001", [
    'git commit -m "Document the approval-requests folder and prompt-approval.sh"',
    'gh issue comment 5 --body "The hook blocks ls of approval-requests"',
    'echo "see prompt-approval.sh"',
    "grep -rn approval-requests docs/",
    "cat > docs/compass/issue-a/notes.md <<'EOF'\nthe approval-requests folder\nEOF",
    "git commit -m \"$(cat <<'EOF'\nExplain approval-requests\nEOF\n)\"",
    # text piped into a stage that only reads it stays text
    'echo "see approval-requests" | head -1',
    'printf "see prompt-approval.sh" | wc -w',
])
_ok("TRC-003", [
    'git commit -m "Fix CLAUDE_CONFIG_DIR handling"',
    'git commit -m "Expand ~ in paths"',
    'gh pr create --title "Allow memory writes" --body "Writes to ~/.claude/projects/x/memory are refused"',
    'compass quick-fix start --title "x" --note "see ~/.claude/projects/x"',
    'grep -rn ".claude/projects" docs/',
    "echo $HOME",
    "echo $CLAUDE_CONFIG_DIR",
], thing="transcript")
_ok("TRC-005", ["ls ~", "ls $HOME", "ls {home}", "ls -la ~/dev/"], thing="transcript")
_ok("TRC-007", [
    r"awk -F$'\t' '{print $1}' /Users/ada/dev/compass-700/x.tsv",
    r"git log --format=$'%h\t%s' -- cli/compass_pkg",
    r"IFS=$'\n' ; ls /Users/ada/dev/compass-700/docs",
], thing="delegation-folder")
_ok("TRC-009", [
    'git commit -m "Explain compass evidence {red,green} files"',
    'git commit -m "Document the --delegated flag for compass evidence approve"',
    'git commit -m "Reject evidence approve --delegated without --as"',
    "git log --grep='--delegated' --oneline",
], thing="delegation-folder")
_ok("TRC-011", [
    'git commit -m "Explain the .compass/delegations folder"',
    "cat > docs/compass/issue-a/d.md <<'EOF'\nThe .compass/delegations folder holds salts.\nEOF",
    'grep -rn ".compass/delegations" docs/',
], thing="delegation-folder")
_ok("TRC-013", [
    "ls .compass/work/issue-a/approval-requests", "ls -la docs/approval-requests",
    "wc -l {request}", "stat {request}",
])
_ok("TRC-015", [
    "ls -la hooks/prompt-approval.sh", "wc -l hooks/prompt-approval.sh docs/refusal-codes.md",
    "git log --oneline -- hooks/prompt-approval.sh", "git add hooks/prompt-approval.sh",
    "cat hooks/prompt-approval.sh",
], thing="prompt-hook-script")
_ok("TRC-045", ["cat > /tmp/s.sh <<'EOF'\nls docs\nEOF\nsh /tmp/s.sh"])
_ok("TRC-050", [
    'git commit --message="see approval-requests and ~/.claude/projects"',
    'git commit --message "see approval-requests"',
    'gh issue comment 5 --body="the .compass/delegations folder"',
    'compass quick-fix start --note="see ~/.claude/projects/x"',
])
_ok_tools = _tools("OK", "memory-folder", None, [
    ("Write", {"file_path": "{memory}/x.md"}, "TRC-017"),
    ("Edit", {"file_path": "{memory}/MEMORY.md"}, "TRC-017"),
    ("Read", {"file_path": "{memory}/MEMORY.md"}, "TRC-017"),
    ("Read", {"file_path": _P + "/-p/Memory/MEMORY.md"}, "TRC-017"),
    ("Grep", {"pattern": "x", "path": "{memory}"}, "TRC-017"),
    ("Grep", {"pattern": "x", "cwd": "{memory}"}, "TRC-017"),
    ("Write", {"file_path": "{home}/.claude-ayeo/projects/-q/memory/x.md"}, "TRC-017"),
    ("Edit", {"file_path": _P + "/-q/memory/MEMORY.md"}, "TRC-017"),
], start=len(_OK) + 1)

ALLOWED = tuple(_OK + _ok_tools)


def controls_for(twin):
    """The allowed rows that belong to the loosening scenario `twin`."""
    return [c for c in ALLOWED if c.twin_of == twin]


def refused_for(twin):
    """The refused rows that pair with the loosening scenario `twin`."""
    return [c for c in REFUSED if c.twin_of == twin]


# --- the world a row runs in -----------------------------------------------------------------

REQUEST = ".compass/work/issue-a/approval-requests/pending/1.yml"
SESSION = "s1"


class World(NamedTuple):
    home: Path
    project: Path
    transcript: Path


def build_world():
    """A temporary home and a Compass project with issue `issue-a`, outside any
    path that holds the word `test`, with a red on record so only the guard can
    refuse. The caller removes `home.parent` when done (see `drop_world`)."""
    from conftest import write_red_record
    base = Path(tempfile.mkdtemp(prefix="compass-guard-")).resolve()
    home = base / "ada"
    project = base / "proj"
    transcript = home / ".claude" / "projects" / "-p" / f"{SESSION}.jsonl"
    memory = transcript.parent / "memory"
    for folder in (transcript.parent, memory, home / ".claude-ayeo" / "projects" / "-q" / "memory",
                   home / "dev"):
        folder.mkdir(parents=True, exist_ok=True)
    transcript.write_text('{"content": "confirm 1a2b-3c4d-5e6f-7a8b"}\n', encoding="utf-8")
    (memory / "MEMORY.md").write_text("# memory\n", encoding="utf-8")
    os.symlink(transcript, memory / "link")
    task = project / ".compass" / "work" / "issue-a"
    task.mkdir(parents=True)
    (project / ".compass" / "current-task").write_text("issue-a", encoding="utf-8")
    (task / "delivery-approach.md").write_text("# Route\n\nroute: express\n", encoding="utf-8")
    write_red_record(task)
    pending = task / "approval-requests" / "pending"
    pending.mkdir(parents=True)
    (pending / "1.yml").write_text("number: 1\n", encoding="utf-8")
    delegations = project / ".compass" / "delegations"
    delegations.mkdir()
    (delegations / "DL-1.yml").write_text("id: DL-1\n", encoding="utf-8")
    for name, body in (("hooks/prompt-approval.sh", "#!/bin/sh\n"), ("docs/refusal-codes.md", "x\n"),
                       ("docs/approval-requests/note.md", "x\n")):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return World(home, project, transcript)


def drop_world(world):
    shutil.rmtree(world.home.parent, ignore_errors=True)


def expand(text, world):
    """Replace each placeholder of `text` by its value in `world`."""
    memory = world.transcript.parent / "memory"
    values = {"{requests_dir}": str(Path(REQUEST).parent.parent), "{request}": REQUEST,
              "{script}": "hooks/prompt-approval.sh", "{transcript}": str(world.transcript),
              "{session}": SESSION, "{home}": str(world.home), "{memory}": str(memory),
              "{delegation}": ".compass/delegations/DL-1.yml", "{project}": str(world.project)}
    for key, value in values.items():
        text = text.replace(key, value)
    return text


def _expand_any(value, world):
    if isinstance(value, str):
        return expand(value, world)
    if isinstance(value, dict):
        return {k: _expand_any(v, world) for k, v in value.items()}
    return value


def payload(case, *, home, project, transcript, agent_type=None):
    """The hook input of one row: the event Claude Code sends to the pre-tool hook."""
    world = World(Path(home), Path(project), Path(transcript))
    if case.tool == "Bash":
        tool_input = {"command": expand(case.command, world)}
        cwd = str(project)
    else:
        tool_input = _expand_any(case.tool_input, world)
        cwd = tool_input.pop("cwd", str(project))
    body = {"tool_name": case.tool, "session_id": "sess-guard", "tool_input": tool_input,
            "cwd": cwd, "transcript_path": str(transcript)}
    if agent_type:
        body["agent_type"] = agent_type
    return body


def hook_env(world):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(world.project), HOME=str(world.home),
               PYTHONDONTWRITEBYTECODE="1")
    env.pop("CLAUDE_CONFIG_DIR", None)
    return env


def run_hook(world, body):
    """Run `hooks/pre-tool.sh` on the event `body`."""
    return subprocess.run(["bash", str(HOOK_PATH)], input=json.dumps(body), capture_output=True,
                          text=True, env=hook_env(world), cwd=str(world.project))


def run_row(world, case, **kw):
    return run_hook(world, payload(case, home=world.home, project=world.project,
                                   transcript=world.transcript, **kw))


def bash_event(world, command):
    return {"tool_name": "Bash", "session_id": "sess-guard",
            "tool_input": {"command": expand(command, world)}, "cwd": str(world.project),
            "transcript_path": str(world.transcript)}


def call(world, tool, tool_input, cwd=None):
    """An event for a tool call whose input holds placeholders."""
    return {"tool_name": tool, "session_id": "sess-guard",
            "tool_input": _expand_any(tool_input, world),
            "cwd": expand(cwd, world) if cwd else str(world.project),
            "transcript_path": str(world.transcript)}


def verdict(result):
    """`"allowed"` for exit 0, the refusal code for exit 2, else the raw outcome."""
    if result.returncode == 0:
        return "allowed"
    if result.returncode == 2:
        import re
        found = re.findall(r"\[([a-z0-9-]+)\]\s*$", result.stderr.strip(), re.M)
        return found[-1] if found else "refused-without-code"
    return f"exit {result.returncode}: {result.stderr.strip()[:120]}"


def misses(world, events, want):
    """The events whose hook verdict is not `want` (`"allowed"` or a code), each
    as a line that names the event and what the hook answered."""
    found = []
    for event in events:
        got = verdict(run_hook(world, event))
        if got != want:
            tool_input = event["tool_input"]
            shown = tool_input.get("command") or json.dumps(tool_input, sort_keys=True)
            found.append(f"{event['tool_name']} {shown!r}: wanted {want}, got {got}")
    return found
