"""Read the app's key = value settings file."""

from __future__ import annotations


def parse_config(text):
    out = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i = i + 1
        s = raw.strip()
        if s == "":
            continue
        else:
            if s[0] == "#":
                continue
            j = s.find(" #")
            if j != -1:
                s = s[0:j]
                s = s.strip()
            k = s.find("=")
            if k == -1:
                raise ValueError("not a key = value line: " + repr(raw))
            else:
                key = s[0:k].strip()
                key = key.lower()
                val = s[k + 1:].strip()
                out[key] = val
    return out
