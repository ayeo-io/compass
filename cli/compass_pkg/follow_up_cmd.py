# compass_pkg.follow_up_cmd - `compass follow-up add`
"""Record a follow-up in an issue's manifest, and optionally the Definition of
Done or Ready item it carries.

```
compass follow-up add FU-ID [--defers CHECK] --summary TEXT [--target SLUG] [--issue SLUG]
```

- `--defers CHECK` carries an item of the issue's Definition of Done or Ready to
  ship. The item reads "carried to ship" while the follow-up is outstanding and
  "met" once `compass follow-up resolve` resolves it (`item_records`).
- `--target SLUG` names another issue. While the follow-up is outstanding it
  blocks that issue's `dod-evidence-typed` (the cross-issue half of the check).

The command refuses, and writes nothing, for a duplicate id, an empty summary, a
check the issue does not list, and a target that is not a slug.
"""
# DEPENDENCY: standard library (re); compass_pkg.core, effective, item_records,
# terminal. It imports no renderer: the entry point's after-command step renders.
from __future__ import annotations

import re

from compass_pkg import effective, item_records
from compass_pkg.core import CompassError, issue_arg, load_manifest, resolve_issue_dir, save_manifest
from compass_pkg.terminal import say

_SLUG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
VERB = "compass follow-up add"


def cmd_follow_up_add(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
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
    entry = {"id": follow_up_id, "status": "outstanding", "summary": summary}
    if args.defers:
        problem = item_records.unlisted_problem(effective.view_or_legacy(task_dir),
                                                args.defers, VERB)
        if problem:
            raise CompassError(problem)
        entry["defers"] = args.defers
    if args.target:
        if not _SLUG.fullmatch(args.target):
            raise CompassError(f"{VERB}: --target '{args.target}' is not an issue slug.")
        entry["target_task"] = args.target
    task.setdefault("follow_ups", []).append(entry)
    save_manifest(task, path)
    detail = [f"summary : {summary}"]
    if args.defers:
        detail.append(f"carries : {args.defers}")
    if args.target:
        detail.append(f"blocks  : {args.target} until it is resolved")
    return say(args, f"{VERB}: {follow_up_id} recorded as outstanding.", detail=detail,
               follow_up=follow_up_id, defers=args.defers, target=args.target)


def register(follow_up_subs):
    """`add` under `compass follow-up`."""
    p = follow_up_subs.add_parser("add", help="record a follow-up, and the item it carries")
    p.add_argument("follow_up_id", metavar="follow-up-id", help="a fresh id, for example FU-1")
    p.add_argument("--summary", required=True, help="what is owed")
    p.add_argument("--defers", metavar="CHECK",
                   help="a Definition of Done or Ready item this follow-up carries to ship")
    p.add_argument("--target", metavar="SLUG",
                   help="another issue whose shipping this follow-up blocks")
    issue_arg(p)
    p.set_defaults(func=cmd_follow_up_add, output_kind="hand-off")
