# compass_pkg.parents - git parents: the pinned spelling, the cache and the fetch
"""A project's `extends:` can name a git parent, `github:<owner>/<repo>@<ref>#<sha>`.

The parent is data. Compass fetches one commit, reads `compass.yml` at the
repository root as strict YAML and nothing else, and runs no code from it.
The pin is the sha: the ref is a label, a remote ref with no sha is refused,
and the fetched commit must be the pinned one. There is no lock file.

Every refusal is a `ParentError` carrying a lint finding code (`L-PARENT-*`),
so a lint, a check and an effective view name the same cause. Git runs with an
argument list and never through a shell.
"""
# DEPENDENCY: standard library (collections, datetime, hashlib, os, re, shutil,
# subprocess, tempfile); PyYAML (bundled); compass_pkg.atomic_io,
# compass_pkg.layers, compass_pkg.core (CompassError, only).
from __future__ import annotations

import datetime
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from collections import namedtuple

import yaml

from compass_pkg import layers
from compass_pkg.atomic_io import StrictYamlError, atomic_write_text, load_yaml_strict
from compass_pkg.core import CompassError

CACHE = os.path.join(".compass", "cache", "parents")
SEEN = "seen.yml"
PARENT_FILE = "compass.yml"
DEFAULT_BASE = "https://github.com"
BASE_ENV = "COMPASS_PARENT_REMOTE_BASE"
GIT_TIMEOUT = 120
MAX_BYTES = 1024 * 1024

# Owner and repository follow GitHub's own rules, and neither may start with
# `-` or `.`, so no part of the spelling can be read by git as an option.
_OWNER = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
_REPO = r"[A-Za-z0-9_][A-Za-z0-9._-]{0,99}"
_REF = r"[A-Za-z0-9_][A-Za-z0-9._/+-]{0,199}"
_SHA = r"[0-9a-f]{7,40}"
_HEAD = re.compile(rf"github:({_OWNER})/({_REPO})@({_REF})")
_SHA_ONLY = re.compile(_SHA)

GitSpec = namedtuple("GitSpec", "owner repo ref sha")

FORM_HELP = "write github:<owner>/<repo>@<ref>#<40-character sha>"


class ParentError(CompassError):
    """A git parent that cannot be used. `code` is the lint finding code,
    `layer` and `path` say where it is reported: the project's `extends:`
    unless the fault is in the parent's own file."""

    def __init__(self, code, message, layer="project", path="extends"):
        self.code, self.layer, self.path = code, layer, path
        super().__init__(f"{code}: {message}")
        self.detail = message


def extends_value(extends):
    """The text of an `extends:` value: the string, or `from` of the map form."""
    if isinstance(extends, dict):
        extends = extends.get("from")
    return extends


def _ref_is_sound(ref):
    return ".." not in ref and "//" not in ref and not ref.endswith(("/", ".", ".lock"))


def spec_of(extends):
    """`GitSpec` for a git `extends:`, or `None` for the shipped form or no
    `extends:`. Raises `ParentError` for any other spelling, and for a remote
    ref with no sha."""
    value = extends_value(extends)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ParentError("L-PARENT-FORM", f"extends: expected text, found "
                          f"{type(value).__name__}; {FORM_HELP}")
    try:
        layers.parse_extends(value)
        return None
    except CompassError:
        pass
    head, _, sha = value.partition("#")
    found = _HEAD.fullmatch(head) if value.startswith("github:") else None
    if not found or not _ref_is_sound(found.group(3)):
        raise ParentError("L-PARENT-FORM", f"extends: {value!r} is not a supported spelling; "
                          f"{FORM_HELP}, or compass:default@<major>")
    if not sha:
        raise ParentError("L-PARENT-NO-SHA", f"extends: {value!r} names a remote ref with no "
                          f"sha; a remote parent is pinned by commit, so {FORM_HELP}")
    if not _SHA_ONLY.fullmatch(sha):
        raise ParentError("L-PARENT-FORM", f"extends: the sha of {value!r} must be 7 to 40 "
                          f"lowercase hexadecimal characters; {FORM_HELP}")
    return GitSpec(*found.groups(), sha)


# --- the cache -----------------------------------------------------------------------

# One resolved parent. `ref` is `github:<owner>/<repo>@<ref>`, `sha` the full
# commit, `layer` the `layers.Layer` of its `compass.yml` and `digest` the
# digest of that layer.
Parent = namedtuple("Parent", "ref sha version digest layer")


def offline():
    """True when `COMPASS_OFFLINE` asks for the cache to be read and nothing fetched."""
    return os.environ.get("COMPASS_OFFLINE", "").strip().lower() in ("1", "true", "yes")


def _refuse_cache(why):
    return ParentError("L-PARENT-CACHE", f"the parent cache {CACHE} {why}; nothing was "
                       "written or read there")


def _inside_compass(root, path):
    """Defence in depth: the link checks refuse a link in the cache path, and
    this refuses any path that still resolves outside `.compass/`, for example
    because `.compass` itself holds a link further up."""
    compass = os.path.realpath(os.path.join(os.path.abspath(os.fspath(root)), ".compass"))
    real = os.path.realpath(path)
    return real == compass or real.startswith(compass + os.sep)


def cache_dir(root):
    """The cache folder of a project. A link at `.compass/cache` or below it,
    or a path that resolves outside `.compass/`, is refused before anything
    is created or read."""
    base = os.path.abspath(os.fspath(root))
    path = os.path.join(base, CACHE)
    for part in (os.path.dirname(path), path):
        if os.path.islink(part):
            raise _refuse_cache("is a symbolic link")
    if not _inside_compass(base, path):
        raise _refuse_cache("resolves outside .compass/")
    return path


def commit_dir(cache, spec):
    """Where the cache keeps one commit: `<cache>/<owner>/<repo>/<sha>`. The
    repository is part of the key, so a commit cached for one repository is
    never read for another."""
    return os.path.join(cache, spec.owner, spec.repo, spec.sha)


def _cached_file(root, folder):
    """The cached `compass.yml` inside `folder`, refused when the folder, the
    repository folder above it, the owner folder or the file is a link, or
    the file resolves outside `.compass/`."""
    path = os.path.join(folder, PARENT_FILE)
    above = (folder, os.path.dirname(folder), os.path.dirname(os.path.dirname(folder)), path)
    if any(os.path.islink(part) for part in above) or not _inside_compass(root, path):
        raise _refuse_cache("holds a link in place of a cached parent")
    return path


def ref_label(spec):
    return f"github:{spec.owner}/{spec.repo}@{spec.ref}"


def version_of(ref):
    """The ref when it reads as a version (`1.2.0`, `v1.2.0`), else empty."""
    found = re.fullmatch(r"v?(\d+(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?)", ref)
    return found.group(1) if found else ""


def _ignore(root):
    """List the cache in `.compass/.gitignore`, so no project commits it."""
    path = os.path.join(os.path.abspath(os.fspath(root)), ".compass", ".gitignore")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        lines = []
    if "cache/" not in lines:
        atomic_write_text(path, "".join(f"{line}\n" for line in lines) + "cache/\n")


def file_digest(raw):
    """The digest of a cached file's bytes, as `seen.yml` records it."""
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _record_seen(cache, spec, sha, raw):
    path = os.path.join(cache, SEEN)
    try:
        held = load_yaml_strict(path) if os.path.isfile(path) else {}
    except StrictYamlError:
        held = {}
    refs = dict((held or {}).get("refs") or {})
    # `content_digest` is the digest of the commit fetched last. `digests` keeps one
    # per commit, so a cached commit can be checked after another is fetched.
    before = refs.get(ref_label(spec))
    digests = dict(before.get("digests") or {}) if isinstance(before, dict) else {}
    digests[sha] = file_digest(raw)
    refs[ref_label(spec)] = {
        "sha": sha, "content_digest": file_digest(raw), "digests": digests,
        "version": version_of(spec.ref),
        "fetched": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    atomic_write_text(path, yaml.safe_dump({"schema": 1, "refs": refs}, sort_keys=True))


# --- git -----------------------------------------------------------------------------

def remote_base():
    """`(base, local)`: where parents are fetched from. The default is
    GitHub over https. `COMPASS_PARENT_REMOTE_BASE` names a mirror, as an
    https URL or an absolute folder of local repositories."""
    base = os.environ.get(BASE_ENV) or DEFAULT_BASE
    local = os.path.isabs(base)
    clean = base.isprintable() and not any(c in base for c in " \t\\") and not base.startswith("-")
    if not clean or not (local or re.fullmatch(r"https://[A-Za-z0-9._:/-]+", base)):
        raise ParentError("L-PARENT-FETCH", f"{BASE_ENV} must be an https:// URL or an "
                          "absolute folder")
    return base.rstrip("/"), local


def _git(argv, *, cwd, local):
    """Run git with an argument list, never a shell, and an allow-list of the
    caller's environment. `HOME`, `XDG_CONFIG_HOME`, `GIT_CONFIG_GLOBAL`,
    `GIT_CONFIG_NOSYSTEM` and `GIT_ASKPASS` pass on purpose: they bring in
    the user's own git configuration, so the user's credential helper runs
    and their `url.<base>.insteadOf` rules apply. A private repository needs
    that. A variable that moves the repository (`GIT_DIR`), names a helper
    program (`GIT_SSH_COMMAND`, `GIT_EXEC_PATH`) or injects configuration
    (`GIT_CONFIG_COUNT`) does not pass. Git never fetches a missing object
    lazily (`GIT_NO_LAZY_FETCH`), so a file the partial fetch left out is not
    pulled in afterwards."""
    keep = ("PATH", "HOME", "USER", "LANG", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR",
            "GIT_SSL_CAINFO", "GIT_ASKPASS", "XDG_CONFIG_HOME", "GIT_CONFIG_GLOBAL",
            "GIT_CONFIG_NOSYSTEM", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy",
            "NO_PROXY", "no_proxy")
    env = {k: v for k, v in os.environ.items() if k in keep or k.startswith("LC_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_ALLOW_PROTOCOL"] = "https:file" if local else "https"
    options = ["-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
               "-c", f"protocol.file.allow={'always' if local else 'never'}",
               "-c", "transfer.fsckObjects=true", "-c", "core.hooksPath=/dev/null"]
    try:
        return subprocess.run(["git", *options, *argv], cwd=cwd, env=env, shell=False,
                              capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=GIT_TIMEOUT)
    except FileNotFoundError:
        raise ParentError("L-PARENT-FETCH", "git is not installed or not on the PATH") from None
    except subprocess.TimeoutExpired:
        raise ParentError("L-PARENT-FETCH", f"git did not finish in {GIT_TIMEOUT} seconds") \
            from None


def _say(done):
    return " ".join(done.stderr.decode("utf-8", "replace").split())[:300]


def _fetch(cache, spec, local, base):
    """Fetch `spec.sha` into `<cache>/<owner>/<repo>/<sha>/compass.yml`.

    The fetch is partial: blobs of `MAX_BYTES` or more are left out, so the
    one file Compass reads arrives and an unrelated large file does not. A
    partial fetch needs a named remote, which only exists in the scratch
    repository."""
    os.makedirs(cache, exist_ok=True)
    work = tempfile.mkdtemp(prefix=".fetch-", dir=cache)
    try:
        url = f"{base}/{spec.owner}/{spec.repo}.git"
        # An empty template: a configured template folder could copy hooks in.
        steps = (["init", "--quiet", "--bare", "--template=", "."],
                 ["remote", "add", "origin", "--", url],
                 ["fetch", "--quiet", "--depth", "1", "--no-tags", "--no-recurse-submodules",
                  f"--filter=blob:limit={MAX_BYTES}", "--", "origin", spec.sha])
        for argv in steps:
            done = _git(argv, cwd=work, local=local)
            if done.returncode != 0:
                raise ParentError("L-PARENT-FETCH", f"git {argv[0]} of {ref_label(spec)} at "
                                  f"{spec.sha} failed: {_say(done)}")
        head = _git(["rev-parse", "--verify", "--quiet", "FETCH_HEAD"], cwd=work, local=local)
        got = head.stdout.decode("utf-8", "replace").strip()
        if head.returncode != 0 or got != spec.sha:
            raise ParentError("L-PARENT-SHA-MISMATCH", f"{ref_label(spec)} is pinned to "
                              f"{spec.sha}, but the fetch returned {got or 'no commit'}; "
                              "nothing was cached")
        kind = _git(["cat-file", "-t", got], cwd=work, local=local)
        if kind.stdout.strip() != b"commit":
            raise ParentError("L-PARENT-FORM", f"the sha {spec.sha} of {ref_label(spec)} "
                              "does not name a commit (it may be a tree or a file); write the "
                              "sha of the commit")
        # Only the root entry is listed: nothing else in the tree is read.
        listing = _git(["ls-tree", "-z", "-l", spec.sha, "--", PARENT_FILE], cwd=work,
                       local=local)
        if listing.returncode != 0:
            raise ParentError("L-PARENT-FETCH", f"git ls-tree of {spec.sha} failed: "
                              f"{_say(listing)}")
        entry = listing.stdout.split(b"\0")[0]
        meta, _, _path = entry.partition(b"\t")
        fields = meta.split()
        if fields[:1] == [b"120000"]:
            raise ParentError("L-PARENT-SYMLINK", f"{PARENT_FILE} of {ref_label(spec)} at "
                              f"{spec.sha} is a symbolic link; a parent file is a regular "
                              "file, so nothing was cached")
        if fields[1:2] != [b"blob"]:
            raise ParentError("L-PARENT-CONTENT", f"{ref_label(spec)} at {spec.sha} has no "
                              f"{PARENT_FILE} file at its root")
        # The size is a number, or BAD when the partial fetch left the blob out
        # because it is too large.
        size = fields[3] if len(fields) > 3 else b""
        if not size.isdigit() or int(size) >= MAX_BYTES:
            raise ParentError("L-PARENT-CONTENT", f"{PARENT_FILE} of {ref_label(spec)} at "
                              f"{spec.sha} is {MAX_BYTES} bytes or larger")
        read = _git(["cat-file", "blob", fields[2].decode()], cwd=work, local=local)
        if read.returncode != 0:
            raise ParentError("L-PARENT-FETCH", f"git cat-file of {PARENT_FILE} at {spec.sha} "
                              f"failed: {_say(read)}; nothing was cached")
        blob = read.stdout
        folder = os.path.join(work, "out")
        os.mkdir(folder)
        with open(os.path.join(folder, PARENT_FILE), "wb") as fh:
            fh.write(blob)
        final = commit_dir(cache, spec)
        os.makedirs(os.path.dirname(final), exist_ok=True)
        try:
            os.rename(folder, final)
        except OSError:
            # Another run cached the same commit first. That is fine when its
            # file is the one fetched here, and a fault when it is not.
            try:
                with open(os.path.join(final, PARENT_FILE), "rb") as fh:
                    same = fh.read() == blob
            except OSError:
                same = False
            if not same:
                raise _refuse_cache(f"already holds a different file for {spec.sha}") \
                    from None
        _record_seen(cache, spec, spec.sha, blob)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _full_sha(cache, spec):
    """The one cached commit of this repository that a short sha names. Git
    fetches a full sha only, so a short sha that names no cached commit is
    refused, and one that names two is ambiguous. Commits cached for another
    repository are not considered."""
    try:
        held = sorted(name for name in os.listdir(os.path.join(cache, spec.owner, spec.repo))
                      if re.fullmatch(r"[0-9a-f]{40}", name) and name.startswith(spec.sha))
    except OSError:
        held = []
    if len(held) > 1:
        raise ParentError("L-PARENT-SHA-AMBIGUOUS", f"the sha {spec.sha} of {ref_label(spec)} "
                          f"names {len(held)} cached commits ({', '.join(held)}); write all "
                          "40 characters")
    if not held:
        raise ParentError("L-PARENT-FORM", f"the sha {spec.sha} of {ref_label(spec)} is short "
                          "and names no cached commit; git fetches a full sha only, so write "
                          "all 40 characters")
    return held[0]


def resolve(root, extends, *, fetch=False):
    """The `Parent` a project's `extends:` names, or `None` for the shipped
    form. With `fetch` an uncached commit is fetched; without it the cache is
    all that is read."""
    spec = spec_of(extends)
    if spec is None:
        return None
    cache = cache_dir(root)
    if len(spec.sha) < 40:
        spec = spec._replace(sha=_full_sha(cache, spec))
    folder = commit_dir(cache, spec)
    if not os.path.isdir(folder) and not os.path.islink(folder):
        if not fetch:
            raise ParentError("L-PARENT-NOT-CACHED", f"{ref_label(spec)} at {spec.sha} is "
                              "not in the cache; run compass policy lint with network access")
        base, local = remote_base()
        _fetch(cache, spec, local, base)
        _ignore(root)
    path = _cached_file(root, folder)
    try:
        doc = load_yaml_strict(path)
    except StrictYamlError as exc:
        raise ParentError("L-LOAD", str(exc).replace(os.path.abspath(path), PARENT_FILE)) \
            from None
    name = f"{ref_label(spec)}#{spec.sha[:7]}"
    if not isinstance(doc, dict):
        raise ParentError("L-SCHEMA", f"parent layer: expected a mapping, found "
                          f"{type(doc).__name__}", name, PARENT_FILE)
    for where, key in layers.non_text_keys(doc):
        raise ParentError("L-KEY-NOT-TEXT", layers.non_text_key_message(key), name, where)
    try:
        inner = spec_of(doc.get("extends"))
    except ParentError as exc:
        raise ParentError(exc.code, f"the parent's own {exc.detail}", name, "extends") from None
    if inner:
        raise ParentError("L-PARENT-CHAIN", f"the parent names a git parent of its own "
                          f"({ref_label(inner)}); chains of git parents are not built yet, so "
                          "a parent may extend only compass:default@<major>", name, "extends")
    layer = layers.Layer(name, "parent", doc, layers.layer_digest(doc, "parent"))
    return Parent(ref_label(spec), spec.sha, version_of(spec.ref), layer.digest, layer)
