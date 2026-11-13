#!/usr/bin/env python3
# =============================================================================
# compass - the issue's SHA256SUMS file
# =============================================================================
# A record's `content_digest` is a digest of re-serialized JSON, which only
# Compass can recompute, and a file cannot hold the digest of its own bytes.
# So the CLI writes `evidence/SHA256SUMS` beside the records, in the format
# `sha256sum` reads, with each path relative to the project root (ADR-089).
# A reviewer runs, from the project root:
#
#     sha256sum -c .compass/work/<slug>/evidence/SHA256SUMS
#
# It holds one line for each record file the CLI's evidence writer wrote,
# with the digest of the bytes written, and one line for each of the issue's
# files in the `file_sha256` of the record written last. A test corrected
# between its red and its green is listed with its green-time digest, and a
# file deleted or renamed since the red is not listed, so a normal red, code,
# green issue passes; the red record keeps the red-time digests.
#
# Compass does not read this file to judge anything. `content_digest` stays
# the identity check (ADR-086); this file is for a reader without Compass.
#
# DEPENDENCY: standard library (hashlib, os) and compass_pkg.atomic_io,
# compass_pkg.core and compass_pkg.red_first.
# =============================================================================
"""Write the issue's `evidence/SHA256SUMS` after each record."""
from __future__ import annotations

import hashlib
import os

from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import find_upwards
from compass_pkg.red_first import load_record

NAME = "SHA256SUMS"


def _escape(path):
    """`sha256sum`'s form of a name: one with a backslash, a newline or a
    carriage return is escaped, and its line starts with a backslash."""
    if not any(c in path for c in "\\\n\r"):
        return "", path
    return "\\", path.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _unescape(flag, path):
    if not flag:
        return path
    out, i = [], 0
    while i < len(path):
        if path[i] == "\\" and i + 1 < len(path):
            out.append({"n": "\n", "r": "\r", "\\": "\\"}.get(path[i + 1], path[i + 1]))
            i += 2
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


def _line(digest, path):
    flag, name = _escape(path)
    return "%s%s  %s\n" % (flag, digest, name)


#: The public name of the sum line, which `trail.md` writes in the same form.
sum_line = _line


def _read(path):
    """`{path: digest}` from an existing sums file, or {}."""
    try:
        with open(path, encoding="utf-8", newline="\n") as fh:
            lines = fh.read().split("\n")
    except (OSError, ValueError):
        return {}
    out = {}
    for line in lines:
        flag = line.startswith("\\")
        body = line[1:] if flag else line
        digest, sep, name = body.partition("  ")
        if sep and len(digest) == 64:
            out[_unescape(flag, name)] = digest
    return out


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def record_written(task_dir, record_path):
    """Rewrite the sums file after the CLI wrote `record_path`. Outside a
    project, or when the file cannot be written, nothing is written: the
    record itself is the evidence, and this file only helps a reader."""
    root = find_upwards(task_dir, ".compass")
    if not root:
        return None
    root = os.path.realpath(root)
    evidence = os.path.realpath(os.path.dirname(record_path))
    sums = os.path.join(evidence, NAME)
    prefix = os.path.relpath(evidence, root) + os.sep
    held = _read(sums)
    records = {p: d for p, d in held.items()
               if p.startswith(prefix) and os.path.isfile(os.path.join(root, p))}
    try:
        written = os.path.relpath(os.path.realpath(record_path), root)
        records[written] = _sha256(os.path.join(root, written))
    except OSError:
        return None
    # The file lines are the files as the record written last saw them. A
    # record that holds no `file_sha256` (outside git, or an older format)
    # keeps the lines already there. Taking every path from the record
    # written last, not the newest record per path, drops a file the issue
    # deleted or renamed since an earlier record, and does not hang on
    # timestamps, which carry only the second.
    files = {p: d for p, d in held.items() if not p.startswith(prefix)}
    digests = load_record(os.path.join(root, written)).get("file_sha256")
    if isinstance(digests, dict):
        files = {p: d for p, d in digests.items()
                 if isinstance(p, str) and isinstance(d, str) and len(d) == 64}
    lines = [_line(d, p) for p, d in sorted(records.items())]
    lines += [_line(d, p) for p, d in sorted(files.items()) if p not in records]
    try:
        atomic_write_text(sums, "".join(lines), newline="")
    except OSError:
        return None
    return sums
