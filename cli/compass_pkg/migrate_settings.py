# compass_pkg.migrate_settings - `compass migrate` on compass.yml: the settings half
"""`compass migrate` rewrites an 8.x `compass.yml` for 9.0.0 (#359, ADR-098 decision 6).

9.0.0 does not read a removed key (ADR-094), so deleting one changes no
verdict. This module deletes each removed key `removed_parts.REPLACEMENTS`
marks as migrated, and writes the tighten-only setting that carries what the
key asked for, where one does:

- `extends: compass:default@6` or `@7` becomes `acceptance_strategy: {state:
  off, reason: ...}`, so `S17` stays off (ADR-094 open question 7), unless the
  file already sets `acceptance_strategy`;
- the labels a `gates.G5` entry adds to `when.labels_any` become
  `signoff_labels`;
- a `rules:` floor whose effect is `add_gate` becomes a `require_evidence`
  entry, when the gate has an evidence token (`evidence_required.
  TOKEN_OF_GATE`);
- a project check with `impl: command-passes`, and the guardrail gate that
  lists it, become a `project_checks` entry, at the path stage of the gate's
  stage (`stable_ids.LEGACY_TO_PATH`; a specify stage runs at build, the
  earliest stage a project check can run at);
- the agent review block that `docs/judged-checks.md` gave before 9.0.0
  becomes `agent_review: on`;
- `approvers.issue-waiver` is renamed `approvers.waiver` when that list is
  absent, since 9.0.0 reads it as `waiver` then.

Each part of a migrated key that no setting carries is named on a line. A key
`REPLACEMENTS` marks as not migrated is left in the file with a line naming
the edit, and so is a migrated key that holds one (`rules.caps` in `rules:`):
a person decides it, then runs `compass migrate` again.

The file is changed by a line edit, not a YAML dump, so its comments stay. A
removed key goes with its indented lines and the comment block directly above
it; the new settings go at the end under one comment line. The edit is then
checked twice before anything is written: the edited text must parse to the
mapping the change list gives, and the settings lint (`settings_lint.lint`,
over the check set) must find no error and no removed key but the ones left.
If either fails, nothing is written and the output names the lines to edit.

Only `compass.yml` is rewritten. A project with only `.compass/config.yml`
keeps it, because 9.0.0 still reads it (ADR-098 open question 5).
The owning doc is `docs/upgrade-9-0-0.md`.
"""
# DEPENDENCY: standard library (copy, difflib, json, os, re, shlex); yaml (bundled);
# compass_pkg.atomic_io, check_set, core (CompassError), evidence_required,
# project_settings, removed_parts, settings_lint, stable_ids.
from __future__ import annotations

import copy
import difflib
import json
import os
import re
import shlex

import yaml

from compass_pkg import atomic_io, removed_parts, settings_lint
from compass_pkg.core import CompassError
from compass_pkg.stable_ids import GATE_G5, LEGACY_TO_PATH, STAGE_BUILD, STAGE_SPECIFY

FILE = "compass.yml"
#: The lock held while `compass.yml` is read, checked and written, so two runs
#: cannot interleave. Under `.compass/`, whose `.*.lock` files the record skips.
LOCK = ".settings.lock"
#: The comment line above the settings `compass migrate` adds.
ADDED_COMMENT = ("# Settings compass migrate wrote in place of keys 9.0.0 removed "
                 "(docs/upgrade-9-0-0.md).")
STRATEGY_REASON = ("kept off from extends: compass:default@{major} (compass migrate, "
                   "ADR-094 open question 7)")
AGENT_REVIEW = settings_lint.AGENT_REVIEW
#: The tighten-only settings in the order they are appended.
ADDED_ORDER = ("acceptance_strategy", "signoff_labels", "require_evidence",
               "project_checks", "agent_review")
#: A plain top-level key, as this editor finds it at column 0.
_TOP = re.compile(r"""^(?P<key>"[^"]*"|'[^']*'|[^\s#:'"][^:]*?)\s*:(?:\s|$)""")


# --- what each removed key becomes ---------------------------------------------------

def _row(key, value=None):
    return removed_parts.replacement_of(key, value)


def removed_top_keys():
    """The top-level keys `REPLACEMENTS` names: a key, or the head of a dotted
    key that is itself a row (`rules`, `checks`). Read from the table, so a
    row a later step adds is migrated with no change here."""
    return [key for key in removed_parts.REPLACEMENTS
            if "." not in key and "@" not in key and "*" not in key]


def edit_for(key, value=None):
    """The edit a person makes for a removed key migrate leaves."""
    settings, _ = _row(key, value)
    if settings:
        return "replace it with " + " or ".join(f"`{s}`" for s in settings)
    return "delete it: nothing replaces it"


def _held_unmigrated(key, value):
    """The dotted rows under `key` that `value` holds and migrate does not rewrite."""
    if not isinstance(value, dict):
        return []
    out = []
    for sub in value:
        path = f"{key}.{sub}"
        if path in removed_parts.REPLACEMENTS and not removed_parts.REPLACEMENTS[path][1]:
            out.append(path)
    return out


class Plan:
    """What `compass migrate` does to one `compass.yml`, built from the parsed
    mapping before any text is edited."""

    def __init__(self, doc):
        self.doc = doc
        self.delete = []        # top-level keys
        self.delete_child = []  # (key, child)
        self.rename_child = []  # (key, child, new)
        self.added = {}         # tighten-only setting -> value
        self.changes = []       # one line per change, for the report
        self.dropped = []       # one line per part no setting carries
        self.left = []          # {"key", "edit"}: what a person edits

    # -- the report lines --
    def change(self, text):
        self.changes.append(text)

    def drop(self, path, why):
        self.dropped.append(f"{path}: {why}")

    def leave(self, key, edit):
        self.left.append({"key": key, "edit": edit})

    @property
    def has_change(self):
        return bool(self.delete or self.delete_child or self.rename_child or self.added)


def build(doc, base=None):
    """The `Plan` for the parsed `compass.yml` `doc`. `base` is the resolved
    check set the new settings are checked against."""
    plan = Plan(doc)
    removed = removed_top_keys()
    for key in list(doc):
        if key in removed or key == "extends":
            _removed_key(plan, key, doc[key], base)
    _project_fields(plan, doc)
    _approvers(plan, doc)
    _capabilities(plan, doc)
    _agent_review_stages(plan, doc)
    return plan


def _removed_key(plan, key, value, base):
    settings, migrated = _row(key, value)
    if not migrated:
        if key == "stages" and _agent_review_only(value):
            return      # part of the agent review block; `_agent_review_stages` decides
        plan.leave(key, f"compass migrate does not rewrite it; {edit_for(key, value)}")
        return
    held = _held_unmigrated(key, value)
    if held:
        edits = "; ".join(f"{p}: {edit_for(p)}" for p in held)
        plan.leave(key, f"it holds {', '.join(held)}, which compass migrate does not "
                        f"rewrite. {edits}. Then run compass migrate again")
        return
    plan.delete.append(key)
    plan.change(f"{key}: deleted ({removed_parts.replacement_text(key, value) or 'removed'})")
    convert = _CONVERTERS.get(key)
    if convert is not None:
        convert(plan, value, base)


# --- extends -------------------------------------------------------------------------

def _extends(plan, value, _base):
    row = removed_parts.extends_row(value)
    if row in ("extends@6", "extends@7") and "acceptance_strategy" not in plan.doc:
        ref = value.get("from") if isinstance(value, dict) else value
        major = ref.rsplit("@", 1)[1]
        plan.added["acceptance_strategy"] = {
            "state": "off", "reason": STRATEGY_REASON.format(major=major)}
        plan.change("acceptance_strategy: added with state off, so the acceptance strategy "
                    f"stays off as the pin {ref} kept it")


# --- gates ---------------------------------------------------------------------------

def _body(entry):
    """The mapping an 8.x catalogue entry sets: its `set:` change, or itself."""
    if not isinstance(entry, dict):
        return {}
    return entry["set"] if isinstance(entry.get("set"), dict) else entry


def _added(value):
    """The items a list field adds: a plain list, or the `add:` of `{add, remove}`."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict) and isinstance(value.get("add"), list):
        return list(value["add"])
    return []


def _signoff(plan, entry):
    from compass_pkg.evidence_required import G5_LABELS
    when = _body(entry).get("when")
    labels = _added(when.get("labels_any")) if isinstance(when, dict) else []
    extra = [str(label) for label in labels if label not in G5_LABELS]
    if extra:
        held = list(plan.added.get("signoff_labels") or plan.doc.get("signoff_labels") or [])
        plan.added["signoff_labels"] = held + [label for label in extra if label not in held]
        plan.change(f"signoff_labels: {', '.join(extra)} added from gates.{GATE_G5}")
    rest = {k: v for k, v in _body(entry).items() if k != "when"}
    other_when = {k: v for k, v in (when or {}).items() if k != "labels_any"} \
        if isinstance(when, dict) else {}
    if rest or other_when or (isinstance(when, dict) and isinstance(
            when.get("labels_any"), dict) and when["labels_any"].get("remove")):
        plan.drop(f"gates.{GATE_G5}", "only the labels it adds carry over "
                                      "(signoff_labels); a setting can only add")


def _gates(plan, value, base):
    gates = value if isinstance(value, dict) else {}
    checks = plan.doc.get("checks") if isinstance(plan.doc.get("checks"), dict) else {}
    for gate_id, entry in gates.items():
        if gate_id == GATE_G5:
            _signoff(plan, entry)
            continue
        commands = _command_checks(entry, checks)
        if not commands:
            plan.drop(f"gates.{gate_id}", "no setting replaces it")
            continue
        for check_id, command in commands:
            _project_check(plan, gate_id, entry, check_id, command, base)


def _command_of(check):
    """The command an 8.x `command-passes` check runs, as one line, or None."""
    body = _body(check)
    if body.get("impl") != "command-passes":
        return None
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    if isinstance(params.get("command"), str) and params["command"].strip():
        return params["command"]
    if isinstance(params.get("script"), str) and params["script"].strip():
        args = params.get("args") if isinstance(params.get("args"), list) else []
        return shlex.join([params["script"], *map(str, args)])
    return None


def _command_checks(entry, checks):
    """`(check id, command)` for each `command-passes` check a project gate lists."""
    body = _body(entry)
    out = []
    for check_id in _added(body.get("checks")):
        command = _command_of(checks.get(check_id)) if check_id in checks else None
        if command:
            out.append((check_id, command))
    return out


def _project_check(plan, gate_id, entry, check_id, command, base):
    body = _body(entry)
    stage = body.get("stage")
    path_stage = LEGACY_TO_PATH.get(stage, stage) if isinstance(stage, str) else None
    note = ""
    if path_stage == STAGE_SPECIFY:
        path_stage, note = STAGE_BUILD, f" (it ran at {stage}; a project check runs at build or ship)"
    elif path_stage != stage and path_stage is not None:
        note = f" (it ran at {stage})"
    check = _body((plan.doc.get("checks") or {}).get(check_id))
    name = body.get("name") or check.get("statement") or check_id
    item = {"id": check_id, "name": " ".join(str(name).split()), "command": command,
            "stage": path_stage}
    if body.get("when"):
        item["when"] = copy.deepcopy(body["when"])
    problems = settings_lint.value_problems({"project_checks": [item]}, base)
    if problems:
        plan.drop(f"gates.{gate_id}", "its command check cannot be written as a project "
                                      "check (" + "; ".join(m for _, m in problems) + ")")
        return
    held = list(plan.added.get("project_checks") or plan.doc.get("project_checks") or [])
    if any(isinstance(h, dict) and h.get("id") == check_id for h in held):
        return
    plan.added["project_checks"] = held + [item]
    plan.change(f"project_checks: {check_id} added at {path_stage} from gates.{gate_id}{note}")


# --- checks --------------------------------------------------------------------------

def _checks(plan, value, _base):
    checks = value if isinstance(value, dict) else {}
    gates = plan.doc.get("gates") if isinstance(plan.doc.get("gates"), dict) else {}
    listed = {c for entry in gates.values() for c in _added(_body(entry).get("checks"))}
    for check_id, entry in checks.items():
        if check_id == AGENT_REVIEW:
            _agent_review(plan)
        elif _command_of(entry) and check_id in listed:
            continue        # carried over with the gate that lists it (`_gates`)
        else:
            plan.drop(f"checks.{check_id}", "no setting replaces it")


def _agent_review(plan):
    held = plan.doc.get("agent_review")
    if held in (False, "off"):
        plan.drop(f"checks.{AGENT_REVIEW}", "agent_review is off in this file, which "
                                            "is the later choice")
        return
    if held is None:
        plan.added["agent_review"] = "on"
        plan.change(f"agent_review: on added from checks.{AGENT_REVIEW}")


def _agent_review_only(value):
    """True when a `stages:` block only adds `agent-review` to the `ship` entry,
    as the agent review block of `docs/judged-checks.md` did before 9.0.0."""
    if not isinstance(value, dict) or list(value) != ["ship"]:
        return False
    body = _body(value["ship"])
    return list(body) == ["entry"] and _added(body["entry"]) == [AGENT_REVIEW]


def _agent_review_stages(plan, doc):
    value = doc.get("stages")
    if value is None or not _agent_review_only(value):
        return
    if "checks" in plan.delete:
        plan.delete.append("stages")
        plan.change("stages: deleted (the ship entry of the agent review block)")
    else:
        plan.leave("stages", f"compass migrate does not rewrite it; {edit_for('stages')}")


# --- rules ---------------------------------------------------------------------------

def _rules(plan, value, base):
    from compass_pkg.evidence_required import TOKEN_OF_GATE
    rules = value if isinstance(value, dict) else {}
    for set_id, entry in rules.items():
        bodies = _rule_bodies(entry)
        if not bodies:
            plan.drop(f"rules.{set_id}", "no setting replaces it")
            continue
        for rule_id, body in bodies:
            where = f"rules.{set_id}.rules.{rule_id}"
            then = body.get("then") if isinstance(body.get("then"), dict) else {}
            for effect in then:
                if effect != "add_gate":
                    plan.drop(f"{where}.then.{effect}", "no setting replaces it")
                    continue
                for gate in then["add_gate"] if isinstance(then["add_gate"], list) \
                        else [then["add_gate"]]:
                    token = TOKEN_OF_GATE.get(gate)
                    if token is None:
                        plan.drop(f"{where}.then.add_gate", f"{gate} has no evidence "
                                                            f"token; no setting replaces it")
                        continue
                    _require(plan, where, body.get("when"), token, base)


def _rule_bodies(entry):
    """`(rule id, body)` for each rule one rule set entry gives: a new set's
    `rules:`, or a `set:` change's `rules:` (whole, or its `set:` or `add:`)."""
    if not isinstance(entry, dict):
        return []
    maps = [entry.get("rules")]
    changes = entry.get("set")
    if isinstance(changes, dict):
        inner = changes.get("rules")
        maps.append(inner)
        if isinstance(inner, dict):
            maps += [inner.get("set"), inner.get("add")]
    out = []
    for held in maps:
        if isinstance(held, dict):
            out += [(rule_id, body) for rule_id, body in held.items()
                    if isinstance(body, dict) and rule_id not in ("set", "add", "remove")]
    return out


def _require(plan, where, when, token, base):
    item = {"when": copy.deepcopy(when)} if when else {}
    item["add"] = [token]
    problems = settings_lint.value_problems({"require_evidence": [item]}, base)
    if problems:
        plan.drop(f"{where}.then.add_gate", "its when cannot be written as a setting ("
                  + "; ".join(m for _, m in problems) + f"); add a require_evidence entry "
                  f"for {token} by hand")
        return
    held = list(plan.added.get("require_evidence") or plan.doc.get("require_evidence") or [])
    if item not in held:
        plan.added["require_evidence"] = held + [item]
        plan.change(f"require_evidence: {token} added from {where}")


_CONVERTERS = {"extends": _extends, "gates": _gates, "checks": _checks, "rules": _rules}


# --- keys of settings that stay ------------------------------------------------------

def _project_fields(plan, doc):
    project = doc.get("project")
    if not isinstance(project, dict):
        return
    for path in removed_parts.SETTING_FIELDS:
        key, field = path.split(".", 1)
        if key != "project" or field not in project:
            continue
        _settings, migrated = _row(path)
        if migrated:
            plan.delete_child.append(("project", field))
            plan.change(f"{path}: deleted (removed)")
        else:
            plan.leave(path, f"compass migrate does not rewrite it; {edit_for(path)}")


def _approvers(plan, doc):
    approvers = doc.get("approvers")
    if not isinstance(approvers, dict):
        return
    if "project-waiver" in approvers:
        plan.delete_child.append(("approvers", "project-waiver"))
        plan.change("approvers.project-waiver: deleted (removed)")
    if "issue-waiver" in approvers and "waiver" not in approvers:
        plan.rename_child.append(("approvers", "issue-waiver", "waiver"))
        plan.change("approvers.issue-waiver: renamed approvers.waiver")


def _capabilities(plan, doc):
    held = doc.get("capabilities")
    if not isinstance(held, dict):
        return
    for name in removed_parts.CAPABILITIES:
        if held.get(name) is not True:
            continue
        path = f"capabilities.{name}"
        _settings, migrated = _row(path)
        if migrated:
            plan.delete_child.append(("capabilities", name))
            plan.change(f"{path}: deleted (removed)")
        else:
            plan.leave(path, f"compass migrate does not rewrite it; {edit_for(path)}")


# --- the line editor -----------------------------------------------------------------

def _key_of(line):
    found = _TOP.match(line)
    if not found:
        return None
    key = found.group("key").strip()
    return key[1:-1] if key[:1] in ("'", '"') else key


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _blank(line):
    return not line.strip()


def _comment(line):
    return line.lstrip().startswith("#")


class Lines:
    """The text of `compass.yml` as lines, with the edits `compass migrate`
    makes: delete a top-level key, delete or rename a key one level down, and
    append. Each edit keeps every line it does not name."""

    def __init__(self, text):
        self.lines = text.splitlines(keepends=True)
        if self.lines and not self.lines[-1].endswith("\n"):
            self.lines[-1] += "\n"

    def text(self):
        return "".join(self.lines)

    def _top(self, key):
        for i, line in enumerate(self.lines):
            if line[:1] not in (" ", "\t", "#", "-") and _key_of(line) == key:
                return i
        raise CompassError(f"compass migrate: cannot find the line of '{key}' in {FILE}")

    def _end(self, start, indent):
        """The index after the last line of the block that starts at `start`:
        every later line that is blank or indented past `indent`, with the
        blank lines at its end left out."""
        end = start + 1
        while end < len(self.lines) and (_blank(self.lines[end])
                                         or _indent(self.lines[end]) > indent):
            end += 1
        while end > start + 1 and _blank(self.lines[end - 1]):
            end -= 1
        return end

    def _comments_above(self, start, indent):
        while start > 0 and _comment(self.lines[start - 1]) \
                and _indent(self.lines[start - 1]) == indent:
            start -= 1
        return start

    def _cut(self, start, end):
        del self.lines[start:end]
        # One blank line between two blocks, none at the start or end.
        if 0 < start < len(self.lines) and _blank(self.lines[start - 1]) \
                and _blank(self.lines[start]):
            del self.lines[start]
        while self.lines and _blank(self.lines[0]):
            del self.lines[0]
        while self.lines and _blank(self.lines[-1]):
            del self.lines[-1]

    def _inline(self, i):
        """True when the value of the key on line `i` is on that line."""
        rest = self.lines[i].split(":", 1)[1].strip()
        return bool(rest) and not rest.startswith("#")

    def delete_top(self, key):
        i = self._top(key)
        self._cut(self._comments_above(i, 0), self._end(i, 0))

    def replace_top(self, key, value):
        """Write `key: value` in flow style in place of the key's lines."""
        i = self._top(key)
        end = self._end(i, 0)
        self.lines[i:end] = [f"{key}: {_flow(value)}\n"]

    def _child(self, key, child):
        """`(line index, indent)` of `child` under the block key `key`."""
        i = self._top(key)
        end = self._end(i, 0)
        indent = next((_indent(line) for line in self.lines[i + 1:end]
                       if not _blank(line) and not _comment(line)), None)
        for j in range(i + 1, end):
            line = self.lines[j]
            if _indent(line) == indent and not _comment(line) \
                    and _key_of(line[indent:]) == child:
                return j, indent
        raise CompassError(f"compass migrate: cannot find the line of '{key}.{child}' "
                           f"in {FILE}")

    def delete_child(self, key, child, value_after):
        """Delete `key.child`; `value_after` is the key's value without it."""
        if self._inline(self._top(key)):
            if value_after:
                self.replace_top(key, value_after)
            else:
                self.delete_top(key)
            return
        j, indent = self._child(key, child)
        self._cut(self._comments_above(j, indent), self._end(j, indent))
        if not value_after:
            self.delete_top(key)

    def rename_child(self, key, child, new, value_after):
        if self._inline(self._top(key)):
            self.replace_top(key, value_after)
            return
        j, indent = self._child(key, child)
        line = self.lines[j]
        _old, sep, rest = line[indent:].partition(":")
        self.lines[j] = line[:indent] + new + sep + rest

    def append(self, block):
        while self.lines and _blank(self.lines[-1]):
            del self.lines[-1]
        if self.lines:
            self.lines.append("\n")
        self.lines += [line + "\n" for line in block]


def _flow(value):
    return yaml.safe_dump(value, default_flow_style=True, sort_keys=False,
                          allow_unicode=True, width=10 ** 6).strip()


def added_lines(added):
    """The block appended for the settings `added`, in `ADDED_ORDER`."""
    lines = [ADDED_COMMENT]
    for key in ADDED_ORDER:
        if key not in added:
            continue
        value = added[key]
        if key == "acceptance_strategy":
            lines.append(f"acceptance_strategy: {{state: off, reason: "
                         f"{json.dumps(value['reason'])}}}")
        elif key == "agent_review":
            lines.append("agent_review: on")
        elif key == "signoff_labels":
            lines.append(f"signoff_labels: {_flow(value)}")
        else:
            lines += yaml.safe_dump({key: value}, default_flow_style=False, sort_keys=False,
                                    allow_unicode=True, width=10 ** 6).splitlines()
    return lines


def _expected(plan):
    """The mapping the edited text must parse to."""
    out = copy.deepcopy(plan.doc)
    for key in plan.delete:
        out.pop(key, None)
    for key, child in plan.delete_child:
        out[key].pop(child, None)
        if not out[key]:
            del out[key]
    for key, child, new in plan.rename_child:
        out[key] = {(new if k == child else k): v for k, v in out[key].items()}
    for key in plan.added:
        out.pop(key, None)
    if plan.added:
        out.update(yaml.safe_load("\n".join(added_lines(plan.added))) or {})
    return out


def edit(text, plan):
    """The text of `compass.yml` with the plan's edits made line by line."""
    lines = Lines(text)
    for key in plan.delete:
        lines.delete_top(key)
    after = copy.deepcopy(plan.doc)
    for key, child in plan.delete_child:
        after[key].pop(child, None)
        lines.delete_child(key, child, after[key])
    for key, child, new in plan.rename_child:
        after[key] = {(new if k == child else k): v for k, v in after[key].items()}
        lines.rename_child(key, child, new, after[key])
    for key in plan.added:
        if key in plan.doc:
            lines.delete_top(key)
    if plan.added:
        lines.append(added_lines(plan.added))
    return lines.text()


# --- the run -------------------------------------------------------------------------

def _problems(new_text, plan, base):
    """Why the edited text must not be written, as lines; empty when it can be."""
    try:
        new_doc = atomic_io.load_yaml_strict_text(new_text, FILE)
    except (ValueError, yaml.YAMLError) as exc:
        return [f"{FILE}: the edited text does not parse ({exc})"]
    if new_doc != _expected(plan):
        return [f"{FILE}: the line edit does not give the settings the change list "
                f"names; edit the keys above by hand"]
    left = {item["key"].split(".", 1)[0] for item in plan.left}
    out = []
    for finding in settings_lint.lint(new_doc, base):
        if finding.level == "error":
            out.append(f"{finding.path}: {finding.message}")
        elif finding.code == "L-SETTING-REMOVED" \
                and finding.path.split(".", 1)[0] not in left:
            out.append(f"{finding.path}: still a removed key after the edit; {finding.message}")
    return out


def migrate(root, compass_dir, apply):
    """Run the settings half on the project at `root`. Returns a result mapping:
    `file`, `result` (`nothing`, `would change`, `changed`, `refused` or
    `left`), `changes`, `dropped`, `left`, `refused` and `diff`."""
    from compass_pkg import check_set, project_settings
    path = os.path.join(root, FILE)
    out = {"file": FILE, "result": "nothing", "changes": [], "dropped": [], "left": [],
           "refused": [], "diff": []}
    if not project_settings.compass_yml_counts(root):
        old = os.path.join(root, project_settings.OLD_CONFIG)
        if os.path.isfile(old):
            out["file"] = project_settings.OLD_CONFIG
            out["result"] = "left"
            out["left"] = [{"key": project_settings.OLD_CONFIG,
                            "edit": "9.0.0 still reads it; compass migrate rewrites "
                                    "compass.yml only"}]
        return out
    with atomic_io.locked(os.path.join(compass_dir, LOCK)):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        try:
            doc = atomic_io.load_yaml_strict_text(text, FILE)
        except (ValueError, yaml.YAMLError) as exc:
            raise CompassError(f"compass migrate: {FILE} cannot be read: {exc}. "
                               f"Nothing was written.") from exc
        if not isinstance(doc, dict):
            raise CompassError(f"compass migrate: {FILE} is not a mapping. "
                               f"Nothing was written.")
        base = check_set.resolved()
        plan = build(doc, base)
        out.update(changes=plan.changes, dropped=plan.dropped, left=plan.left)
        if not plan.has_change:
            out["result"] = "left" if plan.left else "nothing"
            return out
        new_text = edit(text, plan)
        out["diff"] = [line.rstrip("\n") for line in difflib.unified_diff(
            text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile=f"a/{FILE}", tofile=f"b/{FILE}")]
        refused = _problems(new_text, plan, base)
        if refused:
            out.update(result="refused", refused=refused)
            return out
        if apply:
            atomic_io.atomic_write_text(path, new_text)
            out["result"] = "changed"
        else:
            out["result"] = "would change"
    return out
