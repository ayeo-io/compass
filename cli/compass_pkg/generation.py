# compass_pkg.generation - the generation store: a stored copy of an issue's configuration
"""The numbered, stored copy of the configuration an issue runs against
(ADR-036).

A generation is a folder, `.compass/work/<slug>/generations/<n>/`, holding:

- `resolved.yml`, `provenance.yml`, `versions.yml`, `records.yml`: the
  configuration and what it was resolved from, fixed at commit;
- `complete`: a marker written after them, holding a digest of each;
- `results.yml`: the latest check verdicts, rewritten after each run and not
  covered by the marker;
- `proposed.yml`: a pending change to the issue's `config:` layer, written by
  `compass issue configure` and consumed by the reassess that applies it.

This module owns those files, the order a commit writes them in, and the
states a folder can be in. It does not resolve configuration: `effective`
hands it a `Resolution`, and it stores that.

The manifest's `generation: n` names the generation in force. Absent means
the issue predates 6.0.0 and reads live governance. `0` means the issue was
assessed under 6.x and has no generation yet.

A commit takes an exclusive lock on the issue, then writes in a fixed order:
the four files, the marker, then the manifest. The manifest replace is the
commit point: a crash before it leaves the manifest naming the generation
that was whole. This module never adopts a leftover folder on its own.
"""
# DEPENDENCY: standard library (dataclasses, datetime, os, shutil);
# PyYAML (bundled); compass_pkg.atomic_io, compass_pkg.core (CompassError,
# load_yaml and manifest_path, only).
from __future__ import annotations

import datetime
import os
import shutil
from dataclasses import dataclass, field

import yaml

from compass_pkg.atomic_io import (StrictYamlError, atomic_write_text, digest,
                                   load_yaml_strict, locked)
from compass_pkg.core import CompassError, load_yaml, manifest_path

FIX_ZERO = "compass approach evaluate --write"
SCHEMA = 1
RESOLVER_VERSION = "1.0.0"

FILES = ("resolved.yml", "provenance.yml", "versions.yml", "records.yml")
MARKER = "complete"
RESULTS = "results.yml"
PROPOSED = "proposed.yml"
LOCK = ".generation.lock"
DIRECTORY = "generations"

# The manifest fields a reassess computes. A commit whose configuration and
# overlay are unchanged is still a new generation when one of these moved.
OUTCOME_KEYS = ("delivery_approach", "stages", "gates", "checkpoints",
                "policy_rules_fired", "subtask_ceiling", "artifacts")

STATES = ("current", "superseded", "proposal", "incomplete",
          "complete-unreferenced", "broken")


@dataclass
class Resolution:
    """What a commit stores, as the four documents' bodies. `effective`
    builds it from the layers; this module adds the header keys (`schema`,
    `issue`, `generation`) and writes the files. `resolved` holds the merged
    catalogues and the capability switches, `provenance` the layer and
    operation behind each field and the waivers, `versions` what the result
    was resolved with, and `records` the status of each approval, waiver and
    evidence record at commit."""
    resolved: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    versions: dict = field(default_factory=dict)
    records: list = field(default_factory=list)
    # Raises `CompassError` when the chain must not be stored. `commit` calls
    # it just before the first write, so a commit that changes nothing never
    # pays for it.
    validate: object = field(default=None, repr=False, compare=False)
    # Adds the parts of `versions` that cost a scan, such as the stored
    # classification of a git parent. `commit` calls it with `versions` after
    # the "no change" decision, so a commit that writes nothing never pays.
    finish: object = field(default=None, repr=False, compare=False)
    # What a preview reads and a commit ignores: the loaded layers, the chain
    # and the configuration after each layer.
    details: object = field(default=None, repr=False, compare=False)


@dataclass
class Committed:
    """The result of `commit`: the generation now in force, whether this call
    wrote it, and one line for the person."""
    number: int
    committed: bool
    message: str


@dataclass
class GenState:
    number: int
    state: str
    detail: str = ""


def _after_step(step):
    """Called after each write of a commit: `resolved`, `provenance`,
    `versions`, `records`, `marker`, `manifest` and, when a proposal is
    consumed, `proposal`. A test replaces it to interrupt the commit at that
    step. Product code has no switch for it."""


def number(manifest):
    """The generation a manifest names: an integer, or None when it has no
    `generation:` key. A value that is not a whole number of at least 0 is
    refused, not read as absent."""
    if "generation" not in manifest:
        return None
    value = manifest["generation"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CompassError(f"manifest generation: {value!r} is not a whole number of "
                           f"at least 0")
    return value


def gen_dir(task_dir, n):
    return os.path.join(os.fspath(task_dir), DIRECTORY, str(n))


def _dump(document):
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- reading and checking ----------------------------------------------------------------

def _read_whole(task_dir, n):
    """`(documents, "")` when generation n has its marker and every file
    matches the digest the marker holds, otherwise `(None, reason)`. Each file
    is parsed once."""
    folder = gen_dir(task_dir, n)
    if not os.path.isdir(folder):
        return None, "its folder is missing"
    marker = os.path.join(folder, MARKER)
    if not os.path.isfile(marker):
        return None, "its complete marker is missing"
    documents = {}
    try:
        held = (load_yaml_strict(marker).get("files") or {})
        for name in FILES:
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                return None, f"{name} is missing"
            documents[name[:-4]] = load_yaml_strict(path)
            if held.get(name) != digest(documents[name[:-4]]):
                return None, f"{name} does not match the digest in its marker"
    except (StrictYamlError, AttributeError, TypeError) as exc:
        return None, f"it cannot be read: {exc}"
    return documents, ""


def is_whole(task_dir, n):
    """`(True, "")` when generation n has its marker and every file matches
    the digest the marker holds, otherwise `(False, reason)`."""
    documents, reason = _read_whole(task_dir, n)
    return documents is not None, reason


def load(task_dir, n):
    """The four documents of generation n, by file stem. A generation that
    does not pass `is_whole` is broken and raises `CompassError`."""
    documents, reason = _read_whole(task_dir, n)
    if documents is None:
        raise CompassError(
            f"generation {n} of {os.path.basename(os.path.normpath(task_dir))} is "
            f"broken: {reason} ({gen_dir(task_dir, n)}). Restore the folder from "
            f"version control, or remove the folder and the `generation:` line of "
            f"manifest.yml and run `compass approach evaluate --write` to store a new "
            f"generation")
    return documents


def read_results(task_dir, n):
    """`results.yml` of generation n, or None when no check has run."""
    path = os.path.join(gen_dir(task_dir, n), RESULTS)
    return load_yaml_strict(path) if os.path.isfile(path) else None


def write_results(task_dir, n, runs):
    """Replace `results.yml` of generation n. It is not covered by the
    marker, so writing it never makes the generation look broken."""
    atomic_write_text(os.path.join(gen_dir(task_dir, n), RESULTS),
                      _dump({"schema": SCHEMA, "generation": n, "runs": runs}))


def _numbers(task_dir):
    folder = os.path.join(os.fspath(task_dir), DIRECTORY)
    if not os.path.isdir(folder):
        return []
    return sorted(int(name) for name in os.listdir(folder)
                  if name.isascii() and name.isdigit() and os.path.isdir(os.path.join(folder, name)))


def states(task_dir, manifest=None):
    """A `GenState` for every folder under `generations/`, and one `broken`
    for the number the manifest names when its folder is not there."""
    task_dir = os.fspath(task_dir)
    if manifest is None:
        manifest = load_yaml(manifest_path(task_dir))
    current = number(manifest) or 0
    found = []
    held = _numbers(task_dir)
    if current and current not in held:
        found.append(GenState(current, "broken", "its folder is missing"))
    for n in held:
        folder = gen_dir(task_dir, n)
        names = set(os.listdir(folder))
        marked = MARKER in names
        if n == current:
            ok, reason = is_whole(task_dir, n)
            found.append(GenState(n, "current" if ok else "broken", reason))
        elif n < current:
            found.append(GenState(n, "superseded" if marked else "incomplete",
                                  "" if marked else "its complete marker is missing"))
        elif names == {PROPOSED}:
            found.append(GenState(n, "proposal", "a change is proposed"))
        elif marked and is_whole(task_dir, n)[0]:
            found.append(GenState(n, "complete-unreferenced",
                                  "complete, but the manifest does not name it"))
        else:
            found.append(GenState(n, "incomplete",
                                  is_whole(task_dir, n)[1] if marked else
                                  "some files and no complete marker"))
    return sorted(found, key=lambda g: g.number)


# --- the proposal and the leftovers --------------------------------------------------------

@dataclass
class Proposal:
    """A pending change to the issue's `config:` layer, parked in
    `generations/<n+1>/proposed.yml`. `base_config_digest` is the digest of
    the manifest's `config:` (an empty mapping when it has none) when the
    proposal was written; a reassess applies the proposal only while the
    manifest's `config:` still has that digest."""
    number: int
    base_generation: int
    base_config_digest: str
    overlay: dict


def config_digest(manifest):
    """The digest a proposal records for the `config:` it was built on."""
    return digest(manifest.get("config") or {})


def read_proposal(task_dir, n):
    """The proposal in generation folder n, or None when there is none. A
    `proposed.yml` that cannot be read, or lacks a key, is refused with the
    command that removes it; it is never trusted."""
    path = os.path.join(gen_dir(task_dir, n), PROPOSED)
    if not os.path.isfile(path):
        return None
    advice = f"Run `compass issue configure --discard {n}` to remove it."
    try:
        doc = load_yaml_strict(path)
    except StrictYamlError as exc:
        raise CompassError(f"{path} cannot be read as a proposal: {exc}. {advice}")
    ok = (isinstance(doc, dict) and doc.get("schema") == SCHEMA
          and isinstance(doc.get("overlay"), dict)
          and isinstance(doc.get("base_generation"), int)
          and not isinstance(doc.get("base_generation"), bool)
          and isinstance(doc.get("base_config_digest"), str))
    if not ok:
        raise CompassError(f"{path} is not a proposal this version wrote (it needs "
                           f"schema, base_generation, base_config_digest and an overlay "
                           f"mapping). {advice}")
    return Proposal(n, doc["base_generation"], doc["base_config_digest"], doc["overlay"])


def pending_proposal(task_dir, manifest):
    """The proposal waiting above the generation the manifest names, or None."""
    held = number(manifest)
    return read_proposal(task_dir, held + 1) if held else None


def _leftover_advice(task_dir, target):
    found = {g.number: g for g in states(task_dir)}.get(target)
    if found is None or found.state == "proposal":
        return ""
    if found.state == "complete-unreferenced":
        return (f"holds a complete generation {target} that the manifest does not name. "
                f"Run `compass issue configure --commit {target}` to adopt it or "
                f"`compass issue configure --discard {target}` to remove it")
    return (f"holds an {found.state} generation {target} ({found.detail}). Run `compass "
            f"issue configure --discard {target}` to remove it")


def write_proposal(task_dir, manifest, overlay):
    """Park `overlay` as the pending change to the issue's `config:`, in the
    folder above the generation in force, and return the `Proposal`. The
    manifest is not touched. Refuses a landed issue, a folder holding anything
    but a proposal, and a link anywhere in the way; under the issue's lock, so
    it cannot meet a commit half way."""
    task_dir = os.fspath(task_dir)
    held = number(manifest)
    if not held:
        raise CompassError(
            f"issue {os.path.basename(os.path.normpath(task_dir))} has no stored "
            f"configuration to change yet; run `{FIX_ZERO} --issue "
            f"{os.path.basename(os.path.normpath(task_dir))}` first")
    target = held + 1
    with locked(os.path.join(task_dir, LOCK)):
        disk = load_yaml(manifest_path(task_dir))
        if number(disk) != held:
            raise CompassError(f"{manifest_path(task_dir)} changed since it was read (it "
                               f"now names {_named(number(disk))}); run the command again")
        if disk.get("status") == "landed":
            raise CompassError(
                f"issue {os.path.basename(os.path.normpath(task_dir))} is landed and keeps "
                f"the configuration it landed under; it cannot be given a proposal")
        _refuse_links(task_dir, target)
        folder = gen_dir(task_dir, target)
        if os.path.isdir(folder):
            others = sorted(set(os.listdir(folder)) - {PROPOSED})
            if others:
                raise CompassError(f"{folder} {_leftover_advice(task_dir, target)}")
            read_proposal(task_dir, target)       # a proposal we cannot read is refused
        else:
            os.makedirs(folder)
        slug = os.path.basename(os.path.normpath(task_dir))
        proposal = Proposal(target, held, config_digest(disk), overlay)
        atomic_write_text(os.path.join(folder, PROPOSED), _dump({
            "schema": SCHEMA, "issue": slug, "base_generation": held,
            "base_config_digest": proposal.base_config_digest, "overlay": overlay}))
    return proposal


def discard(task_dir, n=None):
    """Remove a proposal or a leftover folder above the generation in force,
    and return its `GenState`. With no number, the one folder there is. The
    generation in force and every older one are never removed. Refuses a link
    instead of following it."""
    task_dir = os.fspath(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    with locked(os.path.join(task_dir, LOCK)):
        manifest = load_yaml(manifest_path(task_dir))
        current = number(manifest) or 0
        above = {g.number: g for g in states(task_dir, manifest) if g.number > current}
        if n is None:
            if not above:
                raise CompassError(f"nothing to discard: {slug} has no proposal or "
                                   f"leftover folder above generation {current}")
            if len(above) > 1:
                raise CompassError(
                    f"{slug} has leftover folders {', '.join(map(str, above))}; name the "
                    f"one to remove, as in `compass issue configure --discard "
                    f"{min(above)}`")
            n = next(iter(above))
        elif n <= current:
            which = "the generation in force" if n == current else "older than the one in force"
            raise CompassError(
                f"generation {n} is {which} (generation {current}); only a proposal or "
                f"a leftover above it can be discarded, so nothing was removed")
        elif n not in above:
            raise CompassError(f"nothing to discard: {slug} has no folder for generation {n}")
        _refuse_links(task_dir, n)
        shutil.rmtree(gen_dir(task_dir, n))
    return above[n]


# --- the commit ---------------------------------------------------------------------------

def _outcome(manifest):
    return {k: manifest.get(k) for k in OUTCOME_KEYS}


def _kind(record_id):
    prefix = str(record_id).split(":", 1)[0]
    return {"result": "check-result", "waiver": "waiver"}.get(prefix, "approval")


def _records(fresh, previous, invalidated):
    """The records of the new generation: the fresh ones, with each id in
    `invalidated` marked so; then each record a lower generation already holds
    as superseded or invalidated and nothing replaced; then any invalidated id
    not seen before."""
    invalidated = dict(invalidated or {})
    out, seen = [], set()
    for record in fresh:
        record = dict(record)
        if record["id"] in invalidated:
            record.update(status="invalidated", reason=invalidated[record["id"]])
        out.append(record)
        seen.add(record["id"])
    for record in previous:
        if record["id"] not in seen and record.get("status") in ("superseded", "invalidated"):
            out.append(dict(record))
            seen.add(record["id"])
    for record_id, reason in invalidated.items():
        if record_id not in seen:
            out.append({"id": record_id, "kind": _kind(record_id),
                        "status": "invalidated", "reason": reason})
    return out


def _documents(task_dir, n, resolution, previous_records, invalidated):
    slug = os.path.basename(os.path.normpath(task_dir))
    return {
        "resolved.yml": {"schema": SCHEMA, "issue": slug, "generation": n,
                         **resolution.resolved},
        "provenance.yml": {"schema": SCHEMA, **resolution.provenance},
        "versions.yml": {"schema": SCHEMA, **resolution.versions},
        "records.yml": {"schema": SCHEMA,
                        "records": _records(resolution.records, previous_records,
                                            invalidated)},
    }


def _same_configuration(stored, documents):
    """True when the resolved configuration and the issue overlay equal what
    generation n holds."""
    def body(document):
        return digest({k: v for k, v in document.items() if k != "generation"})

    same_config = body(stored["resolved"]) == body(documents["resolved.yml"])
    same_overlay = (stored["versions"].get("issue_overlay_digest")
                    == documents["versions.yml"].get("issue_overlay_digest"))
    return same_config and same_overlay


def _unchanged(stored, documents, disk, manifest):
    """True when the resolved configuration, the issue overlay and the
    computed outcome all equal what generation n holds."""
    return _same_configuration(stored, documents) and _outcome(disk) == _outcome(manifest)


def _named(n):
    return "no generation" if n is None else f"generation {n}"


def _refuse_links(task_dir, target):
    """Refuse when `generations/`, the next folder or anything inside it is a
    symbolic link. The next folder is cleared before it is written, and a
    clear that followed a link would delete files outside the issue."""
    folder = gen_dir(task_dir, target)
    paths = [os.path.join(os.fspath(task_dir), DIRECTORY), folder]
    if os.path.isdir(folder) and not os.path.islink(folder):
        paths += [os.path.join(folder, name) for name in os.listdir(folder)]
    for path in paths:
        if os.path.islink(path):
            raise CompassError(
                f"{path} is a symbolic link. Compass does not follow links in a "
                f"generation folder, so nothing was written. Replace it with a real "
                f"folder or file, or remove the link, then run the command again")


def _prepare_target(task_dir, target):
    """Make the next folder ready to write into, or refuse. A folder holding a
    complete generation nothing names is the person's to adopt or discard; any
    other leftover is overwritten, except `proposed.yml`, which is kept."""
    _refuse_links(task_dir, target)
    folder = gen_dir(task_dir, target)
    if not os.path.isdir(folder):
        os.makedirs(folder)
        return
    if os.path.isfile(os.path.join(folder, MARKER)) and is_whole(task_dir, target)[0]:
        raise CompassError(
            f"{folder} holds a complete generation {target} that the manifest does not "
            f"name, so nothing was written. Run `compass issue configure --commit "
            f"{target}` to adopt it (add `--reason \"...\"` to keep the reason of the "
            f"interrupted reassess), or `compass issue configure --discard {target}` to "
            f"remove it, then run the command again")
    for name in os.listdir(folder):
        if name == PROPOSED:
            continue
        path = os.path.join(folder, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.unlink(path)


def _remove(path):
    if os.path.isfile(path):
        os.unlink(path)


def _check_adoption(task_dir, adopt, target, documents, held):
    """Refuse unless the leftover folder `adopt` is the next generation, is
    whole, and holds the four files a fresh resolution gives now. The check
    is on the digests the marker holds: an adopted generation is one the
    project and the issue would still resolve to, so the manifest never names
    a configuration nothing today produces."""
    folder = gen_dir(task_dir, target)
    if adopt != target:
        raise CompassError(
            f"the manifest names {_named(held)}, so the generation to adopt is "
            f"{target}, not {adopt}; nothing was written")
    _refuse_links(task_dir, target)
    stored, reason = _read_whole(task_dir, target)
    if stored is None:
        raise CompassError(
            f"{folder} cannot be adopted: {reason}. Nothing was written. Run `compass "
            f"issue configure --discard {target}` to remove it, or run `compass "
            f"approach evaluate --write` to write the generation again")
    differing = [name for name in FILES
                 if digest(stored[name[:-4]]) != digest(documents[name])]
    if differing:
        raise CompassError(
            f"{folder} cannot be adopted: {', '.join(differing)} no longer match what "
            f"the project and the issue resolve to now. Nothing was written. Run "
            f"`compass issue configure --discard {target}`, then `compass approach "
            f"evaluate --write`")


def preflight(task_dir, resolution, manifest, invalidated=None, adopt=None):
    """Refuse, before the caller prints anything, a commit that will refuse
    later for a reason already known: the issue is landed, the layered lint
    rejects the configuration, or the folder to adopt does not match. A
    configuration equal to the generation in force is left alone: whether it
    commits depends on the computed outcome, which is not known yet, and the
    commit says "no change" without a lint. `commit` checks again under the
    lock; this is the early look. The lint runs at most once: the resolution's
    lint hook is cleared after it passes."""
    task_dir = os.fspath(task_dir)
    disk = load_yaml(manifest_path(task_dir))
    n = number(disk) or 0
    previous = load(task_dir, n) if n else None
    documents = _documents(task_dir, n + 1, resolution,
                           previous["records"].get("records", []) if previous else [],
                           invalidated)
    if previous and _same_configuration(previous, documents):
        return      # the outcome decides, and it is not known yet: `commit` answers
    if disk.get("status") == "landed":
        raise CompassError(
            f"issue {os.path.basename(os.path.normpath(task_dir))} is landed and keeps "
            f"the configuration it landed under; it cannot store a new generation")
    if adopt is not None:
        _check_adoption(task_dir, adopt, n + 1, documents, number(disk))
    if resolution.validate is not None:
        resolution.validate()
        resolution.validate = None


def commit(task_dir, resolution, manifest, invalidated=None, render=None, *,
           adopt=None, proposal=None, stamp=None, force=False):
    """Store `resolution` as the next generation of the issue and replace its
    manifest, or commit nothing when generation n already holds the same
    configuration, overlay and outcome. `force` commits even then: the
    versions a generation pins are not part of that comparison, and
    `migrate-config` changes nothing else. `manifest` is the mapping to write,
    with the outcome fields folded in; it must still name the generation the
    file on disk names. Raises `CompassError` when the file changed since it
    was read, the generation in force is broken, or the next folder is a
    complete generation nobody adopted. `render`, when given, turns the
    manifest's text into the text to write (the gate comments), so they are
    written under the lock, in the same replace.

    `adopt` is the number of a complete leftover folder to adopt: nothing is
    written but the manifest, and only when the folder holds what a fresh
    resolution gives. `proposal` is the `Proposal` this commit applies: it
    must still be the one on disk when the lock is held, and its file is
    removed after the manifest replace. `stamp(mapping, from, to)` may change the
    mapping to write, with the generation it moves from and to (the same
    number twice when nothing is committed)."""
    task_dir = os.fspath(task_dir)
    render = render or (lambda text: text)
    stamp = stamp or (lambda mapping, old, new: None)
    path = manifest_path(task_dir)
    with locked(os.path.join(task_dir, LOCK)):
        disk = load_yaml(path)
        held = number(disk)
        if held != number(manifest):
            raise CompassError(
                f"{path} changed since it was read (it now names {_named(held)}; the "
                f"update was built on {_named(number(manifest))}); run the command again")
        n = held or 0
        previous = load(task_dir, n) if n else None
        target = n + 1
        if proposal is not None and read_proposal(task_dir, target) != proposal:
            raise CompassError(
                f"the proposal in generation {target} changed while the command ran, so "
                f"nothing was written; run the command again")
        documents = _documents(task_dir, target, resolution,
                               previous["records"].get("records", []) if previous else [],
                               invalidated)
        if previous and not force and _unchanged(previous, documents, disk, manifest):
            if adopt is not None:
                raise CompassError(
                    f"generation {n} already holds this configuration, so folder {adopt} "
                    f"adds nothing; nothing was written. Run `compass issue configure "
                    f"--discard {adopt}` to remove it")
            same = dict(manifest)
            stamp(same, n, n)
            atomic_write_text(path, render(_dump(same)))
            if proposal is not None:
                # The proposal asked for what the generation already holds.
                _remove(os.path.join(gen_dir(task_dir, target), PROPOSED))
            return Committed(n, False, f"no change: generation {n} already holds this "
                                       f"configuration")
        if disk.get("status") == "landed":
            raise CompassError(
                f"issue {os.path.basename(os.path.normpath(task_dir))} is landed and keeps "
                f"the configuration it landed under; it cannot store a new generation")
        if resolution.validate is not None:
            resolution.validate()
        if resolution.finish is not None:
            resolution.finish(resolution.versions)
            documents["versions.yml"] = {"schema": SCHEMA, **resolution.versions}
        folder = gen_dir(task_dir, target)
        if adopt is None:
            _prepare_target(task_dir, target)
            for name in FILES:
                atomic_write_text(os.path.join(folder, name), _dump(documents[name]))
                _after_step(name[:-4])
            # The digest is of the content, so it equals the digest of the file read
            # back; the marker test checks that, and parsing four files again would
            # double the commit's cost.
            marker = {"schema": SCHEMA, "written": _now(),
                      "files": {name: digest(documents[name]) for name in FILES}}
            atomic_write_text(os.path.join(folder, MARKER), _dump(marker))
            _after_step("marker")
        else:
            _check_adoption(task_dir, adopt, target, documents, held)
        updated = dict(manifest)
        updated["generation"] = target
        stamp(updated, n, target)
        atomic_write_text(path, render(_dump(updated)))
        _after_step("manifest")
        if proposal is not None:
            _remove(os.path.join(folder, PROPOSED))
            _after_step("proposal")
    verb = "adopted" if adopt is not None else "committed"
    return Committed(target, True, f"{verb} generation {target} -> {folder}")
