#!/usr/bin/env python3
# =============================================================================
# compass - remove credentials from text before it is recorded
# =============================================================================
# An unattended run copies a session's error output into its run record and
# the manifest. An error message can carry a credential, and a record is
# read, committed and shared, so every piece of text `compass run` writes or
# prints passes through `redact` first.
#
# Two kinds are removed: text shaped like a known credential, and the value
# of any environment variable whose name says it is a key, token, secret or
# password. Matching shapes is a fixed list: it catches the common forms,
# not every one, which is why the environment values are removed as well.
#
# DEPENDENCY: standard library (os, re).
# =============================================================================
"""`redact(text)`: the text with credentials replaced by `[REDACTED]`."""
from __future__ import annotations

import os
import re

MARK = "[REDACTED]"

#: Credential shapes: Anthropic and GitHub tokens, AWS access key ids,
#: bearer tokens, and `key=value` or `key: value` pairs whose key names a
#: secret. The pair keeps its key and loses its value.
_SHAPES = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)(\b[\w-]*(?:api[_-]?key|token|secret|password)[\w-]*"
               r"[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]{4,}"),
)

#: An environment variable whose name contains one of these words holds a
#: value worth hiding.
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD", re.IGNORECASE)

#: Values shorter than this are not removed: a two-letter value would
#: blank ordinary words all through the text.
_MIN_VALUE = 8


def redact(text, env=None):
    """`text` with every credential shape, and every value of a secret-named
    environment variable in `env` (the process environment by default),
    replaced by `[REDACTED]`."""
    if not text:
        return text or ""
    env = os.environ if env is None else env
    values = sorted({v for k, v in env.items()
                     if _SECRET_NAME.search(k) and len(v or "") >= _MIN_VALUE},
                    key=len, reverse=True)
    for value in values:
        text = text.replace(value, MARK)
    for shape in _SHAPES:
        if shape.groups:
            text = shape.sub(lambda m: m.group(1) + MARK, text)
        else:
            text = shape.sub(MARK, text)
    return text
