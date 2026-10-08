# compass_pkg.layers - find and load configuration layers, build the chain
"""Where a configuration layer comes from, and the chain they form.

A project states its differences from a parent in one file, `compass.yml`
(ADR-043), and an issue states its own in its manifest's `config:`
(ADR-036). This module finds and loads those layers, accepts a parent
handed in as data (the shipped preset is read by a later increment, ADR-042),
checks each layer alone, and builds the chain with a digest per layer. It
does not merge, and it reads no network and writes no file.

Settings keys (`autonomy`, `adoption` and the rest) belong to the project's
own file. They are split off before anything else, never reach the chain's
layer, and never count towards a digest: a settings change must not look
like a change to the configuration an issue was classified against.
"""
# DEPENDENCY: standard library (os); compass_pkg.atomic_io,
# compass_pkg.catalogue_check, compass_pkg.catalogue_spec,
# compass_pkg.core (CompassError, only).
from __future__ import annotations

import os
from collections import namedtuple

from compass_pkg import catalogue_check, catalogue_spec as spec
from compass_pkg.atomic_io import StrictYamlError, digest, load_yaml_strict
from compass_pkg.core import BOUNDARY_MARKERS, CompassError

PROJECT_FILE = "compass.yml"

# One link of the chain: `name` shows in provenance, `kind` is `parent`,
# `project` or `issue` (what the layer may do), `doc` is the parsed layer
# and `digest` is over its content as `layer_digest` defines it.
Layer = namedtuple("Layer", "name kind doc digest")


def find_project_root(start):
    """The first folder at or above `start` holding `.compass` or `.git`,
    or `start` itself when none does. The project file is looked for there
    only: one in any other folder is ignored."""
    here = os.path.abspath(os.fspath(start))
    node = here
    while True:
        if any(os.path.exists(os.path.join(node, m)) for m in BOUNDARY_MARKERS):
            return node
        up = os.path.dirname(node)
        if up == node:
            return here
        node = up


def split_project_file(doc):
    """`(layer, settings)`: the settings keys of a project file, and
    everything else. A key in neither group stays in the layer so the
    structural check names it."""
    settings = {k: v for k, v in doc.items() if k in spec.SETTINGS_KEYS}
    layer = {k: v for k, v in doc.items() if k not in spec.SETTINGS_KEYS}
    return layer, settings


TOP_LEVEL = "(top level)"

# What a person typed to get each non-text key. YAML reads `on`, `yes` and
# `true` as True, so the key as written is not recoverable; the example
# shows the quoted form of the most common spelling.
_QUOTE_EXAMPLE = {True: "on", False: "off", None: "null"}


def non_text_keys(doc, path=""):
    """`[(dotted path of the mapping, key)]` for every mapping key anywhere
    in `doc` that is not text. YAML reads an unquoted `on:`, `no:`, `true:`
    or `1:` as a boolean or a number, and a mapping that mixes those with
    text keys cannot be sorted for a digest. List positions show as `[n]`."""
    found = []
    if isinstance(doc, dict):
        for key, value in doc.items():
            if not isinstance(key, str):
                found.append((path or TOP_LEVEL, key))
            found += non_text_keys(value, f"{path}.{key}" if path else str(key))
    elif isinstance(doc, (list, tuple)):
        for n, item in enumerate(doc):
            found += non_text_keys(item, f"{path}[{n}]")
    return found


def non_text_key_message(key):
    """What to tell the person about one non-text key: what YAML read it
    as, and how to write it as text."""
    if key is None or isinstance(key, bool):
        kind, example = ("nothing (null)" if key is None else "a boolean"), \
            _QUOTE_EXAMPLE[key]
    else:
        kind = "a number" if isinstance(key, (int, float)) else f"a {type(key).__name__}"
        example = str(key)
    return (f"the key {key!r} is not text: YAML read it as {kind}. "
            f"Quote it, for example \"{example}\":")


def refuse_non_text_keys(doc, where):
    """Raise `CompassError` naming the first non-text key in `doc`."""
    for path, key in non_text_keys(doc):
        raise CompassError(f"{where}: {path}: {non_text_key_message(key)} "
                           f"(L-KEY-NOT-TEXT)")


def layer_digest(doc, kind="project"):
    """The digest of a layer's parsed content. A project or parent layer
    digests its layer keys only, so a settings key or the reserved `preset`
    key changes nothing. An issue layer digests its whole document: its
    `autonomy` is part of what that layer changes."""
    if kind == "issue":
        return digest(doc)
    return digest({k: v for k, v in doc.items() if k in spec.LAYER_KEYS})


def _check(doc, kind, where):
    refuse_non_text_keys(doc, where)
    errors = catalogue_check.check_layer(doc, kind)
    if errors:
        raise CompassError(f"{where}: " + "; ".join(errors))


def _load(path):
    try:
        return load_yaml_strict(path)
    except StrictYamlError as exc:
        raise CompassError(str(exc)) from None


def load_project_layer(root):
    """`(Layer, settings)` from `<root>/compass.yml`, or `None` when the
    project has no such file. The file is read with the strict loader and
    checked before it is split."""
    path = os.path.join(os.fspath(root), PROJECT_FILE)
    if not os.path.isfile(path):
        return None
    doc = _load(path)
    _check(doc, "project", path)
    layer, settings = split_project_file(doc)
    return Layer("project", "project", layer, layer_digest(layer)), settings


def load_issue_layer(manifest):
    """The issue's own layer from a manifest path, or from an already
    parsed manifest mapping: its `config:`. `None` when it has none."""
    where = "issue config"
    if not isinstance(manifest, dict):
        if not isinstance(manifest, (str, os.PathLike)):
            raise CompassError("issue manifest: expected a mapping or a path, "
                               f"found {type(manifest).__name__}")
        where = f"{os.fspath(manifest)}: config"
        manifest = _load(manifest)
        if not isinstance(manifest, dict):
            raise CompassError(f"{where}: the manifest is not a mapping")
    config = manifest.get("config")
    if config is None:
        return None
    _check(config, "issue", where)
    return Layer("issue", "issue", config, layer_digest(config, "issue"))


def _check_parent(doc, name):
    """A settings key is refused by name before the structural check, which
    would only say the key is not allowed."""
    for key in doc if isinstance(doc, dict) else ():
        if key in spec.SETTINGS_KEYS:
            raise CompassError(
                f"{name}: {key} is a settings key and belongs in the project's own "
                f"compass.yml, never in a parent (ADR-043)")
    _check(doc, "parent", name)


def _slot(layer, kind):
    if layer.kind != kind:
        raise CompassError(f"{layer.name}: a layer of kind {layer.kind} cannot sit in "
                           f"the {kind} slot of the chain")
    return layer


def build_chain(parent=None, project=None, issue=None, parent_name="parent"):
    """The layers, root first: the parent (a mapping or a `Layer`), the
    project and the issue, each only when given. Every layer is checked
    alone, before anything merges, whatever form it arrives in, and its
    kind must match its slot."""
    chain = []
    if parent is not None:
        if isinstance(parent, Layer):
            _slot(parent, "parent")
            _check_parent(parent.doc, parent.name)
        else:
            _check_parent(parent, parent_name)
            parent = Layer(parent_name, "parent", parent, layer_digest(parent, "parent"))
        chain.append(parent)
    if project is not None:
        _check(_slot(project, "project").doc, "project", project.name)
        chain.append(project)
    if issue is not None:
        _check(_slot(issue, "issue").doc, "issue", issue.name)
        chain.append(issue)
    return chain
