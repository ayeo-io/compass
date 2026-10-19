# compass_pkg.manifest_store - read and save an issue's manifest safely
"""How `core.load_manifest` and `core.save_manifest` read and write an issue's
`manifest.yml` when two commands, or a command and the pre-tool hook, use it
at once.

- A save writes a temporary file and renames it over the manifest
  (`atomic_io.atomic_write_text`), so a reader sees the old manifest or the
  new one, never part of either.
- A read takes no lock. The pre-tool hook reads a manifest on every tool
  call. A read records the bytes it read and does nothing else.
- A save takes `.manifest.lock` and reads the file again. When another
  command saved it since this command read it, the save merges this
  command's changes into the file now (`merge_manifest`), and raises
  `ManifestConflict`, writing nothing, when both changed the same value.

`docs/safety-contract.md` (guarantee 7) states the behaviour for a reader.
"""
# DEPENDENCY: standard library (copy, errno, os, weakref); the bundled PyYAML;
# atomic_io and project_settings, which import nothing else from Compass.
from __future__ import annotations

import copy
import errno
import os
import weakref

import yaml
import yaml.representer

from compass_pkg import atomic_io
from compass_pkg.project_settings import CompassError


class ManifestConflict(CompassError):
    """Another save changed a value of the manifest that this command also
    changed, to something else, since this command read it."""


class ManifestDict(dict):
    """The mapping a load returns. It is a plain `dict` in every use; the one
    difference is that it can be weakly referenced, so the version it was read
    from is dropped when nothing holds it any more. A copy carries the same
    version, so saving a copy merges as saving the original would."""

    __slots__ = ("__weakref__",)

    def __copy__(self):
        return _same_version(self, ManifestDict(self))

    def __deepcopy__(self, memo):
        # Entered in `memo` before the contents, so a value that refers back
        # to this mapping is copied to the duplicate, not to a second copy.
        duplicate = ManifestDict()
        memo[id(self)] = duplicate
        for key, value in self.items():
            duplicate[copy.deepcopy(key, memo)] = copy.deepcopy(value, memo)
        return _same_version(self, duplicate)


def _register_representer():
    """YAML writes a `ManifestDict` as the mapping it is. Every representer
    class gets the entry, including subclasses defined before this module was
    imported, which keep their own table."""
    stack = [yaml.representer.BaseRepresenter]
    while stack:
        cls = stack.pop()
        cls.add_representer(ManifestDict, yaml.representer.SafeRepresenter.represent_dict)
        stack.extend(cls.__subclasses__())


_register_representer()


# --- the version each manifest was read from ------------------------------------
# A command loads a manifest, changes it and saves it. Another command can save
# the same manifest in between, so a save needs the version this command read
# to tell its own changes from the other command's.
#
# `_READ_BY_OBJECT` maps the identity of each `ManifestDict` to a weak
# reference to it, its path, the bytes it is in step with, and whether it was
# normalised. A finaliser drops the entry when the mapping is collected, so
# a process that loads many manifests does not keep them all. Each mapping
# keeps its own version, so two mappings read at different times in one
# process do not share one.
_READ_BY_OBJECT = {}


def read(path):
    """`(parsed, bytes)` for the manifest at `path`: the parse `core.load_yaml`
    gives, with its error message, and the bytes it came from."""
    with open(path, "rb") as fh:
        data = fh.read()
    return _parse(data, path), data


def _parse(data, path):
    try:
        parsed = yaml.safe_load(data.decode("utf-8")) or {}
    except yaml.YAMLError as exc:
        raise CompassError(f"invalid YAML in {path}: {exc}")
    if not isinstance(parsed, dict):
        raise CompassError(
            f"{path}: the manifest must be a mapping of keys to values, "
            f"not a {type(parsed).__name__}"
        )
    return parsed


def track(manifest, path, data, normalised=True):
    """`manifest` as a `ManifestDict`, with `data` recorded as the version it
    is in step with. A value that is not a mapping is returned unchanged."""
    if not isinstance(manifest, dict):
        return manifest
    if not isinstance(manifest, ManifestDict):
        manifest = ManifestDict(manifest)
    _record(manifest, os.path.abspath(path), data, normalised)
    return manifest


def _record(manifest, path, data, normalised):
    key = id(manifest)
    entry = _READ_BY_OBJECT.get(key)
    if entry is None or entry[0]() is not manifest:
        weakref.finalize(manifest, _READ_BY_OBJECT.pop, key, None)
    _READ_BY_OBJECT[key] = (weakref.ref(manifest), path, data, normalised)


def _same_version(source, duplicate):
    entry = _READ_BY_OBJECT.get(id(source))
    if entry is not None and entry[0]() is source:
        _record(duplicate, *entry[1:])
    return duplicate


def load_file(path):
    """The manifest at `path` as `core.load_yaml` reads it, not normalised, with
    the version recorded for the save. For a writer that changes the file's own
    keys rather than the normalised view."""
    if not os.path.isfile(path):
        raise CompassError(f"not found: {path}")
    manifest, data = read(path)
    return track(manifest, path, data, normalised=False)


def _read_version(manifest, path):
    """`(bytes, normalised)` for the version `manifest` is in step with, or
    None when no load returned it for `path`."""
    entry = _READ_BY_OBJECT.get(id(manifest))
    if entry is not None and entry[0]() is manifest and entry[1] == os.path.abspath(path):
        return entry[2], entry[3]
    return None


# --- the save -------------------------------------------------------------------

def save(manifest, path, lock_name, prepare, normalize):
    """Write `manifest` to `path`, keeping any change another command saved
    since `manifest` was read. `prepare` is `core.prepare_manifest_write`
    and `normalize` is `core.normalize_spine`, passed in so this module does not
    import core.

    After a merge, the merged result is written into `manifest` in place, so a
    later save of it keeps the other command's changes. The caller's own nested
    mappings and lists are updated rather than replaced, so a record the caller
    still holds stays part of `manifest`, and a change made through it later is
    saved. Because a merged save changes `manifest` and its nested lists in
    place, a caller must not save while it iterates over them."""
    if os.path.isfile(path) and not os.access(path, os.W_OK):
        # An in-place write refused a read-only manifest; a rename would not.
        raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), path)
    with atomic_io.locked(os.path.join(os.path.dirname(os.path.abspath(path)), lock_name)):
        try:
            with open(path, "rb") as fh:
                current = fh.read()
        except FileNotFoundError:
            current = None
        version = _read_version(manifest, path)
        out = manifest
        if version is not None and current is not None and current != version[0]:
            out = _merge_with_disk(manifest, version, current, path, normalize)
        text = yaml.safe_dump(prepare(out, path), sort_keys=False, default_flow_style=False)
        atomic_io.atomic_write_text(os.path.realpath(path), text)
    if out is not manifest:
        _apply(manifest, out)
    if isinstance(manifest, ManifestDict):
        # What was just written is the version `manifest` is now in step with.
        _record(manifest, os.path.abspath(path), text.encode("utf-8"),
                version[1] if version is not None else True)


def _merge_with_disk(manifest, version, current, path, normalize):
    data, normalised = version
    base, theirs = _parse(data, path), _parse(current, path)
    if normalised:
        base, theirs = normalize(base), normalize(theirs)
    try:
        return merge_manifest(base, manifest, theirs)
    except ManifestConflict as exc:
        raise ManifestConflict(
            f"{path}: another save changed {exc} after this command read the "
            f"manifest, and this command changed it to a different value; nothing "
            f"was written. Run the command again.") from None


def _apply(target, merged):
    """Make `target` equal to `merged`, keeping `target`'s own nested objects:
    a mapping in both is updated key by key, a list is filled in place, and a
    record matched by `id` (or, in a list without ids, by position) is the
    caller's record, updated, unless the merged list already uses it."""
    if isinstance(target, dict):
        for key in [k for k in target if k not in merged]:
            del target[key]
        for key, value in merged.items():
            if key in target and _reusable(target[key], value):
                _apply(target[key], value)
            else:
                target[key] = value
        return
    held = target
    if _ids(held) is not None and _ids(merged) is not None:
        by_id = {item["id"]: item for item in held}
        mine = [by_id.get(item["id"]) for item in merged]
    else:
        mine = [held[i] if i < len(held) else None for i in range(len(merged))]
    # An object of the caller's that the merged list itself uses, at any
    # position, stays as it is: rewriting it to equal another item would put
    # that item in the list twice and lose this one.
    used = {id(item) for item in merged}
    out = []
    for own, item in zip(mine, merged):
        if own is not None and id(own) not in used and _reusable(own, item):
            _apply(own, item)
            out.append(own)
        else:
            out.append(item)
    target[:] = out


def _reusable(own, value):
    """True when `own` can be updated in place to become `value`."""
    return own is not value and (
        (isinstance(own, dict) and isinstance(value, dict))
        or (isinstance(own, list) and isinstance(value, list)))


# --- the merge ------------------------------------------------------------------

_ABSENT = object()


def merge_manifest(base, ours, theirs):
    """`ours` and `theirs` are two changed copies of `base`. Return `theirs`
    with the changes `ours` made, or raise `ManifestConflict` naming the key
    both changed differently.

    - A value one side changed takes that side's value, and a key one side
      added or removed follows that side. A value of another type, such as
      `true` for `1`, is a change.
    - Mappings merge key by key, in `ours`' order, then keys only `theirs` has.
    - A list whose items are all mappings with distinct `id` values merges
      record by record, matched by `id`. A record both changed merges key by
      key. A record one side removed stays removed when the other side left
      it alone; when the other side changed it, that is a conflict. The result
      keeps `ours`' order. A record only `theirs` added goes after the record
      it follows in `theirs`, or first when it follows none.
    - Any other list merges position by position over `base`'s length, taking
      the side that changed a position; a position both changed differently
      is a conflict. Items each side added at the end are kept, `theirs`'
      first, and an item both added is kept once. A list one side shortened
      while the other changed it is a conflict."""
    return _merge(base, ours, theirs, "")


def _same(a, b):
    """Equal values of the same type, all the way down."""
    if a is b:
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _merge(base, ours, theirs, where):
    if _same(ours, base):
        return theirs
    if _same(theirs, base) or _same(ours, theirs):
        return ours
    if isinstance(ours, dict) and isinstance(theirs, dict) and \
            (base is _ABSENT or isinstance(base, dict)):
        base = {} if base is _ABSENT else base
        out = {}
        for key in list(ours) + [k for k in theirs if k not in ours]:
            value = _merge(base.get(key, _ABSENT), ours.get(key, _ABSENT),
                           theirs.get(key, _ABSENT), f"{where}.{key}" if where else str(key))
            if value is not _ABSENT:
                out[key] = value
        return out
    if isinstance(ours, list) and isinstance(theirs, list) and \
            (base is _ABSENT or isinstance(base, list)):
        base = [] if base is _ABSENT else base
        if all(_ids(items) is not None for items in (base, ours, theirs)):
            return _merge_records(base, ours, theirs, where)
        return _merge_positions(base, ours, theirs, where)
    raise ManifestConflict(where or "the manifest")


def _ids(items):
    """The `id` of each item, or None when an item is not a mapping with a
    string or integer `id`, or two items share one."""
    ids = []
    for item in items:
        value = item.get("id") if isinstance(item, dict) else None
        if type(value) not in (str, int):
            return None
        ids.append(value)
    return ids if len(set(ids)) == len(ids) else None


def _merge_records(base, ours, theirs, where):
    by_id = [{item["id"]: item for item in items} for items in (base, ours, theirs)]
    # This writer's order, with each record only the other writer added put
    # after the record it follows there, or first when it follows none.
    order = [item["id"] for item in ours]
    theirs_ids = [item["id"] for item in theirs]
    for n, key in enumerate(theirs_ids):
        if key in by_id[0] or key in by_id[1]:
            continue
        before = next((k for k in reversed(theirs_ids[:n]) if k in order), None)
        order.insert(0 if before is None else order.index(before) + 1, key)
    # A record this writer removed is not in `order`; the other writer must
    # have left it alone.
    for key, b in by_id[0].items():
        if key not in by_id[1] and key in by_id[2] and not _same(by_id[2][key], b):
            raise ManifestConflict(f"{where}[id={key}]")
    out = []
    for key in order:
        b, o, t = (side.get(key, _ABSENT) for side in by_id)
        at = f"{where}[id={key}]"
        if b is not _ABSENT and (o is _ABSENT or t is _ABSENT):
            kept = t if o is _ABSENT else o
            if not _same(kept, b):
                # One side removed the record and the other changed it.
                # Dropping the change would lose an update.
                raise ManifestConflict(at)
            continue                                    # removed, and left alone
        value = _merge(b, o, t, at)
        if value is not _ABSENT:
            out.append(value)
    return out


def _merge_positions(base, ours, theirs, where):
    n = len(base)
    if len(ours) < n or len(theirs) < n:
        raise ManifestConflict(where or "the manifest")
    out = []
    for i in range(n):
        if _same(ours[i], base[i]):
            out.append(theirs[i])
        elif _same(theirs[i], base[i]) or _same(ours[i], theirs[i]):
            out.append(ours[i])
        else:
            raise ManifestConflict(f"{where}[{i}]")
    added = list(theirs[n:])
    return out + added + [item for item in ours[n:] if not any(_same(item, a) for a in added)]
