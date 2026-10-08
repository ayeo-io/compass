"""`/compass:init` writes a minimal `compass.yml` and migrates an older project.

`compass init` (the verb every entry point runs) writes the state file in
`.compass/` and no settings file. `/compass:init` is the step that writes
`compass.yml`, and it runs `compass policy migrate` instead when the project
already has a `.compass/config.yml` or copied governance, so a project never
holds both settings files (ADR-043).

Scenario ids: IDR-1 to IDR-4, in the acceptance criteria of the issue
`init-docs-release`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
INIT_MD = ROOT / "commands" / "init.md"


def _init_text():
    return INIT_MD.read_text(encoding="utf-8")


def _yaml_blocks(text):
    return re.findall(r"```yaml\n(.*?)```", text, flags=re.S)


def _compass(cwd, *args):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=120, env=env)


def test_idr_1_init_writes_a_minimal_compass_yml_that_lints(tmp_path):
    blocks = [b for b in _yaml_blocks(_init_text()) if "schema:" in b]
    assert blocks, "commands/init.md shows no minimal compass.yml"
    doc = yaml.safe_load(blocks[0])
    assert set(doc) >= {"schema", "extends", "owner"}, doc
    assert doc["extends"].startswith("compass:default@"), doc

    project = tmp_path / "fresh"
    project.mkdir()
    assert _compass(project, "init").returncode == 0
    (project / "compass.yml").write_text(blocks[0], encoding="utf-8")
    run = _compass(project, "policy", "lint")
    assert run.returncode == 0, run.stdout + run.stderr


def _step(text, number):
    """The text of one numbered step of the Steps list, alone."""
    m = re.search(rf"^{number}\. \*\*.*?(?=^{number + 1}\. \*\*)", text,
                  flags=re.S | re.M)
    assert m, f"commands/init.md has no step {number}"
    return m.group(0)


def _migrate_step_problems(text):
    """What is wrong with step 2 (migrate an older project) and step 1 (the
    trigger), read apart from the rest of the file. Both halves of the
    scenario's name are checked: a dry run and approval before `--apply`, and
    no fresh `compass.yml` written beside an older settings file."""
    one, two = _step(text, 1), _step(text, 2)
    problems = []
    if ".compass/config.yml" not in one or "copied governance" not in one:
        problems.append("step 1 does not name both older shapes")
    if not re.search(r"schema:.*(?:not|no).*overwrite|no `schema:`.*(?:migrate|refus|do not)",
                     one, flags=re.S | re.I):
        problems.append("step 1 does not refuse a compass.yml with no schema key")
    dry = two.find("compass policy migrate`")
    apply_ = two.find("compass policy migrate --apply")
    ask = re.search(r"Apply this migration\?|go-ahead|says yes", two)
    if dry < 0 or apply_ < 0 or dry > apply_:
        problems.append("step 2 does not run the dry run before --apply")
    if not re.search(r"dry run", two, flags=re.I):
        problems.append("step 2 does not call the first run a dry run")
    if not ask or ask.start() > apply_:
        problems.append("step 2 does not ask for approval before --apply")
    if not re.search(r"Never write a fresh `compass.yml` beside", two):
        problems.append("step 2 does not forbid writing beside an older file")
    return problems


def test_idr_2_init_migrates_an_older_project_and_never_writes_beside_it():
    assert _migrate_step_problems(_init_text()) == []


def test_idr_2_the_check_fails_on_a_step_2_that_applies_straight_away():
    text = _init_text()
    two = _step(text, 2)
    planted = text.replace(two, (
        "2. **Migrate an older project.** Run `compass policy migrate --apply` "
        "straight away.\n\n"))
    assert planted != text
    problems = _migrate_step_problems(planted)
    assert any("dry run" in p for p in problems), problems
    assert any("approval" in p for p in problems), problems
    assert any("beside" in p for p in problems), problems


def test_idr_2_step_2_asks_for_an_owner_after_migrating():
    two = _step(_init_text(), 2)
    assert re.search(r"owner", two), (
        "a migrated project has no owner, and a waiver needs one")


def test_idr_3_init_copies_no_governance_into_a_new_project():
    text = _init_text()
    assert "Copy `governance/` into the project" not in text
    assert "strategies-rationale.md" not in text, (
        "copying governance is what policy migrate converts, not what init does")
    assert "Copies nothing" in text or "copies nothing" in text


def test_idr_4_the_verb_points_a_new_project_at_compass_yml(tmp_path):
    project = tmp_path / "fresh"
    project.mkdir()
    run = _compass(project, "init")
    out = run.stdout + run.stderr
    assert "adopt your own" not in out, out
    assert "compass.yml" in out, out
    assert (project / ".compass" / "state.yml").is_file()
    assert not (project / ".compass" / "config.yml").exists()
    assert not (project / "compass.yml").exists(), (
        "the verb writes no settings file; only /compass:init does")


# What 5.x said and 6.0.0 does not: `/compass:init` copies governance/ into the
# project. A project that copied it under 5.x is migrated, not told init copies.
SAYS_INIT_COPIES = re.compile(
    r"/compass:init`?\s+(?:also\s+)?copies(?! nothing)"
    r"|\bit copies governance/"
    r"|conversation that copies governance/"
    r"|1\. \*\*Copies `governance/`\*\*",
    re.I)
# Records of past issues and decisions describe what was true then.
HISTORY = ("docs/compass/", "architecture/decisions/", "governance/decisions/",
           "docs/system-spec", "tests/", "templates/architecture/")


def _tracked_text():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout
    for rel in out.split("\0"):
        if not rel or rel.startswith(HISTORY):
            continue
        if rel.endswith((".md", ".py", ".sh", ".yml", ".yaml")):
            path = ROOT / rel
            if path.is_file():
                yield rel, path.read_text(encoding="utf-8")


def test_idr_3_the_pattern_flags_what_5x_said_and_not_what_6_does():
    assert SAYS_INIT_COPIES.search("`/compass:init` copies this file into the project")
    assert SAYS_INIT_COPIES.search("echo \"     it copies governance/ into the project")
    assert not SAYS_INIT_COPIES.search("`/compass:init` copies nothing.")
    assert not SAYS_INIT_COPIES.search("`/compass:init` writes a compass.yml")


def test_idr_4_the_verb_help_does_not_say_init_writes_a_config_file():
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.verb_help import VERB_DESCRIPTIONS
    text = VERB_DESCRIPTIONS["init"]
    assert "config file" not in text, text
    assert "state file" in text and "compass.yml" in text, text


def test_idr_3_no_tracked_text_says_init_copies_governance():
    offenders = {rel: m.group(0) for rel, text in _tracked_text()
                 for m in [SAYS_INIT_COPIES.search(text)] if m}
    assert not offenders, offenders
