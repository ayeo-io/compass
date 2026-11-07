# compass_pkg.issue_link - an issue's link to its GitHub issue and pull request
"""Stores the GitHub issue and pull request an issue is linked to, and runs `gh`.

`compass issue link set --github owner/repo#number` writes the manifest's
`github: {repo, number}` field. `--request` and `--requester` record who asked
for the issue and where (`request_link`, #356); neither calls `gh`. `--pr`
records the pull request that carries the issue, and after the merge the
approving reviews that are the ship approval (`pull_request_link`). `--pr`
then writes `trail.md` again; in committed mode, after the merge of a landed
issue, it prints `next: compass record commit --issue <slug>`, because the
merge fields are not in the commit that holds the record (#356). Linking
writes nothing to GitHub.

A target is checked against a strict pattern before it is stored, so nothing
that could be read as an option or a shell command reaches `gh`. `gh` is called
with an argument list and no shell, with the person's own credentials. Compass
stores and reads no token.
"""
# DEPENDENCY: standard library (os, re, subprocess) and compass_pkg.core,
# compass_pkg.project_settings, compass_pkg.request_link and compass_pkg.terminal;
# for `--pr`, committed_landing (the trail), record_mode and status_words.
# Imported by the entry point (the `link set` parser) and by pull_request_link,
# which uses the `gh` runner and the target patterns.
from __future__ import annotations

import os
import re
import subprocess

from compass_pkg import landing
from compass_pkg.core import CompassError, load_manifest, resolve_issue_dir, save_manifest
from compass_pkg.terminal import say

_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_NAME = r"(?!-)[A-Za-z0-9._-]{1,100}"
_NUMBER = r"[1-9][0-9]{0,8}"
_SHORT = re.compile(rf"({_OWNER}/{_NAME})#({_NUMBER})")
_URL = re.compile(rf"https://github\.com/({_OWNER}/{_NAME})/issues/({_NUMBER})/?")
_REPO = re.compile(rf"{_OWNER}/{_NAME}")
#: Seconds one `gh` call may take, so a hung `gh` does not hold a command for long.
_TIMEOUT = 15


class SyncError(Exception):
    """A `gh` call that could not finish. Its text names the problem for a person."""


class NotFound(SyncError):
    """`gh` reported HTTP 404: the thing asked for is not on GitHub, or not visible."""


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


def _project_root(task_dir):
    from compass_pkg import project_settings
    return project_settings.find_project_root(task_dir)


def cmd_issue_link(args):
    from compass_pkg import request_link
    verb = "compass issue link set"
    pr_text = getattr(args, "pr", None)
    request_text = getattr(args, "request", None)
    requester_text = getattr(args, "requester", None)
    if (args.github is None and pr_text is None and request_text is None
            and requester_text is None):
        raise CompassError(f"{verb}: name a GitHub issue with --github, a pull request "
                           "with --pr, or the request with --request and --requester. "
                           "Nothing was written.")
    target = None
    if args.github is not None:
        target = parse_target(args.github)
        if target is None:
            raise CompassError(
                f"{verb}: '{args.github}' is not a GitHub issue; use owner/repo#number "
                "or https://github.com/owner/repo/issues/number. Nothing was written.")
    link, request_target, requester = request_link.parse(request_text, requester_text, verb)
    if target is not None and request_target is not None and target != request_target:
        raise CompassError(
            f"{verb}: --github names {target[0]}#{target[1]} and --request names "
            f"{request_target[0]}#{request_target[1]}; name one GitHub issue. "
            "Nothing was written.")
    target = target or request_target
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    pr = None
    if pr_text is not None:
        # Read before anything is written, so a pull request `gh` cannot read
        # leaves the issue link unwritten too.
        from compass_pkg import pull_request_link
        pr = pull_request_link.read_pr(pr_text, _project_root(task_dir), verb)
    lines, fields = [], {"issue": task.get("issue")}
    if target is not None:
        repo, number = target
        task["github"] = {"repo": repo, "number": number}
        lines.append(f"{task.get('issue')} -> {repo}#{number}.")
        fields.update(repo=repo, number=number)
        if link is None:
            request_link.link_from_github(task, target)
    held = request_link.record(task, link, requester)
    if held is not None:
        lines.append(_request_line(task.get("issue"), held))
        fields.update(request=held)
    if pr is not None:
        lines += pull_request_link.apply(task, task.get("issue"), pr)
        fields.update(pull_request=task["pull_request"], land_commit=landing.land_commit(task, task_dir))
    save_manifest(task, path)
    follow_up = None
    if pr is not None:
        follow_up = _after_pr(task, task_dir, pr, lines)
        fields.update(next=follow_up)
    code = say(args, f"{verb}: {lines[0]}", detail=lines[1:] or None, **fields)
    if follow_up:
        from compass_pkg.terminal import resolve_mode
        if resolve_mode(args) in ("summary", "verbose"):
            print(f"next: {follow_up}")
    return code


def _after_pr(task, task_dir, pr, lines):
    """Write `trail.md` again after the pull request fields are saved, so the
    trail names them (#356, ADR-096). In committed mode, once the pull request
    is merged on a landed issue, return the command that commits the record:
    the merge fields came after the commit that holds the record, so they are
    not in it yet. Otherwise None."""
    from compass_pkg import committed_landing, record_mode, status_words
    if committed_landing.write_trail(task_dir):
        lines.append("trail.md written again.")
    if pr.merge_commit is None or not status_words.is_completed(task):
        return None
    root = _project_root(task_dir)
    try:
        committed = record_mode.mode(root, task_dir).mode == record_mode.COMMITTED
    except CompassError:
        committed = False
    if not committed:
        return None
    slug = os.path.basename(os.path.normpath(task_dir))
    return f"compass record commit --issue {slug}"


def _request_line(issue, held):
    """The line that reports the request record, naming a part still missing."""
    parts = [f"requested by {held['requester']} (recorded as a claim)"
             if held.get("requester") else "no requester yet (--requester)",
             held["link"] if held.get("link") else "no request link yet (--request)"]
    return f"{issue} request: {'; '.join(parts)}."


# --- gh ----------------------------------------------------------------------------

def _explain(stderr):
    text = " ".join((stderr or "").split())
    if "gh auth login" in text or "not logged in" in text.lower():
        return "gh is not logged in (run `gh auth login`)"
    return "gh failed: " + (text[:160] if text else "no message")


#: The variables `gh` needs: where to find programs and its own configuration, the
#: locale, the user's GitHub token and host (`GH_*`, `GITHUB_*`), the session bus
#: that reaches a Linux keyring holding the token, certificates and proxies. Any
#: other variable, such as another service's secret, is not passed.
_GH_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "TZ", "TERM", "NO_COLOR",
            "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS", "SSL_CERT_FILE",
            "SSL_CERT_DIR", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy",
            "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy")
_GH_KEEP_PREFIXES = ("LC_", "GH_", "GITHUB_")


def _gh_env():
    env = {k: v for k, v in os.environ.items()
           if k in _GH_KEEP or k.startswith(_GH_KEEP_PREFIXES)}
    env["GH_PROMPT_DISABLED"] = "1"
    return env


def _gh(args, stdin=None):
    """Run `gh` with an argument list and no shell; return its standard output.
    Text to send goes in `stdin`, never in `args`, so it cannot be read as an
    option and does not show in the process list."""
    env = _gh_env()
    try:
        done = subprocess.run(["gh", *args], capture_output=True, text=True, input=stdin,
                              timeout=_TIMEOUT, env=env, check=False)
    except FileNotFoundError:
        raise SyncError("gh is not installed or not on PATH") from None
    except subprocess.TimeoutExpired:
        raise SyncError(f"gh did not answer within {_TIMEOUT} seconds") from None
    except OSError as exc:
        raise SyncError(f"gh could not run: {exc}") from None
    if done.returncode != 0:
        if "HTTP 404" in (done.stderr or ""):
            raise NotFound(_explain(done.stderr))
        raise SyncError(_explain(done.stderr))
    return done.stdout


def register(pts, issue_arg):
    """`link set` under `compass issue`."""
    link_group = pts.add_parser("link", help="an issue's link to its GitHub issue")
    linker = link_group.add_subparsers(dest="link_cmd", required=True).add_parser(
        "set", help="link an issue to its GitHub issue")
    linker.add_argument("--github", metavar="TARGET",
                        help="owner/repo#number, or the issue's URL on github.com")
    linker.add_argument("--pr", metavar="PR",
                        help="the pull request that carries the issue: owner/repo#number, "
                             "its URL, or a number in origin's repository. Once it is "
                             "merged, its approving reviews are recorded as the ship "
                             "approval, and once the issue has also landed, land_commit "
                             "moves to its merge commit, unless the record landed with "
                             "the code")
    linker.add_argument("--request", metavar="URL",
                        help="the request this issue answers: an https:// URL, or "
                             "owner/repo#number, which also links the GitHub issue")
    linker.add_argument("--requester", metavar="NAME",
                        help="who asked for it, as free text of at most 100 characters; "
                             "recorded as a claim, not an approval")
    issue_arg(linker)
    linker.set_defaults(func=cmd_issue_link, output_kind="hand-off")
