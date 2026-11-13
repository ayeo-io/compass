"""The worked example in docs/five-minutes.md must match what the CLI does.

The worked example's assessment is fed to the real CLI, and the documented
approach and gates are compared with what it returns, so the transcript in
this onboarding document - the first thing an adopter runs - cannot
silently drift from the code again. The trail headings in the README and
in the walkthrough are compared with the file `compass trail` writes.
"""
import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"
DOC = ROOT / "docs" / "five-minutes.md"


def _documented_readings():
    """The `assessment:` block from the worked example's manifest.yml snippet."""
    text = DOC.read_text(encoding="utf-8")
    m = re.search(r"```yaml\n(.*?schema_version.*?assessment:.*?)```", text, re.S)
    assert m, "docs/five-minutes.md must show a manifest.yml snippet with assessment:"
    parsed = yaml.safe_load(m.group(1))
    return parsed["assessment"]


def _evaluate(readings, *flags):
    args = [sys.executable, str(COMPASS_CLI), "approach", "evaluate", *flags]
    for key, value in readings.items():
        args += ["--assessment", f"{key}={value}"]
    return subprocess.run(args, capture_output=True, text=True, cwd=ROOT, timeout=30)


def test_worked_example_readings_are_accepted_by_the_cli():
    """Every assessment value in the doc is in the routing policy's vocabulary."""
    result = _evaluate(_documented_readings())
    assert result.returncode == 0, (
        "docs/five-minutes.md documents readings the CLI rejects:\n"
        f"{result.stdout}\n{result.stderr}"
    )


def test_worked_example_route_and_gates_match_the_cli():
    """The documented FINAL APPROACH and gate set are the ones the CLI
    computes.

    Against --verbose: the doc shows both views, and this checks the
    detailed one because that is where the labels below live. The labels
    appear only under --verbose.
    """
    out = _evaluate(_documented_readings(), "--verbose").stdout
    doc = DOC.read_text(encoding="utf-8")

    for label in ("FINAL APPROACH", "gate set"):
        m = re.search(rf"^\s*{label}\s*:\s*(.+)$", out, re.M)
        assert m, f"the evaluator printed no '{label}' line:\n{out}"
        actual = m.group(1).strip()
        assert re.search(rf"{re.escape(label)}\s*:\s*{re.escape(actual)}", doc), (
            f"docs/five-minutes.md's transcript does not show the real {label} "
            f"({actual!r}). Re-run `compass approach evaluate` and paste the output."
        )


def _real_trail_headings(tmp_path):
    """The section headings `compass trail` writes, from a scratch issue."""
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, env=env)

    def compass(*args):
        result = subprocess.run([sys.executable, str(COMPASS_CLI), *args], cwd=tmp_path,
                                capture_output=True, text=True, timeout=60, env=env)
        assert result.returncode == 0, result.stdout + result.stderr
    compass("init", "--quiet")
    compass("quick-fix", "start", "fix-it", "--risk", "trivial - one string",
            "--familiarity", "greenfield - new", "--size", "atomic - one line",
            "--intent", "The message is spelled right",
            "--scenario", "Given a bad token When it is checked Then the message is right",
            "--test", "tests/test_x.py::test_x", "--quiet")
    compass("trail", "--issue", "fix-it")
    trail = (tmp_path / ".compass" / "work" / "fix-it" / "trail.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (\d+\. .+)$", trail, re.M)
    assert len(headings) == 6, trail
    return headings


def test_trail_headings_in_the_readme_and_the_walkthrough_are_real(tmp_path):
    """The README lists the sections of trail.md, and the walkthrough shows
    them as `grep '^## '` prints them. Both are compared with the file
    `compass trail` writes, so a renamed or reordered section cannot leave
    the first page a reader sees describing a trail that no longer exists.
    """
    headings = _real_trail_headings(tmp_path)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## What one change leaves", 1)
    assert len(section) == 2, "README.md has no '## What one change leaves' section"
    listed = re.findall(r"^(\d+\. .+)$", section[1].split("\n## ", 1)[0], re.M)
    assert listed == headings, (
        "README.md lists the trail sections as\n  " + "\n  ".join(listed)
        + "\nbut `compass trail` writes\n  " + "\n  ".join(headings))

    shown = "\n".join(f"## {h}" for h in headings)
    assert f"```text\n{shown}\n```" in DOC.read_text(encoding="utf-8"), (
        "docs/five-minutes.md does not show the real trail headings:\n" + shown)
