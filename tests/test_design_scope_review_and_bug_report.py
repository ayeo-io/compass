"""Design-decision scope, the regular requirements review and the hotfix bug report.

- A design decision says `Scope: issue` or `Scope: project`. `compass ship-commit`
  refuses an open issue whose registered technical design holds a project-scoped
  decision that no record in `architecture/decisions/` names (ADR-072).
- The regular approach owes `requirements-review` at depth `lightweight`: Self-QA of
  the spec, Ambiguity ledger and Gate.
- The hotfix approach owes `bug-report` at depth `thorough`.

Every project here is a real git repository driven through `cli/compass`, built with
the helpers of `tests/test_intent_and_release_line.py`.

Scenario ids: DSR-1 to DSR-10, in the acceptance criteria of the issue
`design-scope-review-and-bug-report`. Each test name starts with its id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_intent_and_release_line as irl  # noqa: E402

SLUG = irl.SLUG
CODE = "[project-decision-unrecorded]"
NOTE = "Keep the cache plain."


def design(cite="", scope="project"):
    """A technical design with one issue-scoped decision and one decision of `scope`."""
    scope_line = f"- **Scope:** {scope}\n" if scope else ""
    return (f"# Plan - {SLUG}\n\n## Design decisions (ADR-style)\n\n"
            "### `DD-1` - Keep the parser where it is\n\n- **Scope:** issue\n"
            "- **Decision:** The parser stays in its module.\n\n"
            "### `DD-2` - Keep the cache in one module\n\n" + scope_line +
            f"- **Decision:** One module owns the cache.{cite}\n")


def ready(tmp_path, text, adrs=None):
    """A regular issue ready to ship whose approved design is `text`, in a project whose
    `architecture/decisions/` holds `adrs` ({file name: text}), or none when `adrs` is None."""
    root = irl.project(tmp_path)
    irl.register(root, "technical-design", text=text)
    if adrs is not None:
        folder = root / "architecture" / "decisions"
        folder.mkdir(parents=True, exist_ok=True)
        for name, body in adrs.items():
            (folder / name).write_text(body)
    irl.ready_to_ship(root)
    return root


def ship(root):
    return irl.run(root, "ship-commit", "-m", "Ship it", "--issue", SLUG,
                   "--release-note", NOTE)


def assert_refused(root, done, path):
    assert done.returncode == 2, done
    assert CODE in done.stderr, done.stderr
    assert "DD-2" in done.stderr and "DD-1" not in done.stderr, done.stderr
    assert path in done.stderr, done.stderr
    assert "land_timestamp" not in irl.manifest(root)


# --- DSR-1 ----------------------------------------------------------------------------

def test_dsr_1_project_decision_without_record_refused(tmp_path):
    root = ready(tmp_path, design(), {"ADR-001-other.md": "# ADR-001\n\nAnother issue.\n"})
    before = irl.state(root)
    done = ship(root)
    assert_refused(root, done, "architecture/decisions/ADR-002-keep-the-cache-in-one-module.md")
    assert irl.state(root) == before
    irl.assert_no_gh_call(root)


@pytest.mark.parametrize("spelling", ["Project", "project.", "project - later issues follow it"])
def test_dsr_1_project_scope_read_in_any_case_with_punctuation_or_a_dash_explanation(
        tmp_path, spelling):
    # An author who declares the project scope in their own way still asks for the check.
    root = ready(tmp_path, design(scope=spelling), {"ADR-001-other.md": "# ADR-001\n\nOther.\n"})
    assert_refused(root, ship(root), "architecture/decisions/ADR-002-keep-the-cache-in-one-module.md")


def test_dsr_1_a_scope_line_that_is_prose_is_named_by_lint_and_does_not_refuse(tmp_path):
    # `Scope: project and more` is prose (#544), so the decision is unscoped and lands. The
    # lint reports the line, so a near-miss never passes without a word.
    root = ready(tmp_path, design(scope="project and more"),
                 {"ADR-001-other.md": "# ADR-001\n\nOther.\n"})
    linted = irl.run(root, "issue", "lint", "--issue", SLUG)
    assert linted.returncode == 0, linted
    assert "DD-2" in linted.stdout and "**Scope:** project and more" in linted.stdout, linted.stdout
    assert "`issue` or `project`" in linted.stdout, linted.stdout
    assert ship(root).returncode == 0


def test_dsr_1_a_long_run_of_spaces_after_the_value_reads_in_linear_time():
    # The trailing group once backtracked quadratically: 40,000 spaces took about 5 seconds.
    import time
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
    from compass_pkg import issue_page
    started = time.monotonic()
    for line in ("Scope: project" + " " * 40000 + "x", "Scope: project" + " " * 40000):
        issue_page._SCOPE.match(line)
        issue_page._SCOPE_START.match(line)
    assert time.monotonic() - started < 0.5


# --- DSR-2 ----------------------------------------------------------------------------

def test_dsr_2_record_naming_the_decision_lands(tmp_path):
    cited = ready(tmp_path / "cited", design(cite=" Recorded in ADR-001."),
                  {"ADR-001-cache.md": "# ADR-001\n\nOne module owns the cache.\n"})
    done = ship(cited)
    assert done.returncode == 0, done
    assert "project-decision" not in done.stdout + done.stderr

    named = ready(tmp_path / "named", design(),
                  {"ADR-001-cache.md": f"# ADR-001\n\nFrom {SLUG}, DD-2: one module.\n"})
    done = ship(named)
    assert done.returncode == 0, done


# --- DSR-3 ----------------------------------------------------------------------------

def test_dsr_3_issue_and_unscoped_decisions_not_refused(tmp_path):
    from compass_pkg import decision_scope
    for name, scope in (("issue", "issue"), ("unscoped", "")):
        root = ready(tmp_path / name, design(scope=scope))
        task_dir = str(root / ".compass" / "work" / SLUG)
        assert decision_scope.landing_refusal(irl.manifest(root), task_dir) is None, name
        done = ship(root)
        assert done.returncode == 0, (name, done)


# --- DSR-4 ----------------------------------------------------------------------------

def _shown(tmp_path, kind):
    done = irl.run(tmp_path, "issue", "template", "show", kind, cwd=tmp_path)
    assert done.returncode == 0, done
    return done.stdout


def test_dsr_4_templates_ask_for_the_scope(tmp_path):
    from compass_pkg.issue_page import design_decisions
    text = _shown(tmp_path, "technical-design")
    section = irl._section(text, "Design decisions (ADR-style)")
    blocks = section.split("### ")[1:]
    assert len(blocks) == 2, section
    for block in blocks:
        scope = [line for line in block.splitlines() if line.startswith("- **Scope:**")]
        assert len(scope) == 1 and "issue" in scope[0] and "project" in scope[0], block
    filled = text.replace("{{issue \\| project}}", "project")
    assert [d[2] for d in design_decisions(filled)] == ["project", "project"], filled

    notes = irl._section(_shown(tmp_path, "architecture-notes"), "Candidate decision records")
    assert "Scope: project" in notes and "project-scoped" in notes, notes


# --- DSR-5 ----------------------------------------------------------------------------

def test_dsr_5_regular_owes_lightweight_requirements_review(tmp_path):
    root = irl.project(tmp_path / "regular")
    entries = irl._entries(root, "requirements-review")
    assert [e.get("depth") for e in entries] == ["lightweight"], entries
    owed = irl.generation_config(root)["approaches"]["regular"]["artifacts"]
    assert owed.get("requirements-review") == "lightweight", owed

    full = irl.repo(tmp_path / "full")
    irl.assess(full, "full")
    assert [e.get("depth") for e in irl._entries(full, "requirements-review")] == ["thorough"]


# --- DSR-6 ----------------------------------------------------------------------------

def test_dsr_6_lightweight_review_sections(tmp_path):
    done = irl.run(tmp_path, "issue", "template", "show", "requirements-review",
                   "--depth", "lightweight", cwd=tmp_path)
    assert done.returncode == 0, done
    assert irl._headings(done.stdout) == ["Self-QA of the spec", "Ambiguity ledger",
                                          "Gate"], done.stdout
    assert "<!-- compass:render dor -->" in irl._section(done.stdout, "Gate"), done.stdout


# --- DSR-7 ----------------------------------------------------------------------------

def test_dsr_7_hotfix_owes_thorough_bug_report(tmp_path):
    root = irl.repo(tmp_path)
    irl.assess(root, "hotfix")
    assert [e.get("depth") for e in irl._entries(root, "bug-report")] == ["thorough"]
    assert [e.get("depth") for e in irl._entries(root, "acceptance-criteria")] == ["lightweight"]
    owed = irl.generation_config(root)["approaches"]["hotfix"]["artifacts"]
    assert owed.get("bug-report") == "thorough", owed


# --- DSR-8 ----------------------------------------------------------------------------

def test_dsr_8_missing_cited_record_does_not_count(tmp_path):
    root = ready(tmp_path, design(cite=" Recorded in ADR-009."),
                 {"ADR-001-other.md": "# ADR-001\n\nAnother issue.\n"})
    done = ship(root)
    assert_refused(root, done, "architecture/decisions/ADR-002-keep-the-cache-in-one-module.md")


# --- DSR-9 ----------------------------------------------------------------------------

def test_dsr_9_no_decisions_folder_names_first_record(tmp_path):
    root = ready(tmp_path, design())
    assert not (root / "architecture").exists()
    done = ship(root)
    assert_refused(root, done, "architecture/decisions/ADR-001-keep-the-cache-in-one-module.md")


# --- DSR-10 ---------------------------------------------------------------------------

def test_dsr_10_earlier_generation_owes_neither(tmp_path):
    root = irl.repo(tmp_path)
    irl.assess(root)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")

    def drop(resolved):
        resolved["approaches"]["regular"]["artifacts"].pop("requirements-review", None)
    irl.rewrite_stored(root, drop)
    body = irl.manifest(root)
    body["artifacts"] = [a for a in body.get("artifacts") or []
                         if a.get("kind") != "requirements-review"]
    irl.write_manifest(root, body)
    irl.ready_to_ship(root)
    done = ship(root)
    assert done.returncode == 0, done
    assert irl._entries(root, "requirements-review") == []
