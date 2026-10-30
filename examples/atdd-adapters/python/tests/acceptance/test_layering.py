"""The layers keep their shape.

This test reads the source of the DSL and of the specifications; it does not
run them, and it needs no running system. Each breach it finds is reported as
`<file>:<line>: <rule>: <what it found>`, with the file relative to the
example's root. One test per rule:

- the DSL makes no check: no `assert`, no `raise` and no call to the
  runner's `fail` inside a DSL method, async or not, or inside a
  module-level function of the DSL file. A check belongs in the driver;
- every identifier goes through an alias: a string in a specification that
  matches a pattern in IDENTIFIER_PATTERNS must be an argument of a DSL
  method parameter that the method passes to `self._alias(...)`;
- one DSL call per Given, When or Then line: each statement of a
  specification is one DSL call, and the calls match the step lines of its
  docstring. Lines and calls are matched in three phases: a Given line (and
  the And lines after it) to a method whose name starts `has`, a Then line
  (and its And lines) to one that starts `confirm`, a When line (and its And
  lines) to any other. Within a phase, lines and calls are matched by
  count, so a missing call and a surplus call in one phase cancel out.
  The rule reads module-level `test_*` functions and the `test_*` methods
  of `Test*` classes.

To adopt it, set the paths and the identifier patterns below for your suite.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DSL_FILE = HERE / "dsl.py"
SPEC_FILES = sorted(path for path in HERE.glob("test_*.py") if path.name != Path(__file__).name)

#: The identifiers a specification must name only through the DSL's alias helper.
IDENTIFIER_PATTERNS = {
    "email address": re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"),
}

RULE_NO_CHECK = "the DSL makes no check"
RULE_ALIAS = "every identifier goes through an alias"
RULE_ONE_CALL = "one DSL call per Given, When or Then line"

STEP = re.compile(r"^\s*(Given|When|Then|And)\b\s*(.*?)\s*$")
PHASE_OF_KEYWORD = {"Given": "Given", "When": "When", "Then": "Then"}


def _rel(path):
    return path.relative_to(ROOT).as_posix()


def _report(breaches):
    return "\n" + "\n".join(breaches)


# --- reading the DSL ---------------------------------------------------------------

def _dsl_tree():
    return ast.parse(DSL_FILE.read_text(encoding="utf-8"))


FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _dsl_methods(tree):
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef):
            for method in cls.body:
                if isinstance(method, FUNCTIONS):
                    yield cls, method


def _dsl_functions(tree):
    """(name, function) for every method and every module-level function of
    the DSL, so a check moved into a helper the DSL calls is found too."""
    for node in tree.body:
        if isinstance(node, FUNCTIONS):
            yield node.name, node
    for cls, method in _dsl_methods(tree):
        yield f"{cls.name}.{method.name}", method


def _aliased_parameters(method):
    """The parameters `method` passes to `self._alias(...)`."""
    return {node.args[0].id for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_alias" and node.args
            and isinstance(node.args[0], ast.Name)}


def _dsl_shape(tree):
    """{part: {method: (parameters, aliased parameters)}}, the parts read from
    the assignments `self.<part> = <Class>(...)` in the DSL root's __init__."""
    classes = {cls.name: {} for cls, _ in _dsl_methods(tree)}
    for cls, method in _dsl_methods(tree):
        parameters = [arg.arg for arg in method.args.args[1:]]
        classes[cls.name][method.name] = (parameters, _aliased_parameters(method))
    parts = {}
    for cls, method in _dsl_methods(tree):
        if method.name != "__init__":
            continue
        for node in ast.walk(method):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Attribute)
                    and isinstance(node.targets[0].value, ast.Name)
                    and node.targets[0].value.id == "self"
                    and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                    and node.value.func.id in classes):
                parts[node.targets[0].attr] = classes[node.value.func.id]
    return parts


# --- reading the specifications ----------------------------------------------------

def _spec_functions(tree):
    """Every test pytest collects from the file: module-level `test_*`
    functions and the `test_*` methods of `Test*` classes."""
    found = []
    for node in tree.body:
        if isinstance(node, FUNCTIONS) and node.name.startswith("test_"):
            found.append(node)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            found += [method for method in node.body
                      if isinstance(method, FUNCTIONS) and method.name.startswith("test_")]
    return found


def _docstring_nodes(tree):
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, *FUNCTIONS)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                nodes.add(id(first.value))
    return nodes


def _dsl_calls(node):
    """The calls inside `node` whose callee starts at the name `dsl`."""
    found = []
    for call in ast.walk(node):
        if isinstance(call, ast.Call):
            root = call.func
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id == "dsl":
                found.append(call)
    return found


def _part_and_method(call):
    """('todo', 'add') for `dsl.todo.add(...)`, else None."""
    func = call.func
    if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name) and func.value.value.id == "dsl"):
        return func.value.attr, func.attr
    return None


def _steps(function):
    """[(phase, keyword, text, line)] from the scenario in the docstring."""
    node = function.body[0].value
    steps, phase = [], None
    for offset, text in enumerate(node.value.splitlines()):
        found = STEP.match(text)
        if not found:
            continue
        keyword, rest = found.groups()
        phase = PHASE_OF_KEYWORD.get(keyword, phase)
        steps.append((phase, keyword, f"{keyword} {rest}", node.lineno + offset))
    return steps


def _phase_of_method(method):
    if method.startswith("has"):
        return "Given"
    if method.startswith("confirm"):
        return "Then"
    return "When"


# --- the rules ----------------------------------------------------------------------

def test_the_dsl_makes_no_check():
    breaches = []
    for name, function in _dsl_functions(_dsl_tree()):
        for node in ast.walk(function):
            found = None
            if isinstance(node, ast.Assert):
                found = "an assert statement"
            elif isinstance(node, ast.Raise):
                found = "a raised exception"
            elif isinstance(node, ast.Call):
                func = node.func
                if ((isinstance(func, ast.Name) and func.id == "fail")
                        or (isinstance(func, ast.Attribute) and func.attr == "fail")):
                    found = "a call to the runner's fail"
            if found:
                breaches.append(f"{_rel(DSL_FILE)}:{node.lineno}: {RULE_NO_CHECK}: {found} in "
                                f"{name}; the check belongs in the driver")
    assert not breaches, _report(breaches)


def test_every_identifier_goes_through_an_alias():
    shape = _dsl_shape(_dsl_tree())
    breaches = []
    for path in SPEC_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliased = set()
        for call in _dsl_calls(tree):
            target = _part_and_method(call)
            if not target or target[1] not in shape.get(target[0], {}):
                continue
            parameters, aliased_parameters = shape[target[0]][target[1]]
            bound = list(zip(parameters, call.args))
            bound += [(keyword.arg, keyword.value) for keyword in call.keywords]
            aliased |= {id(value) for name, value in bound if name in aliased_parameters}
        skipped = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (not isinstance(node, ast.Constant) or not isinstance(node.value, str)
                    or id(node) in skipped or id(node) in aliased):
                continue
            for kind, pattern in IDENTIFIER_PATTERNS.items():
                if pattern.search(node.value):
                    breaches.append(f"{_rel(path)}:{node.lineno}: {RULE_ALIAS}: the {kind} "
                                    f"{node.value!r} reaches no DSL parameter that aliases it")
    assert not breaches, _report(breaches)


def test_one_dsl_call_per_line():
    breaches = []
    for path in SPEC_FILES:
        rel = _rel(path)
        for function in _spec_functions(ast.parse(path.read_text(encoding="utf-8"))):
            body = function.body
            if not (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                breaches.append(f"{rel}:{function.lineno}: {RULE_ONE_CALL}: {function.name} "
                                "has no scenario in its docstring")
                continue
            calls = {"Given": [], "When": [], "Then": []}
            for statement in body[1:]:
                found = _dsl_calls(statement)
                if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                        and found and found[0] is statement.value):
                    breaches.append(f"{rel}:{statement.lineno}: {RULE_ONE_CALL}: "
                                    "this statement is not a DSL call")
                    continue
                if len(found) > 1:
                    breaches.append(f"{rel}:{statement.lineno}: {RULE_ONE_CALL}: "
                                    f"one statement makes {len(found)} DSL calls")
                    continue
                target = _part_and_method(statement.value)
                method = target[1] if target else ""
                calls[_phase_of_method(method)].append(statement.lineno)
            steps = {"Given": [], "When": [], "Then": []}
            for phase, keyword, text, line in _steps(function):
                steps[phase or "Given"].append((text, line))
            for phase in ("Given", "When", "Then"):
                lines, made = steps[phase], calls[phase]
                if len(made) > len(lines):
                    surplus = made[len(lines):]
                    if lines:
                        text, line = lines[-1]
                        shared = made[len(lines) - 1:]
                        for at in surplus:
                            breaches.append(
                                f"{rel}:{at}: {RULE_ONE_CALL}: the line {text!r} (line {line}) "
                                f"makes {len(shared)} DSL calls, at lines "
                                f"{', '.join(str(n) for n in shared)}")
                    else:
                        for at in surplus:
                            breaches.append(f"{rel}:{at}: {RULE_ONE_CALL}: a DSL call that "
                                            f"no {phase} line asks for")
                for text, line in lines[len(made):]:
                    breaches.append(f"{rel}:{line}: {RULE_ONE_CALL}: the line {text!r} "
                                    "makes no DSL call")
    assert not breaches, _report(breaches)
