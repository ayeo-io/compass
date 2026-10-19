"""The readiness override in this repository's compass.yml, end to end.

A swap of the timed test command between its two declared choices classifies
as equivalent, `compass policy diff` names it on its own line, and every
`compass policy lint` in the framework repository reads the chain the
write-time lint reads. These tests start CLI processes or read this
repository's own files, so they live outside the micro suite that
`compass readiness` times (`project.test_micro_command`).

Scenario ids: ROA-8 to ROA-11 and ROA-14 to ROA-17 (issue
`readiness-override-assess`). ROA-1 to ROA-7 are in tests/test_classifier.py,
ROA-12 and ROA-13 in tests/test_framework_compass_yml.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import project_readiness_support as support  # noqa: E402

TIMED = "tests-declared-and-under-two-minutes"
MAP_FORM = (f"readiness:\n  {TIMED}:\n"
            "    set: {params: {set: {command: test_micro_command}}}\n")
PLAIN_MAP = (f"readiness:\n  {TIMED}:\n"
             "    set: {params: {command: test_micro_command}}\n")
HEAD = "schema: 1\nextends: compass:default@6\n"
SWAP_LINE = f"changes readiness {TIMED} command: test_command -> test_micro_command"


# --- ROA-8: compass policy diff names the swap -----------------------------------

def test_roa_8_policy_diff_names_the_command_swap(tmp_path):
    project = support.make_project(tmp_path / "p", HEAD + MAP_FORM)
    code, out, err = support.run_compass(project, "policy", "diff", "default@6", "project")
    assert code == 0, out + err
    lines = out.splitlines()
    assert SWAP_LINE in lines, out
    # The line sits outside the classification: it is not part of the verdict.
    assert lines.index(SWAP_LINE) < next(
        i for i, line in enumerate(lines) if line.startswith("classification:"))
    assert "classification: equivalent" in out
    assert "waiver" not in out

    code, out, err = support.run_compass(project, "policy", "diff", "default@6", "project",
                                         "--json")
    assert code == 0, out + err
    assert json.loads(out)["classification"]["result"] == "equivalent"

    code, out, err = support.run_compass(project, "policy", "diff", "default@6", "default@6")
    assert code == 0, out + err
    assert not [line for line in out.splitlines() if line.startswith("changes readiness")]


# --- ROA-9: every policy command here loads compass.yml ----------------------------

def _run_here(home, *argv):
    """Run this repository's CLI with the repository root as the working folder."""
    import subprocess
    done = subprocess.run([sys.executable, str(support.CLI), *argv], cwd=ROOT,
                          env=support.environment(home), capture_output=True, text=True,
                          timeout=300)
    return done.returncode, done.stdout, done.stderr


def _kinds(document):
    return [layer["kind"] for layer in document["layers"]]


def _first_error(document):
    return next(f["code"] for f in document["findings"] if f["level"] == "error")


def _in_process(monkeypatch, capsys, run, slug):
    """Run a policy verb in this process with `--issue slug --json` and
    return its JSON document."""
    import argparse
    capsys.readouterr()
    run(argparse.Namespace(task=slug, file=None, exhaustive=False, offline=True,
                           json=True))
    return json.loads(capsys.readouterr().out)


def test_roa_9_policy_commands_load_compass_yml_in_this_repository(
        tmp_path, monkeypatch, capsys):
    import os
    import shutil
    from compass_pkg import policy_cmd, project_settings
    from compass_pkg.core import FRAMEWORK_ROOT
    slug = f"roa-9-probe-{os.getpid()}"
    probe = ROOT / ".compass" / "work" / slug
    try:
        _probe_manifest(ROOT, slug)
        code, out, err = _run_here(tmp_path, "policy", "lint", "--issue", slug, "--json")
        assert "project" in _kinds(json.loads(out)), out + err
        code, out, err = _run_here(tmp_path, "policy", "show", "--issue", slug, "--json")
        assert code == 0, out + err
        assert "project" in _kinds(json.loads(out)), out + err

        # `--file` reads the named file wherever it runs.
        planted = tmp_path / "compass.yml"
        planted.write_text((ROOT / "compass.yml").read_text(encoding="utf-8")
                           .replace(MAP_FORM, PLAIN_MAP), encoding="utf-8")
        code, out, err = _run_here(tmp_path, "policy", "lint", "--file", str(planted),
                                   "--json")
        assert code == 1 and _first_error(json.loads(out)) == "C-INCOMPARABLE", out + err

        # With the framework-root exemption planted back, neither command
        # reads compass.yml, so the project-layer assertion above would fail.
        def exempt(root):
            if os.path.realpath(root) == os.path.realpath(FRAMEWORK_ROOT):
                return False
            return project_settings.compass_yml_counts(root)
        monkeypatch.chdir(ROOT)
        assert "project" in _kinds(_in_process(monkeypatch, capsys,
                                               policy_cmd.run_policy_lint, slug))
        monkeypatch.setattr(policy_cmd, "_is_layered", exempt)
        for run in (policy_cmd.run_policy_lint, policy_cmd.run_policy_effective):
            assert "project" not in _kinds(_in_process(monkeypatch, capsys, run, slug))
    finally:
        shutil.rmtree(probe, ignore_errors=True)
    assert not probe.exists()


# --- ROA-10: the write-time lint and compass policy lint --issue agree -------------

def _write_time_error(project, slug):
    """The first error code of the write-time lint (`resolve_live` with
    `validate`), or None when it passes."""
    import yaml
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    task = Path(project) / ".compass" / "work" / slug
    manifest = yaml.safe_load((task / "manifest.yml").read_text(encoding="utf-8"))
    try:
        effective.resolve_live(str(project), manifest=manifest, slug=slug,
                               task_dir=str(task), validate=True)
    except CompassError as exc:
        return str(exc).split("First error: ", 1)[1].split(" ", 1)[0]
    return None


def test_roa_10_the_write_time_lint_and_policy_lint_agree(tmp_path):
    real = (ROOT / "compass.yml").read_text(encoding="utf-8")
    for name, text, code_wanted, first in (
            ("real", real, 0, None),
            ("plain", real.replace(MAP_FORM, PLAIN_MAP), 1, "C-INCOMPARABLE")):
        project = support.make_project(tmp_path / name, text)
        _probe_manifest(project, "probe")
        code, out, err = support.run_compass(project, "policy", "lint", "--issue", "probe",
                                             "--json")
        assert code == code_wanted, (name, out + err)
        if first is not None:
            assert _first_error(json.loads(out)) == first, out
        assert _write_time_error(project, "probe") == first, name


# --- ROA-11: the no-argument lint in the framework repository ----------------------

def _framework_copy(tmp_path, monkeypatch, compass_yml=None):
    """A copy of this repository's governance/, .compass/ (its tracked state,
    not the issue folders) and compass.yml, treated as the framework root."""
    import shutil
    from compass_pkg import policy_cmd
    copy = tmp_path / "framework"
    shutil.copytree(ROOT / "governance", copy / "governance")
    shutil.copytree(ROOT / ".compass", copy / ".compass",
                    ignore=shutil.ignore_patterns("work", "private", "cache", "*.lock",
                                                  "sessions.json", "current-task"))
    text = (ROOT / "compass.yml").read_text(encoding="utf-8")
    (copy / "compass.yml").write_text(compass_yml(text) if compass_yml else text,
                                      encoding="utf-8")
    monkeypatch.chdir(copy)
    real = policy_cmd._is_framework_root
    monkeypatch.setattr(policy_cmd, "_is_framework_root",
                        lambda root: real(root) or Path(root).resolve() == copy.resolve())
    return copy


def _lint_here(capsys, json_mode=False):
    import argparse
    from compass_pkg import policy_cmd
    capsys.readouterr()
    code = policy_cmd.run_policy_lint(argparse.Namespace(
        task=None, file=None, exhaustive=False, offline=True, json=json_mode))
    out = capsys.readouterr()
    return code, out.out + out.err


def test_roa_11_policy_lint_without_arguments_lints_compass_yml(
        tmp_path, monkeypatch, capsys):
    _framework_copy(tmp_path / "real", monkeypatch)
    code, out = _lint_here(capsys)
    assert code == 0, out
    results = [line for line in out.splitlines() if line.startswith("compass policy lint:")]
    assert len(results) == 2, out
    assert "routing-policy.yml and guardrails.yml" in results[0]     # the legacy lint
    assert results[1] == "compass policy lint: PASS"                  # the layered lint

    _framework_copy(tmp_path / "plain", monkeypatch,
                    lambda text: text.replace(MAP_FORM, PLAIN_MAP))
    code, out = _lint_here(capsys)
    assert code == 1 and "C-INCOMPARABLE" in out, out
    code, out = _lint_here(capsys, json_mode=True)
    document = json.loads(out)
    assert code == 1 and document["result"] == "fail", out
    assert document["mode"] == "framework"
    assert _kinds(document)[0] == "legacy" and "project" in _kinds(document)

    # A legacy structure error fails the lint although compass.yml is clean.
    import yaml
    copy = _framework_copy(tmp_path / "legacy", monkeypatch)
    guardrails = copy / "governance" / "guardrails.yml"
    doc = yaml.safe_load(guardrails.read_text(encoding="utf-8"))
    doc.pop("defaults")
    guardrails.write_text(yaml.safe_dump(doc), encoding="utf-8")
    code, out = _lint_here(capsys)
    assert code == 1 and "missing top-level key: defaults" in out, out
    assert out.splitlines()[-1] == "compass policy lint: PASS", out     # compass.yml is clean

    text = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")
    assert 'LINT_OUT="$(python3 cli/compass policy lint 2>&1)"' in text

    # Outside the framework root, with no compass.yml, the output is the legacy
    # lint's own, as before.
    from compass_pkg import governance
    plain = support.make_project(tmp_path / "plain-project")
    monkeypatch.chdir(plain)
    code, out = _lint_here(capsys)
    import argparse
    legacy_code = governance.cmd_policy_lint(argparse.Namespace())
    assert (code, out) == (legacy_code, capsys.readouterr().out)


# --- ROA-15: the governance decision entry ------------------------------------------

DECISION = "a-declared-equivalent-parameter-choice-classifies-as-equivalent"


def _sections(text):
    """`{heading: body}` for each `## ` section of a decision entry."""
    out = {}
    for block in text.split("\n## ")[1:]:
        heading, _, body = block.partition("\n")
        out[heading.strip()] = " ".join(body.split())
    return out


def test_roa_15_the_decision_entry_records_the_rule(tmp_path):
    path = ROOT / "governance" / "decisions" / f"2026-10-14-{DECISION}.md"
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == f"# {DECISION}"
    sections = _sections(text)
    assert list(sections) == ["Decided by", "Date", "Supersedes", "Decision", "Why",
                              "Evidence"]
    assert sections["Decided by"] == "jed72" and sections["Date"] == "2026-10-14"
    decision = sections["Decision"]
    for statement in (
            "Only the readiness registry, which ships with the CLI, can declare the "
            "direction `equivalent`",
            "refuses `equivalent` on a parameter that has no `choices` entry",
            "A catalogue or a preset cannot declare `equivalent`",
            "both sides name the same implementation, both values are present and both "
            "are in that implementation's `choices`",
            "A value missing on either side, or a value outside `choices`, is incomparable",
            "never tighter or looser",
            "`compass policy diff` names the swap on its own line"):
        assert statement in decision, statement
    assert "amends no entry" in sections["Supersedes"]
    assert ("`2026-10-13-this-repository-declares-readiness-commands` still holds"
            in sections["Supersedes"])

    # The base is a commit this test makes in its own repository, so the result
    # does not depend on where `origin/main` points when the test runs.
    relative = f"governance/decisions/{path.name}"
    project = support.make_project(tmp_path / "decisions", files={relative: text})
    base = support.git(project, "rev-parse", "HEAD").strip()
    code, out, err = support.run_compass(project, "decision", "check", "--base", base)
    assert code == 0, out + err
    (project / relative).write_text(text + "\nedited\n", encoding="utf-8")
    code, out, err = support.run_compass(project, "decision", "check", "--base", base)
    assert code == 1 and "was changed" in out, out + err


# --- ROA-16: the owning docs ---------------------------------------------------------

def _flat(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def test_roa_16_the_owning_docs_describe_the_rule_and_the_chain():
    import inspect
    from compass_pkg import policy_cmd
    for text in (" ".join(policy_cmd.__doc__.split()),
                 " ".join(inspect.getsource(policy_cmd._is_layered).split()),
                 _flat("docs/policy-lint.md")):
        assert "framework's own repository keeps the legacy lint" not in text
        assert "The framework's repository keeps the legacy lint" not in text
        assert "| The framework's own repository | The legacy lint |" not in text
    lint_doc = _flat("docs/policy-lint.md")
    assert ("With no arguments in the framework's own repository, `compass policy lint` "
            "runs the legacy lint and then the layered lint, and fails if either fails"
            in lint_doc)
    assert "`framework`" in lint_doc
    readiness_doc = _flat("docs/readiness.md")
    assert "`tests-under-limit.command` has the direction `equivalent`" in readiness_doc
    assert "set: {params: {set: {command: test_micro_command}}}" in readiness_doc
    routing = _flat("governance/routing-policy.md")
    assert "the direction `equivalent`" in routing
    assert "this rule raised `CLASSIFIER_VERSION` to 5" in routing
    diff_doc = _flat("docs/policy-diff.md")
    assert "changes readiness <signal> <param>: <parent value> -> <child value>" in diff_doc
    guardrails = _flat("governance/guardrails.md")
    assert "a check parameter cannot declare `equivalent`" in guardrails


# --- ROA-17: this repository's chain resolves for a write ----------------------------

def test_roa_17_the_repository_chain_resolves_for_a_write():
    # The check a write runs: this issue's reassessment, recorded as
    # command-output evidence, is the end-to-end proof in the worktree.
    from compass_pkg import effective
    effective.resolve_live(str(ROOT), validate=True)


# --- ROA-14: assess and start a quick fix under this repository's compass.yml ------

ASSESSMENT = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
              "goal": "delivery", "urgency": "none", "role": "engineer", "labels": []}


def _probe_manifest(project, slug):
    """A probe issue's manifest, written from templates/manifest.yml with a
    real assessment in place of the template's placeholders."""
    import yaml
    text = (ROOT / "templates" / "manifest.yml").read_text(encoding="utf-8")
    doc = yaml.safe_load(text.replace("{{ISSUE_SLUG}}", slug).replace("{{DATE}}", "2026-10-14"))
    doc["assessment"] = dict(ASSESSMENT)
    task = Path(project) / ".compass" / "work" / slug
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return task


def _evaluate(project, slug):
    justify = [arg for name in ("risk", "familiarity", "size", "goal", "urgency", "role")
               for arg in ("--justify", f"{name}=Probe: the {name} was judged.")]
    return support.run_compass(project, "approach", "evaluate", "--issue", slug, "--write",
                               *justify)


def _quick_fix(project, slug):
    return support.run_compass(
        project, "quick-fix", "start", slug,
        "--risk", "trivial - a probe changes one line",
        "--familiarity", "brownfield-mapped - the probe file is known",
        "--size", "atomic - one file",
        "--intent", "A probe issue starts.",
        "--scenario", "Given a probe, when it starts, then it is recorded.",
        "--scenario-id", "QF-1", "--test", "tests/test_probe.py::test_probe")


def _generation_1(project, slug):
    return Path(project) / ".compass" / "work" / slug / "generations" / "1" / "complete"


def _project_with(tmp_path, name, compass_yml):
    project = support.make_project(tmp_path / name, compass_yml)
    support.meet_readiness_floor(project)
    return project


def test_roa_14_assess_and_quick_fix_start_under_this_compass_yml(tmp_path):
    real = (ROOT / "compass.yml").read_text(encoding="utf-8")
    assert "autonomy: autonomous" in real and MAP_FORM in real
    project = _project_with(tmp_path, "real", real)
    _probe_manifest(project, "probe-a")
    code, out, err = _evaluate(project, "probe-a")
    assert code == 0, out + err
    assert _generation_1(project, "probe-a").is_file()
    code, out, err = _quick_fix(project, "probe-b")
    assert code == 0, out + err
    assert _generation_1(project, "probe-b").is_file()

    # A repeat of the readiness override that blocked every assessment: the
    # plain-map override drops `limit_seconds`, and both
    # writes are refused before anything is written.
    planted = _project_with(tmp_path, "plain", real.replace(MAP_FORM, PLAIN_MAP))
    task = _probe_manifest(planted, "probe-c")
    code, out, err = _evaluate(planted, "probe-c")
    assert code == 2 and "C-INCOMPARABLE" in out + err, out + err
    assert not (task / "generations").exists()
    code, out, err = _quick_fix(planted, "probe-d")
    assert code == 2 and "C-INCOMPARABLE" in out + err, out + err
    assert not (Path(planted) / ".compass" / "work" / "probe-d").exists()
