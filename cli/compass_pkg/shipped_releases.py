# compass_pkg.shipped_releases - the governance files each release shipped
"""A table of every shipped governance release, as data.

`compass policy migrate` needs to know which release a project's copy came
from, so it can tell a local edit from a default that moved since. The
installed plugin has no git tags, so the files of each release are kept in
`governance/shipped-releases.tar.xz` and described in
`governance/shipped-releases.yml`: per release the version and the content
digest of each file, hashed the way `tests/test_governance_drift.py` does it
(parsed, without `version:`). `scripts/generate-shipped-releases.py` writes
both from the git tags. Nothing here reads a tag.

`current()` is the pair of files this install ships now. It is a candidate
after the newest release, so an unedited copy of the working tree matches it.
"""
# DEPENDENCY: standard library (hashlib, json, os, tarfile); the bundled
# PyYAML; compass_pkg.core (FRAMEWORK_ROOT, CompassError).
from __future__ import annotations

import hashlib
import json
import os
import tarfile

import yaml

from compass_pkg.core import FRAMEWORK_ROOT, CompassError

TABLE_FILE = os.path.join("governance", "shipped-releases.yml")
ARCHIVE_FILE = os.path.join("governance", "shipped-releases.tar.xz")
POLICY, GUARDRAILS = "routing-policy.yml", "guardrails.yml"
CURRENT = "current"

_CACHE = {}


def content_hash(text):
    """The digest of a governance file's content: parsed, with `version:`
    removed, keys sorted. A comment or a layout change does not move it."""
    data = yaml.safe_load(text)
    data.pop("version", None)
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def member_name(kind, version, digest):
    """The archive member for one file. Releases that shipped the same file
    share a member."""
    return f"{kind}/{version}-{digest[:12]}.yml"


def _root(root):
    return os.fspath(root or FRAMEWORK_ROOT)


def table(root=None):
    """The releases, oldest first. Each is `{tag, routing_policy, guardrails}`
    with `version` and `digest` for the two files."""
    path = os.path.join(_root(root), TABLE_FILE)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return list(yaml.safe_load(fh)["releases"])
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise CompassError(f"cannot read the table of shipped releases {path}: {exc}") from exc


def _members(root):
    path = os.path.join(_root(root), ARCHIVE_FILE)
    if path not in _CACHE:
        try:
            with tarfile.open(path, "r:xz") as archive:
                _CACHE[path] = {m.name: archive.extractfile(m).read().decode("utf-8")
                                for m in archive.getmembers() if m.isfile()}
        except (OSError, tarfile.TarError) as exc:
            raise CompassError(f"cannot read the archive of shipped releases {path}: "
                               f"{exc}") from exc
    return _CACHE[path]


def texts(tag, root=None):
    """`(routing policy text, guardrails text)` of a release."""
    for release in table(root):
        if release["tag"] == tag:
            members = _members(root)
            return tuple(members[member_name(kind, release[key]["version"],
                                              release[key]["digest"])]
                         for kind, key in (("routing-policy", "routing_policy"),
                                           ("guardrails", "guardrails")))
    raise CompassError(f"no shipped release {tag}")


def current(root=None):
    """The release record of the governance files this install ships."""
    out = {"tag": CURRENT}
    for name, key in ((POLICY, "routing_policy"), (GUARDRAILS, "guardrails")):
        with open(os.path.join(_root(root), "governance", name), "r", encoding="utf-8") as fh:
            text = fh.read()
        out[key] = {"version": str(yaml.safe_load(text).get("version")),
                    "digest": content_hash(text)}
    return out


def current_texts(root=None):
    out = []
    for name in (POLICY, GUARDRAILS):
        with open(os.path.join(_root(root), "governance", name), "r", encoding="utf-8") as fh:
            out.append(fh.read())
    return tuple(out)


def missing_tags(releases, tags):
    """The tags the table does not hold."""
    held = {r["tag"] for r in releases}
    return [t for t in tags if t not in held]
