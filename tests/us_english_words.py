"""The word list and the scans of the US English guard.

`US_FORMS` is the one table of British words and their US forms. `WORDS` is
its keys. The guard test, the CLI message pass and the 7.1.0 conversion
script all read this table, so a word is added in one place.

The list holds specific words, not a pattern, so a code identifier or a word
that GitHub spells itself (`cancelled`, `towards`) cannot be a hit. A word
matches whole and in any case: `behavioural` is a hit and `behaviourism` is
not.

An exemption is a marker on the line it covers, with a reason. The marker
covers its own line only, never a file.
"""
from __future__ import annotations

import ast
import io
import os
import re
import tokenize

# British form -> US form. Keep one word to a line.
US_FORMS = {
    "behaviour": "behavior",
    "behaviours": "behaviors",
    "behavioural": "behavioral",
    "judgement": "judgment",
    "judgements": "judgments",
    "catalogue": "catalog",
    "catalogues": "catalogs",
    "initialise": "initialize",
    "initialised": "initialized",
    "initialising": "initializing",
    "initialisation": "initialization",
    "colour": "color",
    "colours": "colors",
    "labelled": "labeled",
    "labelling": "labeling",
    "normalise": "normalize",
    "normalised": "normalized",
    "recognise": "recognize",
    "recognised": "recognized",
    "honour": "honor",
    "honoured": "honored",
    "licence": "license",
    "spelt": "spelled",
    "organise": "organize",
    "organisation": "organization",
    "analyse": "analyze",
    "analysed": "analyzed",
    "centre": "center",
    "favour": "favor",
    "artefact": "artifact",
    "whilst": "while",
    "centrepiece": "centerpiece",
}
WORDS = tuple(US_FORMS)

# The marker covers its own line and needs a reason of at least one word.
MARKER = "us-english-scan: allow - "
NOT_NEEDED = "<exemption not needed>"
NO_REASON = "<exemption has no reason>"

# Path prefixes the guard never reads: the frozen file classes. The
# file test_frozen_files_unchanged.py proves each class is unchanged.
EXCLUDED = (
    "governance/decisions/",
    "architecture/decisions/",
    "governance/presets/default@6",
    "governance/shipped-releases.tar.xz",
    "tests/fixtures/compat/",
    "cli/vendor",
)

_WORD = re.compile(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")\b",
                   re.IGNORECASE)
_MARKER_PREFIX = re.compile(r"us-english-scan: allow")
_MARKER_FULL = re.compile(r"us-english-scan: allow - (?P<reason>.*)")
_CLOSERS = re.compile(r"(-->|\*/|\"\"\"|'''|\"|')\s*$")
