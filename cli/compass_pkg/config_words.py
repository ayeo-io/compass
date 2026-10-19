# compass_pkg.config_words - `compass policy migrate --words`
"""Rewrite a project's own configuration files in the 6.0.0 words.

6.0.0 reads an old word in a project's `compass.yml`, a team preset's
`compass.yml` or a policy-test fixture through `word_map`, with a lint
advisory, and 8.0.0 refuses it. This module rewrites those files so an
upgrading project is not refused. `docs/policy-migrate.md` owns the contract.

It names no word itself. Each file goes through the reader that reads it
(`word_map.map_layer` for `compass.yml`, `word_map.map_fixture` for a
fixture), and only the scalars that mapping changed are replaced in the
file's text, at the positions the YAML parser reports. Comments, order,
quoting and layout therefore stay, and a word the mapping leaves alone, such
as `full` naming an approach, stays too. The new text is parsed again and
must read as the mapping read the old one; a file that does not is refused.

A condition that reads the retired `role` dimension has no mechanical
rewrite (ADR-070). It is reported as a hand edit, in the words `compass
policy lint` and the merge use, and left as it is.

A write must be undoable: `--apply` refuses the whole run when git cannot
restore a file it would write (`migrate_copy_check`), or when the project is
in no repository, unless the person says they have a copy.
"""
# DEPENDENCY: standard library (contextlib, dataclasses, difflib, os, stat,
# tempfile); yaml;
# compass_pkg.atomic_io,
# core (CompassError), migrate_copy_check, preset_test (the fixture walk),
# retired, word_map.
from __future__ import annotations

import contextlib
import difflib
import os
import stat
import tempfile
from dataclasses import dataclass, field

import yaml

from compass_pkg import migrate_copy_check, retired, word_map
from compass_pkg.atomic_io import StrictYamlError, load_yaml_strict_text
from compass_pkg.core import CompassError
from compass_pkg.preset_test import FIXTURE_DIR, _fixture_files

JSON_SCHEMA_VERSION = 1
PROJECT_FILE = "compass.yml"
COMMAND = "compass policy migrate --words"
_MERGE_TAG = "tag:yaml.org,2002:merge"


class Refusal(CompassError):
    """A refusal: nothing is written, and the command exits 2."""


@dataclass
class FileChange:
    path: str            # absolute
    rel: str             # from the project root, with `/`
    text: str
    new_text: str
    changes: list        # [(path, old, new)]
    written: bool = False


@dataclass
class Plan:
    project: str
    folder: str
    files: list = field(default_factory=list)
    hand_edits: list = field(default_factory=list)    # [(file, code, path, message)]
    notes: list = field(default_factory=list)         # [(file, path, message)]
    unrestorable: list = field(default_factory=list)  # rel paths git cannot restore
    no_git: bool = False
    result: str = "dry-run"


# --- the text rewrite -----------------------------------------------------------

class _CannotPlace(Exception):
    pass


def rewrite_text(text, mapper, where):
    """`(new_text, changes)`: `text` with each scalar that `mapper` changes
    replaced in place, and the `(path, old, new)` of each. `mapper` takes the
    parsed document and returns the mapped one without changing its input.
    Raises `Refusal` when a change cannot be placed, or when the new text
    does not read as the mapped document."""
    try:
        raw = load_yaml_strict_text(text, where)
    except StrictYamlError as exc:
        raise Refusal(f"{COMMAND}: {exc}") from None
    mapped = mapper(raw)
    if mapped == raw:
        return text, []
    edits, changes = {}, []
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        _walk(node, raw, mapped, "", text, edits, changes)
    except _CannotPlace as exc:
        raise Refusal(f"{COMMAND}: {where}: the old word at {exc} cannot be rewritten in "
                      "place: it sits in a block scalar, under an anchor, behind a tag, or on a key "
                      "the mapping merges into another. "
                      "Nothing was written. Edit the file by hand, then run the "
                      "command again.") from None
    out = text
    for start in sorted(edits, reverse=True):
        end, new = edits[start]
        out = out[:start] + new + out[end:]
    again = load_yaml_strict_text(out, where)
    if again != mapped or mapper(again) != again:
        raise Refusal(f"{COMMAND}: {where}: the rewritten file would not read as the "
                      "word mapping reads it. Nothing was written. Edit the file by hand.")
    return out, changes


def _walk(node, raw, mapped, path, text, edits, changes):
    if raw == mapped:
        return
    if isinstance(node, yaml.MappingNode):
        if any(k.tag == _MERGE_TAG for k, _ in node.value) or not (
                isinstance(raw, dict) and isinstance(mapped, dict)
                and len(node.value) == len(raw) == len(mapped)):
            raise _CannotPlace(path or "the top level")
        for (key_node, value_node), (rk, rv), (mk, mv) in zip(
                node.value, raw.items(), mapped.items()):
            here = f"{path}.{rk}" if path else str(rk)
            if rk != mk:
                _replace(key_node, rk, mk, here, text, edits, changes)
            _walk(value_node, rv, mv, here, text, edits, changes)
    elif isinstance(node, yaml.SequenceNode):
        if not (isinstance(raw, list) and isinstance(mapped, list)
                and len(node.value) == len(raw) == len(mapped)):
            raise _CannotPlace(path)
        for index, (item, r, m) in enumerate(zip(node.value, raw, mapped)):
            _walk(item, r, m, f"{path}[{index}]", text, edits, changes)
    else:
        _replace(node, raw, mapped, path, text, edits, changes)


def _replace(node, old, new, path, text, edits, changes):
    """Record the replacement of one scalar's span, keeping its quotes."""
    if not (isinstance(node, yaml.ScalarNode) and isinstance(old, str)
            and isinstance(new, str)):
        raise _CannotPlace(path)
    quote = node.style if node.style in ("'", '"') else ""
    start, end = node.start_mark.index, node.end_mark.index
    if node.style not in (None, "", "'", '"') or text[start:end] != f"{quote}{old}{quote}":
        raise _CannotPlace(path)
    replacement = f"{quote}{new}{quote}"
    if start in edits:
        if edits[start] != (end, replacement):
            raise _CannotPlace(path)
        return              # an alias of a node already replaced
    edits[start] = (end, replacement)
    changes.append((path, old, new))


# --- the plan -------------------------------------------------------------------

def _inside(path, root):
    return path == root or path.startswith(root + os.sep)


def _rel(path, project):
    return os.path.relpath(path, project).replace(os.sep, "/")


def _read(path, rel):
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise Refusal(f"{COMMAND}: {rel} cannot be read: "
                      f"{getattr(exc, 'strerror', None) or 'not UTF-8 text'}") from None


def _set_fields(entry):
    """An entry as the merge leaves it: the fields a `set:` names, read as
    fields of the entry."""
    if isinstance(entry.get("set"), dict):
        return {**{k: v for k, v in entry.items() if k != "set"}, **entry["set"]}
    return entry


def _layer_view(config):
    """The project layer as `retired.condition_findings` reads a resolved
    configuration. An entry that `set:`s fields is read as those fields, and a
    rule set's `rules:` map edited with `set:` or `remove:` is read as the
    rules it sets, so a rule added to a shipped set is found where the lint
    finds it."""
    view = {"dimensions": config.get("dimensions") or {}}
    for catalogue in ("rules", "checks", "gates"):
        entries = config.get(catalogue)
        view[catalogue] = {}
        for entry_id, entry in (entries.items() if isinstance(entries, dict) else ()):
            if not isinstance(entry, dict):
                continue
            entry = _set_fields(entry)
            rules = entry.get("rules")
            if (catalogue == "rules" and isinstance(rules, dict) and rules
                    and set(rules) <= {"set", "remove"}):
                entry = dict(entry, rules=rules.get("set") if isinstance(
                    rules.get("set"), dict) else {})
            view[catalogue][entry_id] = entry
    return view


def _hand_edits(config, rel):
    """The role findings `compass policy lint` and the merge give for a layer."""
    if not isinstance(config, dict):
        return []
    out = [(rel, code, path, message)
           for code, path, message in retired.condition_findings(_layer_view(config))
           if code == "M-WHEN-RETIRED"]
    for catalogue, entries in config.items():
        for entry_id, entry in (entries.items() if isinstance(entries, dict) else ()):
            if not isinstance(entry, dict):
                continue
            op = ("set" if "set" in entry else "replace" if entry.get("replace") is True
                  else "remove" if entry.get("remove") is True else None)
            hint = retired.merge_hint(f"{catalogue}.{entry_id}") if op else ""
            if hint:
                out.append((rel, f"M-{op.upper()}-UNKNOWN", f"{catalogue}.{entry_id}",
                            f"{op}: the parent does not hold this id{hint}"))
    return out


def plan(project, folder):
    """Read and map every configuration file in `folder`, below `project`.
    Writes nothing. Raises `Refusal` for a folder outside the project, a linked
    or unreadable file, and a change that cannot be placed."""
    project = os.path.realpath(project)
    shown = folder
    folder = os.path.realpath(folder)
    if not _inside(folder, project):
        raise Refusal(f"{COMMAND}: {shown} is outside the project ({project}), and the "
                      "command writes only inside it. Run it from the project that holds "
                      "the folder.")
    if not os.path.isdir(folder):
        raise Refusal(f"{COMMAND}: {shown} is not a folder")
    made = Plan(project, folder)
    layer_path = os.path.join(folder, PROJECT_FILE)
    targets, declared = [], set()
    if os.path.islink(layer_path):
        raise Refusal(f"{COMMAND}: {_rel(layer_path, project)} is a link, and the command "
                      "does not write through one. Run it where the file itself is.")
    if os.path.isfile(layer_path):
        targets.append((layer_path, lambda doc: word_map.map_layer(doc)[0], "layer"))
    fixtures = os.path.join(folder, FIXTURE_DIR)
    if os.path.islink(fixtures):
        raise Refusal(f"{COMMAND}: {_rel(fixtures, project)} is a link, and the command "
                      "does not write through one. Run it where the folder itself is.")
    problems = []
    for _group, name in _fixture_files(folder, problems):
        targets.append((os.path.join(folder, FIXTURE_DIR, name), word_map.map_fixture,
                        "fixture"))
    made.notes += [(FIXTURE_DIR, "", f"{problem}") for problem in problems]
    for path, mapper, kind in targets:
        rel = _rel(path, project)
        if not _inside(os.path.realpath(path), project):
            raise Refusal(f"{COMMAND}: {rel} leads outside the project, and the command "
                          "writes only inside it.")
        text = _read(path, rel)
        new_text, changes = rewrite_text(text, mapper, rel)
        doc = load_yaml_strict_text(new_text, rel)
        if kind == "layer":
            made.hand_edits += _hand_edits(doc, rel)
            declared = set((doc.get("dimensions") or {}) if isinstance(doc, dict) else ())
        elif isinstance(doc, dict) and isinstance(doc.get("assessment"), dict):
            made.notes += [(rel, f"assessment.{d}", f"{retired.NOT_READ}; it is left in place")
                           for d in retired.DIMENSIONS
                           if d in doc["assessment"] and d not in declared]
        if changes:
            made.files.append(FileChange(path, rel, text, new_text, changes))
    _judge(made)
    made.result = ("hand-edit" if made.hand_edits else
                   "dry-run" if made.files else "nothing-to-change")
    return made


def _judge(made):
    """Which files `--apply` would refuse to write: those git cannot restore,
    or every file when the project is in no repository."""
    if not made.files:
        return
    paths = [f.path for f in made.files]
    found = migrate_copy_check.unrestorable_files(made.project, paths)
    if found.state == "no-git":
        made.no_git, lost = True, paths
    else:
        lost = found.unrestorable
    made.unrestorable = [_rel(p, made.project) for p in paths if p in set(lost)]


def _discard(paths):
    for path in paths:
        with contextlib.suppress(OSError):
            os.unlink(path)


def apply(made, have_copy):
    """Write every file of `made`, or none. Raises `Refusal`, before the first
    write, when git cannot restore a file and `have_copy` is false."""
    if made.unrestorable and not have_copy:
        if made.no_git:
            why = (f"{made.project} is in no git repository, so nothing can undo the "
                   "rewrite")
        else:
            why = ("git cannot restore these files, because each is not tracked, or is "
                   "staged or edited since the last commit:\n" +
                   "\n".join(f"  {rel}" for rel in made.unrestorable))
        raise Refusal(f"{COMMAND} --apply: {why}\n\nNothing was written. Commit the files "
                      "or take a copy, then run again with --i-have-a-copy. The flag says "
                      "you have the copy; it does not switch the check off.")
    # Every new file is written beside its target and every target checked
    # before the first rename, so a failure part way leaves every file as it was.
    staged = []
    try:
        for change in made.files:
            with open(change.path, "rb") as fh:
                if fh.read() != change.text.encode("utf-8"):
                    raise Refusal(f"{COMMAND}: {change.rel} changed while the command ran. "
                                  "Nothing was written. Run the command again.")
            folder = os.path.dirname(change.path)
            fd, tmp = tempfile.mkstemp(dir=folder, prefix=f".{os.path.basename(change.path)}-")
            staged.append(tmp)
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                fh.write(change.new_text)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, stat.S_IMODE(os.stat(change.path).st_mode))
    except OSError as exc:
        _discard(staged)
        # `change` is the file being staged; the error's own filename is the
        # temporary file, which means nothing to the reader.
        raise Refusal(f"{COMMAND} --apply: {change.rel} cannot be written: "
                      f"{exc.strerror or exc}. Nothing was written.") from None
    except BaseException:
        _discard(staged)
        raise
    done = []
    for change, tmp in zip(made.files, staged):
        try:
            os.replace(tmp, change.path)
        except OSError as exc:
            _discard(staged[len(done):])
            raise Refusal(f"{COMMAND} --apply: {change.rel} cannot be replaced: "
                          f"{exc.strerror or exc}. Already rewritten: "
                          f"{', '.join(done) or 'none'}; `git checkout` restores them.") from None
        change.written = True
        done.append(change.rel)
    if made.result == "dry-run":
        made.result = "applied"
    return made


# --- the report -----------------------------------------------------------------

def _diff(change):
    lines = difflib.unified_diff(change.text.splitlines(), change.new_text.splitlines(),
                                 f"a/{change.rel}", f"b/{change.rel}", lineterm="")
    return "\n".join(lines) + "\n"


def report_text(made, mode):
    lines = []
    for change in made.files:
        lines += _diff(change).rstrip("\n").split("\n")
    lines += [f"wrote {c.rel}" for c in made.files if c.written]
    lines += [f"hand edit: {f}: {p}: {m} ({code})" for f, code, p, m in made.hand_edits]
    lines += [f"note: {f}: {p}: {m}" if p else f"note: {f}: {m}" for f, p, m in made.notes]
    count = len(made.files)
    if not made.files:
        lines.append(f"{COMMAND}: nothing to change - no old word in {PROJECT_FILE} or "
                     f"{FIXTURE_DIR}/")
    elif mode == "dry-run":
        lines.append(f"Dry run: nothing was written. Run with --apply to rewrite {count} "
                     f"file{'' if count == 1 else 's'} in the 6.0.0 words.")
        if made.unrestorable:
            lines.append("--apply would refuse: " + (
                "the project is in no git repository" if made.no_git else
                "git cannot restore " + ", ".join(made.unrestorable)) +
                ". Commit first, or pass --i-have-a-copy.")
    else:
        lines.append(f"Rewrote {count} file{'' if count == 1 else 's'} in the 6.0.0 words.")
    if made.hand_edits:
        lines.append(f"{len(made.hand_edits)} hand edit(s) left: a condition or an edit "
                     "that names the retired role dimension has no rewrite (ADR-070). "
                     "Change it as the message says.")
    return lines


def report_json(made, mode):
    folder = _rel(made.folder, made.project)
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "mode": mode,
        "folder": folder,
        "files": [{"path": c.rel,
                   "changes": [{"path": p, "old": o, "new": n} for p, o, n in c.changes],
                   "diff": _diff(c),
                   "written": c.written} for c in made.files],
        "hand_edits": [{"file": f, "code": code, "path": p, "message": m}
                       for f, code, p, m in made.hand_edits],
        "notes": [{"file": f, "path": p, "message": m} for f, p, m in made.notes],
        "result": made.result,
    }


def exit_code(made):
    return 1 if made.hand_edits else 0
