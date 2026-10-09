"""Stable ids live in one module, and no other module in `cli/compass_pkg/` names them.

Scope (ADR-040, and the ruling that fixed what it left open):

- The module `cli/compass_pkg/stable_ids.py` holds delivery-approach ids, stage
  ids and gate ids as constants, and the map from a retired approach name to its
  current id. A test keeps the constants equal to the default preset.
- The scanner reads each module's syntax tree and looks at a string in these
  positions: a dictionary key, a comparison operand (`==`, `!=`, `in`,
  `not in`, against a literal, tuple, list or set), a tuple, list or set
  member, a function default argument, the key and the default argument of
  `.get`, `.setdefault` or `.pop`, a subscript key (`m["spike"]`), a call
  keyword argument (`f(gate_id="verify.analyze")`) and a `match`/`case` string pattern.
  It does not read a docstring, a comment, an f-string, or a bare message or
  `print` argument. A comparison, tuple or keyword inside a `print` or a
  message is still reported, because it is in a scanned position.
- The scanner does not see string concatenation (`"quick" + "-fix"`), a
  value built at run time, or a value (not a key) in a dictionary.
- A literal counts only when it is in the known-id set. The word alone is not
  enough, so `"plan"` as a verb is not a finding unless it is in a scanned
  position.
- Approach ids, gate ids and legacy approach names must be zero outside
  `stable_ids.py`, except the lines on `ALLOW` below.
- Stage ids are found the same way. The real count left in each module is pinned
  in `STAGE_LEDGER` with a reason, so a new one or a removed one fails the test
  until the ledger is updated. The test does not claim zero.
- Out of scope: check ids, rule ids, mode names, dimension ids, and an id built
  at run time (for example by string formatting), which no scan can see.

The allow list is per module and per line. An entry holds a code fragment that
identifies the line (never a line number) and a written reason. A stale entry,
one that matches no scanned literal, fails the test. Only `terminology_cmd.py`
may hold a whole-module entry, and it holds none because the scan finds nothing
in it.

Scenario ids: `SI-1` to `SI-7` (issue `stable-ids`).
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

PACKAGE = ROOT / "cli" / "compass_pkg"
STABLE_IDS = PACKAGE / "stable_ids.py"
PRESET = ROOT / "governance" / "presets" / "default"


def _preset_ids(name, key):
    return list(yaml.safe_load((PRESET / name).read_text(encoding="utf-8"))[key])


def _load_stable_ids():
    assert STABLE_IDS.exists(), "cli/compass_pkg/stable_ids.py does not exist"
    return importlib.import_module("compass_pkg.stable_ids")


def test_si_1_the_constants_equal_the_default_preset():
    ids = _load_stable_ids()
    tree = ast.parse(STABLE_IDS.read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not imports, "stable_ids.py imports a module, so another module cannot rely on importing it"
    others = [n for n in tree.body
              if not isinstance(n, ast.Assign)
              and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert not others, "stable_ids.py holds more than assignments"

    approaches = _preset_ids("approaches.yml", "approaches")
    assert list(ids.APPROACH_IDS) == approaches
    assert {v for k, v in vars(ids).items() if k.startswith("APPROACH_") and isinstance(v, str)} \
        == set(approaches)

    stages = _preset_ids("stages.yml", "stages")
    assert list(ids.STAGE_IDS) == stages
    assert {v for k, v in vars(ids).items() if k.startswith("STAGE_") and isinstance(v, str)} \
        == set(stages)

    gates = _preset_ids("gates.yml", "gates")
    assert list(ids.GATE_IDS) == gates
    assert {v for k, v in vars(ids).items() if k.startswith("GATE_") and isinstance(v, str)} \
        == set(gates)

    aliases = ids.LEGACY_APPROACH_ALIASES
    assert aliases, "no legacy approach names"
    assert not set(aliases) & set(approaches), "a legacy name is also a current id"
    assert set(aliases.values()) <= set(approaches), "a legacy name maps to an id the preset lacks"


# --- the scanner -------------------------------------------------------------

def scan_source(source):
    """`(line, column, value)` of every string literal in a scanned position."""
    found = {}

    def take(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found[(node.lineno, node.col_offset)] = node.value

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                take(key)
        elif isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                take(operand)
        elif isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            for member in node.elts:
                take(member)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                take(default)
        elif isinstance(node, ast.Subscript):
            take(node.slice)
        elif isinstance(node, ast.MatchValue):
            take(node.value)
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                take(keyword.value)
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("get", "setdefault", "pop"):
                for argument in node.args[:2]:
                    take(argument)
    return [(line, col, value) for (line, col), value in sorted(found.items())]


def _found(source):
    return sorted(value for _line, _col, value in scan_source(source))


def test_si_2_the_scanner_finds_ids_in_five_positions_and_skips_text():
    assert _found('d = {"spike": 1}') == ["spike"]
    assert _found('if x == "regular":\n    pass') == ["regular"]
    assert _found('if "G1" != x:\n    pass') == ["G1"]
    assert _found('if x in ("hotfix", "full"):\n    pass') == ["full", "hotfix"]
    assert _found('if x not in {"quick-fix"}:\n    pass') == ["quick-fix"]
    assert _found('t = ("spike", "full")') == ["full", "spike"]
    assert _found('l = ["verify.analyze"]') == ["verify.analyze"]
    assert _found('s = {"S1"}') == ["S1"]
    assert _found('def f(a="regular", *, b="hotfix"):\n    pass') == ["hotfix", "regular"]
    assert _found('x = m.get("key", "regular")') == ["key", "regular"]
    assert _found('x = m.setdefault("key", "spike")') == ["key", "spike"]
    assert _found('x = m.pop("key", "spike")') == ["key", "spike"]

    assert _found('def f():\n    """The spike approach and "regular" ones."""\n') == []
    assert _found('# "spike" in a comment\nx = 1') == []
    assert _found('x = f"the {y} is regular"') == []
    assert _found('raise CompassError("a spike is not delivery")') == []
    assert _found('print("spike", "regular")') == []
    assert _found('x = m.get("spike")') == ["spike"]
    assert _found('x = m["spike"]') == ["spike"]
    assert _found('x = {}.get("verify.analyze")') == ["verify.analyze"]
    assert _found('f(gate_id="verify.analyze")') == ["verify.analyze"]
    assert _found('f(x, "spike")') == []
    assert _found('match x:\n    case "spike":\n        pass\n    case "a" | "G1":\n        pass') \
        == ["G1", "a", "spike"]
    assert _found('print("a", y == "spike")') == ["spike"]
    assert _found('x = "quick" + "-fix"') == []
    assert _found('d = {"key": "spike"}') == ["key"]  # a value is not scanned
    assert _found('x = y == 3\nz = {1: 2}') == []


# --- the allow list ----------------------------------------------------------

# A literal that is spelt like an id and means something else. Each entry is
# (module, a code fragment that identifies the line, why it is not an id). The
# fragment is never a line number. A stale entry fails SI-5.
ALLOW = (
    ("classify.py", '"scan": ("one of", ("full",',
     '"full" is a scan mode (the whole grid was compared), not the approach id'),
    ("locks.py", 'SCANS = ("footprint", "full")',
     '"full" is a scan mode (every label in the layer), not the approach id'),
    ("word_map.py", '"full": "thorough"',
     '"full" is the retired stage weight in the in-module copy of the word table'),
    ("word_map.py", 'FALLBACK["size"] = {"standard": "medium"}',
     '"standard" is the retired size in the in-module copy of the word table'),
)

# Only this module may hold a whole-module entry: it holds retired words as the
# data it checks for. The scan finds nothing in it, so the entry would be stale
# and the table is empty.
WHOLE_MODULE_ALLOW = {}
WHOLE_MODULE_MAY_BE = {"terminology_cmd.py"}


def scan_package():
    """Every known-id literal in a scanned position, outside `stable_ids.py`.

    Each finding is `(module, line, value, kind, line_text)`. `kind` is
    `approach`, `gate`, `legacy` or `stage`, taken from the constants.
    """
    ids = _load_stable_ids()
    kinds = {}
    for kind, values in (("stage", ids.STAGE_IDS), ("legacy", ids.LEGACY_APPROACH_ALIASES),
                         ("gate", ids.GATE_IDS), ("approach", ids.APPROACH_IDS)):
        for value in values:
            kinds[value] = kind
    found = []
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name == "stable_ids.py":
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for line, _col, value in scan_source(source):
            if value in kinds:
                found.append((path.name, line, value, kinds[value], lines[line - 1].strip()))
    return found


def _code(line):
    """The line without its trailing comment, so a fragment cannot match a comment."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#":
            return line[:i].rstrip()
    return line


def _explained(finding):
    module, _line, _value, _kind, text = finding
    if module in WHOLE_MODULE_ALLOW:
        return True
    return any(m == module and fragment in _code(text) for m, fragment, _why in ALLOW)


def _describe(findings):
    return "\n".join(f"  {m}:{n} {v!r}: {t}" for m, n, v, _k, t in findings)


def test_si_3_no_module_holds_an_approach_or_gate_id_literal():
    findings = [f for f in scan_package() if f[3] in ("approach", "gate")]
    loose = [f for f in findings if not _explained(f)]
    assert not loose, (
        f"{len(loose)} approach or gate id literal(s) outside stable_ids.py; "
        "import the constant, or add an allow-list entry with a reason:\n" + _describe(loose))


def test_si_4_legacy_names_live_only_in_stable_ids():
    findings = scan_package()
    legacy = [f for f in findings if f[3] == "legacy" and not _explained(f)]
    assert not legacy, "a retired approach name outside stable_ids.py:\n" + _describe(legacy)
    in_routing = [f for f in findings if f[0] == "routing.py" and f[3] == "approach"
                  and not _explained(f)]
    assert not in_routing, "routing.py names an approach; use a constant:\n" + _describe(in_routing)


def stale_entries(allow, findings):
    """The allow-list entries that match no scanned literal in their module."""
    return [entry for entry in allow
            if not any(f[0] == entry[0] and entry[1] in _code(f[4]) for f in findings)]


def test_si_5_the_allow_list_is_honest():
    findings = scan_package()
    for module, fragment, reason in ALLOW:
        assert (PACKAGE / module).exists(), f"{module} is not a module in cli/compass_pkg/"
        assert fragment and not fragment.strip().isdigit(), f"{module}: the fragment must be code, not a line number"
        assert len(reason.split()) >= 3, f"{module}: {fragment!r} needs a written reason"
    assert stale_entries(ALLOW, findings) == [], "a stale allow-list entry matches no literal"

    commented = ("routing.py", 1, "full", "approach", 'X = ("full", "spike")  # if depth == "full"')
    assert not _explained(commented), "an allow-list fragment matched comment text"
    assert stale_entries(ALLOW, [commented]) != [], "a fragment in a comment kept an entry alive"
    assert _code('x = "a # b"  # note') == 'x = "a # b"'

    planted = ("routing.py", "no such line in the module", "a planted stale entry")
    assert stale_entries((*ALLOW, planted), findings) == [planted]

    assert set(WHOLE_MODULE_ALLOW) <= WHOLE_MODULE_MAY_BE, "only terminology_cmd.py may have a whole-module entry"
    for module, reason in WHOLE_MODULE_ALLOW.items():
        assert len(reason.split()) >= 3
        assert any(f[0] == module for f in findings), f"{module} has no literal, so its entry is stale"


# --- stage ids ---------------------------------------------------------------

# Stage-id literals left in a scanned position, by module: (count, why they stay).
# Everything else that names a stage as an id uses a constant. The count is exact,
# so adding one or removing one fails until this table changes.
STAGE_LEDGER = {
    "lessons.py": (2, 'a lesson source named "verify" is not a pipeline stage'),
}


def test_si_6_the_stage_id_ledger_is_exact():
    counts = {}
    for module, _line, _value, kind, _text in scan_package():
        if kind == "stage":
            counts[module] = counts.get(module, 0) + 1
    assert counts == {m: n for m, (n, _why) in STAGE_LEDGER.items()}, (
        "stage-id literals found per module differ from STAGE_LEDGER")
    for module, (_n, why) in STAGE_LEDGER.items():
        assert len(why.split()) >= 3, f"{module} needs a reason"


# --- behaviour is unchanged --------------------------------------------------

def test_si_7_the_rebuilt_values_equal_todays_values():
    ids = _load_stable_ids()
    from compass_pkg import core, policy

    assert core.ROUTE_NAMES is ids.APPROACH_IDS
    assert core.ROUTE_NAMES == ("spike", "quick-fix", "regular", "hotfix", "full")
    assert policy.CHECKPOINT_ROUTES == ("quick-fix", "regular", "full", "hotfix", "spike")
    assert core.SHAPE_VALUE_MAP == {
        "express": "quick-fix", "standard": "regular", "expedition": "full",
        "feature": "regular", "initiative": "full"}
    assert core.SHAPE_DISPLAY == {
        "express": "quick fix", "standard": "regular", "expedition": "full",
        "feature": "regular", "initiative": "full", "quick-fix": "quick fix"}
    assert core.STAGE_DISPLAY == {s: s for s in (
        "assess", "define", "refine", "plan", "breakdown", "implement", "verify", "ship")}
    assert core.CHECKPOINT_STAGES == ("assess", "define", "refine", "plan")
    lines = (PACKAGE / "core.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 1200, f"core.py is {len(lines)} lines; the cap is 1,200"
