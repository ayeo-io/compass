# compass_pkg.legacy_views - the two legacy policy files, generated from the preset
"""Generate `governance/routing-policy.yml` and `governance/guardrails.yml`.

From the default preset on, the shipped defaults live in
`governance/presets/default/` (ADR-042). The two legacy files stay in the
legacy format, so a project that copied them, the drift report and the tests
that read them keep working, but they are views: this module writes them.

Three inputs make each view:

- the preset, which holds every value a catalogue has a field for;
- `governance/legacy-views.yml`, which holds the values the catalogues have no
  field for (see `legacy_adapter.legacy_views`);
- `legacy_views_template.py`, which holds the comments, the banner, the
  layout and the scalar styles.

The module reads the preset and the sidecar and nothing else. It does not read
`legacy_adapter.py`, so a fault in the adapter cannot hide in both sides of a
comparison, and it does not read the two files it writes.
"""
# DEPENDENCY: PyYAML (bundled); compass_pkg.atomic_io, compass_pkg.legacy_views_template.
from __future__ import annotations

import hashlib
import json
import os
import re

import yaml

from compass_pkg import atomic_io
from compass_pkg import legacy_views_template as tpl

PRESET_DIR = os.path.join("governance", "presets", "default")
SIDECAR = os.path.join("governance", "legacy-views.yml")
POLICY_VIEW = "governance/routing-policy.yml"
GUARDRAILS_VIEW = "governance/guardrails.yml"
VIEWS = (POLICY_VIEW, GUARDRAILS_VIEW)

# Prose keys are always written as a double-quoted string, never plain.
_TEXT_KEYS = frozenset({"rationale", "until", "name", "description", "statement"})
_WRAP_LIST_SECTIONS = frozenset({"defaults", "spike_guardrails"})


def has_implementation(check):
    """True for a check the legacy view can name. Only a `deterministic` check
    has an implementation, and a legacy `checks:` entry is refused without one,
    so the views, the mutation-proof register and the tests that rebuild the
    views all use this one predicate."""
    return check["kind"] == "deterministic"


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# --- the legacy documents, rebuilt from the preset and the sidecar ---------------

_RENAMED_BACK = {"force_minimum_approach": "force_minimum_route",
                 "forbid_approach": "forbid_route"}


def _when_back(when, keys):
    """A `when:` clause in the legacy key spelling the sidecar names."""
    if not isinstance(when, dict):
        return when
    return {keys.get(k, k): ([_when_back(c, keys) for c in v] if k == "any_of" else v)
            for k, v in when.items()}


def rebuild(root):
    """The two legacy documents as `(policy, guardrails)`, in the key order
    the files have, from the preset and the sidecar under `root`."""
    preset_dir = os.path.join(root, PRESET_DIR)
    preset = {name: _load(os.path.join(preset_dir, f"{name}.yml"))[name]
              for name in ("dimensions", "approaches", "rules", "checks", "gates")}
    types = _load(os.path.join(preset_dir, "evidence-types.yml"))
    sidecar = _load(os.path.join(root, SIDECAR))
    rp, gs = sidecar["routing_policy"], sidecar["guardrails"]

    def legacy_rule(rule_id, rule):
        out = {"id": rule_id}
        if "when" in rule:
            out["when"] = _when_back(rule["when"], rp["when_keys"])
        for key, value in rule.get("then", {}).items():
            out[_RENAMED_BACK.get(key, key)] = value
        if "rationale" in rule:
            out["rationale"] = rule["rationale"]
        out.update(rp["legacy_values"].get(rule_id, {}))
        order = rp["rule_key_order"].get(rule_id)
        if order:
            out = {k: out[k] for k in order}
        return out

    def rules_of(name, skip=()):
        return [legacy_rule(i, r) for i, r in preset["rules"][name]["rules"].items()
                if i not in skip]

    approaches = preset["approaches"]
    vocabulary = {name: d["values"] for name, d in preset["dimensions"].items()
                  if name != "labels"}
    vocabulary["labels_common"] = preset["dimensions"]["labels"]["common"]
    policy = {
        "version": rp["version"],
        "routing_strategies": {
            "default_shapes": rules_of("default_shapes", rp["generated_rules"]),
            "default_route": rp["default_route"],
            "biases": [r["rationale"] for r in preset["rules"]["biases"]["rules"].values()],
            "role_defaults": rules_of("role_defaults"),
            "advisory_strategies": rules_of("advisory"),
        },
        "routing_guardrails": {
            "floors": rules_of("floors"), "caps": rules_of("caps"),
            "loop_ceilings": rules_of("loop_ceilings"),
            "immovable_gates": rules_of("immovable_gates"),
            "role_rules": rules_of("role_rules"),
        },
        "assessment_vocabulary": vocabulary,
        "autonomy_checkpoints": {
            level: {a: approaches[a]["checkpoints"][level] for a in row
                    if level in approaches[a].get("checkpoints", {})}
            for level, row in rp["autonomy_checkpoints"].items()},
        "route_shapes": {
            name: {"weight": a["weight"], "stages": a["stages"], "gates": a["gates"],
                   "subtask_ceiling": a["subtask_ceiling"], "artifacts": a["artifacts"]}
            for name, a in approaches.items()},
    }

    def guardrails_of(ships):
        out = []
        for gate_id, gate in preset["gates"].items():
            if gate["kind"] != "guardrail" or gate["applies_to"]["ships"] is not ships:
                continue
            item = {"id": gate_id, "name": gate["name"], "statement": gate["statement"],
                    "checks": gate["checks"]}
            if "when" in gate:
                item["applies_when"] = _when_back(gate["when"], gs["when_keys"])
            item["checked_at"] = gs["checked_at"][gate_id]
            order = gs["key_order"].get(gate_id)
            if order:
                item = {k: item[k] for k in order}
            out.append(item)
        return out

    checks = {}
    for name, check in preset["checks"].items():
        # A human check has no implementation, so only the stage lists of the
        # preset carry it (see `has_implementation`).
        if not has_implementation(check):
            continue
        checks[name] = {"description": check["statement"]}
        if "blocking_when" in check:
            checks[name]["blocking_when"] = _when_back(check["blocking_when"],
                                                       gs["when_keys"])
    guardrails = {
        "version": gs["version"],
        "checks": checks,
        "evidence_types": types["evidence_types"],
        "gate_evidence_requirements": {
            g: e["accepts"] for g, e in preset["gates"].items()
            if e["kind"] == "review" and "accepts" in e},
        "defaults": guardrails_of(True),
        "spike_guardrails": guardrails_of(False),
        "project": gs["project"],
    }
    return policy, guardrails


# --- scalars and flow values -----------------------------------------------------

_PLAIN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-/]*")


def _quote(text):
    return json.dumps(text, ensure_ascii=False)


def _scalar(value, text=False):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if not text and _PLAIN.fullmatch(value) and yaml.safe_load(value) == value:
        return value
    return _quote(value)


def _flow(value):
    if isinstance(value, list):
        return "[" + ", ".join(_flow(v) for v in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{ " + ", ".join(f"{k}: {_flow(v)}" for k, v in value.items()) + " }"
    return _scalar(value)


def _greedy(words, first_width, width):
    """Break `words` into lines; the first line has `first_width` columns."""
    lines, current, room = [], [], first_width
    for word in words:
        if current and len(" ".join(current)) + 1 + len(word) > room:
            lines.append(" ".join(current))
            current, room = [], width
        current.append(word)
    lines.append(" ".join(current))
    return lines


def _words(text):
    if "\n" in text.rstrip("\n") or "  " in text or text != text.strip():
        raise ValueError(f"prose that cannot be wrapped without changing it: {text!r}")
    return text.split(" ")


def _folded(pad, key, text):
    chomp = "" if text.endswith("\n") and not text.endswith("\n\n") else "-"
    if text.endswith("\n\n"):
        raise ValueError("a folded block with several trailing newlines cannot be written")
    body = text.rstrip("\n")
    lines = _greedy(_words(body), tpl.TEXT_WIDTH - len(pad) - 2, tpl.TEXT_WIDTH - len(pad) - 2)
    return [f"{pad}{key}: >{chomp}"] + [f"{pad}  {line}" for line in lines]


def _wrapped(head, cont_pad, text):
    """A double-quoted string that continues on lines indented `cont_pad`."""
    quoted = _quote(text)
    lines = _greedy(quoted.split(" "), tpl.TEXT_WIDTH - len(head),
                    tpl.TEXT_WIDTH - len(cont_pad))
    return [head + lines[0]] + [cont_pad + line for line in lines[1:]]


def _wrapped_list(head, items):
    """A flow list that continues under its first item."""
    cont = " " * len(head)
    lines, current = [], head
    for n, item in enumerate(items):
        piece = item + ("," if n < len(items) - 1 else "]")
        if current.strip() and not current.endswith("[") and \
                len(current) + 1 + len(piece) > tpl.LIST_WIDTH:
            lines.append(current)
            current = cont + piece
        else:
            current += ("" if current.endswith("[") else " ") + piece
    lines.append(current)
    return lines


# --- when clauses, comments and entries -------------------------------------------

def _comment(owner, key, pad):
    return [pad + line for line in tpl.ENTRY_COMMENTS.get((owner, key), ())]


def _inline(lines, owner, key):
    spaces, text = tpl.INLINE_COMMENTS.get((owner, key), (0, ""))
    if text:
        lines[-1] += " " * spaces + text
    return lines


def _when_lines(pad, key, when, bare_items):
    if not isinstance(when, dict) or "any_of" not in when:
        return [f"{pad}{key}: {_flow(when)}"]
    lines = [f"{pad}{key}:"]
    for k, v in when.items():
        if k != "any_of":
            lines.append(f"{pad}  {k}: {_flow(v)}")
            continue
        lines.append(f"{pad}  any_of:")
        for item in v:
            if "any_of" in item:
                raise ValueError("a nested any_of cannot be written")
            if bare_items:
                if len(item) != 1:
                    raise ValueError(f"an any_of item with several keys cannot be written bare: {item!r}")
                (ik, iv), = item.items()
                lines.append(f"{pad}    - {ik}: {_flow(iv)}")
            else:
                lines.append(f"{pad}    - {_flow(item)}")
    return lines


def _kv(pad, key, value, owner, section, bare_items):
    if key in ("when", "applies_when", "blocking_when") and isinstance(value, dict):
        lines = _when_lines(pad, key, value, bare_items)
    elif isinstance(value, str) and key in ("statement", "description") \
            and (section, owner) in tpl.FOLDED:
        lines = _folded(pad, key, value)
    elif isinstance(value, str) and key in _TEXT_KEYS:
        if (owner, key) in tpl.WRAPPED:
            lines = _wrapped(f"{pad}{key}: ", pad + "  ", value)
        else:
            lines = [f"{pad}{key}: {_quote(value)}"]
    elif isinstance(value, list) and section in _WRAP_LIST_SECTIONS \
            and len(f"{pad}{key}: {_flow(value)}") > tpl.LIST_WIDTH:
        lines = _wrapped_list(f"{pad}{key}: [", [_scalar(v) for v in value])
    else:
        lines = [f"{pad}{key}: {_flow(value)}"]
    return _inline(lines, owner, key)


def _entries(section, items, indent, bare_items=False):
    """A list of rules or guardrails, each starting `- id:`."""
    lines = []
    for n, item in enumerate(items):
        if n and section in tpl.GAPPED_SECTIONS:
            lines.append("")
        pad, kpad = " " * indent, " " * (indent + 2)
        lines += _comment(item["id"], "id", pad)
        for key, value in item.items():
            if key == "id":
                lines.append(f"{pad}- id: {_scalar(value)}")
                continue
            lines += _comment(item["id"], key, kpad)
            lines += _kv(kpad, key, value, item["id"], section, bare_items)
    return lines


def _named_map(section, mapping, bare_items=False):
    """A mapping of name to a small mapping, as in `checks:`."""
    lines = []
    for name, body in mapping.items():
        if name in tpl.BLANK_BEFORE:
            lines.append("")
        lines += _comment(name, "id", "  ")
        lines.append(f"  {name}:")
        for key, value in body.items():
            lines += _comment(name, key, "    ")
            lines += _kv("    ", key, value, name, section, bare_items)
    return lines


def _flow_map(owner, mapping, indent=2):
    lines = []
    for key, value in mapping.items():
        lines += _comment(owner, key, " " * indent)
        lines += _inline([f"{' ' * indent}{key}: {_flow(value)}"], owner, key)
    return lines


# --- the two files ---------------------------------------------------------------

def _fill(template, sections):
    out = []
    for line in template.split("\n"):
        m = re.fullmatch(r"<<(\w+)>>", line)
        if m and m.group(1) == "banner":
            out += tpl.BANNER.replace("<<command>>", tpl.REGENERATE_COMMAND).rstrip("\n").split("\n")
        elif m:
            out += sections[m.group(1)]
        else:
            out.append(re.sub(r"<<(\w+)>>", lambda s: sections[s.group(1)], line))
    return "\n".join(out)


def render_policy(root):
    policy, _ = rebuild(root)
    strategies, rules = policy["routing_strategies"], policy["routing_guardrails"]
    biases = []
    for text in strategies["biases"]:
        head = "    - "
        biases += _wrapped(head, "       ", text)
    autonomy = []
    for level, row in policy["autonomy_checkpoints"].items():
        autonomy.append(f"  {level}:")
        autonomy += [f"    {a}: {_flow(stages)}" for a, stages in row.items()]
    shapes = []
    for name, shape in policy["route_shapes"].items():
        shapes += _comment(name, "id", "  ")
        shapes.append(f"  {name}:")
        for key, value in shape.items():
            shapes += _comment(name, key, "    ")
            shapes += _kv("    ", key, value, name, "route_shapes", False)
    sections = {
        "version": _scalar(policy["version"]),
        "default_shapes": _entries("default_shapes", strategies["default_shapes"], 4),
        "default_route": _scalar(strategies["default_route"]),
        "biases": biases,
        "role_defaults": _entries("role_defaults", strategies["role_defaults"], 4),
        "advisory_strategies": _entries("advisory", strategies["advisory_strategies"], 4),
        **{name: _entries(name, rules[name], 4) for name in rules},
        "assessment_vocabulary": _flow_map("assessment_vocabulary",
                                           policy["assessment_vocabulary"]),
        "autonomy_checkpoints": autonomy,
        "route_shapes": shapes,
    }
    return _fill(tpl.POLICY_TEMPLATE, sections)


def render_guardrails(root):
    _, guardrails = rebuild(root)
    sections = {
        "version": _scalar(guardrails["version"]),
        "checks": _named_map("checks", guardrails["checks"]),
        "evidence_types": _named_map("evidence_types", guardrails["evidence_types"]),
        "gate_evidence_requirements": _flow_map("gate_evidence_requirements",
                                                guardrails["gate_evidence_requirements"]),
        "defaults": _entries("defaults", guardrails["defaults"], 2, bare_items=True),
        "spike_guardrails": _entries("spike_guardrails", guardrails["spike_guardrails"],
                                     2, bare_items=True),
        "project": _flow(guardrails["project"]),
    }
    return _fill(tpl.GUARDRAILS_TEMPLATE, sections)


def generate(root):
    """The text of each view, as `{relative path: text}`."""
    return {POLICY_VIEW: render_policy(root), GUARDRAILS_VIEW: render_guardrails(root)}


def stale_views(root):
    """One line for each committed view that differs from the generated text,
    naming the command that regenerates it."""
    stale = []
    for rel, text in generate(root).items():
        path = os.path.join(root, rel)
        current = None
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                current = fh.read()
        if current != text:
            stale.append(f"{rel} is stale: it differs from what the generator writes "
                         f"from the preset. Regenerate it with: {tpl.REGENERATE_COMMAND}")
    return stale


# --- pinned preset digests -------------------------------------------------------

DIGEST_FILE = "tests/fixtures/preset-digests.yml"
PIN_COMMAND = f"{tpl.REGENERATE_COMMAND} --pin"
_DIGEST_HEADER = (
    "# Pinned digests of the default preset, one for each file and one for the\n"
    "# whole preset. A digest is over the parsed content, so a comment or a layout\n"
    "# change does not move it. tests/test_preset_digests.py fails when a preset\n"
    f"# file changes without its digest moving. Pin again with: {PIN_COMMAND}\n")


def preset_locks(root):
    """The `locks:` summary of the preset's `preset.yml` under `root`:
    `{"hard": [...], "locked": [...]}` of `catalogue.id` names. This is the
    one reader of the summary, so no other module reads the preset path."""
    meta = _load(os.path.join(root, PRESET_DIR, "preset.yml"))
    summary = meta.get("locks") or {}
    return {"hard": list(summary.get("hard") or []),
            "locked": list(summary.get("locked") or [])}


def preset_digests(root):
    """`(pin key, {"preset": digest, "files": {file name: digest}})` for the
    preset under `root`. The pin key is the preset's id and version."""
    directory = os.path.join(root, PRESET_DIR)
    parsed = {name: _load(os.path.join(directory, name))
              for name in sorted(os.listdir(directory)) if name.endswith(".yml")}
    meta = parsed["preset.yml"]
    return f"{meta['id']}@{meta['version']}", {
        "preset": atomic_io.digest(parsed),
        "files": {name: atomic_io.digest(doc) for name, doc in parsed.items()},
    }


def digest_problems(root):
    """One line for each way the preset differs from its pinned digests,
    naming the digest file and the command that pins again."""
    where = f"{DIGEST_FILE}; if the change is intended, pin it again with: {PIN_COMMAND}"
    path = os.path.join(root, DIGEST_FILE)
    if not os.path.isfile(path):
        return [f"{DIGEST_FILE} is missing; create it with: {PIN_COMMAND}"]
    key, now = preset_digests(root)
    pins = (_load(path) or {}).get(key)
    if not pins:
        return [f"preset {key} has no pinned digest in {where}"]
    problems = []
    for name in sorted(set(now["files"]) | set(pins["files"])):
        if name not in pins["files"]:
            problems.append(f"{name} is in the preset but not pinned in {where}")
        elif name not in now["files"]:
            problems.append(f"{name} is pinned but no longer in the preset ({where})")
        elif now["files"][name] != pins["files"][name]:
            problems.append(f"{name} changed without its pinned digest moving in {where}")
    if now["preset"] != pins["preset"]:
        problems.append(f"the whole preset digest differs from the one pinned in {where}")
    return problems


def pin_digests(root):
    """Add or update the current id@version entry of the digest file under
    `root`. The pins of earlier versions stay: the stability rule for a
    released version needs each version's digest to check against."""
    key, now = preset_digests(root)
    path = os.path.join(root, DIGEST_FILE)
    pins = (_load(path) or {}) if os.path.isfile(path) else {}
    pins[key] = now
    text = _DIGEST_HEADER + yaml.safe_dump(pins, sort_keys=True, default_flow_style=False)
    atomic_io.atomic_write_text(path, text)
    return DIGEST_FILE


CONTENT_HASH_FILE = "tests/fixtures/governance-content-hashes.json"
HASH_COMMAND = f"{tpl.REGENERATE_COMMAND} --pin-hashes"


def pin_content_hashes(root):
    """Write the fixture that pins each view's content to its declared
    version, as `tests/test_governance_drift.py` reads it. The hash is over
    the parsed view without `version:`, so it follows the generated files.
    Raise the version first (under `routing_policy` or `guardrails` in
    `governance/legacy-views.yml`), regenerate, then run this."""
    out = {}
    for rel in VIEWS:
        data = _load(os.path.join(root, rel))
        version = str(data.pop("version"))
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        out[os.path.basename(rel)] = {
            "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "version": version}
    text = json.dumps(out, indent=2, sort_keys=True) + "\n"
    atomic_io.atomic_write_text(os.path.join(root, CONTENT_HASH_FILE), text)
    return CONTENT_HASH_FILE


def write_views(root):
    """Write both views under `root`; return the relative paths written."""
    written = []
    for rel, text in generate(root).items():
        atomic_io.atomic_write_text(os.path.join(root, rel), text)
        written.append(rel)
    return written
