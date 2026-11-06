# compass_pkg.check_set - the one fixed check set every project runs
"""Read `governance/check-set.yml`, the fixed check set (ADR-094).

The file holds every check, gate and evidence type Compass runs. One file has
one `sha256sum`, so a change can name its rules by one id, one version and one
digest: `compass-checks@9.0.0` and the digest `sha256` gives.

- `load` reads the file and checks its shape.
- `sha256` is the lowercase hex digest of the file's bytes, as `sha256sum`
  prints it.
- `ref` is `<id>@<version>`.
- `resolved` returns the set in the shape `generations/<n>/resolved.yml`
  holds, so every reader of `EffectiveView` and every stored generation reads
  it the same way.

`resolved` leaves out the file's own keys (`id`, `version`, `never_waived`,
`optional`) and returns the display names as `vocabulary`. The entries under
`optional` run only when a project turns them on with a tighten-only setting
of `compass.yml`.

Nothing reads this module yet. `effective.resolve_live` still resolves the
default preset; `tests/test_check_set.py` checks that the two give the same
configuration.
"""
# DEPENDENCY: standard library (copy, hashlib, os); compass_pkg.atomic_io
# (load_yaml_strict), core (CompassError, FRAMEWORK_ROOT).
from __future__ import annotations

import copy
import hashlib
import os

from compass_pkg.atomic_io import load_yaml_strict
from compass_pkg.core import FRAMEWORK_ROOT, CompassError

PATH = os.path.join("governance", "check-set.yml")
ID = "compass-checks"

#: The catalogues of the set, in the order `resolved.yml` holds them. The 8.x
#: catalogues `artifacts` and `readiness` are empty since ADR-091 and ADR-093,
#: and the set does not declare them.
CATALOGUES = ("dimensions", "stages", "approaches", "rules", "checks", "gates")
#: The file's keys besides the catalogues. `names` is returned as `vocabulary`.
OWN_KEYS = ("schema", "id", "version", "capabilities", "never_waived", "evidence_types",
            "names", "optional")
#: The settings that can turn on an entry under `optional`.
OPTIONAL = ("agent_review",)


def path(root=None):
    """The file's path under `root`, the framework's root by default."""
    return os.path.join(root or FRAMEWORK_ROOT, PATH)


def sha256(file=None):
    """The lowercase hex sha256 of the file's bytes, as `sha256sum` prints it."""
    with open(file or path(), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _problems(doc):
    """What is wrong with the shape of a loaded check set, as a list of strings."""
    if not isinstance(doc, dict):
        return ["the file is not a mapping"]
    out = [f"unknown key '{key}'" for key in doc if key not in CATALOGUES + OWN_KEYS]
    out += [f"missing key '{key}'" for key in CATALOGUES + OWN_KEYS if key not in doc]
    if doc.get("schema") != 1:
        out.append("schema must be 1")
    if doc.get("id") != ID:
        out.append(f"id must be '{ID}'")
    if not isinstance(doc.get("version"), str) or len(str(doc.get("version")).split(".")) != 3:
        out.append("version must be a string MAJOR.MINOR.PATCH")
    for key in CATALOGUES + ("capabilities", "evidence_types", "names", "optional"):
        if key in doc and not isinstance(doc[key], dict):
            out.append(f"'{key}' must be a mapping")
    for key in doc.get("optional") or {}:
        if key not in OPTIONAL:
            out.append(f"optional entry '{key}' is not one of {', '.join(OPTIONAL)}")
    out += _locked(doc, "")
    never = doc.get("never_waived")
    if not isinstance(never, list):
        out.append("'never_waived' must be a list")
        never = []
    for name in never:
        catalogue, _, entry = str(name).partition(".")
        if catalogue not in CATALOGUES or entry not in (doc.get(catalogue) or {}):
            out.append(f"never_waived names '{name}', which the set does not hold")
    return out


def _locked(node, where):
    """A `locked:` anywhere is refused: no layer sits above the set, so there is
    nothing for a lock to hold back."""
    if isinstance(node, dict):
        found = [f"{where or 'the file'} holds 'locked'"] if "locked" in node else []
        for key, value in node.items():
            found += _locked(value, f"{where}.{key}" if where else str(key))
        return found
    if isinstance(node, list):
        return [p for value in node for p in _locked(value, where)]
    return []


def load(file=None):
    """The check set as a mapping. Raises `CompassError` when the file is missing,
    does not parse or does not have the shape of a check set."""
    file = file or path()
    if not os.path.isfile(file):
        raise CompassError(f"the check set {file} is missing")
    doc = load_yaml_strict(file)
    problems = _problems(doc)
    if problems:
        raise CompassError(f"the check set {file} is not valid: " + "; ".join(problems))
    return doc


def ref(doc=None):
    """`<id>@<version>`, the name a change gives its rules."""
    doc = doc if doc is not None else load()
    return f"{doc['id']}@{doc['version']}"


def resolved(doc=None, autonomy="balanced"):
    """The set in the shape `generations/<n>/resolved.yml` holds: `capabilities`,
    `approach`, `autonomy`, `conformance`, the catalogues and `evidence_types`.
    No issue names an approach, and no lock exists to be unlocked, so `approach`
    is None and `conformance` is always conformant. The mapping is a copy: a
    caller can change it."""
    doc = copy.deepcopy(doc if doc is not None else load())
    out = {
        "capabilities": dict(doc["capabilities"]),
        "approach": None,
        "autonomy": autonomy,
        "conformance": {"status": "conformant", "unlocked": []},
        **{name: doc[name] for name in CATALOGUES},
        "vocabulary": doc["names"],
        "evidence_types": doc["evidence_types"],
    }
    return out
