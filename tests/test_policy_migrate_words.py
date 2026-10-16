"""`compass policy migrate --words` rewrites a project's own configuration in
the 6.0.0 words (issue `config-rewrite-tool`, scenarios CRW-1 to CRW-17).

6.0.0 reads an old word in `compass.yml` or a policy-test fixture through
`word_map` with a lint advisory, and 7.0.0 refuses it. The command maps each
file through that same mapping and replaces only the changed words in the
file's text. Every test runs the CLI over a temporary project, with no
network; the ones that need git make a repository there.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

ADVISORY = "the old word is read until 7.0.0"

OLD_LAYER = (
    "# Our Compass settings.\n"
    "schema: 1\n"
    "extends: compass:default@6\n"
    "\n"
    "approaches:\n"
    "  regular:\n"
    "    set:\n"
    "      # keep refine light for now\n"
    "      stages: {refine: light, plan: \"full\"}   # reviewed\n"
)

OLD_RULE = (
    "rules:\n"
    "  extra:\n"
    "    kind: floors\n"
    "    hit: {force_minimum_approach: max}\n"
    "    rules:\n"
    "      X-1:\n"
    "        order: 1\n"
    "        when: {size: standard}\n"
    "        then: {force_minimum_approach: full}\n"
    "        rationale: probe\n"
)

ROLE_RULE = (
    "rules:\n"
    "  extra:\n"
    "    kind: floors\n"
    "    hit: {force_minimum_approach: max}\n"
    "    rules:\n"
    "      X-1:\n"
    "        order: 1\n"
    "        when: {role: designer}\n"
    "        then: {force_minimum_approach: full}\n"
    "        rationale: probe\n"
)

OLD_FIXTURE = (
    "name: one\n"
    "assessment:\n"
    "  risk: contained\n"
    "  familiarity: brownfield-mapped\n"
    "  size: standard\n"
    "  goal: delivery\n"
    "  labels: []\n"
    "expect:\n"
    "  approach: regular\n"
    "  stages: {implement: full}\n"
)


def _git(cwd, *argv):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd),
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    done = subprocess.run(["git", *argv], cwd=str(cwd), env=env, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _project(tmp_path, files, git=True, name="proj"):
    """A project folder holding `files` ({path: text}), committed when `git`."""
    root = tmp_path / name
    (root / ".compass").mkdir(parents=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    if git:
        _git(root, "init", "--quiet", "-b", "main")
        _git(root, "add", "-A")
        _git(root, "commit", "--quiet", "-m", "start")
    return root


def _run(root, *args, cwd=None):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    # A temporary folder must never be judged as part of the repository
    # that holds the test run.
    env["GIT_CEILING_DIRECTORIES"] = str(Path(root).parent)
    env["COMPASS_OFFLINE"] = "1"
    proc = subprocess.run([sys.executable, str(CLI), "policy", "migrate", *args],
                          cwd=str(cwd or root), capture_output=True, text=True,
                          env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def _cli(root, *args):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(root).parent)
    env["COMPASS_OFFLINE"] = "1"
    proc = subprocess.run([sys.executable, str(CLI), *args], cwd=str(root),
                          capture_output=True, text=True, env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


# --- A: the dry run -----------------------------------------------------------

def test_crw_1_dry_run_shows_a_diff_and_writes_nothing(tmp_path):
    text = OLD_LAYER + OLD_RULE
    root = _project(tmp_path, {"compass.yml": text})
    code, out, err = _run(root, "--words")
    assert code == 0, out + err
    assert "--- a/compass.yml" in out and "+++ b/compass.yml" in out, out
    assert "-      stages: {refine: light, plan: \"full\"}   # reviewed" in out, out
    assert "+      stages: {refine: lightweight, plan: \"thorough\"}   # reviewed" in out, out
    assert "-        when: {size: standard}" in out and "+        when: {size: medium}" in out
    assert "nothing was written" in out.lower() and "--apply" in out, out
    assert (root / "compass.yml").read_text(encoding="utf-8") == text


def test_crw_2_dry_run_covers_the_fixtures(tmp_path):
    root = _project(tmp_path, {
        "compass.yml": "schema: 1\nextends: compass:default@6\n",
        "compass-fixtures/one.yml": OLD_FIXTURE,
        "compass-fixtures/banking/two.yml": OLD_FIXTURE.replace("  stages: {implement: full}\n", ""),
    })
    code, out, err = _run(root, "--words")
    assert code == 0, out + err
    assert "+++ b/compass-fixtures/one.yml" in out, out
    assert "+++ b/compass-fixtures/banking/two.yml" in out, out
    assert "+  size: medium" in out and "+  stages: {implement: thorough}" in out, out
    assert "+++ b/compass.yml" not in out, out


def test_crw_3_a_word_outside_the_mapped_fields_is_left_alone(tmp_path):
    text = ("schema: 1\nextends: compass:default@6\n"
            "# light is how we like it\n"
            + OLD_RULE.replace("{size: standard}", "{size: medium}")
                      .replace("rationale: probe", "rationale: standard practice"))
    root = _project(tmp_path, {"compass.yml": text})
    code, out, err = _run(root, "--words", "--apply")
    assert code == 0, out + err
    assert "nothing to change" in out, out
    assert (root / "compass.yml").read_text(encoding="utf-8") == text


# --- B: the rewrite -------------------------------------------------------------

def test_crw_4_apply_keeps_comments_order_and_quoting(tmp_path):
    root = _project(tmp_path, {"compass.yml": OLD_LAYER})
    code, out, err = _run(root, "--words", "--apply")
    assert code == 0, out + err
    assert "wrote compass.yml" in out, out
    before = OLD_LAYER.splitlines()
    after = (root / "compass.yml").read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    changed = [(b, a) for b, a in zip(before, after) if b != a]
    assert changed == [("      stages: {refine: light, plan: \"full\"}   # reviewed",
                        "      stages: {refine: lightweight, plan: \"thorough\"}   # reviewed")]


def test_crw_5_after_apply_lint_is_quiet_and_a_second_run_changes_nothing(tmp_path):
    root = _project(tmp_path, {"compass.yml": OLD_LAYER + OLD_RULE})
    _, out, err = _cli(root, "policy", "lint")
    assert ADVISORY in out + err, out + err          # the lint sees the old words first
    code, out, err = _run(root, "--words", "--apply")
    assert code == 0, out + err
    _git(root, "commit", "--quiet", "-am", "rewrite")
    _, out, err = _cli(root, "policy", "lint")
    assert ADVISORY not in out + err, out + err
    code, out, err = _run(root, "--words")
    assert code == 0 and "nothing to change" in out, out + err


def test_crw_6_a_file_the_rewrite_cannot_place_is_refused(tmp_path):
    # A block scalar spans lines, so its old word cannot be swapped in place.
    # (A `<<` merge key never gets here: the strict loader refuses it.)
    text = ("schema: 1\nextends: compass:default@6\n"
            "approaches:\n  regular:\n    set:\n"
            "      stages:\n        refine: >-\n          light\n")
    fixture = OLD_FIXTURE
    root = _project(tmp_path, {"compass.yml": text, "compass-fixtures/one.yml": fixture})
    code, out, err = _run(root, "--words", "--apply")
    assert code == 2, out + err
    assert "compass.yml" in err and "by hand" in err, err
    assert (root / "compass.yml").read_text(encoding="utf-8") == text
    assert (root / "compass-fixtures" / "one.yml").read_text(encoding="utf-8") == fixture


# --- C: where it may write ------------------------------------------------------

def test_crw_7_a_folder_outside_the_project_is_refused(tmp_path):
    root = _project(tmp_path, {"compass.yml": "schema: 1\nextends: compass:default@6\n"})
    other = tmp_path / "other"
    other.mkdir()
    (other / "compass.yml").write_text(OLD_LAYER, encoding="utf-8")
    code, out, err = _run(root, "--words", "../other", "--apply")
    assert code == 2, out + err
    assert "outside the project" in err, err
    assert (other / "compass.yml").read_text(encoding="utf-8") == OLD_LAYER


def test_crw_8_a_linked_file_is_refused(tmp_path):
    real = tmp_path / "real.yml"
    real.write_text(OLD_LAYER, encoding="utf-8")
    root = _project(tmp_path, {}, git=False)
    (root / "compass.yml").symlink_to(real)
    code, out, err = _run(root, "--words", "--apply", "--i-have-a-copy")
    assert code == 2, out + err
    assert "compass.yml" in err and "link" in err, err
    assert real.read_text(encoding="utf-8") == OLD_LAYER


def test_crw_9_an_unrestorable_file_is_refused_unless_there_is_a_copy(tmp_path):
    root = _project(tmp_path, {"compass.yml": OLD_LAYER,
                               "compass-fixtures/one.yml": OLD_FIXTURE})
    edited = OLD_LAYER + "# edited since the commit\n"
    (root / "compass.yml").write_text(edited, encoding="utf-8")
    code, out, err = _run(root, "--words")
    assert code == 0, out + err
    assert "--apply would refuse" in out and "compass.yml" in out, out
    code, out, err = _run(root, "--words", "--apply")
    assert code == 2, out + err
    assert "compass.yml" in err and "--i-have-a-copy" in err, err
    assert "compass-fixtures/one.yml" not in err.split("\n\n")[0], err
    assert (root / "compass.yml").read_text(encoding="utf-8") == edited
    assert (root / "compass-fixtures" / "one.yml").read_text(encoding="utf-8") == OLD_FIXTURE
    code, out, err = _run(root, "--words", "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    assert "lightweight" in (root / "compass.yml").read_text(encoding="utf-8")
    assert "size: medium" in (root / "compass-fixtures" / "one.yml").read_text(encoding="utf-8")


def test_crw_10_outside_git_the_write_needs_a_copy(tmp_path):
    root = _project(tmp_path, {"compass.yml": OLD_LAYER}, git=False)
    code, out, err = _run(root, "--words", "--apply")
    assert code == 2, out + err
    assert "--i-have-a-copy" in err and "git" in err, err
    assert (root / "compass.yml").read_text(encoding="utf-8") == OLD_LAYER
    code, out, err = _run(root, "--words", "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    assert "lightweight" in (root / "compass.yml").read_text(encoding="utf-8")


# --- D: the retired role dimension ---------------------------------------------

def test_crw_11_a_rule_that_reads_role_is_listed_for_a_hand_edit(tmp_path):
    from compass_pkg import retired
    root = _project(tmp_path, {"compass.yml": OLD_LAYER + ROLE_RULE})
    code, out, err = _run(root, "--words", "--apply")
    assert code == 1, out + err
    after = (root / "compass.yml").read_text(encoding="utf-8")
    assert "refine: lightweight" in after
    assert "        when: {role: designer}\n" in after
    lint = [m for c, p, m in retired.condition_findings(
        {"rules": {"extra": {"rules": {"X-1": {"when": {"role": "designer"}}}}}})]
    assert "M-WHEN-RETIRED" in out and "rules.extra.rules.X-1.when" in out, out
    assert lint and lint[0] in out, (lint, out)


def test_crw_12_a_declared_role_dimension_is_not_a_hand_edit(tmp_path):
    text = ("schema: 1\nextends: compass:default@6\ndimensions:\n  role:\n    type: enum\n"
            "    values: [engineer, designer]\n" + ROLE_RULE)
    root = _project(tmp_path, {"compass.yml": text})
    code, out, err = _run(root, "--words")
    assert code == 0, out + err
    assert "M-WHEN-RETIRED" not in out + err, out


def test_crw_13_an_edit_to_a_retired_rule_set_names_its_replacement(tmp_path):
    text = ("schema: 1\nextends: compass:default@6\nrules:\n  role_rules:\n"
            "    set:\n      hit: {force_minimum_approach: max}\n")
    root = _project(tmp_path, {"compass.yml": text})
    code, out, err = _run(root, "--words")
    assert code == 1, out + err
    assert "rules.role_rules" in out and "RP-ART-001" in out, out
    assert "rules.artifact_rules" in out, out


def test_crw_14_a_fixture_role_is_kept_with_a_note(tmp_path):
    from compass_pkg import retired
    fixture = OLD_FIXTURE.replace("  goal: delivery\n", "  goal: delivery\n  role: engineer\n")
    root = _project(tmp_path, {"compass-fixtures/one.yml": fixture})
    code, out, err = _run(root, "--words", "--apply")
    assert code == 0, out + err
    after = (root / "compass-fixtures" / "one.yml").read_text(encoding="utf-8")
    assert "  size: medium\n" in after and "  role: engineer\n" in after
    assert "compass-fixtures/one.yml" in out and retired.NOT_READ in out, out


# --- E: the command -------------------------------------------------------------

def test_crw_15_the_json_report(tmp_path):
    root = _project(tmp_path, {"compass.yml": OLD_LAYER})
    code, out, err = _run(root, "--words", "--json")
    assert code == 0, out + err
    doc = json.loads(out)
    assert list(doc) == ["schema_version", "mode", "folder", "files", "hand_edits",
                         "notes", "result"], list(doc)
    assert doc["mode"] == "dry-run" and doc["result"] == "dry-run" and doc["folder"] == "."
    (entry,) = doc["files"]
    assert list(entry) == ["path", "changes", "diff", "written"]
    assert entry["path"] == "compass.yml" and entry["written"] is False
    assert {"path": "approaches.regular.set.stages.refine", "old": "light",
            "new": "lightweight"} in entry["changes"], entry["changes"]
    assert entry["diff"].startswith("--- a/compass.yml\n")


def test_crw_16_nothing_to_change(tmp_path):
    root = _project(tmp_path, {
        "compass.yml": OLD_LAYER.replace("light", "lightweight").replace('"full"', '"thorough"'),
        "compass-fixtures/one.yml": OLD_FIXTURE.replace("standard", "medium")
                                               .replace("implement: full", "implement: thorough"),
    })
    code, out, err = _run(root, "--words")
    assert code == 0, out + err
    assert "nothing to change" in out, out
    assert "---" not in out, out


def test_crw_17_the_word_flags_need_words(tmp_path):
    root = _project(tmp_path, {"compass.yml": OLD_LAYER})
    for args in (["."], ["--i-have-a-copy"]):
        code, out, err = _run(root, *args)
        assert code == 2, (args, out + err)
        assert "--words" in err, (args, err)
    assert (root / "compass.yml").read_text(encoding="utf-8") == OLD_LAYER


def test_crw_4_the_text_rewrite_keeps_line_endings_quotes_and_aliases():
    """The text function under CRW-4: CRLF line endings, a single-quoted word
    and an alias of a replaced node all survive the rewrite."""
    from compass_pkg import config_words, word_map
    text = ("schema: 1\r\napproaches:\r\n  regular:\r\n    set:\r\n"
            "      stages: &s {refine: 'light'}\r\n"
            "  quick-fix:\r\n    set:\r\n      stages: *s\r\n")
    new, changes = config_words.rewrite_text(
        text, lambda doc: word_map.map_layer(doc)[0], "compass.yml")
    assert new == text.replace("'light'", "'lightweight'"), new
    assert changes == [("approaches.regular.set.stages.refine", "light", "lightweight")]


def test_crw_11_a_role_rule_set_into_a_shipped_rule_set_is_listed(tmp_path):
    """A project adds its rule to a shipped rule set with `set:` on the set and
    on its `rules:` map; the lint reads the merged rule, so the hand edit must
    find it there too."""
    text = ("schema: 1\nextends: compass:default@6\nrules:\n  floors:\n    set:\n"
            "      rules:\n        set:\n          X-1:\n            order: 9\n"
            "            when: {role: designer}\n"
            "            then: {force_minimum_approach: full}\n"
            "            rationale: probe\n")
    root = _project(tmp_path, {"compass.yml": text})
    code, out, err = _run(root, "--words")
    assert code == 1, out + err
    assert "M-WHEN-RETIRED" in out and "rules.floors.rules.X-1.when" in out, out


def test_crw_9_a_write_that_fails_leaves_every_file_as_it_was(tmp_path):
    """A run writes every file or none: when the second file cannot be
    written, the first is not rewritten either."""
    root = _project(tmp_path, {"compass.yml": OLD_LAYER,
                               "compass-fixtures/one.yml": OLD_FIXTURE})
    folder = root / "compass-fixtures"
    folder.chmod(0o555)
    try:
        code, out, err = _run(root, "--words", "--apply")
    finally:
        folder.chmod(0o755)
    assert code == 2, out + err
    assert "Traceback" not in err and "Nothing was written" in err, err
    assert "compass-fixtures/one.yml cannot be written" in err, err
    assert (root / "compass.yml").read_text(encoding="utf-8") == OLD_LAYER
    assert (folder / "one.yml").read_text(encoding="utf-8") == OLD_FIXTURE


def test_crw_8_a_linked_fixture_folder_is_refused(tmp_path):
    root = _project(tmp_path, {"compass.yml": "schema: 1\nextends: compass:default@6\n",
                               "elsewhere/one.yml": OLD_FIXTURE})
    (root / "compass-fixtures").symlink_to(root / "elsewhere")
    code, out, err = _run(root, "--words", "--apply", "--i-have-a-copy")
    assert code == 2, out + err
    assert "compass-fixtures" in err and "link" in err, err
    assert (root / "elsewhere" / "one.yml").read_text(encoding="utf-8") == OLD_FIXTURE
