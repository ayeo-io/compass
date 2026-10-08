"""Acceptance tests for `compass bdd extract` (issue executable-bdd-and-richer-plans).

`compass bdd extract` lifts the Gherkin out of an issue's
`acceptance-criteria.md` into a plain `.feature` file that a real BDD runner
can run, tagging each scenario with its traceability id so a runner's
per-scenario result maps back to `manifest.yml`.

Three properties matter as much as the extraction itself, and all three are
tested here:

  * It is DETERMINISTIC. Same input, byte-identical output, no timestamps and no
    absolute paths. Without that the output cannot be committed or diffed.
  * It FAILS CLOSED. A spec with no Gherkin, malformed Gherkin, or a title that
    differs between the markdown heading and the fence is an error that
    writes nothing at all - not a partial file.
  * It is ANCHORED ON THE TRACEABILITY COMMENT, not on the ```gherkin fence.
    Compass documents contain illustrative Gherkin that is not a scenario;
    extracting every fence would pick those up as if they were.

Spec: executable-bdd-and-richer-plans/acceptance-criteria.md
      (TRC-A1..A8, `TRC-F1`..F4).
"""
from __future__ import annotations

import hashlib
import re

import pytest
import yaml


# --- helpers ---------------------------------------------------------------

def scenario_block(trc_id: str, title: str, steps: str, intent: str = "INT-1") -> str:
    """One scenario in the shape every Compass acceptance-criteria.md uses."""
    return (
        f"### Scenario: {title}\n"
        f"<!-- traceability id: {trc_id} · serves: {intent} -->\n"
        f"\n"
        f"```gherkin\n"
        f"Scenario: {title}\n"
        f"{steps}\n"
        f"```\n"
    )


SPEC_HEADER = "# Spec - demo\n\n## Summary\n\n**Goal:** a demo spec.\n\n"


def write_spec(task_dir, body: str) -> None:
    (task_dir / "acceptance-criteria.md").write_text(SPEC_HEADER + body, encoding="utf-8")


def three_scenario_spec() -> str:
    return (
        scenario_block("TRC-A1", "the first thing should happen",
                       "  Given a starting state\n"
                       "  When the trigger fires\n"
                       "  Then the outcome holds")
        + "\n"
        + scenario_block("TRC-A2", "the second thing should happen",
                         "  Given another state\n"
                         "  When a different trigger fires\n"
                         "  Then a different outcome holds\n"
                         "  And a further outcome holds")
        + "\n"
        + scenario_block("TRC-B1", "the third thing should happen",
                         "  Given a third state\n"
                         "  When the third trigger fires\n"
                         "  Then the third outcome holds", intent="INT-2")
    )


@pytest.fixture
def demo_task(make_task):
    """An issue whose acceptance-criteria.md holds three well-formed
    scenarios."""
    task_dir = make_task("demo", {
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                     "size": "small", "intent": "delivery",
                     "role": "engineer", "labels": []},
        "scenarios": [
            {"id": "TRC-A1", "title": "the first thing should happen",
             "intent": "INT-1", "tests": ["tests/t.py::a"]},
            {"id": "TRC-A2", "title": "the second thing should happen",
             "intent": "INT-1", "tests": ["tests/t.py::b"]},
            {"id": "TRC-B1", "title": "the third thing should happen",
             "intent": "INT-2", "tests": ["tests/t.py::c"]},
        ],
    })
    write_spec(task_dir, three_scenario_spec())
    return task_dir


# ---------------------------------------------------------------------------
# `TRC-A1` - extraction produces a feature file a BDD runner can read
# ---------------------------------------------------------------------------

def test_trc_a1_extract_produces_readable_feature(demo_task, run_cli):
    result = run_cli("bdd", "extract", "--issue", "demo")
    assert result.returncode == 0, result

    out = demo_task / "acceptance-criteria.feature"
    assert out.is_file(), f"no spec.feature written to the task dir: {result}"

    text = out.read_text(encoding="utf-8")
    assert text.count("Scenario:") == 3, text

    # every Scenario block is preceded by a tag line and carries Given/When/Then
    # (split on the tag line itself - ` *` not `\s*`, so the newline before it
    # stays with the previous chunk rather than starting an empty one)
    for chunk in re.split(r"(?=^ *@TRC-)", text, flags=re.M)[1:]:
        assert re.match(r" *@TRC-\w+", chunk), chunk
        assert "Scenario:" in chunk, chunk
        assert re.search(r"^\s*Given ", chunk, re.M), chunk
        assert re.search(r"^\s*When ", chunk, re.M), chunk
        assert re.search(r"^\s*Then ", chunk, re.M), chunk


# ---------------------------------------------------------------------------
# `TRC-A2` - extraction is byte-for-byte deterministic
# ---------------------------------------------------------------------------

def test_trc_a2_extract_is_deterministic(demo_task, run_cli):
    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0
    first = (demo_task / "acceptance-criteria.feature").read_bytes()

    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0
    second = (demo_task / "acceptance-criteria.feature").read_bytes()

    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest(), (
        "two runs over an unchanged spec produced different bytes"
    )

    text = first.decode("utf-8")
    # no timestamp: no ISO date, no 4-digit year
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text), text
    # no absolute filesystem path
    assert not re.search(r"(?m)^\s*[#\w ]*/(Users|home|tmp|private)/", text), text
    assert str(demo_task) not in text, "output leaks an absolute path"


# ---------------------------------------------------------------------------
# `TRC-A3` - each scenario carries its traceability id as a tag
# ---------------------------------------------------------------------------

def test_trc_a3_scenarios_tagged_with_trc_id(demo_task, run_cli):
    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0
    text = (demo_task / "acceptance-criteria.feature").read_text(encoding="utf-8")

    assert "@TRC-A1" in text
    # the tag sits on its own line immediately above its Scenario
    m = re.search(r"^\s*@TRC-A1\s*\n\s*Scenario: the first thing should happen$",
                  text, re.M)
    assert m, text

    # the reverse direction: every TRC id in manifest.yml appears as a tag
    task = yaml.safe_load((demo_task / "manifest.yml").read_text())
    for scn in task["scenarios"]:
        assert f"@{scn['id']}" in text, f"{scn['id']} in manifest.yml but not tagged"


# ---------------------------------------------------------------------------
# `TRC-A4` - the extracted Feature names the issue it came from
# ---------------------------------------------------------------------------

def test_trc_a4_feature_names_source_task(demo_task, run_cli):
    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0
    text = (demo_task / "acceptance-criteria.feature").read_text(encoding="utf-8")

    features = re.findall(r"^Feature: (.+)$", text, re.M)
    assert features == ["demo"], features

    # a provenance header naming the source, matching the house convention in
    # docs/system-spec.md ("DERIVED FILE - do not hand-edit")
    head = text.split("Feature:")[0]
    assert "acceptance-criteria.md" in head, head
    assert re.search(r"do not hand-edit", head, re.I), head


# ---------------------------------------------------------------------------
# `TRC-A5` - extraction resolves the current issue when none is named
# ---------------------------------------------------------------------------

def test_trc_a5_resolves_current_task_pointer(demo_task, run_cli, project):
    assert (project / ".compass" / "current-task").read_text().strip() == "demo"

    result = run_cli("bdd", "extract")          # no issue flag
    assert result.returncode == 0, result
    assert (demo_task / "acceptance-criteria.feature").is_file()
    # it reports where it wrote
    assert "acceptance-criteria.feature" in result.stdout, result


# ---------------------------------------------------------------------------
# `TRC-A7` - a configured features directory overrides the default location
# ---------------------------------------------------------------------------

def test_trc_a7_features_dir_overrides_default(demo_task, run_cli, project):
    cfg = project / ".compass" / "config.yml"
    cfg.write_text(
        "version: 1.0.0\nmode: enforced\nproject:\n  bdd_features_dir: features\n",
        encoding="utf-8",
    )
    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0

    assert (project / "features" / "demo.feature").is_file(), (
        "configured bdd_features_dir was not honoured"
    )
    assert not (demo_task / "acceptance-criteria.feature").exists(), (
        "wrote to the default location as well as the configured one"
    )

    # and with no key set, the default applies
    cfg.write_text("version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0
    assert (demo_task / "acceptance-criteria.feature").is_file()


# ---------------------------------------------------------------------------
# `TRC-F1` - a spec with no gherkin fences fails loudly
# ---------------------------------------------------------------------------

def test_trc_f1_no_fences_fails_loudly(make_task, run_cli):
    task_dir = make_task("empty", {"assessment": {}, "scenarios": []})
    write_spec(task_dir, "There is prose here but no scenario at all.\n")

    result = run_cli("bdd", "extract", "--issue", "empty")
    assert result.returncode != 0, result
    assert "acceptance-criteria.md" in result.combined, result
    assert not (task_dir / "spec.feature").exists(), "wrote a file on failure"


# ---------------------------------------------------------------------------
# `TRC-F2` - a malformed gherkin fence fails loudly, leaving nothing behind
# ---------------------------------------------------------------------------

def test_trc_f2_malformed_gherkin_fails_loudly(make_task, run_cli):
    task_dir = make_task("bad", {"assessment": {}, "scenarios": []})
    write_spec(task_dir, (
        scenario_block("TRC-A1", "a good one",
                       "  Given a state\n  When it fires\n  Then it holds")
        + "\n"
        # no Given/When/Then at all - not Gherkin
        + "### Scenario: a bad one\n"
          "<!-- traceability id: TRC-A2 · serves: INT-1 -->\n\n"
          "```gherkin\n"
          "Scenario: a bad one\n"
          "  this line is not a Gherkin step\n"
          "```\n"
    ))

    result = run_cli("bdd", "extract", "--issue", "bad")
    assert result.returncode != 0, result
    assert "TRC-A2" in result.combined, result
    assert not (task_dir / "spec.feature").exists(), "left a partial file behind"


# ---------------------------------------------------------------------------
# `TRC-F3` - a title that differs between heading and fence is caught
# ---------------------------------------------------------------------------

def test_trc_f3_title_drift_is_caught(make_task, run_cli):
    task_dir = make_task("drift", {"assessment": {}, "scenarios": []})
    write_spec(task_dir, (
        "### Scenario: the heading says this\n"
        "<!-- traceability id: TRC-A1 · serves: INT-1 -->\n\n"
        "```gherkin\n"
        "Scenario: but the fence says something else\n"
        "  Given a state\n  When it fires\n  Then it holds\n"
        "```\n"
    ))

    result = run_cli("bdd", "extract", "--issue", "drift")
    assert result.returncode != 0, result
    assert "the heading says this" in result.combined, result
    assert "but the fence says something else" in result.combined, result
    assert "TRC-A1" in result.combined, result
    assert not (task_dir / "spec.feature").exists()


# ---------------------------------------------------------------------------
# `TRC-F4` - extraction changes nothing it did not create
# ---------------------------------------------------------------------------

def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_trc_f4_extract_mutates_nothing_else(demo_task, run_cli):
    before = {p: _digest(p) for p in sorted(demo_task.rglob("*")) if p.is_file()}

    assert run_cli("bdd", "extract", "--issue", "demo").returncode == 0

    after = {p: _digest(p) for p in sorted(demo_task.rglob("*")) if p.is_file()}
    created = set(after) - set(before)
    assert created == {demo_task / "acceptance-criteria.feature"}, created

    for path, digest in before.items():
        assert after[path] == digest, f"{path.name} was modified by extract"


# ---------------------------------------------------------------------------
# `TRC-A6` - `bdd` is on the documented CLI surface
# ---------------------------------------------------------------------------

# The full subcommand set, frozen deliberately: a new verb must edit this
# list, so adding one is a visible decision rather than a silent one.
EXPECTED_SUBCOMMANDS = {
    "approach", "bdd", "check", "analyze", "retro", "ci", "tdd-red",
    "tdd-green", "policy", "plan", "intent", "issue", "adr", "rework-scan", "flow",
    "next", "follow-up", "ship-commit", "gate", "scenario", "changed-file",
    "evidence", "terminology",
    "review-rule", "spec", "preset",  # `review-rule list`, `spec sync`, `preset init|test`
    "init",                       # creates .compass/ - safe to run twice
    "acceptance",                 # the acceptance verb group
    "quick-fix",                  # start|finish - the quick-fix verb group
    "lesson",                     # add|list|remove|propose|accept - project lessons (ADR-029)
    "run",                        # one stage of one issue unattended (ADR-030)
    "record",                     # sync|restore - the delivery record (ADR-031)
    "decision",                   # record|list|show|check - the ledger (ADR-027)
}


def test_trc_a6_bdd_is_on_the_documented_subcommand_surface(run_cli):
    result = run_cli("--help")
    assert result.returncode == 0, result
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", result.stdout)
    assert m, result.stdout
    actual = set(m.group(1).split(","))

    assert "bdd" in actual, "the bdd subcommand group is not registered"
    assert actual == EXPECTED_SUBCOMMANDS, (
        "the CLI surface does not match the frozen subcommand list.\n"
        f"  unexpected: {sorted(actual - EXPECTED_SUBCOMMANDS)}\n"
        f"  missing   : {sorted(EXPECTED_SUBCOMMANDS - actual)}"
    )

    # `bdd` is a GROUP, so future BDD work adds `compass bdd <thing>` rather
    # than a second top-level verb.
    sub = run_cli("bdd", "--help")
    assert sub.returncode == 0, sub
    assert "extract" in sub.stdout, sub.stdout


# ---------------------------------------------------------------------------
# `TRC-A8` - the shipped config template documents the new keys, inert by default
# ---------------------------------------------------------------------------

BDD_CONFIG_KEYS = ("bdd_runner", "bdd_features_dir", "bdd_steps_dir",
                   "bdd_run_command")


def test_trc_a8_config_template_documents_bdd_keys(framework_root):
    # the config /compass:init copies into a project
    text = (framework_root / ".compass" / "config.yml").read_text(encoding="utf-8")

    for key in BDD_CONFIG_KEYS:
        assert key in text, f"{key} is not documented in the shipped config"

    # each key must carry a comment saying what it does - a bare key is not
    # documentation. Look for a comment line within the 6 lines above it.
    lines = text.splitlines()
    for key in BDD_CONFIG_KEYS:
        idx = next(i for i, l in enumerate(lines) if key in l)
        window = lines[max(0, idx - 6):idx + 1]
        assert any(l.lstrip().startswith("#") for l in window), (
            f"{key} has no explanatory comment above it"
        )

    # and each must be inert: commented out, or present with an empty value, so
    # a project that edits nothing has opted into nothing (ADR-006).
    cfg = yaml.safe_load(text) or {}
    project_cfg = cfg.get("project") or {}
    for key in BDD_CONFIG_KEYS:
        value = project_cfg.get(key, "")
        assert not value, (
            f"{key} ships with a value ({value!r}) - a project that edits "
            f"nothing would have opted in"
        )


# ---------------------------------------------------------------------------
# The anchor rule: Gherkin with no traceability comment is illustration, not
# a scenario, and is not extracted.
# ---------------------------------------------------------------------------

def test_illustrative_gherkin_without_a_trc_comment_is_ignored(make_task, run_cli):
    task_dir = make_task("anchor", {"assessment": {}, "scenarios": []})
    write_spec(task_dir, (
        "Here is an illustration of what a scenario looks like:\n\n"
        "```gherkin\n"
        "Scenario: this is only an example in prose\n"
        "  Given something\n  When something\n  Then something\n"
        "```\n\n"
        + scenario_block("TRC-A1", "the real one",
                         "  Given a state\n  When it fires\n  Then it holds")
    ))

    assert run_cli("bdd", "extract", "--issue", "anchor").returncode == 0
    text = (task_dir / "acceptance-criteria.feature").read_text(encoding="utf-8")
    assert text.count("Scenario:") == 1, text
    assert "only an example in prose" not in text, text
    assert "the real one" in text
