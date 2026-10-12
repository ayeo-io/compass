# compass_pkg.template_lists - `compass issue template show`
"""Print a document template for an issue.

The requirements review holds the Definition of Ready and the verification
report holds the Definition of Done as rendered blocks (`dor` and `dod`,
ADR-051). `compass issue render` writes them from the issue's configured plan
entry list and `verify` exit list, so the template carries no checklist to
follow the lists: `render` returns the text of the template as it is. A list on
another stage has no block kind yet; its checks are judged from the manifest's
records by the stage lists and are not written into the documents.
"""
# DEPENDENCY: standard library; compass_pkg.stage_lists (for the document kinds),
# compass_pkg.effective, terminal and core inside the verb.
from __future__ import annotations

from compass_pkg.stage_lists import CHECKLIST_DOCUMENTS

_SIDE_OF = {kind: side for side, kind in CHECKLIST_DOCUMENTS.items()}


def kinds():
    """The document kinds whose lists are rendered blocks."""
    return tuple(sorted(_SIDE_OF))


def render(text, view, kind):
    """`text`, the template of `kind`, unchanged: a list is a rendered block."""
    return text


def cmd_issue_template(args):
    """`compass issue template show <kind> [--issue SLUG] [--json]`. Prints the
    template of `kind`. The text is the whole output, so a caller can write it to
    the document. With `--json` the output is one object:

        {"kind": "<kind>", "issue": "<slug>" or null,
         "source": "generation" | "live" | "none", "text": "<the document>"}

    `source` says where the lists came from: the issue's stored generation, the
    live project configuration, or "none" when no configuration is read and the
    template is the file as it is."""
    import json
    import os
    import sys

    from compass_pkg import effective, terminal
    from compass_pkg.core import FRAMEWORK_ROOT, CompassError, resolve_issue_dir

    directory = os.path.join(FRAMEWORK_ROOT, "templates")
    available = sorted(name[:-3] for name in os.listdir(directory) if name.endswith(".md"))
    kind = args.kind
    if kind not in available:
        raise CompassError(
            f"compass issue template show: no template '{kind}'. The templates are: "
            f"{', '.join(available)}.")
    slug = getattr(args, "task", None)
    try:
        task_dir = resolve_issue_dir(slug)
    except CompassError:
        if slug:
            raise
        task_dir = None
    with open(os.path.join(directory, kind + ".md"), encoding="utf-8") as fh:
        text = fh.read()
    view = effective.view_or_legacy(task_dir)
    rendered = render(text, view, kind)
    if terminal.resolve_mode(args) == "json":
        print(json.dumps({"kind": kind,
                          "issue": os.path.basename(os.path.normpath(task_dir)) if task_dir else None,
                          "source": view.source if view is not None else "none",
                          "text": rendered}, indent=2))
        terminal.mark_handled()
        return 0
    sys.stdout.write(rendered)
    return 0
