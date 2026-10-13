# compass_pkg.github_page - the issue page, posted as one comment on the linked GitHub issue
"""Keeps one comment on an issue's linked GitHub issue equal to the issue's README.

A project opts in with the third `github_labels` switch, `page: true`. It is off
by default because it widens who reads the issue's documents: everyone who can
read the GitHub issue.

After a command in `record_triggers.PAGE_TRIGGERS` exits 0, the entry point
calls `after_command` third, after the label sync and the README render. It
reads the README the render has just written from disk; it never renders. It
syncs only the issue the command named. Another issue whose README the render
rewrote waits for its own next sync, and `compass issue lint` reports it as
out of date meanwhile.

One sync, in order:

1. Compose the comment: the marker line `<!-- compass:issue-page -->`, then the
   README with its links rewritten by `github_links` and its size bounded to
   GitHub's limit. Its SHA-256 digest is compared with the one recorded in
   `github-sync.yml`; an unchanged page makes no call.
2. Run the two checks of `publish_check` on the comment and, until it is
   decided once, on the issue body. A hit refuses the whole post.
3. Edit the comment by its recorded id; when that is gone, edit the oldest
   comment whose first line is the marker; otherwise create one.
4. Once only: when the GitHub issue body is empty, whitespace or the ask
   marker alone, write the ask there; otherwise keep the person's body.

Every call is `gh api` with the JSON on standard input. Compass reads back only
comment ids and whether the body is empty, and stores no text from GitHub.
A failure or refusal never changes the exit code of the command that triggered
the sync; `compass issue github sync` exits non-zero on one.
"""
# DEPENDENCY: compass_pkg.github_labels (link, switches, gh runner, label sync),
# compass_pkg.github_sync_record, compass_pkg.record_triggers, compass_pkg.issue_layout,
# compass_pkg.core and compass_pkg.terminal; compass_pkg.publish_check and
# compass_pkg.github_links are imported inside the functions that post or compose.
# It imports nothing from render_after, render_cmd or render_after_entry, and they
# import nothing from it.
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass

from compass_pkg import github_labels, github_sync_record, project_settings, record_triggers
from compass_pkg.core import CompassError, load_manifest, resolve_issue_dir
from compass_pkg.github_labels import NotFound, SyncError, link_of
from compass_pkg.issue_layout import docs_dir_for, is_one_segment
from compass_pkg.terminal import say

MARKER = "<!-- compass:issue-page -->"
ASK_MARKER = "<!-- compass:issue-ask -->"
#: GitHub's limit on a comment, in characters, with the marker line counted.
LIMIT = 65536
PAGE = "page"
TRIGGERS = record_triggers.PAGE_TRIGGERS
VERB = "compass issue github sync"

_BLOCK = r"(<!-- compass:render {kind} -->\n)(.*?)(\n<!-- /compass:render -->)"
_BOLD = re.compile(r"^\*\*(.+)\*\*$")
_ROW_SPLIT = re.compile(r"(?<!\\)\|")


class Refused(SyncError):
    """A post the checks refused, or one too long to post. Nothing was sent."""


@dataclass(frozen=True)
class Composed:
    comment: str
    body_lines: tuple       # the ask, without the closing line that links the comment
    digest: str
    reduced: tuple          # the blocks the size bound left out or reduced

    def body(self, repo, number, comment_id):
        url = f"https://github.com/{repo}/issues/{number}#issuecomment-{comment_id}"
        return "\n".join((ASK_MARKER, *self.body_lines, "",
                          f"The Compass page for this issue is in [this comment]({url})."))


# --- the setting -------------------------------------------------------------

def page_on(project_root):
    """Whether `github_labels.page` is `true`. Any other value, and a file that
    cannot be read, leave it off."""
    try:
        block = project_settings.settings(project_root).get(github_labels.SETTING)
    except CompassError:
        return False
    return isinstance(block, dict) and block.get(PAGE) is True


# --- composing ---------------------------------------------------------------

def _readme_rel(task, task_dir):
    slug = os.path.basename(os.path.normpath(task_dir))
    created = str(task.get("created") or "").strip()
    rel = docs_dir_for(created, slug).replace(os.sep, "/") + "/README.md"
    parts = rel.split("/")
    if not is_one_segment(slug) or len(parts) != 4 or ".." in parts \
            or os.path.normpath(rel).replace(os.sep, "/") != rel:
        raise SyncError(f"the issue page path built from created '{created}' would leave "
                        "docs/compass")
    return rel


def _read_readme(root, rel):
    full = os.path.join(root, *rel.split("/"))
    # A link could point the post at any file on the machine.
    if os.path.islink(full) or os.path.commonpath(
            [os.path.realpath(root), os.path.realpath(full)]) != os.path.realpath(root):
        raise SyncError(f"the issue page {rel} is a symbolic link or leaves the project")
    try:
        with open(full, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        raise SyncError(f"the issue page {rel} does not exist; run `compass issue render`") \
            from None
    except (OSError, UnicodeDecodeError) as exc:
        raise SyncError(f"the issue page {rel} cannot be read: {type(exc).__name__}") from None


def _block(text, kind):
    return re.search(_BLOCK.format(kind=re.escape(kind)), text, re.S)


def _ask_lines(text):
    """The parts of the README's ask block the issue body holds: Problem and Desired
    outcome when the intent gives them, otherwise the issue line."""
    found = _block(text, "ask")
    if not found:
        return ()
    parts, current = {}, None
    for line in found.group(2).split("\n"):
        heading = _BOLD.match(line.strip())
        if heading:
            current = heading.group(1)
            parts[current] = []
        elif current is not None:
            parts[current].append(line)
    chosen = [t for t in ("Problem", "Desired outcome") if t in parts] \
        or [t for t in ("Issue",) if t in parts]
    if not chosen:
        return tuple(found.group(2).split("\n"))
    lines = []
    for title in chosen:
        body = list(parts[title])
        while body and not body[0].strip():
            body.pop(0)
        while body and not body[-1].strip():
            body.pop()
        lines += ["", f"**{title}**", ""] + body
    return tuple(lines[1:])


def _left_out(text, kind, line):
    found = _block(text, kind)
    if not found:
        return text
    return text[:found.start(2)] + line + text[found.end(2):]


def _reduce_artifacts(text, pointer):
    found = _block(text, "artifacts")
    if not found:
        return text
    kept, links, rows = [], [], 0
    for line in found.group(2).split("\n"):
        if line.lstrip().startswith("|"):
            rows += 1
            # The first two table lines are the header and its rule.
            if rows > 2:
                cells = _ROW_SPLIT.split(line)
                if len(cells) > 1:
                    links.append("- " + cells[1].strip())
        else:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    note = ("The artifacts table is reduced to its first column to keep this comment within "
            f"GitHub's size limit. The full table is in the README: {pointer}")
    inner = "\n".join(kept + ([""] if kept else []) + [note, ""] + links)
    return text[:found.start(2)] + inner + text[found.end(2):]


def _bounded(comment, pointer):
    """The comment within `LIMIT`, if leaving out the traceability chart and then
    reducing the artifacts table can bring it there, and the blocks it changed."""
    reduced = []
    if len(comment) > LIMIT:
        comment = _left_out(comment, "traceability",
                            "The traceability chart is left out to keep this comment within "
                            f"GitHub's size limit. It is in the README: {pointer}")
        reduced.append("traceability")
    if len(comment) > LIMIT:
        comment = _reduce_artifacts(comment, pointer)
        reduced.append("artifacts")
    return comment, tuple(reduced)


def compose(task, task_dir):
    """The comment and body to post, from the README on disk. Raises `SyncError`
    when the README cannot be read."""
    from compass_pkg import github_links
    root = github_labels._project_root(task_dir)
    rel = _readme_rel(task, task_dir)
    text = _read_readme(root, rel)
    base = github_links.link_base(root)
    rewritten = github_links.rewrite_links(text, rel, root, base)
    pointer = github_links.link_for(rel, root, base=base)
    comment, reduced = _bounded(MARKER + "\n" + rewritten, pointer)
    digest = "sha256:" + hashlib.sha256(comment.encode("utf-8")).hexdigest()
    return Composed(comment, _ask_lines(rewritten), digest, reduced)


# --- posting -----------------------------------------------------------------

def _id_of(output):
    try:
        value = json.loads(output).get("id")
    except (ValueError, AttributeError):
        value = None
    if not isinstance(value, int) or isinstance(value, bool):
        raise SyncError("gh gave a comment in a form Compass does not read")
    return value


def _find(repo, number):
    """The id of the oldest comment whose first line is the marker, or None."""
    output = github_labels._gh(["api", f"repos/{repo}/issues/{number}/comments",
                                "--paginate", "--slurp"])
    try:
        pages = json.loads(output)
    except ValueError:
        raise SyncError("gh gave comments in a form Compass does not read") from None
    found = []
    for page in pages if isinstance(pages, list) else []:
        for item in page if isinstance(page, list) else []:
            if not isinstance(item, dict):
                continue
            ident, text = item.get("id"), item.get("body")
            if isinstance(ident, int) and isinstance(text, str) \
                    and text.splitlines()[:1] == [MARKER]:
                found.append(ident)
    return min(found) if found else None


def _edit(repo, comment_id, payload):
    github_labels._gh(["api", f"repos/{repo}/issues/comments/{comment_id}",
                       "--method", "PATCH", "--input", "-"], stdin=payload)


def _put_comment(repo, number, comment, held):
    """Edit Compass's comment, or create it. `held["comment_id"]` is updated as soon
    as an id is known, so a later failure still records it. True when created."""
    payload = json.dumps({"body": comment})
    known = held.get("comment_id")
    if isinstance(known, int) and not isinstance(known, bool) and known > 0:
        try:
            _edit(repo, known, payload)
            return False
        except NotFound:
            held["comment_id"] = None
    found = _find(repo, number)
    if found is not None:
        held["comment_id"] = found
        _edit(repo, found, payload)
        return False
    output = github_labels._gh(["api", f"repos/{repo}/issues/{number}/comments",
                                "--method", "POST", "--input", "-"], stdin=payload)
    held["comment_id"] = _id_of(output)
    return True


def _put_body(repo, number, body):
    """Write the ask when the issue body is empty, and say which happened."""
    output = github_labels._gh(["api", f"repos/{repo}/issues/{number}"])
    try:
        current = json.loads(output).get("body")
    except (ValueError, AttributeError):
        raise SyncError("gh gave the issue in a form Compass does not read") from None
    if (current if isinstance(current, str) else "").strip() not in ("", ASK_MARKER):
        return "kept"
    github_labels._gh(["api", f"repos/{repo}/issues/{number}", "--method", "PATCH",
                       "--input", "-"], stdin=json.dumps({"body": body}))
    return "set"


def _fail(task_dir, exc, **fields):
    github_sync_record.update(task_dir, PAGE, error=str(exc), **fields)


def sync_page(task, task_dir):
    """Bring the GitHub issue's Compass comment, and once its body, to the README.
    Returns "unchanged", "edited" or "created". Raises `Refused` or `SyncError`,
    having recorded the problem."""
    from compass_pkg import publish_check
    repo, number = link_of(task)
    recorded = github_sync_record.read(task_dir)[PAGE]
    decided = recorded.get("body") in ("set", "kept")
    try:
        composed = compose(task, task_dir)
    except SyncError as exc:
        _fail(task_dir, exc)
        raise
    if composed.digest == recorded.get("digest") and not recorded.get("error") and decided:
        return "unchanged"
    if len(composed.comment) > LIMIT:
        problem = Refused(f"the comment is {len(composed.comment)} characters with the "
                          f"traceability chart left out and the artifacts table reduced, over "
                          f"GitHub's limit of {LIMIT}")
        _fail(task_dir, problem)
        raise problem
    known = recorded.get("comment_id")
    # The comment id is known only after the post; an id is digits, which no check reads.
    body = None if decided else composed.body(repo, number, known or 0)
    refusal = publish_check.check({"comment": composed.comment, "body": body},
                                  github_labels._project_root(task_dir))
    if refusal is not None:
        _fail(task_dir, refusal.line)
        raise Refused(refusal.line)
    held = {"comment_id": known}
    try:
        created = _put_comment(repo, number, composed.comment, held)
        flag = recorded.get("body") if decided else _put_body(
            repo, number, composed.body(repo, number, held["comment_id"]))
    except SyncError as exc:
        _fail(task_dir, exc, **({"comment_id": held["comment_id"]}
                                if held["comment_id"] != known else {}))
        raise
    github_sync_record.update(task_dir, PAGE, digest=composed.digest,
                              comment_id=held["comment_id"], body=flag, error=None)
    return "created" if created else "edited"


# --- after a command -----------------------------------------------------------

def _fail_line(problem):
    return f"compass: github page not synced - {problem}. Run `{VERB}` to retry."


def _refused_line(problem):
    return (f"compass: github page not posted - {problem}. Change the text, then run "
            f"`{VERB}`.")


def after_command(args, code):
    """Called by the entry point after the render, for every command. Posts the
    named issue's page when the command can have changed its README, and returns
    `code` unchanged: a sync never fails the work."""
    if code != 0:
        return code
    name = getattr(getattr(args, "func", None), "__name__", "")
    if name not in TRIGGERS or (TRIGGERS[name] and not getattr(args, TRIGGERS[name], False)):
        return code
    try:
        task_dir = resolve_issue_dir(getattr(args, "task", None))
        if not page_on(github_labels._project_root(task_dir)):
            return code
        task, _ = load_manifest(task_dir)
        if task.get("github") is None:
            return code
        try:
            sync_page(task, task_dir)
        except Refused as exc:
            sys.stderr.write(_refused_line(exc) + "\n")
        except SyncError as exc:
            sys.stderr.write(_fail_line(exc) + "\n")
    except Exception as exc:  # noqa: BLE001 - nothing here may fail the triggering command
        if not isinstance(exc, CompassError):
            sys.stderr.write(_fail_line(f"unexpected {type(exc).__name__}") + "\n")
    return code


# --- the verb --------------------------------------------------------------------

def cmd_github_sync(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, _ = load_manifest(task_dir)
    slug = task.get("issue")
    try:
        target = link_of(task)
    except SyncError as exc:
        raise CompassError(f"{VERB}: {exc}") from None
    if target is None:
        raise CompassError(
            f"{VERB}: '{slug}' is not linked to a GitHub issue; run "
            "`compass issue link set --github owner/repo#number` first.")
    root = github_labels._project_root(task_dir)
    domain_on, status_on = github_labels.switches(root)
    on = page_on(root)
    if not (domain_on or status_on or on):
        return say(args, f"{VERB}: nothing is switched on, so nothing was sent. Set "
                         "`github_labels` in compass.yml (docs/github-labels.md).", issue=slug)
    problems, detail = [], []
    if domain_on or status_on:
        try:
            add, remove, skipped = github_labels.sync_issue(task, task_dir)
            detail += ([f"labels added: {', '.join(add)}"] if add else []) \
                + ([f"labels removed: {', '.join(remove)}"] if remove else []) \
                + ([] if add or remove else ["labels: already current"])
            if skipped:
                sys.stderr.write(github_labels._skipped_line(skipped) + "\n")
        except SyncError as exc:
            github_labels.record_failure(task_dir, exc)
            problems.append(f"labels: {exc}")
    if on:
        try:
            outcome = sync_page(task, task_dir)
            detail.append(f"page: {outcome}")
        except Refused as exc:
            problems.append(f"page not posted: {exc}")
        except SyncError as exc:
            problems.append(f"page: {exc}")
    where = f"{target[0]}#{target[1]}"
    if problems:
        raise CompassError(f"{VERB}: {slug} -> {where} - " + "; ".join(problems) + ".")
    return say(args, f"{VERB}: {slug} -> {where}.", detail=detail, issue=slug)


# --- issue lint --------------------------------------------------------------------

def lint_notes(task, task_dir):
    """The line `compass issue lint` prints about the page, or none. It reads only
    local files and git: no `gh` call."""
    root = github_labels._project_root(task_dir)
    if not page_on(root):
        return []
    try:
        if link_of(task) is None:
            return []
    except SyncError as exc:
        if any(github_labels.switches(root)):
            return []       # the label notes already name the malformed link
        return [f"github: {exc}; run `compass issue link set` to correct it."]
    recorded = github_sync_record.read(task_dir)[PAGE]
    fix = f" Run `{VERB}`."
    if recorded.get("error"):
        return [f"github: page out of date - the last sync failed: {recorded['error']}.{fix}"]
    if not recorded.get("digest"):
        return [f"github: page out of date - it has not been posted.{fix}"]
    try:
        composed = compose(task, task_dir)
    except SyncError as exc:
        return [f"github: page out of date - {exc}.{fix}"]
    if composed.digest != recorded.get("digest"):
        return [f"github: page out of date - the README changed since it was posted.{fix}"]
    return []


def register(pts, issue_arg):
    """`github sync` under `compass issue`."""
    group = pts.add_parser("github", help="an issue's labels and page on GitHub")
    verbs = group.add_subparsers(dest="github_cmd", required=True)
    syncer = verbs.add_parser("sync", help="write an issue's labels and page to its GitHub "
                                           "issue now")
    issue_arg(syncer)
    syncer.set_defaults(func=cmd_github_sync, output_kind="hand-off")
