# compass_pkg.preset_init - `compass policy init-preset`: scaffold a team preset
"""Write the files of a new preset repository.

A preset is a folder with a `compass.yml` that other projects extend as a git
parent, and a `compass-fixtures/` folder that `compass policy test` runs. The
scaffold is a working preset: it passes `policy test` where it stands, and it
makes one change to the shipped default, so its example fixture shows a real
difference. The command never overwrites a file: it refuses and writes
nothing when any of its files exists. `docs/policy-test.md` owns the contract.
"""
# DEPENDENCY: standard library (json, os), yaml; compass_pkg.core
# (CompassError), layers, obligations, policy_lint, preset_test (FIXTURE_DIR,
# JSON_SCHEMA_VERSION, resolve, shown).
from __future__ import annotations

import json
import os

import yaml

from compass_pkg import layers, obligations, policy_lint
from compass_pkg.core import CompassError
from compass_pkg.preset_test import FIXTURE_DIR, JSON_SCHEMA_VERSION, resolve, shown

COMPASS_YML = """\
# A team preset. Other projects extend this file as a git parent:
#   extends: github:<owner>/<repo>@<ref>#<sha>
# A preset is data only: it cannot carry unlock:, a settings key or an impl
# that the check registry does not hold. Run `compass policy test` after every
# change.
schema: 1
owner: {owner}
# Add or set entries in approaches, checks, gates, stages and rules here.
# This example makes the quick fix approach also run the clarity review.
approaches:
  quick-fix:
    set:
      gates: {{add: [verify.clarity]}}
"""

EXAMPLE_FIXTURE = """\
# One fixture: an assessment, and what the preset must compute for it.
# `expect` holds any of approach, gates (the exact set), stages (only the
# stages named) and checks (the exact set the gates in force run).
name: Small contained work also gets the clarity review
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
  labels: []
expect:
  approach: quick-fix
  gates: [{gates}]
  stages: {{implement: full}}
"""

# The assessment of the example fixture. The fixture's gates are computed from
# the scaffold's own `compass.yml` over the shipped default, so the example
# stays true when the shipped default changes.
EXAMPLE_ASSESSMENT = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
                      "goal": "delivery", "role": "engineer", "labels": []}

README = """\
# {owner} Compass preset

A Compass preset: the `compass.yml` in this repository changes the shipped
default, and other projects extend it as a git parent.

## Test it

```
compass policy test
```

The command lints `compass.yml` as a parent, so it fails on `unlock:`, a
settings key, an `impl` that the check registry does not hold and a change to
a locked entry. It then runs each file in `compass-fixtures/` and reports
whether the approach, gates, stages and checks match the fixture. Exit 0
passes, 1 fails, 2 means an input could not be read. `--json` prints a
documented report for CI.

## Write fixtures

One `.yml` file in `compass-fixtures/` is one fixture: an `assessment` and an
`expect`. `compass-fixtures/example.yml` shows all four things `expect` can
hold. The format is in `docs/policy-test.md` in the Compass repository.

## Use it in a project

Pin a commit of this repository in the project's `compass.yml`:

```
extends: github:<owner>/<repo>@<ref>#<sha>
```

The ref is a label for people and the sha is the pin. `docs/git-parents.md` in
the Compass repository describes how a pinned parent is fetched and cached.
"""

# Relative path of each file the scaffold writes, in the order they are listed.
FILES = (".gitignore", "README.md", f"{FIXTURE_DIR}/example.yml", "compass.yml")


def _example_gates(compass_yml):
    """The gates in force for the example assessment under the scaffold's
    `compass.yml`, sorted, as the example fixture lists them."""
    parent, _ = policy_lint.load_parent()
    doc = yaml.safe_load(compass_yml)
    preset = layers.Layer("preset", "parent", doc, layers.layer_digest(doc, "parent"))
    config, capabilities = resolve([parent, preset])
    owed = obligations.obligations(config, EXAMPLE_ASSESSMENT, capabilities=capabilities)
    return sorted(owed.gate_set)


def _contents(owner):
    compass_yml = COMPASS_YML.format(owner=json.dumps(owner))   # a quoted string is YAML
    gates = ", ".join(_example_gates(compass_yml))
    return {".gitignore": ".compass/\n", "README.md": README.format(owner=owner),
            f"{FIXTURE_DIR}/example.yml": EXAMPLE_FIXTURE.format(gates=gates),
            "compass.yml": compass_yml}


def scaffold(folder, owner):
    """`(result, files)`: `("written", every file)` or `("refused", the files
    that already exist)`. Nothing is written on a refusal."""
    owner = (owner or "").strip()
    if not owner:
        raise CompassError("--owner needs the name of the team that owns the preset")
    folder = os.fspath(folder)
    if os.path.exists(folder) and not os.path.isdir(folder):
        raise CompassError(f"{shown(folder)}: not a folder")
    present = [name for name in FILES if os.path.lexists(os.path.join(folder, name))]
    if present:
        return "refused", present
    try:
        for name, text in _contents(owner).items():
            path = os.path.join(folder, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "x", encoding="utf-8") as fh:
                fh.write(text)
    except OSError as exc:
        raise CompassError(f"{shown(folder)}: cannot write the preset: {exc.strerror}") from exc
    return "written", list(FILES)


def report_json(folder, result, files):
    return {"schema": JSON_SCHEMA_VERSION, "dir": shown(folder), "result": result,
            "files": files}


def text(folder, result, files):
    if result == "refused":
        return [f"compass policy init-preset: refused; {shown(folder)} already holds "
                f"{', '.join(files)}", "  nothing was written"]
    return [f"compass policy init-preset: wrote a preset in {shown(folder)}"] + [
        f"  {name}" for name in files]
