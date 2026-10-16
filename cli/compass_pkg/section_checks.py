# compass_pkg.section_checks - the checks that read a section of the spec or the design
"""The two blocking checks that read one named section of an issue document
(ADR-064). Both sit in no gate; `compass check` runs them through
`outside_gate`.

- `nfr-rows-resolved` reads the spec's Non-functional requirements table. Each
  concern row names scenario ids the manifest holds, or a reason the concern
  does not apply. At `thorough` depth each cited scenario states a number in
  its Then.
- `contracts-declared` reads the design's Data and interfaces section when a
  changed file is a trigger path. The trigger patterns are the check's
  `params` in the configuration, never constants here. The section must hold
  a field table or a contract table with a data row, or an `erDiagram` fence.

Both decline, reporting nothing to check, before they read any document, when
the first of these holds (`declines`):

1. the manifest has no `generation` key, so the issue predates the checks;
2. the issue is closed;
3. the document the check reads is not registered with a path;
4. the catalogue of the issue's generation does not list the section at the
   depth the document is registered at. An entry with no `depth` key lists
   nothing.

The order decides which detail an archived issue shows, and the corpus of
each check pins it. Every document is read through `rendered_blocks.masked_text`,
and the text of an HTML comment is never read as part of a section.
"""
# DEPENDENCY: standard library (fnmatch, os, re); compass_pkg.check_results,
# compass_pkg.stable_ids, compass_pkg.status_words, and, inside the functions,
# compass_pkg.effective, artifact_kinds, doc_sections, layers and rendered_blocks.
# It imports no command module, and nothing that imports one, so the check
# registry can import it.
from __future__ import annotations

import fnmatch
import os
import re

from compass_pkg import status_words
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.stable_ids import DEPTH_THOROUGH

NFR_HEADING = "Non-functional requirements"
NFR_KIND = "acceptance-criteria"
CONTRACTS_HEADING = "Data and interfaces"
CONTRACTS_KIND = "technical-design"
CONTRACTS_CHECK = "contracts-declared"

#: The columns a field table's header holds, and those of a contract table, lowercased.
FIELD_COLUMNS = ("name", "type", "required", "meaning", "written by", "read by")
CONTRACT_COLUMNS = ("inputs", "outputs", "exit codes", "errors")

#: The concerns every Non-functional requirements table holds a row for, in order.
CONCERNS = ("performance", "capacity", "compatibility", "security", "privacy",
            "operability", "accessibility")

_FENCE = ("```", "~~~")
_PLACEHOLDER_ONLY = re.compile(r"^(?:\{\{[^{}]*\}\}\s*)+$")
_SEPARATOR = re.compile(r"^:?-+:?$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_DIGIT = re.compile(r"\d")
#: A leading section number, which an issue stored before headings were named still
#: lists (`1. Approach`). The same rule as `template_lists.same_heading`, which this
#: module cannot import: `template_lists` reaches `check_cmd`.
_SECTION_NUMBER = re.compile(r"^\d{1,2}[a-z]?\.?\s+")


def _same_heading(a, b):
    def plain(heading):
        return _SECTION_NUMBER.sub("", str(heading).strip())
    return plain(a) == plain(b)


# --- the declining conditions ----------------------------------------------------------------

def _registered(task, kind):
    """The first registry entry of `kind` that holds a path, or None."""
    for entry in task.get("artifacts") or []:
        if isinstance(entry, dict) and entry.get("kind") == kind and entry.get("path"):
            return entry
    return None


def _generation(task):
    """The manifest's `generation` value, or None when it has no such key. Only
    `effective` reads the generation store; the key alone decides condition 1."""
    return task.get("generation") if isinstance(task, dict) else None


def _listed(task_dir, kind, depth, heading):
    """Whether the catalogue of the issue's configuration lists `heading` for
    `kind` at `depth`. No depth lists nothing."""
    from compass_pkg import artifact_kinds, effective

    if not depth:
        return False
    entry = artifact_kinds.entry(effective.view_or_legacy(task_dir), kind) or {}
    sections = entry.get("sections")
    listed = sections.get(depth) if isinstance(sections, dict) else None
    return any(isinstance(one, str) and _same_heading(one, heading) for one in listed or ())


def declines(task, task_dir, kind, heading):
    """The detail of the first declining condition that holds, or None when
    the check must judge the issue."""
    number = _generation(task)
    if number is None:
        # `compass check` names no stored configuration on such an issue, so the
        # detail does not either.
        return "the issue predates the section checks: its manifest names no stored configuration"
    if status_words.is_closed(task):
        return "the issue is closed"
    entry = _registered(task, kind)
    if entry is None:
        return "no %s is registered with a path" % kind
    depth = entry.get("depth")
    if not _listed(task_dir, kind, depth, heading):
        return ('the catalogue of generation %s does not list "%s" for %s at %s'
                % (number, heading, kind, "depth %s" % depth if depth else "no depth"))
    return None


# --- reading a section -----------------------------------------------------------------------

def _read(task_dir, entry):
    """`(text, None)` of the registered document, or `(None, detail)`."""
    from compass_pkg import layers

    path = str(entry.get("path"))
    full = os.path.join(layers.find_project_root(task_dir), *path.split("/"))
    try:
        with open(full, encoding="utf-8") as handle:
            return handle.read(), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, "%s cannot be read: %s" % (path, exc.__class__.__name__)


def section_lines(text, heading):
    """The visible lines of the first `## <heading>` section of `text`, or None
    when it has none. A section runs to the next `# ` or `## ` heading; a deeper
    heading is part of it. Rendered block text and the text of HTML comments
    are left out, and a heading inside a code fence is not a heading."""
    from compass_pkg import doc_sections, rendered_blocks

    shown = doc_sections.visible(rendered_blocks.masked_text(text).split("\n"))
    body, inside, fenced = [], False, False
    for line in shown:
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
        elif not fenced and line.startswith(("# ", "## ")):
            if inside:
                return body
            inside = _same_heading(line.lstrip("#").strip(), heading)
            continue
        if inside:
            body.append(line)
    return body if inside else None


def _cells(line):
    text = line.strip()
    if not text.startswith("|"):
        return None
    text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.strip() for cell in _CELL_SPLIT.split(text)]


def tables(lines):
    """`[(header cells, [row cells])]` of each Markdown table in `lines` outside a
    code fence, in order. A table is a header row, a separator row and its data
    rows."""
    found, fenced, index = [], False, 0
    while index < len(lines):
        line = lines[index]
        if line.lstrip().startswith(_FENCE):
            fenced = not fenced
            index += 1
            continue
        header = None if fenced else _cells(line)
        rule = _cells(lines[index + 1]) if header and index + 1 < len(lines) else None
        if header and rule and all(_SEPARATOR.match(cell) for cell in rule):
            rows, index = [], index + 2
            while index < len(lines) and _cells(lines[index]) is not None:
                rows.append(_cells(lines[index]))
                index += 1
            found.append((header, rows))
            continue
        index += 1
    return found


def _value(cell):
    """A cell's text, empty when it holds only `{{...}}` placeholders."""
    text = (cell or "").strip()
    return "" if _PLACEHOLDER_ONLY.match(text) else text


#: The two readers `design_size` uses too, under names that are part of this
#: module's interface: a registered document's text, and a table cell's value.
read_registered = _read
cell_value = _value


def _column(header, test):
    for index, name in enumerate(header):
        if test(name.strip().strip("*").strip().lower()):
            return index
    return None


# --- nfr-rows-resolved -----------------------------------------------------------------------

def numbered_then(text, scenario_id):
    """Whether the scenario `scenario_id` states a number in its Then: in the
    first fence after its `traceability id:` line, the Then line or a Then, And
    or But line after it holds a digit. None when the text has no such line.
    The id must end where the match ends, so `DSS-1` never matches `DSS-10`."""
    from compass_pkg import rendered_blocks

    lines = rendered_blocks.masked_text(text).split("\n")
    marker = re.compile(r"traceability id:\s*" + re.escape(scenario_id) + r"(?![0-9A-Za-z-])")
    for at, line in enumerate(lines):
        if not marker.search(line):
            continue
        opens = next((n for n in range(at + 1, len(lines))
                      if lines[n].lstrip().startswith(_FENCE)), None)
        if opens is None:
            return False
        seen_then = False
        for body in lines[opens + 1:]:
            if body.lstrip().startswith(_FENCE):
                break
            word = (body.split() or [""])[0]
            if word == "Then":
                seen_then = True
            if seen_then and word in ("Then", "And", "But") and _DIGIT.search(body):
                return True
        return False
    return None


def _concern(cell):
    return cell.replace("*", "").replace("`", "").strip().lower()


def _check_nfr_rows_resolved(task, task_dir):
    """`(passed, detail)`: every concern row of the spec's Non-functional
    requirements table is resolved by scenario ids the manifest holds or by a
    reason; at `thorough` depth each cited scenario states a number in its Then."""
    held = declines(task, task_dir, NFR_KIND, NFR_HEADING)
    if held:
        return NOTHING_TO_CHECK, held
    entry = _registered(task, NFR_KIND)
    path = str(entry.get("path"))
    text, unreadable = _read(task_dir, entry)
    if text is None:
        return False, unreadable
    lines = section_lines(text, NFR_HEADING)
    if lines is None:
        return False, '%s has no "%s" section' % (path, NFR_HEADING)
    table = next(((h, rows) for h, rows in tables(lines)
                  if _column(h, lambda name: name == "concern") is not None), None)
    if table is None:
        return False, '%s: the "%s" section holds no table with a Concern column' % (
            path, NFR_HEADING)
    header, rows = table
    at_concern = _column(header, lambda name: name == "concern")
    at_scenario = _column(header, lambda name: name.startswith("scenario"))
    at_reason = _column(header, lambda name: name.startswith("reason"))
    known = {str(s.get("id")) for s in task.get("scenarios") or [] if isinstance(s, dict)}
    thorough = entry.get("depth") == DEPTH_THOROUGH

    def cell(row, index):
        return _value(row[index]) if index is not None and index < len(row) else ""

    problems, seen = [], []
    for row in rows:
        name = _concern(row[at_concern] if at_concern < len(row) else "")
        if not name:
            continue
        seen.append(name)
        cited = [token.strip().strip("`").strip()
                 for token in cell(row, at_scenario).split(",")]
        cited = [token for token in cited if token]
        unknown = [token for token in cited if token not in known]
        for token in unknown:
            problems.append('"%s" cites %s, which the manifest does not hold' % (name, token))
        if not cited and not cell(row, at_reason):
            problems.append('"%s" has neither a scenario nor a reason' % name)
        if thorough:
            for token in cited:
                if token in unknown:
                    continue
                found = numbered_then(text, token)
                if found is None:
                    problems.append('"%s" cites %s, which has no traceability id line in %s'
                                    % (name, token, path))
                elif not found:
                    problems.append('"%s" cites %s, whose Then states no number'
                                    % (name, token))
    for name in CONCERNS:
        if name not in seen:
            problems.append('"%s" is missing' % name)
    if problems:
        return False, "%s: %s" % (path, "; ".join(problems))
    return True, "%d of %d concerns resolved" % (len(seen), len(seen))


# --- contracts-declared ----------------------------------------------------------------------

def _trigger_patterns(task_dir):
    """`(trigger_paths, trigger_contents)` the issue's configuration declares for
    `contracts-declared`: the check of that id, else the first check whose
    implementation it is. The patterns are data (ADR-033): none is held here."""
    from compass_pkg import effective

    view = effective.view_or_legacy(task_dir)
    checks = (view.config.get("checks") if view is not None else None) or {}
    entry = checks.get(CONTRACTS_CHECK)
    if not isinstance(entry, dict):
        entry = next((one for one in checks.values()
                      if isinstance(one, dict) and one.get("impl") == CONTRACTS_CHECK), {})
    params = entry.get("params") or {}

    def listed(name):
        value = params.get(name) if isinstance(params, dict) else None
        return value if isinstance(value, list) else []

    paths = [p for p in listed("trigger_paths") if isinstance(p, str) and p]
    contents = [one for one in listed("trigger_contents")
                if isinstance(one, dict) and one.get("path") and one.get("contains")]
    return paths, contents


def _changed_paths(task):
    out = []
    for one in task.get("changed_files") or []:
        path = one.get("path") if isinstance(one, dict) else one
        if isinstance(path, str) and path.strip():
            out.append(path.strip().replace("\\", "/"))
    return out


def _inside(root, rel):
    """The file `rel` names under the project root, or None for a path that leaves it,
    which is never opened."""
    real_root = os.path.realpath(root)
    full = os.path.realpath(os.path.join(real_root, *rel.split("/")))
    return full if full.startswith(real_root + os.sep) else None


def _holds(root, rel, text):
    full = _inside(root, rel)
    if full is None or not os.path.isfile(full):
        return False
    try:
        with open(full, encoding="utf-8", errors="replace") as handle:
            return text in handle.read()
    except OSError:
        return False


def triggers(task, task_dir):
    """The changed paths that make `contracts-declared` judge the design, in order:
    each matches a path pattern, or a contents pattern's path and its text. Patterns
    are `fnmatch` globs on the project-relative path, where `*` also matches `/`."""
    from compass_pkg import layers

    root = layers.find_project_root(task_dir)
    paths, contents = _trigger_patterns(task_dir)
    found = []
    for rel in _changed_paths(task):
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in paths) or any(
                fnmatch.fnmatchcase(rel, str(one["path"]))
                and _holds(root, rel, str(one["contains"])) for one in contents):
            if rel not in found:
                found.append(rel)
    return found


def _holds_columns(header, wanted):
    names = {name.strip().strip("*").strip().lower() for name in header}
    return all(column in names for column in wanted)


def declarations(lines):
    """The number of declarations in a section's visible lines: field tables and
    contract tables with a data row, and `erDiagram` fences. A table or fence that
    holds a `{{...}}` placeholder does not count."""
    count = 0
    for header, rows in tables(lines):
        if not (_holds_columns(header, FIELD_COLUMNS) or _holds_columns(header,
                                                                       CONTRACT_COLUMNS)):
            continue
        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if rows and "{{" not in " ".join(header + [c for row in rows for c in row]):
            count += 1
    fence = None
    for line in lines:
        if line.lstrip().startswith(_FENCE):
            if fence is None:
                fence = []
                continue
            body = [one for one in fence if one.strip()]
            if body and body[0].strip() == "erDiagram" and "{{" not in "\n".join(body):
                count += 1
            fence = None
        elif fence is not None:
            fence.append(line)
    return count


def _check_contracts_declared(task, task_dir):
    """`(passed, detail)`: when a changed file is a trigger path, the technical
    design's Data and interfaces section declares at least one contract."""
    held = declines(task, task_dir, CONTRACTS_KIND, CONTRACTS_HEADING)
    if held:
        return NOTHING_TO_CHECK, held
    found = triggers(task, task_dir)
    if not found:
        return NOTHING_TO_CHECK, "no changed file matches a trigger pattern of %s" % (
            CONTRACTS_CHECK)
    entry = _registered(task, CONTRACTS_KIND)
    path = str(entry.get("path"))
    changed = ", ".join(found)
    text, unreadable = _read(task_dir, entry)
    if text is None:
        return False, unreadable
    lines = section_lines(text, CONTRACTS_HEADING)
    if lines is None:
        return False, '%s has no "%s" section, and these trigger paths changed: %s' % (
            path, CONTRACTS_HEADING, changed)
    count = declarations(lines)
    if not count:
        return False, ('%s: the "%s" section declares no contract (a field table or a '
                       'contract table with a data row, or an erDiagram), and these trigger '
                       'paths changed: %s' % (path, CONTRACTS_HEADING, changed))
    return True, '%s declares %d contract(s) under "%s" for %d trigger path(s): %s' % (
        path, count, CONTRACTS_HEADING, len(found), changed)
