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


def test_idr_2_init_migrates_an_older_project_and_never_writes_beside_it():
    text = _init_text()
    assert "compass policy migrate" in text
    assert "--apply" in text
    assert re.search(r"dry run", text, flags=re.I), "the dry run comes first"
    assert re.search(r"go-ahead|says yes|agrees|approv", text, flags=re.I), (
        "--apply needs the person's go-ahead")
    # The trigger is stated for both older shapes.
    assert ".compass/config.yml" in text
    assert "copied governance" in text or "copied `governance/`" in text


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
