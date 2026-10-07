# compass_pkg.generation - the generation store: a stored copy of an issue's configuration
"""The numbered, stored copy of the configuration an issue runs against
(ADR-036).

A generation is a folder, `.compass/work/<slug>/generations/<n>/`, holding:

- `resolved.yml`, `provenance.yml`, `versions.yml`, `records.yml`: the
  configuration and what it was resolved from, fixed at commit;
- `complete`: a marker written after them, holding a digest of each;
- `results.yml`: the latest check verdicts, rewritten after each run and not
  covered by the marker;
- `proposed.yml`: a pending change, which this module only recognises.

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
    `versions`, `records`, `marker`, `manifest`. A test replaces it to
    interrupt the commit at that step. Product code has no switch for it."""


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


def _unchanged(stored, documents, disk, manifest):
    """True when the resolved configuration, the issue overlay and the
    computed outcome all equal what generation n holds."""
    def body(document):
        return digest({k: v for k, v in document.items() if k != "generation"})

    same_config = body(stored["resolved"]) == body(documents["resolved.yml"])
    same_overlay = (stored["versions"].get("issue_overlay_digest")
                    == documents["versions.yml"].get("issue_overlay_digest"))
    return same_config and same_overlay and _outcome(disk) == _outcome(manifest)


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
            f"name, so nothing was written. Delete the folder and run the command again")
    for name in os.listdir(folder):
        if name == PROPOSED:
            continue
        path = os.path.join(folder, name)
        shutil.rmtree(path) if os.path.isdir(path) else os.unlink(path)


def commit(task_dir, resolution, manifest, invalidated=None, render=None):
    """Store `resolution` as the next generation of the issue and replace its
    manifest, or commit nothing when generation n already holds the same
    configuration, overlay and outcome. `manifest` is the mapping to write,
    with the outcome fields folded in; it must still name the generation the
    file on disk names. Raises `CompassError` when the file changed since it
    was read, the generation in force is broken, or the next folder is a
    complete generation nobody adopted. `render`, when given, turns the
    manifest's text into the text to write (the gate comments), so they are
    written under the lock, in the same replace."""
    task_dir = os.fspath(task_dir)
    render = render or (lambda text: text)
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
        documents = _documents(task_dir, target, resolution,
                               previous["records"].get("records", []) if previous else [],
                               invalidated)
        if previous and _unchanged(previous, documents, disk, manifest):
            atomic_write_text(path, render(_dump(manifest)))
            return Committed(n, False, f"no change: generation {n} already holds this "
                                       f"configuration")
        if disk.get("status") == "landed":
            raise CompassError(
                f"issue {os.path.basename(os.path.normpath(task_dir))} is landed and keeps "
                f"the configuration it landed under; it cannot store a new generation")
        if resolution.validate is not None:
            resolution.validate()
        _prepare_target(task_dir, target)
        folder = gen_dir(task_dir, target)
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
        updated = dict(manifest)
        updated["generation"] = target
        atomic_write_text(path, render(_dump(updated)))
        _after_step("manifest")
    return Committed(target, True, f"committed generation {target} -> {folder}")
