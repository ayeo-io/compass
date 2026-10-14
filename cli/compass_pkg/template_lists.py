# compass_pkg.template_lists - `compass issue template show`
"""Print a document template for an issue.

A template of a catalogue kind prints as a skeleton: a title, a header built
from the kind's catalogue entry (the reader, the stage, the owner, the home and
the traditional name), then the kind's headings at one depth, each with the
template's prose for it. The catalogue says who reads the document and which
headings it has; the template holds only prose. A template that is not a
catalogue kind (`devlog`, `incident`, `pull-request-body`) prints as the file.

The requirements review holds the Definition of Ready and the verification
report holds the Definition of Done as rendered blocks (`dor` and `dod`,
ADR-051). `compass issue render` writes them from the issue's configured plan
entry list and `verify` exit list, so the template carries no checklist to
follow the lists: `render` returns the text of the template as it is. A list on
another stage has no block kind yet; its checks are judged from the manifest's
records by the stage lists and are not written into the documents.
"""
# DEPENDENCY: standard library; compass_pkg.stage_lists (for the document kinds),
# compass_pkg.artifact_kinds, effective, terminal and core inside the verb.
from __future__ import annotations

import re

from compass_pkg.stable_ids import DEPTH_THOROUGH
from compass_pkg.stage_lists import CHECKLIST_DOCUMENTS

_SIDE_OF = {kind: side for side, kind in CHECKLIST_DOCUMENTS.items()}

#: The line under a heading that marks a section the author may leave out.
OPTIONAL_MARKER = "<!-- compass:optional -->"
OPTIONAL_LABEL = " (optional)"

_PLACEHOLDER = re.compile(r"\{\{.*?\}\}|<[^<>]*>")
#: A leading section number such as `1. `, `5a. ` or `4b `. At most two digits, so a heading
#: that starts with a year is not changed.
_SECTION_NUMBER = re.compile(r"^\d{1,2}[a-z]?\.?\s+")


def kinds():
    """The document kinds whose lists are rendered blocks."""
    return tuple(sorted(_SIDE_OF))


def render(text, view, kind):
    """`text`, the template of `kind`, unchanged: a list is a rendered block."""
    return text


def same_heading(a, b):
    """Whether two headings are one: a `{{...}}` token of a template and a
    `<...>` token of the catalogue each stand for one placeholder, and a leading
    section number is not part of the words. An issue stored before the headings lost
    their numbers lists `1. Approach`; the template holds `Approach`."""
    def plain(heading):
        return _SECTION_NUMBER.sub("", _PLACEHOLDER.sub("<>", heading).strip())
    return plain(a) == plain(b)


class Template:
    """A template read as: the lines before its title, the title, the lines
    between the title and the first `## ` heading, and its sections. A `## `
    line inside a code fence or an HTML comment is not a heading."""

    def __init__(self, text):
        lines = text.split("\n")
        self.head, self.title, self.preamble, self.sections = [], None, [], []
        fenced = commented = False
        current = None
        for n, line in enumerate(lines):
            plain = not fenced and not commented
            if plain and line.startswith("# ") and self.title is None:
                self.title = line[2:].strip()
                current = self.preamble
                continue
            if plain and line.startswith("## ") and self.title is not None:
                optional = n + 1 < len(lines) and lines[n + 1].strip() == OPTIONAL_MARKER
                current = []
                self.sections.append({"heading": line[3:].strip(), "optional": optional,
                                      "body": current})
                continue
            if self.title is None:
                self.head.append(line)
            else:
                current.append(line)
            if line.startswith("```"):
                fenced = not fenced
            elif not fenced:
                if "<!--" in line and "-->" not in line.split("<!--", 1)[1]:
                    commented = True
                elif commented and "-->" in line:
                    commented = False
        for section in self.sections:
            body = section["body"]
            if section["optional"] and body and body[0].strip() == OPTIONAL_MARKER:
                del body[0]


def _lines(heading, body):
    return ["## " + heading] + list(body)


def skeleton(kind, entry, template_text, depth, issue=None):
    """What `template show` prints for a catalogue kind at one depth.

    `entry` is the kind's catalogue entry and `template_text` its template, or
    None when the kind has no template (its headings print with no prose).
    `issue` is `(slug, documents folder)` for an issue, or None for the
    placeholders `<created>-<issue-slug>`."""
    slug, folder = issue if issue else ("<issue-slug>", "docs/compass/<created>-<issue-slug>")
    template = Template(template_text) if template_text is not None else None
    title = (template.title if template and template.title
             else kind[:1].upper() + kind[1:].replace("-", " ") + " - {{ISSUE_SLUG}}")
    if issue:
        title = title.replace("{{ISSUE_SLUG}}", slug)
    out = list(template.head) if template else []
    out += ["# " + title, "",
            "> **Audience:** " + " ".join(str(entry.get("audience", "")).split()),
            "> **Stage:** %s · **Owner:** %s · **Home:** %s/%s" % (
                entry.get("stage"), entry.get("owner"), folder, entry.get("file")),
            "> **Traditional name:** %s · **Depth:** %s" % (entry.get("stands_for"), depth)]
    preamble = list(template.preamble) if template else [""]
    if preamble and preamble[0].strip():
        out.append("")
    out += preamble
    wanted = list((entry.get("sections") or {}).get(depth) or [])
    found = template.sections if template else []
    labelled = depth == DEPTH_THOROUGH
    pointer = 0
    for heading in wanted:
        index = next((i for i in range(pointer, len(found))
                      if not found[i]["optional"] and same_heading(found[i]["heading"], heading)),
                     None)
        if index is None:
            out += ["## " + heading, ""]
            continue
        for between in found[pointer:index]:
            if labelled and between["optional"]:
                out += _lines(between["heading"] + OPTIONAL_LABEL, between["body"])
        out += _lines(heading, found[index]["body"])
        pointer = index + 1
    for rest in found[pointer:]:
        if labelled and rest["optional"]:
            out += _lines(rest["heading"] + OPTIONAL_LABEL, rest["body"])
    return "\n".join(out).rstrip("\n") + "\n"


def _depth_for(entry, asked, registered):
    """The depth to print: the one asked for, else the one the issue registers
    the kind at, else thorough, else the kind's only depth."""
    from compass_pkg.core import CompassError

    sections = entry.get("sections") or {}
    if asked:
        if asked not in sections:
            raise CompassError(
                "compass issue template show: no depth '%s' for this kind. Its sections hold: %s."
                % (asked, ", ".join(sorted(sections)) or "none"))
        return asked
    if registered in sections:
        return registered
    if DEPTH_THOROUGH in sections:
        return DEPTH_THOROUGH
    return sorted(sections)[0]


def cmd_issue_template(args):
    """`compass issue template show <kind> [--depth D] [--issue SLUG] [--json]`.
    Prints the skeleton of a catalogue kind, or the file of a template that is
    not a kind. The text is the whole output, so a caller can write it to the
    document. With `--json` the output is one object:

        {"kind": "<kind>", "issue": "<slug>" or null, "depth": "<depth>" or null,
         "source": "generation" | "live" | "none", "text": "<the document>"}

    `source` says where the catalogue came from: the issue's stored generation,
    the live project configuration, or "none" when no configuration is read and
    the shipped default's catalogue is used. `depth` is null for a template that
    is not a catalogue kind."""
    import json
    import os
    import sys

    from compass_pkg import artifact_kinds, effective, terminal
    from compass_pkg.core import (FRAMEWORK_ROOT, CompassError, docs_dir, load_yaml,
                                  manifest_path, resolve_issue_dir)

    directory = os.path.join(FRAMEWORK_ROOT, "templates")
    available = sorted(name[:-3] for name in os.listdir(directory) if name.endswith(".md"))
    kind = args.kind
    slug = getattr(args, "task", None)
    try:
        task_dir = resolve_issue_dir(slug)
    except CompassError:
        if slug:
            raise
        task_dir = None
    view = effective.view_or_legacy(task_dir)
    catalogue = artifact_kinds.catalogue(view)
    asked = getattr(args, "depth", None)
    if kind not in catalogue and kind not in available:
        raise CompassError(
            f"compass issue template show: no template or kind '{kind}'. The kinds are: "
            f"{', '.join(sorted(catalogue))}. The other templates are: "
            f"{', '.join(n for n in available if n not in catalogue)}.")
    template_text = None
    if kind in available:
        with open(os.path.join(directory, kind + ".md"), encoding="utf-8") as fh:
            template_text = fh.read()
    depth = None
    if kind in catalogue:
        entry = catalogue[kind]
        registered, issue = None, None
        if task_dir:
            held = load_yaml(manifest_path(task_dir)) or {}
            registered = next((a.get("depth") for a in (held.get("artifacts") or [])
                               if isinstance(a, dict) and a.get("kind") == kind
                               and a.get("depth")), None)
            issue = (os.path.basename(os.path.normpath(task_dir)), docs_dir(task_dir))
        depth = _depth_for(entry, asked, registered)
        rendered = skeleton(kind, entry, template_text, depth, issue)
    else:
        if asked:
            raise CompassError(
                f"compass issue template show: '{kind}' is not a catalogue kind and has no "
                f"sections, so --depth does not apply. Print it without --depth.")
        rendered = render(template_text, view, kind)
    if terminal.resolve_mode(args) == "json":
        print(json.dumps({"kind": kind,
                          "issue": os.path.basename(os.path.normpath(task_dir)) if task_dir else None,
                          "depth": depth,
                          "source": view.source if view is not None else "none",
                          "text": rendered}, indent=2))
        terminal.mark_handled()
        return 0
    sys.stdout.write(rendered)
    return 0
