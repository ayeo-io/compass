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
# password. Only values are removed, never a key name. Matching shapes is a fixed list: it catches the common forms,
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
#:
#: A pair's key must end in the secret word (`password`, `GITHUB_TOKEN`,
#: `client_secret`) and its value must be on the same line. Otherwise a key
#: that only contains the word, such as `secret-scan-declared` or
#: `input_tokens`, would lose its value or the key on the next line, and a
#: record copied to the delivery record would no longer equal its source.
_SECRET_KEY = (r"(?:api|secret|access|private)[_-]?key|token|secret"
               r"|password|passwd")
_SHAPES = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)(\b(?:[\w-]*[_-])?(?:" + _SECRET_KEY + r")"
               r"[\"']?[ \t]*[:=][ \t]*[\"']?)[^\s\"',;]{4,}"),
)

#: A YAML key that names a secret and whose value is empty or a block
#: scalar indicator (`|`, `|-`, `>`, `>-`, `|2-` and the like). Its value is
#: on the more-indented lines that follow, where no shape above would see it.
_BLOCK_KEY = re.compile(r"(?i)^([ \t]*)(?:-[ \t]+)?[\"']?(?:[\w-]*[_-])?(?:"
                        + _SECRET_KEY + r")[\"']?[ \t]*:"
                        r"[ \t]*(?:[|>][0-9+-]{0,2})?[ \t]*$")

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
    text = _redact_blocks(text)
    for shape in _SHAPES:
        if shape.groups:
            text = shape.sub(lambda m: m.group(1) + MARK, text)
        else:
            text = shape.sub(MARK, text)
    return text


def _redact_blocks(text):
    """`text` with each line of a block value under a secret-named key
    replaced by `[REDACTED]` at its own indentation. The block ends at the
    first non-blank line indented no more than the key, so a sibling key on
    the next line is left as it is."""
    lines = text.split("\n")
    key_indent = None
    for i, line in enumerate(lines):
        stripped = line.lstrip(" \t")
        indent = len(line) - len(stripped)
        if key_indent is not None:
            if not stripped:
                continue
            if indent > key_indent:
                lines[i] = line[:indent] + MARK
                continue
            key_indent = None
        match = _BLOCK_KEY.match(line)
        if match:
            key_indent = len(match.group(1))
    return "\n".join(lines)
