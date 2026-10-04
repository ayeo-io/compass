"""Find and replace rival product names without naming them.

A project can keep a names key: a private file, never committed, that maps
codes such as R1 to a rival product's name, aliases and URLs. Committed text
uses the codes. This module gives three things from the key:

- hashes of every entry, which can be committed because they name nothing;
- `scan`, which finds an entry in text from those hashes alone, so CI can
  check text without the key;
- `redact_names`, which replaces each entry with its code, for the delivery
  record.

Matching is on tokens, runs of ASCII letters and digits, so a name matches
whatever joins its words (a space, hyphen, underscore, dot or slash), and a
name inside a longer word does not match.
"""
# DEPENDENCY: standard library (hashlib, os, re) and compass_pkg.core.
from __future__ import annotations

import hashlib
import os
import re

from compass_pkg.core import CompassError, load_yaml

#: Where the committed hashes live, from the project root. Not under
#: `governance/`, which `init` copies into adopter projects.
HASHES_PATH = os.path.join("scripts", "rival-name-hashes.txt")

#: Literal strings that are not a rival's name although they end with one
#: of its aliases. Each is replaced by a space before matching.
#: `implement-specs`: the backlog command's own file name ends with an alias
#: of R2.
ALLOWED_COMPOUNDS = ("implement-specs",)

_TOKEN = re.compile(r"[A-Za-z0-9]+")


def tokens(text):
    """The lower-cased ASCII alphanumeric runs of `text`, in order. Matched
    before lower-casing: a few non-ASCII letters, such as the Kelvin sign,
    lower-case to ASCII ones, and `mask` and `redact_names` would not see
    them as part of a name."""
    return [token.lower() for token in _TOKEN.findall(text)]


def _without_allowed(text, allowed):
    """`text` with each allowed compound blanked to spaces of the same
    length, so offsets into the result are offsets into `text`."""
    for compound in allowed:
        text = re.sub(re.escape(compound), lambda m: " " * len(m.group(0)),
                      text, flags=re.IGNORECASE)
    return text


def readable_text(data):
    """The text the gate and record sync both scan in a file's bytes:
    UTF-8 as it is, and any other file as its printable runs of four or
    more characters, as `strings` reads them. A name in an image's metadata
    is still found; compressed bytes that happen to spell a short alias are
    not."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return "\n".join(run.decode("ascii")
                         for run in re.findall(rb"[\x20-\x7e]{4,}", data))


def _digest(token_list):
    return hashlib.sha256(" ".join(token_list).encode("utf-8")).hexdigest()


# --- the key -------------------------------------------------------------------

def load_key(path):
    """`{code: [entry, ...]}` from a names key, where each entry is a name,
    alias or URL. Refuses a key that is missing or malformed."""
    if not path or not os.path.isfile(path):
        raise CompassError(f"the names key {path} is missing")
    try:
        data = load_yaml(path)
    except Exception as exc:                                # noqa: BLE001
        raise CompassError(f"the names key {path} cannot be read: {exc}")
    rivals = (data or {}).get("rivals") if isinstance(data, dict) else None
    if not isinstance(rivals, dict) or not rivals:
        raise CompassError(f"the names key {path} has no `rivals:` mapping")
    key = {}
    for code, entry in rivals.items():
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise CompassError(f"the names key {path}: {code} has no name")
        found = [entry["name"]]
        for field in ("aliases", "urls"):
            values = entry.get(field) or []
            if not isinstance(values, list) or \
                    not all(isinstance(v, str) for v in values):
                raise CompassError(
                    f"the names key {path}: {code}'s {field} is not a list")
            found += values
        key[str(code)] = found
    return key


def _entries(key):
    """Each entry as `(token list, code)`, with each multi-token entry's
    joined spelling added, longest first."""
    seen = {}
    for code, values in key.items():
        for value in values:
            parts = tokens(value)
            if not parts:
                continue
            seen.setdefault(tuple(parts), code)
            if len(parts) > 1:
                seen.setdefault(("".join(parts),), code)
    return sorted(((list(t), c) for t, c in seen.items()),
                  key=lambda e: (-sum(map(len, e[0])), e[0]))


def hash_lines(key):
    """The hash file's lines: each entry's token count and hash, sorted."""
    return sorted({f"{len(t)} {_digest(t)}" for t, _ in _entries(key)})


def write_hash_file(key, path):
    lines = ["# Hashes of rival product names, aliases and URLs, one per line:",
             "# the entry's token count, then SHA-256 of its lower-cased",
             "# alphanumeric tokens joined by one space. Generated by",
             "# `scripts/rival-name-gate.py --write-hashes <key>`; the key is",
             "# held by the maintainer and never committed."]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines + hash_lines(key)) + "\n")


def load_hashes(path):
    """`{token count: {hash, ...}}` from a hash file."""
    hashes = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            count, digest = line.split()
            hashes.setdefault(int(count), set()).add(digest)
    return hashes


def hashes_from_key(key):
    hashes = {}
    for line in hash_lines(key):
        count, digest = line.split()
        hashes.setdefault(int(count), set()).add(digest)
    return hashes


# --- scanning ------------------------------------------------------------------

def _hits(token_list, hashes):
    """Each `(start, length)` span of `token_list` whose hash is listed."""
    found = []
    for count, digests in hashes.items():
        for start in range(len(token_list) - count + 1):
            if _digest(token_list[start:start + count]) in digests:
                found.append((start, count))
    return found


def scan(text, hashes, allowed=ALLOWED_COMPOUNDS):
    """The line numbers of `text` where a listed entry occurs. A name
    wrapped across two lines is found, and reported at its first line."""
    lines = [tokens(_without_allowed(line, allowed))
             for line in text.split("\n")]
    reach = max(hashes, default=1) - 1
    found = set()
    for index, line in enumerate(lines):
        if _hits(line, hashes):
            found.add(index + 1)
        elif reach and index + 1 < len(lines):
            # Only the tokens near the join, so a span found here crosses
            # it; one inside the next line is reported at that line.
            tail, head = line[-reach:], lines[index + 1][:reach]
            if any(start < len(tail) < start + count
                   for start, count in _hits(tail + head, hashes)):
                found.add(index + 1)
    return sorted(found)


def mask(text, hashes, allowed=ALLOWED_COMPOUNDS):
    """`text` with each listed entry replaced by `[name]`, so a finding can
    show where it is without showing the name."""
    spans = list(re.finditer(r"[A-Za-z0-9]+", _without_allowed(text, allowed)))
    token_list = [m.group(0).lower() for m in spans]
    # Character ranges of every hit, merged where they overlap, so a longer
    # name that contains a shorter one is masked whole.
    ranges = sorted((spans[start].start(), spans[start + count - 1].end())
                    for start, count in _hits(token_list, hashes))
    merged = []
    for begin, end in ranges:
        if merged and begin <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([begin, end])
    out, last = [], 0
    for begin, end in merged:
        out.append(text[last:begin] + "[name]")
        last = end
    return "".join(out) + text[last:]


# --- redaction -----------------------------------------------------------------

def redact_names(text, key, allowed=ALLOWED_COMPOUNDS):
    """`text` with every entry in `key` replaced by its code."""
    held = {}

    def hold(match):
        # Private-use characters, never letters or digits, so a marker
        # cannot join a name next to it into one token.
        marker = "\ue000" + chr(0xe100 + len(held)) + "\ue000"
        held[marker] = match.group(0)
        return marker

    for compound in allowed:
        text = re.sub(re.escape(compound), hold, text, flags=re.IGNORECASE)
    for parts, code in _entries(key):
        pattern = (r"(?<![A-Za-z0-9])"
                   + r"[^A-Za-z0-9]+".join(map(re.escape, parts))
                   + r"(?![A-Za-z0-9])")
        # ASCII only: under Unicode rules a long s matches "s" without case.
        text = re.sub(pattern, code, text, flags=re.IGNORECASE | re.ASCII)
    for marker, original in held.items():
        text = text.replace(marker, original)
    return text
