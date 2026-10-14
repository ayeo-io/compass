# compass_pkg.readiness_registry - the registry of readiness signal implementations
"""The implementations a readiness signal can name (ADR-059).

A catalogue entry of `readiness.yml` names an implementation by id, and the CLI
runs the version it ships. Each implementation here has a semantic version, the
types of its parameters and the values a parameter may take. The version is
written into the readiness record, so a changed implementation cannot keep an
old result fresh.

This is a leaf module: it imports the standard library only, so the
session-start hook and the record reader can import it without loading the
check implementations. `check_registry.READINESS` is this table, so an
implementation is looked up in one place. `compass check` never runs one:
`check_registry.REGISTRY` and `CHECK_FNS` do not hold them.
"""
# DEPENDENCY: standard library (dataclasses); imports nothing from Compass.
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReadinessImpl:
    name: str
    # The attribute of `readiness_signals` that decides the signal.
    function: str
    version: str = "1.0.0"
    # Parameter name -> type name (`string`, `integer`).
    params_spec: dict = field(default_factory=dict)
    # Parameter name -> the values it may take. A parameter that is not here
    # takes any value of its type.
    choices: dict = field(default_factory=dict)
    # Parameter name -> `higher`, `lower`, `none` or `equivalent`: which way is
    # stricter. A missing parameter means `none`, which makes any change
    # incomparable. `equivalent` makes a swap between two of the parameter's
    # `choices` equal, so it needs a `choices` entry.
    tighter: dict = field(default_factory=dict)
    # True only where the implementation runs a command the project wrote.
    runs_project_command: bool = False

    def __post_init__(self):
        # A leaf module raises ValueError, not CompassError: an entry like this
        # is a defect in the CLI, found when the module is imported.
        for param, direction in self.tighter.items():
            if direction == "equivalent" and param not in self.choices:
                raise ValueError(
                    f"readiness implementation '{self.name}': parameter '{param}' "
                    f"declares the direction equivalent but has no choices entry")

    @property
    def major(self) -> int:
        return int(self.version.split(".")[0])


def _entry(name, function, **kw):
    return ReadinessImpl(name=name, function=function, **kw)


_ENTRIES = (
    _entry("agent-instructions-present", "agent_instructions_present"),
    _entry("project-command-succeeds", "project_command_succeeds",
           params_spec={"key": "string"},
           choices={"key": ("lint_command", "format_check_command", "build_command",
                            "typecheck_command")},
           runs_project_command=True),
    _entry("tests-under-limit", "tests_under_limit",
           params_spec={"command": "string", "limit_seconds": "integer"},
           choices={"command": ("test_command", "test_micro_command")},
           # A swap between the two declared commands is equivalent: each
           # times a test suite the project declares, under the same limit.
           tighter={"limit_seconds": "lower", "command": "equivalent"},
           runs_project_command=True),
    _entry("no-flaky-records", "no_flaky_records"),
    _entry("project-declaration", "project_declaration",
           params_spec={"key": "string"},
           choices={"key": ("secret_scan", "structured_logging")}),
    _entry("codeowners-present", "codeowners_present"),
    _entry("pre-commit-hooks-present", "pre_commit_hooks_present"),
)

READINESS: dict[str, ReadinessImpl] = {e.name: e for e in _ENTRIES}


def installed_version(impl):
    """The shipped version of an implementation, or None when it is not registered."""
    entry = READINESS.get(impl)
    return entry.version if entry else None
