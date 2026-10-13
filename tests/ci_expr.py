"""A small evaluator of GitHub Actions expressions, for tests only.

The workflow tests check what a job condition or a concurrency group means
for a stated event, not how its text reads, because two conditions that
read alike can mean different things. This evaluator models only what this
repository's workflows use in those places:

- literals: 'strings' (with '' for a quote), numbers, true, false, null;
- property paths under the contexts the caller gives (github, needs,
  steps, matrix, strategy), where a missing property is null;
- the operators ==, !=, &&, ||, ! and parentheses;
- the status functions cancelled() and success().

It follows GitHub's documented rules: && and || return one of their
operands, == and != compare strings without regard to case and convert
operands of different types to numbers, and a condition with no status
function is read as `success() && (condition)`.

Anything else, such as another function, an index, a comparison like `<`,
or a context the caller did not give, raises ExprError. A new construct in
a workflow then fails its test instead of evaluating to something.
"""
from __future__ import annotations

import math
import re
from typing import Any

__all__ = ["ExprError", "evaluate", "render", "condition", "job_runs",
           "step_runs", "truthy"]


class ExprError(ValueError):
    """The expression holds a construct this evaluator does not model."""


_TOKEN = re.compile(r"""
    (?P<space>\s+)
  | (?P<string>'(?:[^']|'')*')
  | (?P<number>-?\d+(?:\.\d+)?)
  | (?P<op>==|!=|&&|\|\||!|\(|\))
  | (?P<name>[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z_][A-Za-z0-9_-]*)*)
""", re.X)

_FUNCTIONS = {"cancelled", "success"}
_STATUS = re.compile(r"\b(?:success|failure|cancelled|always)\s*\(")


def _tokens(text: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ExprError(f"unknown token at {text[pos:pos + 20]!r} in {text!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind != "space":
            out.append((kind, m.group()))
    return out


class _Parser:
    def __init__(self, text: str, contexts: dict, status: dict):
        self.text = text
        self.tokens = _tokens(text)
        self.at = 0
        self.contexts = contexts
        self.status = status

    def _peek(self):
        return self.tokens[self.at] if self.at < len(self.tokens) else (None, None)

    def _take(self, value=None):
        kind, text = self._peek()
        if kind is None or (value is not None and text != value):
            raise ExprError(f"expected {value or 'a value'} in {self.text!r}")
        self.at += 1
        return kind, text

    def parse(self):
        value = self._or()
        if self.at != len(self.tokens):
            raise ExprError(f"unexpected {self._peek()[1]!r} in {self.text!r}")
        return value

    def _or(self):
        value = self._and()
        while self._peek()[1] == "||":
            self._take("||")
            right = self._and()
            value = value if truthy(value) else right
        return value

    def _and(self):
        value = self._eq()
        while self._peek()[1] == "&&":
            self._take("&&")
            right = self._eq()
            value = right if truthy(value) else value
        return value

    def _eq(self):
        value = self._unary()
        while self._peek()[1] in ("==", "!="):
            _, op = self._take()
            right = self._unary()
            same = _equal(value, right)
            value = same if op == "==" else not same
        return value

    def _unary(self):
        if self._peek()[1] == "!":
            self._take("!")
            return not truthy(self._unary())
        return self._primary()

    def _primary(self):
        kind, text = self._take()
        if text == "(":
            value = self._or()
            self._take(")")
            return value
        if kind == "string":
            return text[1:-1].replace("''", "'")
        if kind == "number":
            return float(text) if "." in text else int(text)
        if kind == "name":
            if self._peek()[1] == "(":
                return self._call(text)
            if text in ("true", "false"):
                return text == "true"
            if text == "null":
                return None
            return self._path(text)
        raise ExprError(f"unexpected {text!r} in {self.text!r}")

    def _call(self, name):
        if name not in _FUNCTIONS:
            raise ExprError(f"function {name}() is not modelled, in {self.text!r}")
        self._take("(")
        self._take(")")
        if name == "cancelled":
            return bool(self.status.get("cancelled", False))
        results = [n.get("result") for n in self.status.get("needs", {}).values()]
        return (not self.status.get("cancelled", False)
                and all(r == "success" for r in results))

    def _path(self, dotted):
        root, *rest = dotted.split(".")
        if root not in self.contexts:
            raise ExprError(f"context {root!r} is not given, in {self.text!r}")
        value = self.contexts[root]
        for part in rest:
            value = value.get(part) if isinstance(value, dict) else None
        return value


def truthy(value: Any) -> bool:
    if value is None or value is False or value == "":
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0 and not math.isnan(value)
    return True


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return 0.0
        try:
            return float(text)
        except ValueError:
            return math.nan
    return math.nan


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    if type(left) is type(right) and not isinstance(left, (int, float)):
        return left == right
    a, b = _number(left), _number(right)
    return not (math.isnan(a) or math.isnan(b)) and a == b


def _strip_braces(text: str) -> str:
    text = str(text).strip()
    if text.startswith("${{") and text.endswith("}}"):
        return text[3:-2]
    return text


def evaluate(text: str, *, status: dict | None = None, **contexts) -> Any:
    """Evaluate one expression, with or without its ${{ }}. YAML has
    already read a bare true or false as a boolean."""
    if isinstance(text, bool):
        return text
    return _Parser(_strip_braces(text), contexts, status or {}).parse()


def _as_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render(template: str, **contexts) -> str:
    """A string holding ${{ }} parts, such as a concurrency group."""
    out, pos = [], 0
    for m in re.finditer(r"\$\{\{(.*?)\}\}", template):
        out.append(template[pos:m.start()])
        out.append(_as_string(evaluate(m.group(1), **contexts)))
        pos = m.end()
    out.append(template[pos:])
    return "".join(out)


def condition(text: Any, *, cancelled: bool = False, needs: dict | None = None,
              **contexts) -> bool:
    """A job's or step's `if:`, with the implicit success() GitHub adds
    when the condition calls no status function."""
    if text is None:
        text = "success()"
    if isinstance(text, bool):
        text = "true" if text else "false"
    body = _strip_braces(text)
    if not _STATUS.search(body):
        body = f"success() && ({body})"
    status = {"cancelled": cancelled, "needs": needs or {}}
    return truthy(evaluate(body, status=status, needs=needs or {}, **contexts))


def job_runs(job: dict, *, github: dict, needs: dict | None = None,
             cancelled: bool = False) -> bool:
    """Whether a job runs, given the event and the results of the jobs it
    needs. Only the needed jobs reach its needs context, as on GitHub."""
    wanted = job.get("needs", [])
    wanted = [wanted] if isinstance(wanted, str) else list(wanted)
    mine = {k: v for k, v in (needs or {}).items() if k in wanted}
    return condition(job.get("if"), cancelled=cancelled, needs=mine,
                     github=github)


def step_runs(step: dict, *, github: dict, steps: dict) -> bool:
    """Whether a step runs in a job where every earlier step succeeded."""
    return condition(step.get("if"), github=github, steps=steps)
