# compass_pkg.policy_migrate - `compass policy migrate`
"""Turn copied legacy governance and the old settings file into `compass.yml`.

The project's own `governance/routing-policy.yml` and `guardrails.yml`
become an overlay over the shipped default preset, and the settings in the
old settings file fold into the same file (ADR-042, ADR-043). The module
plans first and writes only when asked.

The overlay holds the project's local edits: the difference between its copy
and the release of the shipped governance files the copy came from, both
converted to catalogue form by the legacy adapter. The release is found from
the table in `shipped_releases` (the copy's `version:` lines, else the
release that gives the fewest entries, else the files this install ships). A
default that moved since that release is adopted without a waiver and is
listed in the report. The preset holds fields the legacy format cannot state
(stage entry and exit lists, three Definition of Done checks), so the copy is
never compared with the preset itself. The classifier checks that the base
release plus the overlay is the copy. Whatever cannot be written is reported,
not written over.
"""
# DEPENDENCY: standard library (copy, hashlib, os); the bundled PyYAML;
# compass_pkg.atomic_io, catalogue_spec, classify, core, layers,
# legacy_adapter, merge, policy_lint, project_settings, shipped_releases and
# waivers.
from __future__ import annotations

import copy
import hashlib
import os
from dataclasses import dataclass, field

import yaml

from compass_pkg import catalogue_spec as spec
from compass_pkg import (classify, layers, legacy_adapter, merge, policy_lint,
                         project_settings, shipped_releases, waivers)
from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import FRAMEWORK_ROOT, CompassError, load_yaml, migrate_map_section

GOVERNANCE_FILES = ("governance/routing-policy.yml", "governance/guardrails.yml")
# The old settings file's path, as `project_settings` names it, in the form the
# report shows. Only that module spells it out.
OLD_CONFIG = project_settings.OLD_CONFIG.replace(os.sep, "/")
COMPASS_YML = "compass.yml"
LEGACY_DIR = ".compass/legacy"
MIGRATION_YML = ".compass/migration.yml"
STATE_YML = ".compass/state.yml"
UNAPPROVED = waivers.UNAPPROVED
STUB_REASON = ("Migrated from a copy of the governance files whose local edit loosens "
               "the shipped release it came from. Confirm the departure, then set "
               "approved_by and approved_on.")
NOT_EQUIVALENT = "MIG-NOT-EQUIVALENT"
UNEXPRESSED = "MIG-UNEXPRESSED"
UNCLASSIFIABLE = "MIG-UNCLASSIFIABLE"

# A copy whose nearest release still needs more overlay entries than this, and
# whose version lines match no release, came from none of them: the base falls
# back to the files this install ships.
FAR_ENTRIES = 40

HEADER = ("# Written by compass policy migrate. This file holds only what differs from\n"
          "# the shipped default preset named in extends, and the project's settings.\n")


@dataclass
class Plan:
    result: str = "nothing-to-migrate"
    sources: list = field(default_factory=list)
    ops: list = field(default_factory=list)       # [{catalogue, id, operation, waiver}]
    blocked: list = field(default_factory=list)   # [{code, path, message}]
    equivalence: object = None
    behaviour: object = None
    base_release: object = None                   # {release, chosen_by}
    adopted: list = field(default_factory=list)   # [{catalogue, id, operation}]
    doc: dict = field(default_factory=dict)
    compass_yml: str = ""
    moved: list = field(default_factory=list)     # [{key, to}]
    state: dict = field(default_factory=dict)     # for the state file
    dropped: list = field(default_factory=list)   # [{key, reason}]
    unread: list = field(default_factory=list)    # keys no code reads
    digests: dict = field(default_factory=dict)   # source path -> sha256
    files: list = field(default_factory=list)     # [{action, path, to}]
    resumed: bool = False                         # only the old file is left to remove


def _present(root, rel):
    return os.path.isfile(os.path.join(root, *rel.split("/")))


def _absolute(root, rel):
    return os.path.join(root, *rel.split("/"))


def file_digest(path):
    with open(path, "rb") as fh:
        return "sha256:" + hashlib.sha256(fh.read()).hexdigest()


def _marker(root):
    """The parsed `migration.yml`, or None."""
    path = _absolute(root, MIGRATION_YML)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def pending_removal(root):
    """True when an earlier `--apply` wrote `compass.yml` and stopped before it
    removed the old settings file: the marker is there and its digest of the
    old file is the digest of the file that is still there. Anything else, an
    edited old file included, is a conflict a person must settle."""
    marker, old = _marker(root), _absolute(root, OLD_CONFIG)
    if not (_present(root, COMPASS_YML) and marker and os.path.isfile(old)):
        return False
    recorded = (marker.get("sources") or {}).get(OLD_CONFIG)
    return recorded == file_digest(old)


def _has_schema(root):
    """Whether `compass.yml` is Compass's file: it has a top-level `schema:`.
    A file that cannot be read counts as Compass's, so it is never called
    foreign on a guess."""
    try:
        with open(_absolute(root, COMPASS_YML), "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return True
    return not isinstance(data, dict) or "schema" in data


def _compass_yml_refusal(root):
    """The reason a `compass.yml` that is already there stops the command. It
    never advises a step that loses a setting: a recognised file holds the
    project's settings, so it is not moved away."""
    if _marker(root) is not None:
        return ("compass.yml was written by compass policy migrate, which "
                "migration.yml in .compass records, and it now holds this project's "
                "settings. Nothing was changed. Do not move it away: the settings "
                f"would fall back to their defaults. To go back to the old files, "
                f"copy {OLD_CONFIG} and the two governance files from the legacy "
                "folder in .compass to where they were, then remove compass.yml and "
                "migration.yml")
    if not _has_schema(root):
        return ("compass.yml exists and has no `schema:`, so Compass does not read "
                "it: it looks like another tool's file. Nothing was changed. Move "
                "it to another name, or add `schema: 1` if it is Compass's, then "
                "run the command again")
    message = ("compass.yml already exists and Compass reads it, so there is nothing "
               "to migrate into. Nothing was changed")
    keys = project_settings.settings_conflict(root)
    if keys:
        message += (f". {OLD_CONFIG} still sets {', '.join(keys)}: move them into "
                    "compass.yml (write mode as adoption) and delete them from the "
                    "old file")
    return message


def refusals(root):
    """Raise `CompassError` when the command must not run here. Nothing is
    written first, so a refusal leaves the project as it was."""
    if os.path.realpath(root) == os.path.realpath(FRAMEWORK_ROOT):
        raise CompassError(
            "compass policy migrate does not run in the Compass framework "
            "repository: its governance files are generated from the shipped "
            "preset, so there is no copy to migrate")
    if _present(root, COMPASS_YML) and not pending_removal(root):
        raise CompassError(_compass_yml_refusal(root))
    held = [rel for rel in GOVERNANCE_FILES if _present(root, rel)]
    if len(held) == 1:
        missing = next(rel for rel in GOVERNANCE_FILES if rel not in held)
        raise CompassError(
            f"{held[0]} is present without {missing}. A copy needs both files, "
            "and Compass does not read a lone one. Add the missing file or "
            "remove this one, then run the command again")


# --- the settings --------------------------------------------------------------------

STATE_KEYS = ("initialised", "records_signed_since")
DROPPED = {"version": "schema: 1 replaces it"}


def _read_old_config(root):
    path = os.path.join(root, *OLD_CONFIG.split("/"))
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise CompassError(f"cannot read {OLD_CONFIG}: {exc}") from exc
    if not isinstance(data, dict):
        raise CompassError(f"{OLD_CONFIG}: expected a mapping of settings")
    return data


def _fold_settings(root, made):
    """The settings for `compass.yml`, and the record of where each old key
    went. Fills `moved`, `state`, `dropped` and `unread` on `made`."""
    if not _present(root, OLD_CONFIG):
        return {}
    old = _read_old_config(root)
    renames = migrate_map_section("config_keys", {})
    counted = (set(spec.SETTINGS_KEYS) | set(project_settings.OLD_FILE_EXTRA_KEYS)) - {"adoption"}
    settings = {}
    for key, value in old.items():
        target = "adoption" if key == "mode" else renames.get(key, key)
        if key in STATE_KEYS:
            made.state[key] = copy.deepcopy(value)
        elif key in DROPPED:
            made.dropped.append({"key": key, "reason": DROPPED[key]})
        elif (key == "mode" or target in counted) and target not in settings:
            settings[target] = copy.deepcopy(value)
            made.moved.append({"key": key, "to": target})
        else:
            made.unread.append(key)
    # A script setting found outside its heading was read by the old lookup;
    # `compass.yml` is read at the documented path only.
    for name, (heading, leaf) in project_settings.SCRIPT_SETTINGS.items():
        held = settings.get(heading)
        if isinstance(held, dict) and leaf in held:
            continue
        value = project_settings.found_scalar(old, name)
        if value is None or (heading in settings and not isinstance(held, dict)):
            continue
        settings[heading] = {**(held or {}), leaf: copy.deepcopy(value)}
        made.moved.append({"key": name, "to": f"{heading}.{leaf}"})
        if name in made.unread:
            made.unread.remove(name)
    return settings


# --- the overlay ---------------------------------------------------------------------

_ABSENT = object()


def _strip(config):
    """A configuration as the merge and the classifier read it: the
    catalogues, without the document's `schema:`."""
    return {k: v for k, v in config.items() if k in spec.CATALOGUES}


def _convert(policy, guardrails, where):
    try:
        return _strip(legacy_adapter.adapt(policy, guardrails))
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise CompassError(f"cannot convert {where} to catalogue form: "
                           f"{type(exc).__name__}: {exc}") from exc


def _field_change(kind, before, after):
    """The value to write for a changed field. A map is written as
    `{set, remove}` so one changed key is one line of the overlay."""
    if kind == "map" and isinstance(before, dict) and isinstance(after, dict) \
            and before and after != before:
        out = {}
        changed = {k: v for k, v in after.items() if before.get(k, _ABSENT) != v}
        gone = [k for k in before if k not in after]
        if changed:
            out["set"] = copy.deepcopy(changed)
        if gone:
            out["remove"] = gone
        return out
    return copy.deepcopy(after)


def _sequence(rules):
    return [rule_id for rule_id, _ in sorted(rules.items(), key=lambda kv: kv[1].get("order", 0))]


def _by_sequence(before, after):
    """`after`, a rule set's rules, with each shared rule's `order` put back to
    the one in `before` when the two sets list their shared rules in the same
    sequence. `order` is only a position: removing a rule renumbers the rules
    after it and changes no relative order, and an overlay that listed each of
    them would hide the one real edit. Where the sequence did change, or the
    result would put two rules at one position, `after` stays as written so
    the rules that moved carry their own `order`."""
    shared = [r for r in _sequence(after) if r in before]
    if shared != [r for r in _sequence(before) if r in after]:
        return after
    kept = {rule_id: ({**rule, "order": before[rule_id].get("order")}
                      if rule_id in before and "order" in rule and "order" in before[rule_id]
                      else rule)
            for rule_id, rule in after.items()}
    positions = [rule.get("order") for rule in kept.values()]
    if len(set(positions)) != len(positions) or _sequence(kept) != _sequence(after):
        return after
    return kept


def _entry_change(catalogue, before, after):
    """`(operation, body)` that turns the entry `before` into `after`, or
    None when nothing the catalogue holds differs."""
    fields = spec.FIELDS[catalogue]
    if any(name in before and name not in after for name in fields):
        # A field cannot be unset, so the entry is swapped whole.
        return "replace", {"replace": True, **{n: copy.deepcopy(after[n])
                                               for n in fields if n in after}}
    after = dict(after)
    if catalogue == "rules" and isinstance(before.get("rules"), dict) \
            and isinstance(after.get("rules"), dict):
        after["rules"] = _by_sequence(before["rules"], after["rules"])
    changed = {n: _field_change(fields[n]["merge"], before.get(n), after[n])
               for n in fields if n in after and before.get(n, _ABSENT) != after[n]}
    return ("set", {"set": changed}) if changed else None


def overlay_between(base, legacy):
    """`(overlay, ops)`: the catalogue entries that turn the configuration
    `base` into `legacy`, and one record per entry in catalogue and id order."""
    overlay, ops = {}, []
    for catalogue in spec.CATALOGUES:
        before, after = base.get(catalogue) or {}, legacy.get(catalogue) or {}
        for entry_id in sorted(set(before) | set(after)):
            if entry_id not in after:
                change = ("remove", {"remove": True})
            elif entry_id not in before:
                change = ("add", {n: copy.deepcopy(after[entry_id][n])
                                  for n in spec.FIELDS[catalogue] if n in after[entry_id]})
            else:
                change = _entry_change(catalogue, before[entry_id], after[entry_id])
            if change:
                overlay.setdefault(catalogue, {})[entry_id] = change[1]
                ops.append({"catalogue": catalogue, "id": entry_id,
                            "operation": change[0], "waiver": None})
    return overlay, ops


# --- the base release ----------------------------------------------------------------

_RELEASE_CACHE = {}


def _release_files(release):
    if release["tag"] == shipped_releases.CURRENT:
        texts = shipped_releases.current_texts()
    else:
        texts = shipped_releases.texts(release["tag"])
    return tuple(yaml.safe_load(text) for text in texts)


def _release_config(release):
    """The catalogue form of a release's files, converted once."""
    key = (release["tag"], release["routing_policy"]["digest"],
           release["guardrails"]["digest"])
    if key not in _RELEASE_CACHE:
        policy, guardrails = _release_files(release)
        _RELEASE_CACHE[key] = _convert(policy, guardrails, f"release {release['tag']}")
    return _RELEASE_CACHE[key]


def choose_base(policy, guardrails, legacy):
    """`(release, chosen_by)` for a copy. The release whose `version:` lines
    match the copy's, else the one that gives the fewest overlay entries, and
    the newest of equals. A copy far from every release gets the files this
    install ships, `as-built`."""
    releases = shipped_releases.table() + [shipped_releases.current()]
    versions = (str(policy.get("version")), str(guardrails.get("version")))
    named = [r for r in releases
             if (r["routing_policy"]["version"], r["guardrails"]["version"]) == versions]
    if named:
        return named[-1], "version"
    scored = sorted(((len(overlay_between(_release_config(r), legacy)[1]), -index, r)
                     for index, r in enumerate(releases)), key=lambda t: t[:2])
    best = scored[0]
    if best[0] > FAR_ENTRIES:
        return releases[-1], "as-built"
    return best[2], "fewest-entries"


def _unexpressed(base_views, copy_views):
    """What only the legacy views hold, and the catalogue cannot state, that
    the copy changed from the base release: the stages a guardrail is checked
    at beyond the first (a gate keeps one `stage`)."""
    found = []
    for gate, stages in (copy_views.get("guardrails", {}).get("checked_at") or {}).items():
        was = (base_views.get("guardrails", {}).get("checked_at") or {}).get(gate) or []
        if list(stages[1:]) != list(was[1:]):
            first = stages[0] if stages else "none"
            found.append({"code": UNEXPRESSED, "path": f"gates.{gate}.checked_at",
                          "message": f"{gate} is checked at {', '.join(stages)}; compass.yml "
                                     f"keeps only the first stage ({first}), so the others "
                                     "cannot be written"})
    return found + _unexpressed_project(base_views, copy_views)


# What a project guardrail's gate and check can state. `params` belong to the
# `command-passes` check the guardrail becomes; `checked_at` is compared above.
PROJECT_FIELDS = ("id", "name", "statement", "checks", "applies_when", "checked_at")


def _unexpressed_project(base_views, copy_views):
    """A field of a project guardrail the copy added or changed that neither
    the gate nor the check it becomes can hold. It would be dropped while the
    report said "equivalent", so it blocks by name."""
    was = {g.get("id"): g for g in base_views.get("guardrails", {}).get("project") or []
           if isinstance(g, dict)}
    found = []
    for guardrail in copy_views.get("guardrails", {}).get("project") or []:
        if not isinstance(guardrail, dict) or "id" not in guardrail:
            continue
        for key, value in guardrail.items():
            kept = key in PROJECT_FIELDS or (
                key == "params" and "command-passes" in (guardrail.get("checks") or []))
            if not kept and was.get(guardrail["id"], {}).get(key) != value:
                found.append({"code": UNEXPRESSED, "path": f"project.{guardrail['id']}.{key}",
                              "message": f"project guardrail {guardrail['id']} sets {key}, "
                                         "which no gate or check in compass.yml can hold"})
    return found


# --- the plan ------------------------------------------------------------------------

_MAJOR = []


def _default_major():
    if not _MAJOR:
        _MAJOR.append(policy_lint.load_parent()[1]["version"].split(".")[0])
    return _MAJOR[0]


def _layer_document(overlay, settings=None):
    doc = {"schema": 1, "extends": layers.default_extends(_default_major())}
    doc.update(copy.deepcopy(settings or {}))
    doc.update(overlay)
    return doc


def _blocked_from(errors):
    return [{"code": code, "path": path, "message": message}
            for code, path, message in errors]


def _project_layer(doc):
    return layers.Layer("project", "project", doc, layers.layer_digest(doc, "project"))


def _needs_excuse(base_config, overlay, ops):
    """The ops whose entry, applied alone to the base release, loosens it or
    cannot be compared with it. Those are the ones a waiver must excuse."""
    needed = []
    for op in ops:
        entry = {op["catalogue"]: {op["id"]: overlay[op["catalogue"]][op["id"]]}}
        try:
            alone = merge.apply(base_config, entry, "project", "project")[0]
            refused = classify.classify(base_config, alone, early_exit=True).result \
                in waivers.REFUSED
        except CompassError:
            refused = True
        if refused:
            needed.append(op)
    return needed


def _stub():
    return {"reason": STUB_REASON, "approved_by": UNAPPROVED}


def _verdict(parent, child, **names):
    shown = classify.classify(parent, child, **names).to_json()
    return shown, {"result": shown["result"], "reason": shown["reason"],
                   "points": shown["grid"]["evaluated"], "scan": shown["scan"]}


def _derive(root, made, settings):
    """Fill `made` from the project's copied governance: the base release, the
    overlay, the waiver stubs, the classifier's verdicts and the lint errors.
    False when the overlay cannot be applied, so nothing more can be said."""
    directory = os.path.join(root, "governance")
    policy = load_yaml(os.path.join(directory, "routing-policy.yml"))
    guardrails = load_yaml(os.path.join(directory, "guardrails.yml"))
    legacy = _convert(policy, guardrails, "the copied governance")
    release, chosen_by = choose_base(policy, guardrails, legacy)
    base = _release_config(release)
    made.base_release = {"release": None if chosen_by == "as-built" else release["tag"],
                         "chosen_by": chosen_by}
    current = _release_config(shipped_releases.current())
    made.adopted = [{k: op[k] for k in ("catalogue", "id", "operation")}
                    for op in overlay_between(base, current)[1]]
    overlay, ops = overlay_between(base, legacy)
    made.ops = ops
    base_views = legacy_adapter.legacy_views(*_release_files(release))
    made.blocked += _unexpressed(base_views, legacy_adapter.legacy_views(policy, guardrails))
    parent, _meta = policy_lint.load_parent()
    parent_config = merge.resolve([parent])[0]
    try:
        migrated = merge.resolve([parent, _project_layer(_layer_document(overlay))])[0]
        faithful = merge.apply(base, overlay, "project", "project")[0]
    except merge.MergeError as exc:
        made.doc = _layer_document(overlay, settings)
        made.blocked += _blocked_from(exc.errors)
        return False
    try:
        if classify.classify(base, faithful, early_exit=True).result in waivers.REFUSED:
            for op in _needs_excuse(base, overlay, ops):
                overlay[op["catalogue"]][op["id"]]["waiver"] = _stub()
                op["waiver"] = UNAPPROVED
        made.doc = _layer_document(overlay, settings)
        shown, made.equivalence = _verdict(legacy, faithful, parent_name="copy",
                                           child_name="base plus overlay")
        _, made.behaviour = _verdict(legacy, migrated, parent_name="copy",
                                     child_name="migrated")
        counts = classify.classify(legacy, migrated).to_json()["counts"]
        made.behaviour["changed"] = counts["looser"] + counts["tighter"] + counts["mixed"]
        made.behaviour = {k: made.behaviour[k] for k in ("result", "reason", "points", "changed")}
    except CompassError as exc:
        made.doc = made.doc or _layer_document(overlay, settings)
        made.blocked.append({"code": UNCLASSIFIABLE, "path": "configuration",
                             "message": f"the classifier cannot compare the configurations: {exc}"})
        return True
    if made.equivalence["result"] != "equivalent":
        made.blocked.append({"code": NOT_EQUIVALENT, "path": "configuration",
                             "message": f"the base release plus the overlay is "
                                        f"{made.equivalence['result']} to the copy: "
                                        f"{made.equivalence['reason']}"})
    return True


class _NoAlias(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def render(doc):
    """The text of `compass.yml` for a document."""
    return HEADER + yaml.dump(doc, Dumper=_NoAlias, sort_keys=False,
                              default_flow_style=False, allow_unicode=True, width=100)


def _lint_errors(made):
    report = policy_lint.lint_chain(policy_lint.load_parent()[0], _project_layer(made.doc))
    return [{"code": f.code, "path": f.path, "message": f.message} for f in report.errors]


def _creates_state(root, made):
    """Whether this run makes the state file. A state file that is there is
    this command's own when an earlier run's marker says it made it."""
    if not made.state:
        return False
    if not _present(root, STATE_YML):
        return True
    marker = _marker(root)
    return bool(marker and marker.get("created_state") is True)


def _files(root, made):
    """What the command copies, writes, removes and keeps, in the order it
    does them."""
    if made.resumed:
        return [{"action": "remove", "path": OLD_CONFIG, "to": None}]
    files = [{"action": "copy", "path": rel, "to": f"{LEGACY_DIR}/{rel.rsplit('/', 1)[-1]}"}
             for rel in made.sources]
    files.append({"action": "write", "path": MIGRATION_YML, "to": None})
    if made.state:
        files.append({"action": "write" if _creates_state(root, made) else "keep",
                      "path": STATE_YML, "to": None})
    files.append({"action": "write", "path": COMPASS_YML, "to": None})
    if OLD_CONFIG in made.sources:
        files.append({"action": "remove", "path": OLD_CONFIG, "to": None})
    files += [{"action": "keep", "path": rel, "to": None}
              for rel in GOVERNANCE_FILES if rel in made.sources]
    return files


def plan(root):
    """The `Plan` for a project root. It reads files and writes none."""
    refusals(root)
    if _present(root, COMPASS_YML):
        made = Plan(result="ready", sources=[OLD_CONFIG], resumed=True)
        made.digests = {OLD_CONFIG: file_digest(_absolute(root, OLD_CONFIG))}
        made.files = _files(root, made)
        return made
    made = Plan(sources=[rel for rel in GOVERNANCE_FILES + (OLD_CONFIG,)
                         if _present(root, rel)])
    made.digests = {rel: file_digest(_absolute(root, rel)) for rel in made.sources}
    settings = _fold_settings(root, made)
    derived = True
    if all(_present(root, rel) for rel in GOVERNANCE_FILES):
        derived = _derive(root, made, settings)
    if made.sources:
        made.doc = made.doc or _layer_document({}, settings)
        if derived:
            made.blocked += _lint_errors(made)
        made.compass_yml = render(made.doc)
        made.result = "blocked" if made.blocked else "ready"
        made.files = _files(root, made)
    return made


# --- the writes ----------------------------------------------------------------------

STATE_HEADER = ("# Compass - state the CLI wrote. Do not edit. Settings go in compass.yml.\n"
                "# Moved here from the old settings file by compass policy migrate.\n")


def _tool_version():
    try:
        with open(os.path.join(FRAMEWORK_ROOT, "VERSION"), "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return "unknown"


def remove_old_config(root):
    """The last step. A stop before it leaves `compass.yml` and the old file
    together, which `pending_removal` recognises on the next run."""
    os.remove(_absolute(root, OLD_CONFIG))


def _read_exact(path):
    """A file's text with its line endings as they are on disk, so the copy
    has the bytes the recorded digest was taken from."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8")


def apply(root, made):
    """Write what `made` planned, in the order that keeps the project in
    either the whole old state or the whole new state: `compass.yml` is the
    commit point. The marker comes before the state file, so a run that stops
    between them is still known to have made it."""
    if made.resumed:
        remove_old_config(root)
        return
    os.makedirs(_absolute(root, LEGACY_DIR), exist_ok=True)
    for rel in made.sources:
        atomic_write_text(_absolute(root, f"{LEGACY_DIR}/{rel.rsplit('/', 1)[-1]}"),
                          _read_exact(_absolute(root, rel)))
    creates_state = _creates_state(root, made)
    atomic_write_text(_absolute(root, MIGRATION_YML), yaml.dump(
        {"schema": 1, "tool": _tool_version(), "sources": dict(made.digests),
         "created_state": creates_state},
        Dumper=_NoAlias, sort_keys=False, default_flow_style=False))
    if creates_state:
        atomic_write_text(_absolute(root, STATE_YML), STATE_HEADER + yaml.dump(
            made.state, Dumper=_NoAlias, sort_keys=False, default_flow_style=False))
    atomic_write_text(_absolute(root, COMPASS_YML), made.compass_yml)
    if OLD_CONFIG in made.sources:
        remove_old_config(root)


# --- the report ----------------------------------------------------------------------

JSON_SCHEMA_VERSION = 1
OPERATIONS = ("add", "set", "replace", "remove")

# The readers resolve the effective view: compass.yml over the shipped default
# for an issue with no generation, the stored generation for one that has it.
NOT_IN_FORCE = ("Note: compass.yml becomes the project's configuration: an issue with no "
                "stored generation is judged by it at once, and an issue with a generation "
                "keeps that generation until its next reassess. The governance copies stay "
                "in place as the record of what the project ran.")


def report_json(made, mode):
    """The document `--json` prints. Keys are in a fixed order and nothing in
    it depends on the time or on a path outside the project."""
    counts = {name: sum(1 for o in made.ops if o["operation"] == name) for name in OPERATIONS}
    return {
        "schema": JSON_SCHEMA_VERSION,
        "mode": mode,
        "result": made.result,
        "base_release": made.base_release,
        "sources": [{"path": rel, "digest": made.digests.get(rel)} for rel in made.sources],
        "adopted": made.adopted,
        "overlay": {"counts": counts,
                    "entries": [{"catalogue": o["catalogue"], "id": o["id"],
                                 "operation": o["operation"], "waiver": o["waiver"]}
                                for o in made.ops]},
        "settings": {"moved": made.moved, "state": list(made.state),
                     "dropped": made.dropped, "unread": made.unread},
        "equivalence": made.equivalence,
        "behaviour": made.behaviour,
        "blocked_by": made.blocked,
        "files": made.files,
        "compass_yml": made.compass_yml or None,
    }


def _heading(made, mode):
    if made.result == "nothing-to-migrate":
        return ("compass policy migrate: nothing to migrate - no copied governance "
                "and no old settings file")
    if made.result == "blocked":
        return "compass policy migrate: BLOCKED - nothing was written"
    if made.result == "applied":
        return "compass policy migrate: applied"
    return "compass policy migrate: dry run - nothing was written"


_CHOSEN = {"version": "chosen by the version lines",
           "fewest-entries": "the nearest by overlay size: the version lines match no release"}


def _base_lines(made):
    base = made.base_release
    if base is None:
        return []
    if base["release"] is None:
        return ["  base release: none - the copy matched no shipped release, so every "
                "difference from the files this install ships is a local edit and each "
                "removal needs approval"]
    lines = [f"  base release: {base['release']} ({_CHOSEN[base['chosen_by']]})"]
    if made.adopted:
        lines.append(f"  adopted from the current default, with no waiver ({len(made.adopted)} "
                     "entries; an entry you also edited keeps your edit):")
        lines += [f"    {a['operation']:<8}{a['catalogue']}.{a['id']}" for a in made.adopted]
    else:
        lines.append("  adopted from the current default: nothing")
    if made.behaviour:
        lines.append(f"  behaviour: against the copy the migrated project is "
                     f"{made.behaviour['result']} ({made.behaviour['changed']} of "
                     f"{made.behaviour['points']} points differ)")
    return lines


def report_text(made, mode):
    lines = [_heading(made, mode)]
    if made.result == "nothing-to-migrate":
        return lines
    lines.append("  read: " + ", ".join(made.sources))
    if made.resumed:
        lines.append("  an earlier run wrote compass.yml and stopped before it removed "
                     "the old settings file; the recorded digest still matches it")
    else:
        lines += _base_lines(made)
        if made.ops:
            lines.append(f"  overlay: {len(made.ops)} entries")
            lines += [f"    {o['operation']:<8}{o['catalogue']}.{o['id']}"
                      + (" (waiver stub, UNAPPROVED)" if o["waiver"] else "")
                      for o in made.ops]
        else:
            lines.append("  overlay: none - the copy has no local edit")
        if made.moved:
            lines.append("  settings moved: " + ", ".join(
                m["key"] if m["key"] == m["to"] else f"{m['key']} -> {m['to']}"
                for m in made.moved))
        if made.state:
            lines.append("  state moved to the state file in .compass: " + ", ".join(made.state))
        for item in made.dropped:
            lines.append(f"  dropped: {item['key']} ({item['reason']})")
        if made.unread:
            lines.append("  not copied (no code reads them; they stay in the copy of the "
                         "old file in .compass/legacy): " + ", ".join(made.unread))
        if made.equivalence:
            lines.append(f"  equivalence: base release plus overlay is "
                         f"{made.equivalence['result']} to the copy "
                         f"({made.equivalence['points']} points) - {made.equivalence['reason']}")
    for item in made.blocked:
        lines.append(f"  blocked: {item['code']} {item['path']}: {item['message']}")
    lines.append("  files:")
    for item in made.files:
        target = f" -> {item['to']}" if item["to"] else ""
        lines.append(f"    {item['action']:<8}{item['path']}{target}")
    lines.append("  " + NOT_IN_FORCE)
    if made.result == "ready" and made.compass_yml:
        lines += ["  compass.yml would be:"]
        lines += ["    " + text for text in made.compass_yml.splitlines()]
    elif made.result == "blocked":
        lines += ["  compass.yml as migrated:"] + [
            "    " + text for text in made.compass_yml.splitlines()]
    if made.result == "ready":
        lines.append("Run with --apply to make these changes.")
    elif made.result == "blocked":
        lines.append("Fix what is blocked. A waiver stub needs an `owner` in compass.yml and "
                     "an approved_by and approved_on from someone it allows.")
    return lines
