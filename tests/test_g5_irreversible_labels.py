"""Guardrail `G5` asks for a person's sign-off only on the four labels whose
change is irreversible: `auth`, `payments`, `personal-data` and `migrations`.

Its trigger also fired on critical risk alone. That asked a person to sign off
on critical-risk code that touches no data, money, auth or privacy, which can
be reverted at merge and which CI and review already gate. jed72 decided on
2026-10-12 to drop the critical-risk arm and keep the four labels
(governance decision
`2026-10-12-guardrail-5-triggers-on-the-irreversible-labels`). The check
`human-approval-present` and its hard lock do not change.

A stored generation keeps the trigger it was committed with, and a project can
put critical risk back in `compass.yml`, because the lock allows a stricter
trigger.

Scenarios: g5-irreversible-labels/acceptance-criteria.md (GIL-1 to GIL-11).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
       "-c", "commit.gpgsign=false"]
LABELS = ["auth", "payments", "personal-data", "migrations"]
LABEL_TRIGGER = "      labels_any: [auth, payments, personal-data, migrations]\n"
OLD_TRIGGER = ("      any_of:\n"
               "      - labels_any: [auth, payments, personal-data, migrations]\n"
               "      - {risk: critical}\n")

TIGHTER = """\
gates:
  G5:
    set:
      when:
        any_of:
        - labels_any: [auth, payments, personal-data, migrations]
        - {risk: critical}
"""
LOOSER = """\
gates:
  G5:
    set:
      when:
        labels_any: [auth, payments, personal-data]
"""


def _run(cli, root, *args):
    return subprocess.run([sys.executable, str(cli), *args], cwd=root,
                          capture_output=True, text=True, timeout=120)


def _project(tmp_path, *, risk="critical", labels=(), layer="", cli=CLI,
             name="proj"):
    """A git project on the shipped default, with one issue assessed by
    `compass quick-fix start`. The start exits 1 when the approach is heavier
    than a quick fix; the manifest and the generation are written either way."""
    root = tmp_path / name
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\n" + layer)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    (root / ".compass").mkdir()
    args = ["quick-fix", "start", "thing", "--risk", f"{risk} - why",
            "--familiarity", "brownfield-mapped - the file and its test exist",
            "--size", "atomic - one line", "--intent", "the thing is right",
            "--scenario", "Given the thing, when read, then it is right",
            "--test", "tests/test_thing.py"]
    if labels:
        args += ["--labels", ",".join(labels)]
    started = _run(cli, root, *args)
    assert (root / ".compass" / "work" / "thing" / "manifest.yml").is_file(), (
        started.stdout + started.stderr)
    return root


def _check(root, cli=CLI):
    done = _run(cli, root, "check", "--verbose", "--issue", "thing")
    return done.stdout + done.stderr


def _g5_line(out):
    return next((line for line in out.splitlines() if " G5 " in line), "")


# --- Group A - the trigger ---------------------------------------------------

def test_gil_1_critical_risk_without_a_label_needs_no_sign_off(tmp_path):
    out = _check(_project(tmp_path, risk="critical", labels=["infra"]))
    assert "not applicable" in _g5_line(out), out
    assert "FAIL human-approval-present" not in out, out


def test_gil_2_critical_risk_with_migrations_needs_the_sign_off(tmp_path):
    out = _check(_project(tmp_path, risk="critical", labels=["migrations"]))
    assert "not applicable" not in _g5_line(out), out
    assert "FAIL human-approval-present" in out, out


@pytest.mark.parametrize("label", LABELS)
def test_gil_3_each_irreversible_label_needs_the_sign_off(tmp_path, label):
    out = _check(_project(tmp_path, risk="contained", labels=[label]))
    assert "FAIL human-approval-present" in out, (label, out)


# --- Group B - stored configuration -----------------------------------------

@pytest.fixture(scope="module")
def old_framework(tmp_path_factory):
    """A copy of the framework whose `G5` trigger still has the critical-risk
    arm, as every release before this change shipped it."""
    dest = tmp_path_factory.mktemp("old-framework")
    for name in ("cli", "governance", "agents", "templates", "approaches", "schemas"):
        shutil.copytree(ROOT / name, dest / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "VERSION", dest / "VERSION")
    gates = dest / "governance" / "presets" / "default" / "gates.yml"
    text = gates.read_text(encoding="utf-8")
    assert text.count(LABEL_TRIGGER) == 1, "G5's trigger is not the four labels"
    gates.write_text(text.replace(LABEL_TRIGGER, OLD_TRIGGER), encoding="utf-8")
    old = yaml.safe_load(gates.read_text(encoding="utf-8"))["gates"]["G5"]["when"]
    assert {"risk": "critical"} in old["any_of"], old
    return dest / "cli" / "compass"


def test_gil_5_a_generation_stored_before_the_change_keeps_critical_risk(
        tmp_path, old_framework):
    root = _project(tmp_path, risk="critical", labels=["infra"], cli=old_framework)
    generations = root / ".compass" / "work" / "thing" / "generations"
    stored = yaml.safe_load(
        (sorted(generations.iterdir())[-1] / "resolved.yml").read_text())
    assert "any_of" in yaml.safe_dump(stored), "the generation lost the old arm"
    out = _check(root)
    assert "not applicable" not in _g5_line(out), out
    assert "FAIL human-approval-present" in out, out


# --- Group C - tightening and the assess prompt ------------------------------

def test_gil_7_a_project_can_put_critical_risk_back(tmp_path):
    root = _project(tmp_path, risk="critical", labels=[], layer=TIGHTER)
    lint = _run(CLI, root, "policy", "lint")
    assert lint.returncode == 0 and "PASS" in lint.stdout, lint.stdout + lint.stderr
    out = _check(root)
    assert "FAIL human-approval-present" in out, out


def test_gil_8_a_project_cannot_drop_a_label(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "compass.yml").write_text("schema: 1\nextends: compass:default@6\n" + LOOSER)
    lint = _run(CLI, root, "policy", "lint")
    out = lint.stdout + lint.stderr
    assert lint.returncode != 0, out
    assert "K-LOCK-REFUSED" in out and "gates.G5" in out, out


def _prompt(out):
    return [line for line in out.splitlines() if "`G5` sign-off" in line]


def test_gil_9_evaluate_names_the_labels_at_critical_risk(tmp_path):
    unlabelled = _project(tmp_path, risk="critical", labels=["infra"], name="a")
    done = _run(CLI, unlabelled, "approach", "evaluate", "--issue", "thing")
    lines = _prompt(done.stdout)
    assert len(lines) == 1, done.stdout + done.stderr
    assert all(label in lines[0] for label in LABELS), lines
    assert done.stdout.index("Pay attention to:") < done.stdout.index(lines[0])

    labelled = _project(tmp_path, risk="critical", labels=["migrations"], name="b")
    done = _run(CLI, labelled, "approach", "evaluate", "--issue", "thing")
    assert not _prompt(done.stdout), done.stdout

    tightened = _project(tmp_path, risk="critical", labels=[], layer=TIGHTER, name="c")
    done = _run(CLI, tightened, "approach", "evaluate", "--issue", "thing")
    assert not _prompt(done.stdout), done.stdout

    contained = _project(tmp_path, risk="contained", labels=[], name="d")
    done = _run(CLI, contained, "approach", "evaluate", "--issue", "thing")
    assert not _prompt(done.stdout), done.stdout


# --- Group D - the documents ---------------------------------------------------

def _section(path, start, end):
    text = (ROOT / path).read_text(encoding="utf-8")
    i = text.index(start)
    j = text.find(end, i + len(start))
    return text[i:j if j != -1 else len(text)]


def test_gil_10_the_documents_name_the_same_four_cases():
    gate = yaml.safe_load((ROOT / "governance/presets/default/gates.yml").read_text())
    g5 = gate["gates"]["G5"]
    assert g5["when"] == {"labels_any": LABELS}, g5["when"]
    assert g5["locked"] == "hard" and g5["checks"] == ["human-approval-present"]

    contract = _section("docs/safety-contract.md",
                        "### 5. Irreversible work", "The evidence records")
    guardrails = _section("governance/guardrails.md",
                          "### A human signs off on the irreversible (`G5`)",
                          "The routing policy")
    statement = " ".join(g5["statement"].split())
    for text in (contract, guardrails, statement):
        for word in ("auth", "payments", "personal", "migrations"):
            assert word in text, (word, text)
        assert "critical" not in text, text

    view = yaml.safe_load((ROOT / "governance/guardrails.yml").read_text())
    g5_view = next(g for g in view["defaults"] if g["id"] == "G5")
    assert g5_view["applies_when"] == {"touches_any": LABELS}, g5_view

    methodology = (ROOT / "docs/methodology.md").read_text(encoding="utf-8")
    assert "critical-risk work" not in methodology
    for path in ("approaches/assess-procedure.md", "skills/adaptive-routing/SKILL.md"):
        flat = " ".join((ROOT / path).read_text(encoding="utf-8").split())
        assert "`auth`, `payments`, `personal-data` or `migrations`" in flat, path
        assert "critical risk alone does not" in flat.lower(), path


def test_gil_11_the_decision_record_and_upgrade_note_exist():
    record = (ROOT / "governance" / "decisions" /
              "2026-10-12-guardrail-5-triggers-on-the-irreversible-labels.md")
    text = " ".join(record.read_text(encoding="utf-8").split())
    for needle in ("jed72", "2026-10-12", "yes narrow guardrail 5",
                   "`auth`, `payments`, `personal-data` and `migrations`"):
        assert needle in text, needle

    upgrade = _section("docs/upgrade-7-0-0.md",
                       "## Guardrail 5 triggers on the irreversible labels", "\n## ")
    assert TIGHTER.strip().splitlines()[0] in upgrade
    assert "{risk: critical}" in upgrade and "set:" in upgrade
