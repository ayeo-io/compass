# compass_pkg.execution_profile_store - the profile store: add a version, read one back
"""The profile store is the `profiles` folder of the project, committed with it.
It holds one flat file for each id and version, named `<id>.<version>.yml`.

`add` stores the bytes of a file that passes every rule of `lint`, and nothing
else. A stored version never changes: the file is linked into place, which fails
when the name exists, and a second `add` of the same content reports that it is
already stored.

`docs/execution-profiles.md` owns this behaviour.
"""
# DEPENDENCY: standard library (os, tempfile); compass_pkg.execution_profile (the rules).
from __future__ import annotations

import os
import re
import tempfile

from compass_pkg import atomic_io, model_tiers
from compass_pkg import execution_profile as ep

STORE_DIR = "profiles"

STORED = "stored"
ALREADY_STORED = "already-stored"


def store_path(root, profile_id, version):
    """The path of one stored version. The caller has checked the id and version."""
    return os.path.join(root, STORE_DIR, f"{profile_id}.{version}.yml")


def _folder_faults(root):
    """A `profiles/` folder that is a link could send a stored file outside the
    project, so it is refused."""
    folder = os.path.join(root, STORE_DIR)
    if os.path.islink(folder):
        return [(ep.FILE_UNREADABLE, f"{folder}: the folder is a symbolic link")]
    return []


def _existing(dest, data):
    """What a stored file at `dest` means for a file with the content `data`:
    `(ALREADY_STORED, [])` for the same content, else `version-immutable`."""
    stored, faults = ep.read_text_file(dest, follow_links=False)
    if faults:
        return None, faults
    if ep.content_digest(stored) == data["digest"]:
        return ALREADY_STORED, []
    return None, [(ep.VERSION_IMMUTABLE,
                   f"{data['id']} version {data['version']} is stored with the digest "
                   f"{stored.get('digest')}; a stored version never changes, so add a new "
                   "version")]


def _parent_faults(root, data):
    parent = data["parent"]
    if parent is None:
        return []
    where = store_path(root, data["id"], parent["version"])
    if not os.path.isfile(where):
        return [(ep.PARENT_MISSING, f"{data['id']} version {parent['version']} is not in "
                                    "the store, so it cannot be the parent")]
    stored, faults = ep.read_text_file(where, follow_links=False)
    if faults:
        return faults
    actual = ep.content_digest(stored)
    if actual != parent["digest"]:
        return [(ep.PARENT_DIGEST_MISMATCH,
                 f"the stored {data['id']} version {parent['version']} has the digest "
                 f"{actual} but the file names {parent['digest']}")]
    return []


def add(root, source):
    """Store the file `source`. Returns `(outcome, path, faults)`: the outcome is
    `STORED` or `ALREADY_STORED`, and `faults` is empty, or holds the reasons the
    file was refused and nothing was written."""
    data, faults = ep.check_file(source, root)
    if faults:
        return None, None, faults
    faults = _folder_faults(root)
    if faults:
        return None, None, faults
    dest = store_path(root, data["id"], data["version"])
    if os.path.exists(dest):
        outcome, faults = _existing(dest, data)
        return outcome, dest, faults
    faults = _parent_faults(root, data)
    if faults:
        return None, dest, faults
    with open(source, "rb") as handle:
        content = handle.read()
    folder = os.path.dirname(dest)
    os.makedirs(folder, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=folder, prefix=".profile-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(content)
        os.chmod(temporary, 0o644)
        try:
            os.link(temporary, dest)
        except FileExistsError:
            outcome, faults = _existing(dest, data)
            return outcome, dest, faults
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return STORED, dest, []


# --- the component registry -----------------------------------------------------

REGISTRY_FILE = "component-registry.yml"
_KINDS = tuple(kind for _, kind in ep.COMPONENT_KINDS)
_ENTRY_KEYS = ("kind", "id", "revision", "runner_versions", "approval")


def registry_path(root):
    return os.path.join(root, STORE_DIR, REGISTRY_FILE)


def _entry_faults(entry, where):
    faults = []
    if not isinstance(entry, dict):
        return [(ep.FIELD_MALFORMED, f"{where} must be a mapping, not {ep.show(entry)}")]
    for key in entry:
        if key not in _ENTRY_KEYS:
            faults.append((ep.FIELD_MALFORMED, f"{where}.{key} is not a field of an entry"))
    for key in ("kind", "id", "revision", "runner_versions"):
        if key not in entry:
            faults.append((ep.FIELD_MISSING, f"{where}.{key} is required"))
    if "kind" in entry and entry["kind"] not in _KINDS:
        faults.append((ep.FIELD_MALFORMED, f"{where}.kind is {ep.show(entry['kind'])}; it "
                                           f"must be one of {', '.join(_KINDS)}"))
    if "id" in entry and not ep.is_text(entry["id"]):
        faults.append((ep.FIELD_MALFORMED, f"{where}.id must be text"))
    if "revision" in entry and not (isinstance(entry["revision"], str)
                                    and ep.DIGEST_FORMAT.fullmatch(entry["revision"])):
        faults.append((ep.FIELD_MALFORMED, f"{where}.revision is {ep.show(entry['revision'])}; "
                                           "it must be sha256: and 64 lower-case hexadecimal "
                                           "digits"))
    if "runner_versions" in entry:
        versions = entry["runner_versions"]
        if not isinstance(versions, list) or not all(
                isinstance(v, str) and ep.RUNNER_FORMAT.fullmatch(v) for v in versions):
            faults.append((ep.FIELD_MALFORMED, f"{where}.runner_versions must be a list of "
                                               "versions such as 7.0.0"))
    if "approval" in entry:
        ep.check_approval(entry["approval"], f"{where}.approval", faults)
    return faults


def load_registry(root):
    """`(index, duplicates, faults)` for the component registry of the project.

    `index` maps `(kind, id, revision)` to its entry. `duplicates` holds the keys
    that more than one entry gave. A file that does not exist, is empty or lacks
    the `components` key holds no entry. A file that cannot be used gives faults
    and no index, because it says nothing about components."""
    path = registry_path(root)
    if os.path.islink(path):
        return {}, set(), [(ep.FILE_UNREADABLE, f"{path}: the file is a symbolic link")]
    if not os.path.exists(path):
        return {}, set(), []
    data, faults = ep.read_yaml(path)
    if faults:
        return {}, set(), faults
    if not isinstance(data, dict):
        return {}, set(), [(ep.FILE_UNREADABLE, f"{path}: the file does not hold a mapping")]
    faults = [(ep.FIELD_MALFORMED, f"{path}: {key} is not a key of the registry; the only "
                                   "key is components") for key in data if key != "components"]
    entries = data.get("components")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        faults.append((ep.FIELD_MALFORMED, f"{path}: components must be a list"))
        entries = []
    index, duplicates = {}, set()
    for position, entry in enumerate(entries):
        found = _entry_faults(entry, f"components[{position}]")
        faults.extend((code, f"{path}: {message}") for code, message in found)
        if found:
            continue
        key = (entry["kind"], entry["id"], entry["revision"])
        if key in index:
            duplicates.add(key)
        index[key] = entry
    if faults:
        return {}, set(), faults
    return index, duplicates, []


# --- show: the resolver ---------------------------------------------------------

def _component_faults(references, runners, index, duplicates):
    faults = []
    for kind, comp_id, revision in references:
        key = (kind, comp_id, revision)
        name = f"{kind} {comp_id!r} at revision {revision}"
        if key in duplicates:
            faults.append((ep.REGISTRY_DUPLICATE,
                           f"the registry lists {name} more than once; no entry is chosen"))
            continue
        entry = index.get(key)
        if entry is None:
            faults.append((ep.COMPONENT_MISSING, f"{name} is not in the registry"))
            continue
        approval = entry.get("approval")
        state = approval.get("state") if isinstance(approval, dict) else None
        if state != "approved":
            faults.append((ep.COMPONENT_NOT_APPROVED,
                           f"{name} has approval state {state if state else 'none'}"))
        lacking = [v for v in runners if v not in entry["runner_versions"]]
        if lacking:
            faults.append((ep.COMPONENT_INCOMPATIBLE,
                           f"{name} does not support the runner version "
                           f"{', '.join(lacking)}; it supports "
                           f"{', '.join(entry['runner_versions']) or 'none'}"))
    return faults


def _limits(root, model):
    mapped = model_tiers.mapping(root)[model["tier"]]["model"]
    limits = []
    if mapped == model_tiers.INHERIT:
        limits.append({"code": ep.MODEL_FOLLOWS_SESSION, "tier": model["tier"],
                       "model": mapped,
                       "message": f"the tier {model['tier']} maps to {mapped}, the model the "
                                  "session runs on, so the model is not fixed"})
    if model["provider_revision"] is None:
        limits.append({"code": ep.MODEL_VERSION_NOT_PINNED, "tier": model["tier"],
                       "model": mapped,
                       "message": f"the profile pins no provider revision for the model "
                                  f"{mapped} of the tier {model['tier']}"})
    return mapped, limits


def resolve(root, profile_id, version):
    """Resolve one stored version. Returns `(result, faults)`; `result` is None
    when there is any fault, so nothing resolved is ever printed with a refusal."""
    if version is None:
        return None, [(ep.VERSION_REQUIRED, "give --version N; no version is chosen as "
                                            "the latest")]
    # Nine digits is far above any real version; a longer text is no stored version.
    number = (int(version) if re.fullmatch(r"[1-9][0-9]{0,8}", str(version)) else None)
    if number is None or not ep.ID_FORMAT.fullmatch(str(profile_id)):
        return None, [(ep.PROFILE_MISSING,
                       f"{profile_id} version {version} is not in the store")]
    faults = _folder_faults(root)
    if faults:
        return None, faults
    path = store_path(root, profile_id, number)
    if not os.path.isfile(path):
        return None, [(ep.PROFILE_MISSING, f"{profile_id} version {number} is not in the "
                                           "store")]
    data, faults = ep.check_file(path, root, follow_links=False)
    if faults:
        return None, faults
    if data["id"] != profile_id:
        return None, [(ep.FIELD_MALFORMED, f"{path}: the file name says {profile_id} but the "
                                           f"file holds {data['id']}")]
    if data["version"] != number:
        return None, [(ep.FIELD_MALFORMED, f"{path}: the file name says version {number} but "
                                           f"the file holds version {data['version']}")]
    index, duplicates, faults = load_registry(root)
    if faults:
        return None, faults
    references = [(kind, ref["id"], ref["revision"])
                  for name, kind in ep.COMPONENT_KINDS for ref in data["components"][name]]
    faults = _component_faults(references, data["runner_versions"], index, duplicates)
    if faults:
        return None, faults
    mapped, limits = _limits(root, data["model"])
    model = dict(data["model"], mapped_model=mapped)
    return {"id": data["id"], "version": data["version"], "digest": data["digest"],
            "owner": data["owner"], "approval": data["approval"],
            "runner_versions": data["runner_versions"], "model": model,
            "components": [{"kind": k, "id": i, "revision": r} for k, i, r in references],
            "runner_settings": data["runner_settings"],
            "reproducibility_limits": limits}, []
