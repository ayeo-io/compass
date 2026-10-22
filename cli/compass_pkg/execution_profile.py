# compass_pkg.execution_profile - the execution profile file: formats, rules, digest, ceilings
"""The rules for one execution profile file.

A profile file fixes one way of working: the model tier and effort, the exact
revision of each skill, prompt fragment and piece of tool guidance, and the
limits of an unattended run. `read_profile_file` reads it, `content_faults`
checks every rule at once, and `check_file` adds the digest check when the
content has no fault. `compass profile lint`, `add` and `show` all call
`check_file`, so `add` and `show` accept nothing that `lint` refuses.

The code is the authority on the format. `schemas/execution-profile.schema.json`
states the same structure for tools, and only the tests check against it.
The tiers and efforts come from `model_tiers`, and the ceilings from the
routing policy, so this module holds no copy of either.

`docs/execution-profiles.md` owns this behaviour.
"""
# DEPENDENCY: standard library (math, os, re); compass_pkg.atomic_io (strict YAML and
# the digest), compass_pkg.core (governance and policy files), compass_pkg.effective
# (the layered routing policy), compass_pkg.loop_ceilings (which ceilings exist) and
# compass_pkg.model_tiers (the tiers and efforts).
from __future__ import annotations

import math
import os
import re

from compass_pkg import atomic_io, model_tiers
from compass_pkg.loop_ceilings import CEILINGS

# --- reason codes ---------------------------------------------------------------

FILE_UNREADABLE = "file-unreadable"
FIELD_MISSING = "field-missing"
FIELD_MALFORMED = "field-malformed"
FIELD_UNKNOWN = "field-unknown"
POLICY_COPY = "policy-copy"
SCOPE_EMPTY = "scope-empty"
COMPONENT_DUPLICATE = "component-duplicate"
REVISION_NOT_EXACT = "revision-not-exact"
TIER_UNKNOWN = "tier-unknown"
EFFORT_UNKNOWN = "effort-unknown"
VERSION_NOT_NEXT = "version-not-next"
RUNNER_SETTING_OVER_CEILING = "runner-setting-over-ceiling"
DIGEST_MISMATCH = "digest-mismatch"
VERSION_IMMUTABLE = "version-immutable"
PARENT_MISSING = "parent-missing"
PARENT_DIGEST_MISMATCH = "parent-digest-mismatch"
VERSION_REQUIRED = "version-required"
PROFILE_MISSING = "profile-missing"
COMPONENT_MISSING = "component-missing"
COMPONENT_NOT_APPROVED = "component-not-approved"
COMPONENT_INCOMPATIBLE = "component-incompatible"
REGISTRY_DUPLICATE = "registry-duplicate"
#: Not refusals: a fact that stops a reader repeating a run exactly.
MODEL_FOLLOWS_SESSION = "model-follows-session"
MODEL_VERSION_NOT_PINNED = "model-version-not-pinned"

REFUSALS = (FILE_UNREADABLE, FIELD_MISSING, FIELD_MALFORMED, FIELD_UNKNOWN, POLICY_COPY,
            SCOPE_EMPTY, COMPONENT_DUPLICATE, REVISION_NOT_EXACT, TIER_UNKNOWN,
            EFFORT_UNKNOWN, VERSION_NOT_NEXT, RUNNER_SETTING_OVER_CEILING, DIGEST_MISMATCH,
            VERSION_IMMUTABLE, PARENT_MISSING, PARENT_DIGEST_MISMATCH, VERSION_REQUIRED,
            PROFILE_MISSING, COMPONENT_MISSING, COMPONENT_NOT_APPROVED,
            COMPONENT_INCOMPATIBLE, REGISTRY_DUPLICATE)
LIMITS = (MODEL_FOLLOWS_SESSION, MODEL_VERSION_NOT_PINNED)
ALL_CODES = REFUSALS + LIMITS

# --- formats --------------------------------------------------------------------

# Every use calls `fullmatch`: `$` alone also matches before a final newline, which would
# let an id with a newline name a store file.
ID_FORMAT = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
DIGEST_FORMAT = re.compile(r"^sha256:[0-9a-f]{64}$")
RUNNER_FORMAT = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

#: The 11 fields after `schema`, in the order a reader sees them.
REQUIRED_FIELDS = ("id", "version", "digest", "parent", "owner", "approval", "applies_to",
                   "runner_versions", "model", "components", "runner_settings")
TOP_FIELDS = ("schema",) + REQUIRED_FIELDS
#: Names that belong to the routing policy; a profile refers to it, never copies it.
POLICY_KEYS = ("model_rules", "default_tiers", "floors", "loop_ceilings", "readiness_floor")
#: The component lists of a profile, and the registry kind each one holds.
COMPONENT_KINDS = (("skills", "skill"), ("prompt_fragments", "prompt_fragment"),
                   ("tool_guidance", "tool_guidance"))
#: The runner setting, and the routing-policy ceiling that bounds it.
SETTING_CEILING = {"max_cycles": "run_cycles", "max_minutes": "run_minutes",
                   "max_cost_usd": "run_cost_usd"}


def show(value):
    """A value as the output prints it: text in quotes, anything else as it is."""
    return repr(value)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value):
    if isinstance(value, bool):
        return False
    # An int is finite; math.isfinite fails on one too large for a float.
    return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value))


def is_text(value):
    return isinstance(value, str) and value != ""


# --- reading --------------------------------------------------------------------

def read_yaml(path):
    """`(data, faults)` for the YAML at `path`: the loaded value, or one
    `file-unreadable` fault. Input the YAML reader cannot hold - a number of more
    than 4300 digits, nesting deeper than the stack, a key that is a list - is
    refused here, never raised."""
    try:
        with open(path, "rb") as handle:
            text = handle.read().decode("utf-8")
        return atomic_io.load_yaml_strict_text(text, path), []
    except UnicodeDecodeError:
        return None, [(FILE_UNREADABLE, f"{path}: the file is not UTF-8 text")]
    except OSError as exc:
        return None, [(FILE_UNREADABLE, f"{path}: cannot read: {exc.strerror or exc}")]
    except atomic_io.StrictYamlError as exc:
        return None, [(FILE_UNREADABLE, str(exc))]
    except (ValueError, RecursionError, TypeError):
        return None, [(FILE_UNREADABLE, f"{path}: the YAML cannot be read: a number with too "
                                        "many digits, nesting that is too deep, or a key "
                                        "that is not text")]


def read_text_file(path, follow_links=True):
    """`(mapping, faults)` for the YAML file at `path`. A file that is missing, is a
    folder, is not UTF-8 text, is not valid YAML, repeats a key, is empty or holds
    something other than a mapping gives `file-unreadable` and no mapping. The store
    passes `follow_links=False`: a link in `profiles/` could show parts of another
    file, so it is refused."""
    path = os.fspath(path)
    if not follow_links and os.path.islink(path):
        return None, [(FILE_UNREADABLE, f"{path}: the file is a symbolic link")]
    data, faults = read_yaml(path)
    if faults:
        return None, faults
    if not isinstance(data, dict) or not data:
        return None, [(FILE_UNREADABLE, f"{path}: the file does not hold a mapping of fields")]
    return data, []


# --- ceilings -------------------------------------------------------------------

def ceilings(root=None):
    """`{setting: limit}` for the runner settings, from the routing policy in force.

    A profile belongs to no assessment, so the ceiling of a setting is the lowest
    limit among the rules for it, whatever their `when`. A setting no rule limits is
    absent. The rules come from the two places `loop_ceilings.loop_ceilings` reads."""
    from compass_pkg import effective
    from compass_pkg.core import find_governance, load_yaml
    view = effective.view_or_legacy(None, start=root)
    if view is not None:
        rules = view.loop_ceiling_rules()
    else:
        policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))
        rules = ((policy or {}).get("routing_guardrails") or {}).get("loop_ceilings") or []
    by_ceiling = {}
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("ceiling") not in CEILINGS:
            continue
        limit = rule.get("limit")
        if not is_int(limit) or limit < 1:
            continue
        name = rule["ceiling"]
        if name not in by_ceiling or limit < by_ceiling[name]:
            by_ceiling[name] = limit
    return {setting: by_ceiling[name] for setting, name in SETTING_CEILING.items()
            if name in by_ceiling}


# --- content rules --------------------------------------------------------------

def content_digest(data):
    """The digest of a profile's content: everything except `digest`."""
    return atomic_io.digest({k: v for k, v in data.items() if k != "digest"})


def _unknown(mapping, allowed, where, faults):
    for key in mapping:
        if key not in allowed:
            faults.append((FIELD_UNKNOWN, f"{where}.{key} is not a field of a profile"))


def _need(mapping, key, where, faults):
    """True when `mapping[key]` is present; else adds `field-missing`."""
    if key in mapping:
        return True
    faults.append((FIELD_MISSING, f"{where} is required"))
    return False


def _mapping(value, where, faults):
    if isinstance(value, dict):
        return True
    faults.append((FIELD_MALFORMED, f"{where} must be a mapping, not {show(value)}"))
    return False


def _bad(where, value, rule, faults):
    faults.append((FIELD_MALFORMED, f"{where} is {show(value)}; {rule}"))


def _check_parent(data, faults):
    parent = data["parent"]
    if parent is None:
        return
    if not _mapping(parent, "parent", faults):
        return
    _unknown(parent, ("version", "digest"), "parent", faults)
    if _need(parent, "version", "parent.version", faults) and \
            not (is_int(parent["version"]) and parent["version"] >= 1):
        _bad("parent.version", parent["version"], "it must be a whole number of 1 or more",
             faults)
    if _need(parent, "digest", "parent.digest", faults) and \
            not (isinstance(parent["digest"], str) and DIGEST_FORMAT.fullmatch(parent["digest"])):
        _bad("parent.digest", parent["digest"],
             "it must be sha256: and 64 lower-case hexadecimal digits", faults)


def check_approval(approval, where, faults):
    if not _mapping(approval, where, faults):
        return
    _unknown(approval, ("state", "by", "at"), where, faults)
    if _need(approval, "state", f"{where}.state", faults) and not is_text(approval["state"]):
        _bad(f"{where}.state", approval["state"], "it must be text", faults)
    for key in ("by", "at"):
        if _need(approval, key, f"{where}.{key}", faults) and approval[key] is not None \
                and not is_text(approval[key]):
            _bad(f"{where}.{key}", approval[key], "it must be text or null (quote a date)",
                 faults)


def _check_scope(scope, faults):
    if not _mapping(scope, "applies_to", faults):
        return
    _unknown(scope, ("task_classes", "repositories"), "applies_to", faults)
    for name, rule in (("task_classes", ID_FORMAT), ("repositories", None)):
        where = f"applies_to.{name}"
        if not _need(scope, name, where, faults):
            continue
        items = scope[name]
        if not isinstance(items, list):
            _bad(where, items, "it must be a list", faults)
        elif not items:
            faults.append((SCOPE_EMPTY, f"{where} is empty; a profile applies somewhere"))
        else:
            for index, item in enumerate(items):
                if rule is not None and not (isinstance(item, str) and rule.fullmatch(item)):
                    _bad(f"{where}[{index}]", item, "it must be lower-case letters, digits and "
                         "hyphens, starting with a letter", faults)
                elif rule is None and not is_text(item):
                    _bad(f"{where}[{index}]", item, "it must be text", faults)


def _check_runners(versions, faults):
    if not isinstance(versions, list):
        _bad("runner_versions", versions, "it must be a list", faults)
        return
    if not versions:
        # An empty list would make every component compatible, so it is refused.
        _bad("runner_versions", versions, "it must list at least one runner version", faults)
        return
    for index, item in enumerate(versions):
        if not (isinstance(item, str) and RUNNER_FORMAT.fullmatch(item)):
            _bad(f"runner_versions[{index}]", item,
                 "it must be three whole numbers with dots, such as 7.0.0", faults)


def _check_model(model, faults):
    if not _mapping(model, "model", faults):
        return
    _unknown(model, ("tier", "effort", "provider_revision"), "model", faults)
    for key, accepted, code in (("tier", model_tiers.TIERS, TIER_UNKNOWN),
                                ("effort", model_tiers.EFFORTS, EFFORT_UNKNOWN)):
        if _need(model, key, f"model.{key}", faults) and model[key] not in accepted:
            faults.append((code, f"model.{key} is {show(model[key])}; it must be one of "
                                 f"{', '.join(accepted)}"))
    if _need(model, "provider_revision", "model.provider_revision", faults) and \
            model["provider_revision"] is not None and not is_text(model["provider_revision"]):
        _bad("model.provider_revision", model["provider_revision"], "it must be text or null",
             faults)


def _check_components(components, faults):
    if not _mapping(components, "components", faults):
        return
    _unknown(components, [name for name, _ in COMPONENT_KINDS], "components", faults)
    for name, kind in COMPONENT_KINDS:
        where = f"components.{name}"
        if not _need(components, name, where, faults):
            continue
        refs = components[name]
        if not isinstance(refs, list):
            _bad(where, refs, "it must be a list", faults)
            continue
        seen = set()
        for index, ref in enumerate(refs):
            here = f"{where}[{index}]"
            if not _mapping(ref, here, faults):
                continue
            _unknown(ref, ("id", "revision"), here, faults)
            ok = _need(ref, "id", f"{here}.id", faults)
            if ok and not is_text(ref["id"]):
                _bad(f"{here}.id", ref["id"], "it must be text", faults)
                ok = False
            if _need(ref, "revision", f"{here}.revision", faults):
                revision = ref["revision"]
                if not isinstance(revision, str):
                    _bad(f"{here}.revision", revision, "it must be text", faults)
                elif not DIGEST_FORMAT.fullmatch(revision):
                    faults.append((REVISION_NOT_EXACT,
                                   f"{kind} {ref.get('id')!r} has revision {show(revision)}; "
                                   "an exact revision is sha256: and 64 lower-case "
                                   "hexadecimal digits"))
            if ok:
                if ref["id"] in seen:
                    faults.append((COMPONENT_DUPLICATE,
                                   f"{kind} {ref['id']!r} is listed more than once"))
                seen.add(ref["id"])


def _check_settings(settings, limits, faults):
    if not _mapping(settings, "runner_settings", faults):
        return
    _unknown(settings, tuple(SETTING_CEILING), "runner_settings", faults)
    for name in SETTING_CEILING:
        where = f"runner_settings.{name}"
        if not _need(settings, name, where, faults):
            continue
        value = settings[name]
        if name == "max_cycles":
            ok, rule = is_int(value) and value >= 1, "it must be a whole number of 1 or more"
        else:
            ok, rule = is_number(value) and value > 0, "it must be a number above 0"
        if not ok:
            _bad(where, value, rule, faults)
        elif name in limits and value > limits[name]:
            faults.append((RUNNER_SETTING_OVER_CEILING,
                           f"{where} is {show(value)}, above the ceiling {limits[name]} "
                           "of the routing policy"))


def _check_version(data, faults):
    version, parent = data.get("version"), data.get("parent", False)
    if not (is_int(version) and version >= 1):
        return
    if parent is None:
        expected, shown = 1, "no parent"
    elif isinstance(parent, dict) and is_int(parent.get("version")) and parent["version"] >= 1:
        expected, shown = parent["version"] + 1, f"parent version {parent['version']}"
    else:
        return
    if version != expected:
        faults.append((VERSION_NOT_NEXT, f"version {version} does not follow {shown}; "
                                         f"it must be version {expected}"))


def content_faults(data, limits):
    """Every content fault of the mapping `data`, as `(code, message)` pairs.
    `limits` is `ceilings()`. The digest is not checked here."""
    faults = []
    for key in data:
        if key in TOP_FIELDS:
            continue
        if key in POLICY_KEYS:
            faults.append((POLICY_COPY, f"{key} copies the routing policy; a profile refers "
                                        "to the policy and never holds a copy"))
        else:
            faults.append((FIELD_UNKNOWN, f"{key} is not a field of a profile"))
    for key in TOP_FIELDS:
        _need(data, key, key, faults)
    if "schema" in data and not (is_int(data["schema"]) and data["schema"] == 1):
        _bad("schema", data["schema"], "it must be 1", faults)
    if "id" in data and not (isinstance(data["id"], str) and ID_FORMAT.fullmatch(data["id"])):
        _bad("id", data["id"], "it must be lower-case letters, digits and hyphens, 1 to 64 "
             "characters, starting with a letter", faults)
    if "version" in data and not (is_int(data["version"]) and data["version"] >= 1):
        _bad("version", data["version"], "it must be a whole number of 1 or more", faults)
    if "digest" in data and not (isinstance(data["digest"], str)
                                 and DIGEST_FORMAT.fullmatch(data["digest"])):
        _bad("digest", data["digest"],
             "it must be sha256: and 64 lower-case hexadecimal digits", faults)
    if "parent" in data:
        _check_parent(data, faults)
    if "owner" in data and not is_text(data["owner"]):
        _bad("owner", data["owner"], "it must be text of 1 or more characters", faults)
    if "approval" in data:
        check_approval(data["approval"], "approval", faults)
    if "applies_to" in data:
        _check_scope(data["applies_to"], faults)
    if "runner_versions" in data:
        _check_runners(data["runner_versions"], faults)
    if "model" in data:
        _check_model(data["model"], faults)
    if "components" in data:
        _check_components(data["components"], faults)
    if "runner_settings" in data:
        _check_settings(data["runner_settings"], limits, faults)
    _check_version(data, faults)
    return faults


def check_file(path, root=None, follow_links=True):
    """`(mapping, faults)` after every rule of `lint`: the file reads, the content
    has no fault, and only then the recorded digest equals the computed one."""
    data, faults = read_text_file(path, follow_links)
    if faults:
        return None, faults
    faults = content_faults(data, ceilings(root))
    if faults:
        return data, faults
    computed = content_digest(data)
    if data["digest"] != computed:
        return data, [(DIGEST_MISMATCH, f"{os.fspath(path)}: the recorded digest is "
                                        f"{data['digest']} but the content has the digest "
                                        f"{computed}")]
    return data, []
