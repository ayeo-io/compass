"""No printed CLI string names the retired stage "triage", or a raw retired
delivery-approach name or stage name (`expedition`, `express`, `land`).

The project-wide vocabulary scan (`test_terminology.py`) bans only the
capitalised heading form of the retired word, because the lowercase word
is ordinary English elsewhere. Inside the CLI's own printed strings it is
never ordinary English - it always names the retired assess stage - so
this test bans the lowercase word there specifically.

Scenario: RTP-5.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The files this test's issue owns. Every line in them that can reach a
# terminal (a print, an f-string, an argparse help string, an error message)
# must not say "triage".
_SOURCE_FILES = [
    "cli/compass",
    "cli/compass_pkg/analyze.py",
    "cli/compass_pkg/calibration.py",
    "cli/compass_pkg/check_cmd.py",
    "cli/compass_pkg/checks.py",
    "cli/compass_pkg/policy.py",
    "cli/compass_pkg/routing.py",
]

# The one line allowed to say "triage": an input-parsing alias, so a
# delivery-approach.md written months ago - which still spells the retired
# stage name - still resolves to the current stage key. It is read, never
# printed.
_ALLOWED_LINE = '"assess": "assess", "triage": "assess", "frame": "assess",'


def test_no_owned_source_file_prints_triage():
    offenders = []
    for rel in _SOURCE_FILES:
        offenders += _offending_lines(rel, (ROOT / rel).read_text(encoding="utf-8"))
    assert not offenders, (
        "these lines still print or could print the retired word "
        "'triage':\n  " + "\n  ".join(offenders)
    )


def _offending_lines(rel, text):
    offenders = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "triage" not in line.lower():
            continue
        if line.strip() == _ALLOWED_LINE:
            continue
        offenders.append(f"{rel}:{lineno}: {line.strip()}")
    return offenders


def test_the_scan_can_fail():
    """The control runs the scan itself on a planted breach."""
    planted = '        "why": "graduating to delivery must be a fresh triage"\n'
    assert _offending_lines("planted.py", planted)
    assert not _offending_lines("planted.py", _ALLOWED_LINE + "\n")


def _word(name):
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])", re.I)


def test_approach_evaluate_default_view_names_ship_not_land(run_cli):
    """`RP-ROLE-001` blocks a stage until a claim traces to a scenario. The
    policy's own key for that stage is still the retired `land` - the
    default view must not print it raw."""
    r = run_cli(
        "approach", "evaluate",
        "--assessment", "risk=contained",
        "--assessment", "familiarity=brownfield-mapped",
        "--assessment", "size=small",
        "--assessment", "goal=delivery",
        "--assessment", "role=product-marketer",
        "--assessment", "labels=auth",
    )
    assert r.returncode == 0, r
    out = r.stdout
    assert _word("land").search(out) is None, (
        f"compass approach evaluate prints the retired stage name "
        f"'land':\n{out}")
    assert "ship is blocked" in out, (
        f"the blocked-stage concern did not name the ship stage by its "
        f"display name:\n{out}")


def test_approach_evaluate_verbose_names_ship_not_land(run_cli):
    """The two `--verbose` print sites: the policy-rule detail line and the
    BLOCKED phase summary line."""
    r = run_cli(
        "approach", "evaluate", "--verbose",
        "--assessment", "risk=contained",
        "--assessment", "familiarity=brownfield-mapped",
        "--assessment", "size=small",
        "--assessment", "goal=delivery",
        "--assessment", "role=product-marketer",
        "--assessment", "labels=auth",
    )
    assert r.returncode == 0, r
    out = r.stdout
    assert _word("land").search(out) is None, (
        f"compass approach evaluate --verbose prints the retired stage "
        f"name 'land':\n{out}")
    assert "stage 'ship' blocked until" in out, (
        f"the policy-rule detail line did not name the ship stage:\n{out}")
    assert "BLOCKED phase   : ship until" in out, (
        f"the BLOCKED phase summary line did not name the ship stage:\n{out}")


def test_retro_transitions_print_no_raw_route_name(make_task, run_cli):
    """A re-assessment recorded before the display layer existed still
    carries the retired route names `express`/`expedition` raw on disk
    (they are not touched by `normalize_spine`). `compass retro` must map
    them for display without rewriting the record."""
    make_task("old-reframe", {
        "assessment": {
            "risk": "contained", "familiarity": "brownfield-mapped",
            "size": "small", "goal": "delivery", "role": "engineer",
            "labels": [],
        },
        "delivery_approach": "feature",
        "reassessments": [
            {"date": "2026-06-01", "from_route": "express",
             "to_route": "expedition", "reason": "scope grew"},
        ],
    })
    r = run_cli("retro")
    assert r.returncode == 0, r
    out = r.stdout
    for retired in ("express", "expedition"):
        assert _word(retired).search(out) is None, (
            f"compass retro prints the retired route name {retired!r}:\n"
            f"{out}")
    assert "quick fix -> initiative" in out, (
        f"compass retro does not show the transition by its current "
        f"route names:\n{out}")


def test_retro_no_route_message_does_not_say_triage(make_task, run_cli):
    make_task("unrouted-issue", {
        "assessment": {
            "risk": "contained", "familiarity": "brownfield-mapped",
            "size": "small", "goal": "delivery", "role": "engineer",
            "labels": [],
        },
    })
    r = run_cli("retro")
    assert r.returncode == 0, r
    assert "triage" not in r.stdout.lower(), (
        f"compass retro still prints the retired word 'triage':\n"
        f"{r.stdout}")
    assert "unrouted-issue" in r.stdout


def test_approach_evaluate_help_does_not_say_triage(run_cli):
    r = run_cli("approach", "evaluate", "--help")
    assert r.returncode == 0, r
    assert "triage" not in r.stdout.lower(), (
        f"'compass approach evaluate --help' still says 'triage':\n"
        f"{r.stdout}")


def test_top_level_help_names_retro_without_triage(run_cli):
    """The `retro` line in `compass --help`'s subcommand listing, which is
    `cli/compass`'s own `help=` string (line 167) - not
    `cli/compass_pkg/verb_help.py`'s longer `--description`, which this
    issue's design does not cover."""
    r = run_cli("--help")
    assert r.returncode == 0, r
    # argparse wraps a long help string onto continuation lines indented past
    # the next subcommand's column, so the block runs to the next line whose
    # only leading whitespace is the subcommand column (4 spaces).
    m = re.search(r"\n {4}retro\b(.*?)(?=\n {4}\S)", r.stdout, re.S)
    assert m, f"the top-level help does not list 'retro':\n{r.stdout}"
    assert "triage" not in m.group(1).lower(), (
        f"the top-level help's 'retro' entry still says 'triage': "
        f"{m.group(1)!r}")


_LITERAL = re.compile(r"""(["'])(?:(?!\1).)*triage(?:(?!\1).)*\1""", re.I)


def _all_cli_and_hook_sources():
    return ([ROOT / "cli" / "compass"]
            + sorted((ROOT / "cli" / "compass_pkg").glob("*.py"))
            + sorted((ROOT / "hooks").glob("*.sh"))
            + sorted((ROOT / "scripts").glob("*.sh")))


def test_no_string_literal_in_the_cli_or_hooks_says_triage():
    """The whole class, not the listed files: every string literal in the
    CLI and the hooks - what can reach a terminal. Comments name the
    retired word freely and are not scanned."""
    offenders = []
    for path in _all_cli_and_hook_sources():
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip().startswith("#") or line.strip() == _ALLOWED_LINE:
                continue
            if _LITERAL.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert not offenders, "string literals saying 'triage':\n  " + \
        "\n  ".join(offenders)


def test_the_literal_scan_can_fail():
    assert _LITERAL.search('    "report whether triage is sized",')
    assert not _LITERAL.search("    # triage was the old name")
