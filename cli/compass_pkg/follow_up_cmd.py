# compass_pkg.follow_up_cmd - `compass follow-up add` and `compass follow-up resolve`
"""Record a follow-up in an issue's manifest, and optionally the Definition of
Done or Ready item it carries, and mark one resolved.

```
compass follow-up add FU-ID [--defers CHECK] [--github owner/repo#N] --summary TEXT [--issue SLUG]
compass follow-up resolve --issue SLUG FU-ID
```

- `--github owner/repo#N` (or the issue's URL) links the follow-up to the
  GitHub issue that tracks the work. It is parsed as `compass issue link set`
  parses a target (`issue_link.parse_target`) and written as
  `github: {repo, number}`. Nothing is written to GitHub.
- `--defers CHECK` carries an item of the issue's Definition of Done or Ready.

On a path issue (ADR-092) there is one rule (ADR-093): an open Definition of
Done item is met only by a follow-up that links to a GitHub issue. So
`--github` is required there, and `--defers` must name an item of the build exit
list. The item reads met while the follow-up is outstanding, and nothing waits
for `compass follow-up resolve`.

On an issue assessed before 9.0.0 every older rule holds: the item reads
"carried to ship" while the follow-up is outstanding and "met" once `compass
follow-up resolve` resolves it (`item_records`), and an outstanding follow-up
fails `compass check` until then. `--target`, which made a follow-up block another issue,
was removed in 9.0.0 (`removed_parts`); the `target_task` entries it wrote are
still read.

The command refuses, and writes nothing, for a duplicate id, an empty summary, a
check the issue does not list, a target that is not a GitHub issue, and a path
issue's follow-up with no `--github`.

`compass follow-up resolve` sets one follow-up's status to `resolved`. An issue
assessed before 9.0.0 with an outstanding follow-up cannot close until then.
"""
# DEPENDENCY: compass_pkg.core, effective, issue_link, item_records,
# path_stages, terminal. It imports no renderer: the entry point's
# after-command step renders.
from __future__ import annotations

from compass_pkg import effective, item_records
from compass_pkg.core import CompassError, issue_arg, load_manifest, resolve_issue_dir, save_manifest
from compass_pkg.issue_link import parse_target
from compass_pkg.path_stages import is_path_issue
from compass_pkg.terminal import say

VERB = "compass follow-up add"


def cmd_follow_up_add(args):
    target = None
    if args.github is not None:
        target = parse_target(args.github)
        if target is None:
            raise CompassError(
                f"{VERB}: --github '{args.github}' is not a GitHub issue; use owner/repo#number "
                "or https://github.com/owner/repo/issues/number. Nothing was written.")
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    path_issue = is_path_issue(task)
    follow_up_id = " ".join(str(args.follow_up_id or "").split())
    summary = " ".join(str(args.summary or "").split())
    if not follow_up_id:
        raise CompassError(f"{VERB}: the follow-up id must not be empty (for example FU-1).")
    if not summary:
        raise CompassError(f"{VERB}: --summary must say what is owed; an empty summary "
                           f"records nothing a reader can act on.")
    listed = [f for f in task.get("follow_ups") or [] if isinstance(f, dict)]
    if any(f.get("id") == follow_up_id for f in listed):
        raise CompassError(f"{VERB}: '{follow_up_id}' is already a follow-up of this issue. "
                           f"Use a fresh id.")
    if args.defers:
        problem = _defers_problem(task_dir, task, args.defers, path_issue)
        if problem:
            raise CompassError(problem)
    if path_issue and target is None:
        raise CompassError(
            f"{VERB}: on a path issue a follow-up must link to the GitHub issue that tracks "
            f"the work: add --github owner/repo#number. A follow-up with no link meets no "
            f"Definition of Done item. Nothing was written.")
    entry = {"id": follow_up_id, "status": "outstanding", "summary": summary}
    if args.defers:
        entry["defers"] = args.defers
    if target is not None:
        entry["github"] = {"repo": target[0], "number": target[1]}
    task.setdefault("follow_ups", []).append(entry)
    save_manifest(task, path)
    detail = [f"summary : {summary}"]
    if args.defers:
        detail.append(f"carries : {args.defers}")
    if target is not None:
        detail.append(f"tracked : {target[0]}#{target[1]}")
    linked = f"{target[0]}#{target[1]}" if target is not None else None
    return say(args, f"{VERB}: {follow_up_id} recorded as outstanding.", detail=detail,
               follow_up=follow_up_id, defers=args.defers, github=linked)


def _defers_problem(task_dir, task, check_id, path_issue):
    """Why `--defers` cannot name `check_id`, or None. A path issue has only the
    Definition of Done, its build exit list, so the message names that list."""
    view = effective.view_or_legacy(task_dir)
    if not path_issue:
        return item_records.unlisted_problem(view, check_id, VERB, task=task)
    listed = [c for c, _ in item_records.listed_checks(view, "dod")]
    if check_id in listed:
        return None
    return (f"{VERB}: --defers '{check_id}' is not an item of this path issue's Definition "
            f"of Done (the build exit list). The list holds - {', '.join(listed) or 'no item'}.")


def cmd_backfill_pay(args):
    """`compass follow-up resolve`: set the named follow-up's status to
    `resolved` in the issue's manifest.yml. The function keeps its old name
    because `record_triggers.RECORD_TRIGGERS` names it. On a path issue nothing
    waits for it: the linked GitHub issue tracks the work."""
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    bf_id = args.backfill_id
    follow_ups = task.get("follow_ups") or []
    found = None
    for bf in follow_ups:
        if isinstance(bf, dict) and bf.get("id") == bf_id:
            found = bf
            break
    if not found:
        raise CompassError(
            f"follow-up '{bf_id}' not found in issue '{args.task}'. "
            f"Available follow-ups: "
            f"{[b.get('id') for b in follow_ups if isinstance(b, dict)]}"
        )
    if found.get("status") == "resolved":
        print(f"compass follow-up resolve: '{bf_id}' is already resolved.")
        return 0
    found["status"] = "resolved"
    task["follow_ups"] = follow_ups
    save_manifest(task, task_path)
    target = found.get("target_task")
    target_note = (f" (cross-issue debt on '{target}' is now cleared)"
                   if target else "")
    print(f"compass follow-up resolve: '{bf_id}' in issue '{args.task}' "
          f"marked resolved{target_note}.")
    return 0


def register(follow_up_subs):
    """`add` under `compass follow-up`."""
    p = follow_up_subs.add_parser("add", help="record a follow-up, and the item it carries")
    p.add_argument("follow_up_id", metavar="follow-up-id", help="a fresh id, for example FU-1")
    p.add_argument("--summary", required=True, help="what is owed")
    p.add_argument("--defers", metavar="CHECK",
                   help="a Definition of Done or Ready item this follow-up carries")
    p.add_argument("--github", metavar="OWNER/REPO#N",
                   help="the GitHub issue that tracks the work (owner/repo#N or its URL); "
                        "required on a path issue")
    issue_arg(p)
    p.set_defaults(func=cmd_follow_up_add, output_kind="hand-off")
