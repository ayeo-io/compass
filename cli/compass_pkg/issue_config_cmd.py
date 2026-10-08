# compass_pkg.issue_config_cmd - `compass issue configure` and the reassess plan
"""Propose a change to an issue's own configuration layer, see what it would
do, and apply or discard it.

`compass issue configure` never touches the manifest. It parks the proposed
`config:` in `generations/<n+1>/proposed.yml` and prints a preview
(`config_preview`). The change takes effect when a reassess commits it:
`approach evaluate --write` asks `reassess_plan` for the proposal, the waiver
re-check and the flags (`--reset-config`, `--commit`) before it prints
anything, then commits in the order the generation store fixes.

`--discard [N]` removes a proposal or a leftover folder above the generation
in force. `--commit [N]` adopts a complete leftover folder: it runs the
reassess with the folder named, and the commit adopts it only if a fresh
resolution gives the same four files.
"""
# DEPENDENCY: standard library (copy, json, os, types); compass_pkg.atomic_io,
# catalogue_spec, config_preview, core, effective, layers, terminal.
from __future__ import annotations

import copy
import json
import os
import types
from dataclasses import dataclass, field

from compass_pkg import catalogue_spec as spec
from compass_pkg import config_preview, effective, layers
from compass_pkg.atomic_io import StrictYamlError, load_yaml_strict
from compass_pkg.core import CompassError, load_manifest, resolve_issue_dir
from compass_pkg.terminal import mark_handled, resolve_mode

FIX = effective.FIX_ZERO
GIVE_A_CHANGE = ("give a change: --from-file PATH, --mode STAGE=MODE, --route NAME, "
                 "--autonomy VALUE or --ceiling NAME=N (or --discard, or --commit)")


# --- the overlay a call builds ---------------------------------------------------------------

def _pair(text, flag, number=False):
    name, sep, value = str(text).partition("=")
    if not (sep and name.strip() and value.strip()):
        raise CompassError(f"{flag} expects NAME=VALUE, found '{text}'")
    if number:
        try:
            value = int(value)
        except ValueError:
            raise CompassError(f"{flag} {text}: '{value}' is not a whole number") from None
        if value < 1:
            raise CompassError(f"{flag} {text}: a ceiling is a whole number of at least 1")
    return name.strip(), (value if number else value.strip())


def _mapping(parent, key, what):
    held = parent.setdefault(key, {})
    if not isinstance(held, dict):
        raise CompassError(f"the proposed config: holds {what} that is not a mapping")
    return held


def _from_file(path):
    try:
        doc = load_yaml_strict(path)
    except (OSError, StrictYamlError) as exc:
        raise CompassError(f"--from-file {path}: {exc}") from None
    if not isinstance(doc, dict):
        raise CompassError(f"--from-file {path}: an overlay is a mapping of layer keys, "
                           f"found {type(doc).__name__}")
    return doc


def build_overlay(base, args):
    """The overlay for the call: `base` (the pending proposal's overlay, else
    the manifest's `config:`), or the file's whole mapping when `--from-file`
    is given, then each flag applied on top."""
    overlay = _from_file(args.from_file) if args.from_file else copy.deepcopy(base)
    for pair in args.mode or ():
        stage, mode = _pair(pair, "--mode")
        entry = _mapping(_mapping(overlay, "stages", "stages"), stage, f"stages.{stage}")
        _mapping(entry, "set", f"stages.{stage}.set")["mode"] = mode
    if args.route:
        overlay["approach"] = args.route
    if args.autonomy:
        if args.autonomy not in spec.AUTONOMY:
            raise CompassError(f"--autonomy {args.autonomy}: it must be one of "
                               f"{', '.join(spec.AUTONOMY)}")
        overlay["autonomy"] = args.autonomy
    for pair in args.ceiling or ():
        name, limit = _pair(pair, "--ceiling", number=True)
        _mapping(overlay, "ceilings", "ceilings")[name] = limit
    return overlay


# --- the preview ---------------------------------------------------------------------------------

def _show(value, limit=64):
    text = json.dumps(value, sort_keys=True)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def render_text(doc):
    lines = [f"compass issue configure: {doc['issue']} (generation {doc['generation']}, "
             f"proposed {doc['proposed']})",
             f"  verdict          : {doc['verdict']}"]
    for reason in doc["reasons"]:
        lines.append(f"    - {reason}")
    if doc["verdict"] == "refused":
        lines.append("    the proposal is written; a reassess refuses it until the "
                     "reasons are fixed")
    lines.append(f"  proposal         : {doc['proposal']}")
    lines.append("  builds on     : " + ("the pending proposal" if doc["base"] == "pending proposal"
                                        else "the manifest's config:"))
    changes = doc["changes"]
    lines.append(f"  resolved fields that change ({len(changes)})" + (":" if changes else ""))
    for change in changes:
        lines.append(f"    {change['path']}: {_show(change['before'])} -> "
                     f"{_show(change['after'])}")
    klass = doc["classification"]
    lines.append(f"  classification   : {klass['result']} - {klass['reason']}")
    point = klass["first_point"]
    if point:
        lines.append(f"    first point: {point['summary']}")
    owed = doc["assessment"]
    approach = owed["approach"]
    lines.append(f"  at this issue's assessment: {owed['result']} (approach "
                 f"{approach['before'] or 'unknown'} -> {approach['after'] or 'unknown'})")
    for change in owed["changes"]:
        key = f" ({change['key']})" if change["key"] is not None else ""
        lines.append(f"    {change['field']}{key}: {_show(change['before'])} -> "
                     f"{_show(change['after'])} [{change['outcome']}]")
    if owed["refused"]:
        lines.append(f"    the evaluator refuses: {owed['refused']['after']}")
    invalid = doc["invalidates"]
    lines.append(f"  records invalidated on reassess ({len(invalid)})"
                 + (":" if invalid else ""))
    for record in invalid:
        lines.append(f"    {record['id']} ({record['kind']}): {record['reason']}")
    if invalid:
        lines.append("    the files stay on disk; only their status in records.yml changes")
    lines.append(f"  next: {doc['next']}")
    return lines


def _emit(args, doc):
    mark_handled()
    mode = resolve_mode(args)
    if mode == "json":
        print(json.dumps(doc, indent=2))
    elif mode == "quiet":
        print(f"{doc['verdict']}: {doc['proposal']}")
    else:
        print("\n".join(render_text(doc)))


# --- the verb --------------------------------------------------------------------------------------

def _number(text, flag):
    if text in (None, "next"):
        return None
    try:
        return int(text)
    except ValueError:
        raise CompassError(f"{flag} {text}: a generation number is a whole number") from None


def _changes_given(args):
    return bool(args.from_file or args.mode or args.route or args.autonomy or args.ceiling)


def _discard(args, task_dir, slug):
    found = effective.discard(task_dir, _number(args.discard, "--discard"))
    print(f"compass issue configure: discarded generation {found.number} ({found.state}) "
          f"of {slug}; the manifest and the generation in force are as they were")
    return 0


def _commit(args, task_dir, slug):
    from compass_pkg import routing
    manifest, _ = load_manifest(task_dir)
    held = effective.generation_number(manifest) or 0
    wanted = _number(args.commit, "--commit")
    target = held + 1 if wanted is None else wanted

    def reassess(reset):
        return routing.cmd_route_evaluate(types.SimpleNamespace(
            reading=None, task=slug, write=True, reason=args.reason, kind=None, _mode=None,
            evidence_out=None, json=False, reset_config=reset, adopt=target))
    try:
        return reassess(False)
    except CompassError as first:
        # An interrupted `--reset-config` leaves no record of the flag, but the
        # folder it left records that the issue had no overlay. Try that reading.
        if not (manifest.get("config")
                and effective.leftover_overlay_digest(task_dir, target) is None):
            raise
        try:
            return reassess(True)
        except CompassError:
            raise first from None


def run_configure(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    slug = os.path.basename(os.path.normpath(task_dir))
    if args.discard is not None and args.commit is not None:
        raise CompassError("--discard and --commit are two ways to resolve a leftover "
                           "folder; give one")
    if (args.discard is not None or args.commit is not None) and _changes_given(args):
        raise CompassError("--discard and --commit take no change; propose the change in "
                           "a separate call")
    if (args.discard is not None or args.commit is not None) and resolve_mode(args) == "json":
        raise CompassError("--json is the preview's form; --discard and --commit print "
                           "text")
    if args.discard is not None:
        return _discard(args, task_dir, slug)
    if args.commit is not None:
        return _commit(args, task_dir, slug)
    if not _changes_given(args):
        raise CompassError(GIVE_A_CHANGE)
    manifest, _ = load_manifest(task_dir)
    held = effective.generation_number(manifest)
    if not held:
        raise CompassError(f"issue {slug} has no stored configuration to change yet; "
                           f"run `{FIX} --issue {slug}` first")
    if manifest.get("status") == "landed":
        raise CompassError(f"issue {slug} is landed and keeps the configuration it landed "
                           f"under; it cannot be given a proposal")
    pending = effective.pending_proposal(task_dir, manifest)
    live = (pending is not None and pending.base_generation == held
            and pending.base_config_digest == effective.config_digest(manifest))
    base = pending.overlay if live else manifest.get("config") or {}
    overlay = build_overlay(base, args)
    root = layers.find_project_root(task_dir)
    doc = config_preview.build(root, task_dir, manifest, overlay, slug,
                               base="pending proposal" if live and not args.from_file
                               else "config")
    effective.write_proposal(task_dir, manifest, overlay)
    _emit(args, doc)
    return 0 if doc["verdict"] == "accepted" else 1


# --- the reassess plan -------------------------------------------------------------------------------

@dataclass
class Plan:
    """What `approach evaluate --write` does beyond what it did before: the
    resolution to store (with stale waivers left out), the records that makes
    invalid, the proposal it applies, the generation folder to adopt
    and the lines to print after the commit."""
    resolution: object
    invalidated: dict
    resolve_with: dict
    proposal: object = None
    adopt: object = None
    notes: list = field(default_factory=list)
    config_digests: tuple = (None, None)

    @property
    def config_changed(self):
        """True when the reassess changes the manifest's `config:` layer."""
        return self.config_digests[0] != self.config_digests[1]


def _stale(proposal, held, manifest):
    if proposal.base_generation != held:
        return (f"it was built on generation {proposal.base_generation} and the issue is "
                f"at generation {held}")
    if proposal.base_config_digest != effective.config_digest(manifest):
        return "the manifest's config: has changed since it was written"
    return None


def _check_adoptable(task_dir, slug, held, adopt):
    """Refuse, before anything prints, a folder `--commit` cannot adopt."""
    nxt = (held or 0) + 1
    if adopt != nxt:
        raise CompassError(
            f"{slug} is at {'generation ' + str(held) if held is not None else 'no generation'}"
            f", so the generation to adopt is {nxt}, not {adopt}; nothing was written")
    found = effective.leftover(task_dir, adopt)
    if found is None:
        raise CompassError(f"nothing to adopt: {slug} has no folder for generation {adopt}")
    if found.state == "proposal":
        raise CompassError(
            f"generation {adopt} of {slug} holds only a proposal, not a generation. Apply "
            f"it with `compass approach evaluate --write --reason \"...\"`")
    if found.state != "complete-unreferenced":
        raise CompassError(
            f"generation {adopt} of {slug} is {found.state} ({found.detail}) and cannot be "
            f"adopted. Nothing was written. Run `compass issue configure --discard {adopt}` "
            f"to remove it, or `compass approach evaluate --write` to write it again")


def reassess_plan(manifest, task_dir, args):
    """Apply what a reassess carries to `manifest` (the manifest mapping, changed in
    place) and return the `Plan`. Raises `CompassError` before anything prints
    or writes: a stale proposal, `--reset-config` while one is pending, a
    project that does not resolve."""
    slug = os.path.basename(os.path.normpath(task_dir))
    held = effective.generation_number(manifest)
    adopt = getattr(args, "adopt", None)
    reset = bool(getattr(args, "reset_config", False))
    if adopt is not None:
        _check_adoptable(task_dir, slug, held, adopt)
    proposal = effective.pending_proposal(task_dir, manifest) if held else None
    notes = []
    if reset and proposal:
        raise CompassError(
            f"--reset-config cannot run while a change is proposed for {slug} (generation "
            f"{proposal.number}). Run `compass issue configure --discard` to drop the "
            f"proposal, or reassess without --reset-config to apply it; nothing was written")
    if proposal:
        why = _stale(proposal, held, manifest)
        if why:
            raise CompassError(
                f"the proposal in generation {proposal.number} of {slug} is stale: {why}. "
                f"Nothing was written. Run `compass issue configure --discard`, then "
                f"propose the change again")
        if proposal.overlay:
            manifest["config"] = copy.deepcopy(proposal.overlay)
        else:
            manifest.pop("config", None)
        notes.append(f"applied the proposed configuration of generation {proposal.number}")
    elif reset:
        had = manifest.pop("config", None)
        notes.append("dropped the issue's config: layer" if had else
                     "the issue had no config: layer to drop")
    root = layers.find_project_root(task_dir)
    resolution, invalidated, resolve_with = config_preview.plan_resolution(
        root, task_dir, manifest, slug)
    # What the commit would refuse later is refused now, before anything prints.
    stored = effective.stored_documents(task_dir, manifest)
    effective.preflight(task_dir, resolution, manifest, invalidated, adopt, stored=stored)
    # The layer changes when the overlay this resolves from differs from the one
    # the generation in force recorded. A first commit changes nothing: there is
    # no earlier layer.
    now = resolution.versions.get("issue_overlay_digest")
    was = stored["versions"].get("issue_overlay_digest") if stored else now
    for record_id, reason in sorted(invalidated.items()):
        notes.append(f"invalidated {record_id}: {reason}"
                     + (f". {effective.ways_out(reason)}"
                        if record_id.startswith("waiver:") else ""))
    return Plan(resolution, invalidated, resolve_with, proposal=proposal, adopt=adopt,
                notes=notes, config_digests=(was, now))


def register(issue_subs, issue_arg):
    """Add `configure` to the `compass issue` group."""
    p = issue_subs.add_parser(
        "configure", help="propose, preview, discard or recover a change to an issue's "
                          "own configuration")
    issue_arg(p)
    p.add_argument("--from-file", dest="from_file", metavar="PATH",
                   help="replace the proposed overlay with this YAML mapping")
    p.add_argument("--mode", action="append", metavar="STAGE=MODE",
                   help="set a stage's mode in the overlay (repeatable)")
    p.add_argument("--route", metavar="NAME",
                   help="name the delivery approach the issue asks for")
    p.add_argument("--autonomy", metavar="VALUE",
                   help="set the issue's autonomy: " + ", ".join(spec.AUTONOMY))
    p.add_argument("--ceiling", action="append", metavar="NAME=N",
                   help="set a ceiling, a whole number of at least 1 (repeatable)")
    p.add_argument("--discard", nargs="?", const="next", metavar="N",
                   help="remove the proposal or leftover folder above the generation in "
                        "force (the one, or N)")
    p.add_argument("--commit", nargs="?", const="next", metavar="N",
                   help="adopt the complete leftover folder N (default: the next one)")
    p.add_argument("--reason", help="with --commit: the reason a reassess records")
    p.set_defaults(func=run_configure, output_kind="report")
