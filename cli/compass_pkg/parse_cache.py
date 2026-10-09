#!/usr/bin/env python3
# =============================================================================
# compass_pkg.parse_cache - a store of manifest parses, keyed on content
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md (ADR-013). This module stores the results of the one
# parser. It is not a second parser, and it never reads YAML any other way.
#
# `ParseCache.load_yaml` has the contract of `core.load_yaml` and is faster on
# a second run, because a parse of the same bytes is the same value
# `yaml.safe_load` would give again (ADR-049). Only `flow.board()` reads
# through it. `core.load_yaml` and every path that reads a manifest to change
# and save it do not, so a fault here can at worst misplace a row on an
# advisory board.
# =============================================================================

import datetime
import hashlib
import io
import json
import os
import re
import tempfile

import yaml

from compass_pkg.core import CompassError

#: Bumped when the layout of an entry changes; older entries then miss.
FORMAT = 1

#: The folder under `<project>/.compass/cache/`. It has an underscore, which a
#: GitHub owner name cannot, so it never collides with the parent cache's
#: `<owner>/<repo>/<sha>` layout (`parents.commit_dir`).
FOLDER = "parsed_yaml"

_ENTRY_NAME = re.compile(r"^[0-9a-f]{64}\.json$")
_UTC = datetime.timezone.utc
_MISS = object()


# --- the stored form --------------------------------------------------------
# Tagged JSON over a closed set of types. Every container is an array whose
# first item is a tag, so a list in the document cannot be mistaken for a
# tagged value. Entries are read with json.loads only: no file here can run
# code when loaded.
#
#   ["m", k1, v1, k2, v2, ...]   a mapping, keeping order and non-text keys
#   ["l", v1, v2, ...]           a list
#   ["r", n]                     the n-th container seen, so an anchor and its
#                                alias stay one object
#   ["d", y, m, d]               a date
#   ["t", y, m, d, h, mi, s, us, offset seconds or null]   a datetime

class _Refuse(Exception):
    """The document holds a value outside the closed set."""


def _encode(value, seen):
    kind = type(value)
    if value is None or kind is bool or kind is int or kind is float or kind is str:
        return value
    if kind is dict or kind is list:
        number = seen.get(id(value))
        if number is not None:
            return ["r", number]
        seen[id(value)] = len(seen)
        if kind is list:
            return ["l"] + [_encode(item, seen) for item in value]
        out = ["m"]
        for key, item in value.items():
            key_kind = type(key)
            if not (key is None or key_kind is bool or key_kind is int or key_kind is float
                    or key_kind is str or key_kind is datetime.date
                    or key_kind is datetime.datetime):
                raise _Refuse(key_kind)
            out.append(_encode(key, seen))
            out.append(_encode(item, seen))
        return out
    if kind is datetime.date:
        return ["d", value.year, value.month, value.day]
    if kind is datetime.datetime:
        zone = value.tzinfo
        if zone is None:
            offset = None
        elif zone is _UTC:
            offset = 0
        elif type(zone) is datetime.timezone:
            delta = zone.utcoffset(None)
            # A named zone, or an offset that is not whole seconds, is not stored.
            if delta.microseconds or zone != datetime.timezone(delta):
                raise _Refuse("timezone")
            offset = delta.days * 86400 + delta.seconds
        else:
            raise _Refuse("timezone")
        return ["t", value.year, value.month, value.day, value.hour, value.minute,
                value.second, value.microsecond, offset]
    raise _Refuse(kind)


def encode(doc):
    """Tagged JSON text for `doc`, or None when it holds a value outside the
    closed set: dict, list, str, int, float, bool, None, date, and datetime
    with no zone, UTC or a fixed offset. A value that is not stored is parsed
    every time, which costs speed and never correctness."""
    try:
        return json.dumps(_encode(doc, {}), separators=(",", ":"))
    except (_Refuse, RecursionError, ValueError, TypeError):
        return None


def _decode(node, seen):
    kind = type(node)
    if kind is not list:
        if node is None or kind is str or kind is int or kind is float or kind is bool:
            return node
        raise ValueError("unexpected node in a stored parse")
    tag = node[0]
    if tag == "m":
        out = {}
        seen.append(out)
        for index in range(1, len(node), 2):
            out[_decode(node[index], seen)] = _decode(node[index + 1], seen)
        return out
    if tag == "l":
        out = []
        seen.append(out)
        for index in range(1, len(node)):
            out.append(_decode(node[index], seen))
        return out
    if tag == "r":
        return seen[node[1]]
    if tag == "d":
        return datetime.date(node[1], node[2], node[3])
    if tag == "t":
        offset = node[8]
        zone = (None if offset is None else _UTC if offset == 0
                else datetime.timezone(datetime.timedelta(seconds=offset)))
        return datetime.datetime(node[1], node[2], node[3], node[4], node[5], node[6],
                                 node[7], tzinfo=zone)
    raise ValueError("unknown tag in a stored parse")


def decode(text):
    """The document `encode` wrote, as new objects. Raises on anything
    unexpected."""
    return _decode(json.loads(text), [])


# --- the reader -------------------------------------------------------------

class ParseCache:
    """Reads YAML files as `core.load_yaml` does, storing each parse under the
    SHA-256 of the bytes it came from.

    Every read opens the file and reads all its bytes first, so the cache can
    save a parse and can never skip a read: a changed, removed or malformed
    file behaves as it always did. An entry is used only when its recorded
    format, parser version and source digest all match, and any doubt parses
    the same bytes with `yaml.safe_load`."""

    def __init__(self, folder, store):
        self._folder = folder           # None: a pass-through reader
        self._store = bool(store and folder)
        self._used = set()
        self._reads = 0
        self._ready = False

    def load_yaml(self, path):
        """The contract of `core.load_yaml`, unchanged: "not found" for a path
        that is not a regular file, UnicodeDecodeError for bytes that are not
        UTF-8, "invalid YAML in <path>: <error>" for malformed YAML, `{}` for
        a falsy document, and new objects on every call. Never raises or
        prints because of the cache."""
        if not os.path.isfile(path):
            raise CompassError(f"not found: {path}")
        with open(path, "rb") as fh:
            raw = fh.read()
        raw.decode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        self._reads += 1
        if self._folder:
            self._used.add(digest)
            found = self._lookup(digest)
            if found is not _MISS:
                return found or {}
        doc = self._parse(raw, path)
        if self._store:
            self._save(digest, doc)
        return doc or {}

    def finish(self):
        """Delete entries this run did not use, only when the folder holds more
        than twice as many entries as this run read. Only names of 64 hex digits
        and `.json` are touched. Never raises, never prints."""
        if not self._store:
            return
        try:
            with os.scandir(self._folder) as listing:
                names = [e.name for e in listing if _ENTRY_NAME.match(e.name)]
            if len(names) <= 2 * self._reads:
                return
            keep = {digest + ".json" for digest in self._used}
            for name in names:
                if name not in keep:
                    try:
                        os.unlink(os.path.join(self._folder, name))
                    except OSError:
                        pass
        except Exception:                                   # noqa: BLE001
            pass

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _parse(raw, path):
        # The bytes are parsed through a text wrapper named with the path, so the
        # newline handling and the error marks match `open(path)`.
        buffer = io.BytesIO(raw)
        buffer.name = path
        try:
            return yaml.safe_load(io.TextIOWrapper(buffer, encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise CompassError(f"invalid YAML in {path}: {exc}")

    def _lookup(self, digest):
        try:
            with open(os.path.join(self._folder, digest + ".json"), "r",
                      encoding="utf-8") as fh:
                entry = json.loads(fh.read())
            if (type(entry) is dict and entry.get("format") == FORMAT
                    and entry.get("pyyaml") == yaml.__version__
                    and entry.get("source") == digest and "doc" in entry):
                return _decode(entry["doc"], [])
        except Exception:                                   # noqa: BLE001
            pass
        return _MISS

    def _save(self, digest, doc):
        tmp = None
        try:
            text = encode(doc)
            if text is None or not self._prepare():
                return
            body = ('{"format":%d,"pyyaml":%s,"source":"%s","doc":%s}'
                    % (FORMAT, json.dumps(yaml.__version__), digest, text))
            fd, tmp = tempfile.mkstemp(dir=self._folder, prefix=".tmp-")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, os.path.join(self._folder, digest + ".json"))
            tmp = None
        except Exception:                                   # noqa: BLE001
            pass
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _prepare(self):
        """Create the folder and its own `.gitignore` (containing `*`) before
        the first entry, so `git status` does not change in a project that
        commits `.compass/work/`. False when the folder cannot be used."""
        if self._ready:
            return True
        os.makedirs(self._folder, exist_ok=True)
        if not _folder_is_safe(self._folder):
            self._store = False
            return False
        ignore = os.path.join(self._folder, ".gitignore")
        if not os.path.exists(ignore):
            with open(ignore, "w", encoding="utf-8") as fh:
                fh.write("*\n")
        self._ready = True
        return True


def _folder_is_safe(folder):
    """No link in the path under `.compass`, and nothing resolving outside it."""
    cache = os.path.dirname(folder)
    compass = os.path.dirname(cache)
    if os.path.islink(cache) or os.path.islink(folder):
        return False
    real_compass = os.path.realpath(compass)
    real = os.path.realpath(folder)
    return real == real_compass or real.startswith(real_compass + os.sep)


def for_work_root(work_root, store=True):
    """The cache of the project that owns `work_root`.

    It is a pass-through reader (parse every time, store nothing) when the
    parent of `work_root` is not a folder named `.compass`, or when
    `.compass/cache` or the cache folder is a link or resolves outside
    `.compass`. With `store=False` it reads entries but never writes, creates
    or prunes anything."""
    try:
        compass = os.path.dirname(os.path.abspath(os.fspath(work_root)))
        if os.path.basename(compass) != ".compass":
            return ParseCache(None, False)
        folder = os.path.join(compass, "cache", FOLDER)
        if not _folder_is_safe(folder):
            return ParseCache(None, False)
        return ParseCache(folder, store)
    except (OSError, ValueError, TypeError):
        return ParseCache(None, False)
