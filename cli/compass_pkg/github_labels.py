# compass_pkg.github_labels - an issue's labels and state, written to GitHub
"""Writes an issue's domain labels and workflow state to its linked GitHub issue.

A project opts in with the settings key `github_labels` in `compass.yml`:
`domain` writes the issue's declared domain labels, `status` writes the
`status:<state>` label and, on a closed issue, `close:<reason>`. Both default
to off, and with both off nothing in this module reaches `gh`.

The manifest is the source of truth and GitHub is only written. A sync
compares the labels Compass owns with the labels on the GitHub issue and
writes the difference, so a label removed on GitHub is found and put back by
the next write. It is reported as drift by `compass issue lint` and never read
back into the manifest.

Compass owns the five `status:` labels and three `close:` labels it writes, and
the domain labels the project declared. It adds and removes nothing else.

`gh` is called with an argument list and no shell, with the person's own
credentials. Compass stores and reads no token.
"""
# DEPENDENCY: compass_pkg.core, compass_pkg.lifecycle, compass_pkg.status_words,
# compass_pkg.project_settings, compass_pkg.layers, compass_pkg.effective,
# compass_pkg.atomic_io and compass_pkg.terminal. Nothing imports this module
# except the entry point, `issue lint` and the registry of verbs.
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import yaml

from compass_pkg import lifecycle, project_settings, status_words
from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import CompassError, load_manifest, resolve_issue_dir, save_manifest
from compass_pkg.terminal import say

SETTING = "github_labels"
DOMAIN, STATUS = "domain", "status"

STATUS_PREFIX, CLOSE_PREFIX = "status:", "close:"
#: The labels Compass writes under its own prefixes. Only these are removed,
#: so a label a team made under the same prefix (`status:legal-hold`) stays.
STATUS_LABELS = tuple(STATUS_PREFIX + state for state in status_words.STATES)
CLOSE_LABELS = tuple(CLOSE_PREFIX + reason for reason in status_words.CLOSE_REASONS)

#: One fixed colour per kind of label, used only when Compass creates it.
COLOURS = {"status": "1d76db", "close": "d73a4a", "domain": "0e8a16"}
DESCRIPTION = "Set by Compass"

#: Commands that change an issue's records. After one exits 0, the issue's
#: labels are brought up to date. The value names an argument that must be set
#: for the command to count (`approach evaluate` writes only with `--write`).
TRIGGERS = {
    "cmd_route_evaluate": "write",
    "cmd_task_set_status": None,
    "cmd_task_status_remove": None,
    "cmd_issue_link": None,
    "cmd_land_commit": None,
    "cmd_quick_fix_finish": None,
    "cmd_scenario_add": None,
    "cmd_gate_pass": None,
    "cmd_issue_artifact": None,
    "cmd_subtask_add": None,
}

_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_NAME = r"(?!-)[A-Za-z0-9._-]{1,100}"
_NUMBER = r"[1-9][0-9]{0,8}"
_SHORT = re.compile(rf"({_OWNER}/{_NAME})#({_NUMBER})")
_URL = re.compile(rf"https://github\.com/({_OWNER}/{_NAME})/issues/({_NUMBER})/?")
_REPO = re.compile(rf"{_OWNER}/{_NAME}")
#: What a label name may hold. No comma, quote, shell character or leading dash,
#: so a name is safe as one argument to `gh` and as one item of a list.
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._:/-]{0,49}")
_TIMEOUT = 60


class SyncError(Exception):
    """A sync that could not finish. Its text names the problem for a person."""


# --- the link ----------------------------------------------------------------

def parse_target(text):
    """`(repo, number)` from `owner/repo#number` or an issue URL on github.com,
    or None. The result is safe to pass to `gh` as separate arguments."""
    for pattern in (_SHORT, _URL):
        found = pattern.fullmatch(text or "")
        if found and _repo_ok(found.group(1)):
            return found.group(1), int(found.group(2))
    return None


def _repo_ok(repo):
    """A repository name of `.` or `..` matches the pattern but names no repository."""
    return bool(_REPO.fullmatch(repo)) and repo.split("/")[1] not in (".", "..")


def link_of(task):
    """`(repo, number)` from the manifest's `github` field, None when the issue
    is not linked. A field that was edited into another shape is an error,
    because its values would reach `gh`."""
    value = task.get("github") if isinstance(task, dict) else None
    if value is None:
        return None
    repo = value.get("repo") if isinstance(value, dict) else None
    number = value.get("number") if isinstance(value, dict) else None
    if not (isinstance(repo, str) and _repo_ok(repo)
            and isinstance(number, int) and not isinstance(number, bool)
            and 1 <= number <= 999999999):
        raise SyncError("the manifest's `github` field is not {repo: owner/repo, number: N}")
    return repo, number


def cmd_issue_link(args):
    verb = "compass issue link"
    target = parse_target(args.github)
    if target is None:
        raise CompassError(
            f"{verb}: '{args.github}' is not a GitHub issue; use owner/repo#number "
            "or https://github.com/owner/repo/issues/number. Nothing was written.")
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    repo, number = target
    task["github"] = {"repo": repo, "number": number}
    save_manifest(task, path)
    return say(args, f"{verb}: {task.get('issue')} -> {repo}#{number}.",
               issue=task.get("issue"), repo=repo, number=number)


# --- the settings --------------------------------------------------------------

def switches(project_root):
    """`(domain, status)`: which writes the project switched on. Only the value
    `true` turns one on, and a file that cannot be read turns both off."""
    try:
        block = project_settings.settings(project_root).get(SETTING)
    except CompassError:
        return False, False
    if not isinstance(block, dict):
        return False, False
    return block.get(DOMAIN) is True, block.get(STATUS) is True


def declared_labels(task_dir):
    """The domain labels the project declared in the configuration the issue
    runs against: the labels dimension's common list, and every label a rule
    names in `labels_any`."""
    from compass_pkg import effective
    from compass_pkg.core import find_governance, load_yaml
    view = effective.view_or_legacy(task_dir)
    if view is not None:
        policy = view.evaluator_policy()
    else:
        policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))
    found = {str(x) for x in (policy.get("assessment_vocabulary") or {}).get("labels_common") or []}
    stack = [policy]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "labels_any" and isinstance(value, list):
                    found |= {str(x) for x in value}
                else:
                    stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
    return found


# --- what the labels should be ---------------------------------------------------

def wanted_and_owned(task, task_dir, domain_on, status_on):
    """`(wanted, owned, skipped)`: the labels the issue should carry, the labels
    Compass may add or remove, and the declared labels whose names are not safe
    to send."""
    wanted, owned, skipped = set(), set(), []
    if status_on:
        owned |= set(STATUS_LABELS) | set(CLOSE_LABELS)
        state = lifecycle.state_of(task, task_dir)
        wanted.add(STATUS_PREFIX + state)
        if state == status_words.DONE and status_words.close_reason(task):
            wanted.add(CLOSE_PREFIX + status_words.close_reason(task))
    if domain_on:
        declared = declared_labels(task_dir)
        safe = {name for name in declared if _LABEL.fullmatch(name)}
        assessed = {str(x) for x in (task.get("assessment") or {}).get("labels") or []}
        owned |= safe
        wanted |= assessed & safe
        skipped = sorted((assessed & declared) - safe)
    return wanted, owned, skipped


def difference(current, wanted, owned):
    """`(add, remove)`: what to write so the issue carries every wanted label
    and no owned label that is not wanted. Labels Compass does not own are
    never in either list."""
    return sorted(wanted - current), sorted((owned - wanted) & current)


# --- gh ----------------------------------------------------------------------------

def _explain(stderr):
    text = " ".join((stderr or "").split())
    if "gh auth login" in text or "not logged in" in text.lower():
        return "gh is not logged in (run `gh auth login`)"
    return "gh failed: " + (text[:160] if text else "no message")


def _gh(args):
    """Run `gh` with an argument list and no shell; return its standard output."""
    env = dict(os.environ, GH_PROMPT_DISABLED="1")
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True,
                              timeout=_TIMEOUT, env=env, check=False)
    except FileNotFoundError:
        raise SyncError("gh is not installed or not on PATH") from None
    except subprocess.TimeoutExpired:
        raise SyncError(f"gh did not answer within {_TIMEOUT} seconds") from None
    except OSError as exc:
        raise SyncError(f"gh could not run: {exc}") from None
    if done.returncode != 0:
        raise SyncError(_explain(done.stderr))
    return done.stdout


def _names(text, key=None):
    try:
        data = json.loads(text)
        items = data.get(key) if key else data
        return {str(item["name"]) for item in items}
    except (ValueError, AttributeError, KeyError, TypeError):
        raise SyncError("gh gave labels in a form Compass does not read") from None


def issue_labels(repo, number):
    return _names(_gh(["issue", "view", str(number), "--repo", repo, "--json", "labels"]),
                  "labels")


def _colour(name):
    if name.startswith(STATUS_PREFIX):
        return COLOURS["status"]
    return COLOURS["close"] if name.startswith(CLOSE_PREFIX) else COLOURS["domain"]


def write_labels(repo, number, add, remove):
    """Create the labels the repository lacks, then edit the issue once."""
    if add:
        existing = _names(_gh(["label", "list", "--repo", repo, "--limit", "1000",
                               "--json", "name"]))
        for name in add:
            if name not in existing:
                _gh(["label", "create", name, "--repo", repo, "--color", _colour(name),
                     "--description", DESCRIPTION])
    edit = ["issue", "edit", str(number), "--repo", repo]
    for name in add:
        edit += ["--add-label", name]
    for name in remove:
        edit += ["--remove-label", name]
    _gh(edit)


# --- the sync ------------------------------------------------------------------------

def _project_root(task_dir):
    from compass_pkg import layers
    return layers.find_project_root(task_dir)


def _record_path(task_dir):
    return os.path.join(task_dir, "github-sync.yml")


def read_record(task_dir):
    try:
        with open(_record_path(task_dir), "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_record(task_dir, **fields):
    from compass_pkg.core import now_iso
    text = yaml.safe_dump({"at": now_iso(), **fields}, sort_keys=False)
    atomic_write_text(_record_path(task_dir), text)


def sync_issue(task, task_dir):
    """Bring the linked GitHub issue's labels to what the records say. Returns
    `(add, remove, skipped)`, or None when the issue is not linked or no switch
    is on. Raises `SyncError` when GitHub cannot be reached or read."""
    target = link_of(task)
    domain_on, status_on = switches(_project_root(task_dir))
    if target is None or not (domain_on or status_on):
        return None
    repo, number = target
    try:
        wanted, owned, skipped = wanted_and_owned(task, task_dir, domain_on, status_on)
    except CompassError as exc:
        raise SyncError(f"cannot read the configuration: {exc}") from None
    add, remove = difference(issue_labels(repo, number), wanted, owned)
    if add or remove:
        write_labels(repo, number, add, remove)
    _write_record(task_dir, error=None, state=sorted(wanted))
    return add, remove, skipped


def _skipped_line(skipped):
    return ("compass: github labels - skipped " + ", ".join(skipped)
            + "; a label name may hold letters, digits, spaces and . _ : / - only.")


def _fail_line(problem):
    return (f"compass: github labels not synced - {problem}. "
            "Run `compass issue labels sync` to retry.")


def after_command(args, code):
    """Called by the entry point after every command. Syncs the issue's labels
    when the command changed its records, and returns `code` unchanged: a sync
    never fails the work."""
    if code != 0:
        return code
    name = getattr(getattr(args, "func", None), "__name__", "")
    if name not in TRIGGERS or (TRIGGERS[name] and not getattr(args, TRIGGERS[name], False)):
        return code
    try:
        task_dir = resolve_issue_dir(getattr(args, "task", None))
        if not any(switches(_project_root(task_dir))):
            return code
        task, _ = load_manifest(task_dir)
        try:
            outcome = sync_issue(task, task_dir)
        except SyncError as exc:
            _write_record(task_dir, error=str(exc))
            sys.stderr.write(_fail_line(exc) + "\n")
            return code
        if outcome and outcome[2]:
            sys.stderr.write(_skipped_line(outcome[2]) + "\n")
    except Exception as exc:  # noqa: BLE001 - nothing here may fail the triggering command
        if isinstance(exc, CompassError):
            return code
        sys.stderr.write(_fail_line(f"unexpected {type(exc).__name__}") + "\n")
    return code


def cmd_labels_sync(args):
    verb = "compass issue labels sync"
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, _ = load_manifest(task_dir)
    slug = task.get("issue")
    try:
        target = link_of(task)
    except SyncError as exc:
        raise CompassError(f"{verb}: {exc}") from None
    if target is None:
        raise CompassError(
            f"{verb}: '{slug}' is not linked to a GitHub issue; run "
            "`compass issue link --github owner/repo#number` first.")
    if not any(switches(_project_root(task_dir))):
        return say(args, f"{verb}: nothing is switched on, so nothing was sent. Set "
                         "`github_labels` in compass.yml (docs/github-labels.md).",
                   issue=slug)
    try:
        add, remove, skipped = sync_issue(task, task_dir)
    except SyncError as exc:
        _write_record(task_dir, error=str(exc))
        raise CompassError(f"{verb}: {exc}") from None
    if skipped:
        sys.stderr.write(_skipped_line(skipped) + "\n")
    where = f"{target[0]}#{target[1]}"
    if not (add or remove):
        return say(args, f"{verb}: {slug} already matches {where}.", issue=slug)
    detail = ([f"added: {', '.join(add)}"] if add else []) \
        + ([f"removed: {', '.join(remove)}"] if remove else [])
    return say(args, f"{verb}: {slug} -> {where}.", detail=detail,
               issue=slug, added=add, removed=remove)


# --- issue lint ------------------------------------------------------------------------

def lint_notes(task, task_dir):
    """The lines `compass issue lint` prints about the labels. Empty when the
    issue is not linked, no switch is on, or GitHub matches. The lint keeps its
    exit code: a note is a report, not a failure."""
    try:
        target = link_of(task)
        domain_on, status_on = switches(_project_root(task_dir))
        if target is None or not (domain_on or status_on):
            return []
        problem = read_record(task_dir).get("error")
        if problem:
            return [f"github: out of sync - the last sync failed: {problem}. "
                    "Run `compass issue labels sync`."]
        wanted, owned, _ = wanted_and_owned(task, task_dir, domain_on, status_on)
        add, remove = difference(issue_labels(*target), wanted, owned)
    except SyncError as exc:
        return [f"github: out of sync - cannot read the labels on GitHub: {exc}."]
    except CompassError as exc:
        return [f"github: out of sync - cannot read the configuration: {exc}."]
    if not (add or remove):
        return []
    parts = ([f"missing on GitHub: {', '.join(add)}"] if add else []) \
        + ([f"not wanted on GitHub: {', '.join(remove)}"] if remove else [])
    return ["github: out of sync - " + "; ".join(parts)
            + ". Run `compass issue labels sync`."]


def register(pts, issue_arg):
    """`link` and `labels sync` under `compass issue`."""
    linker = pts.add_parser("link", help="link an issue to its GitHub issue")
    linker.add_argument("--github", required=True, metavar="TARGET",
                        help="owner/repo#number, or the issue's URL on github.com")
    issue_arg(linker)
    linker.set_defaults(func=cmd_issue_link, output_kind="hand-off")
    group = pts.add_parser("labels", help="an issue's labels on GitHub")
    verbs = group.add_subparsers(dest="labels_cmd", required=True)
    syncer = verbs.add_parser("sync", help="write an issue's labels to its GitHub issue now")
    issue_arg(syncer)
    syncer.set_defaults(func=cmd_labels_sync, output_kind="hand-off")
