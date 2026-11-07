"""An issue started with Compass 5.6.0 finishes under this branch's CLI.

`tests/test_upgrade_from_5_0_0.py` reads a 5.0.0 project with the new CLI.
This one goes further: the 5.6.0 release (from its tag, no network) assesses
an issue and takes it through define, with a red recorded. This branch's CLI
then finishes it: green, the quick-fix gates and the ship commit. The word
rewrite (schema 3.0, the new stage-mode words, the dropped `active` status)
happens on the first save, and the test checks what that leaves behind:

- the manifest is schema 3.0 in the new words, with status `done` and close
  reason `completed`
- `manifest.yml.v5.bak` holds the 5.6.0 text byte for byte and is written once
- every rewrite notice on standard error names the issue
- the living spec heads the issue `(completed <date>)`
- the 5.6.0 CLI refuses the saved manifest with its version message

The second case is a 5.6.0 project whose `governance/` files and
`.compass/config.yml` are copies from the release, so they hold the old
words. This branch reads and evaluates them to the same delivery approach
under its new name. On the four-stage path (ADR-092) the CLI shows an
issue's evidence owed, not its approach, so the approach is read from the
8.x evaluator (`routing.evaluate_route`) over the project's configuration,
and the CLI's path view is checked beside it.

Scenario id: UP-2.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
TAG = "v5.6.0"
SLUG = "fix-greeting"

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
}


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    """The 5.6.0 tree, from the tag. A clone without the tag cannot run this
    test, so it is skipped with the reason."""
    has_tag = subprocess.run(["git", "rev-parse", "--verify", "-q", TAG + "^{commit}"],
                             cwd=ROOT, capture_output=True).returncode == 0
    if not has_tag:
        pytest.skip(f"the {TAG} tag is not in this clone; fetch tags to run the "
                    f"5.6.0 upgrade test")
    out = tmp_path_factory.mktemp("release-5-6-0")
    archive = subprocess.run(["git", "archive", TAG], cwd=ROOT, capture_output=True,
                             check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(out)], input=archive, check=True)
    return out


def _cli(cli, cwd, *args):
    return subprocess.run([sys.executable, str(cli), *args], cwd=cwd, env=ENV,
                          capture_output=True, text=True)


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, env=ENV, check=True, capture_output=True)


def _seed(root):
    (root / "data").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "data" / "greeting.txt").write_text("Hi, %s!\n")
    (root / "tests" / "test_greeting.py").write_text(
        "import pathlib\n\n\ndef test_greeting_says_hello():\n"
        "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'greeting.txt'\n"
        "    assert p.read_text().strip() == 'Hello, %s!'\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")


def _quick_fix_start(old_cli, root, slug, *, risk, familiarity, size, labels=None,
                     heavier=False):
    """`quick-fix start` records the assessment either way. It exits 1 when the
    work computes to a heavier approach and writes no scenario."""
    args = ["quick-fix", "start", slug, "--risk", risk, "--familiarity", familiarity,
            "--size", size, "--intent", "The greeting says hello", "--scenario",
            "Given the greeting, when read, then it says hello", "--scenario-id",
            "TRC-001", "--test", "tests/test_greeting.py"]
    if labels:
        args += ["--labels", labels]
    r = _cli(old_cli, root, *args)
    assert r.returncode == (1 if heavier else 0), r.stdout + r.stderr
    assert _manifest_path(root, slug).exists(), r.stdout + r.stderr
    return r


def _pytest_cmd():
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "tests/test_greeting.py"]


def _manifest_path(root, slug=SLUG):
    return root / ".compass" / "work" / slug / "manifest.yml"


def test_up_2_an_issue_started_in_5_6_0_finishes_under_this_branch(release, tmp_path):
    old_cli = release / "cli" / "compass"
    root = tmp_path / "proj"
    root.mkdir()
    _seed(root)
    assert _cli(old_cli, root, "init").returncode == 0

    # 1. Assess and take the issue through define with the 5.6.0 CLI.
    _quick_fix_start(old_cli, root, SLUG, risk="trivial - a text change",
                     familiarity="brownfield-mapped - known file",
                     size="atomic - one line")
    red = _cli(old_cli, root, "tdd-red", "--issue", SLUG, "--scenario", "TRC-001",
               "--", *_pytest_cmd())
    assert red.returncode == 0, red.stdout + red.stderr

    manifest = _manifest_path(root)
    v560_bytes = manifest.read_bytes()
    v560 = yaml.safe_load(v560_bytes)
    assert v560["schema_version"] == "2.0"
    assert v560["status"] == "active", "5.6.0 stores a status of its own"
    assert v560["stages"]["assess"] == "full"
    assert not (manifest.parent / "manifest.yml.v5.bak").exists()

    # 2. Finish it with this branch's CLI.
    (root / "data" / "greeting.txt").write_text("Hello, %s!\n")
    green = _cli(CLI, root, "tdd-green", "--issue", SLUG, "--scenario", "TRC-001",
                 "--", *_pytest_cmd())
    assert green.returncode == 0, green.stdout + green.stderr
    backup = manifest.parent / "manifest.yml.v5.bak"
    backup_written = backup.stat().st_mtime_ns
    # While the issue is open the manifest stores no status; the records give it.
    assert "status" not in yaml.safe_load(manifest.read_text())

    _git(root, "add", "data")
    finish = _cli(CLI, root, "quick-fix", "finish", "--issue", SLUG, "-m",
                  "Say hello", "--", *_pytest_cmd())
    assert finish.returncode == 0, finish.stdout + finish.stderr

    # 3. What the upgrade left behind.
    now = yaml.safe_load(manifest.read_text())
    assert now["schema_version"] == "3.0"
    assert now["status"] == "done" and now["close_reason"] == "completed"
    assert now["delivery_approach"] == "quick-fix"
    assert now["stages"]["assess"] == "thorough"
    assert now["stages"]["define"] == "lightweight"
    assert now["artifacts"][0]["depth"] == "lightweight"
    words = {v for v in now["stages"].values()}
    assert not words & {"full", "light"}, f"old stage words survive: {words}"

    # The backup is the 5.6.0 text, byte for byte, and was written once.
    assert backup.read_bytes() == v560_bytes
    assert backup.stat().st_mtime_ns == backup_written, "the backup was written again"
    assert sorted(p.name for p in manifest.parent.glob("manifest.yml*")) == [
        "manifest.yml", "manifest.yml.v5.bak"]

    # Each rewrite notice names the issue; the first save printed them and the
    # later saves, which had nothing left to rewrite, printed none.
    notices = [ln for ln in green.stderr.splitlines() if "v5.bak" in ln]
    assert len(notices) >= 4, green.stderr
    for line in notices:
        assert line.startswith(f"compass: {SLUG}: "), line
    shown = " ".join(notices)
    assert "'full' is now 'thorough'" in shown
    assert "'light' is now 'lightweight'" in shown
    assert "'active' is no longer stored" in shown
    assert "v5.bak" not in finish.stderr, finish.stderr

    # The living spec, when the project derives one, heads the issue "completed".
    spec = root / "docs" / "system-spec.md"
    if spec.exists():
        headings = re.findall(r"^### (\S+) \((\w+) ([0-9-]+)\)$", spec.read_text(), re.M)
        assert (SLUG, "completed") in [(s, w) for s, w, _ in headings], headings

    # The 5.6.0 CLI refuses the saved manifest and says why.
    refused = _cli(old_cli, root, "check", "--issue", SLUG)
    assert refused.returncode != 0
    assert "schema_version is '3.0'" in refused.stdout + refused.stderr
    assert "this CLI handles '2.0'" in refused.stdout + refused.stderr


def _evaluate_lines(text):
    """The gate count and the key choices of `approach evaluate`'s output `text`,
    which do not change with the approach's display name."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    head = re.search(r"(\d+) gate\(s\), (.*)$", lines[0])
    assert head, text
    choices = [ln for ln in lines[1:] if ln.lstrip().startswith("- ")]
    return head.groups(), choices


def _legacy_view(root, slug):
    """The default view `approach evaluate --issue` printed before the path, rebuilt
    from the 8.x evaluator over the project's configuration and rendered by the
    same `Emitter`."""
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import effective, routing
    from compass_pkg.core import display_shape, load_yaml, normalize_spine
    from compass_pkg.render import fired_rule_line
    from compass_pkg.terminal import Emitter
    resolution = effective.resolve_live(str(root))
    policy = effective.EffectiveView("live", None, None, resolution.resolved,
                                     resolution.versions).evaluator_policy()
    task = normalize_spine(load_yaml(str(_manifest_path(root, slug))))
    result = routing.evaluate_route(task["assessment"], policy)
    ceiling = result["subtask_ceiling"]
    emitter = Emitter(mode="summary")
    emitter.hand_off(
        outcome="%s - %d gate(s), %s" % (
            display_shape(result["delivery_approach"]), len(result["gates"]),
            "unbounded parallel subtasks" if ceiling is None
            else "up to %d parallel subtask(s)" % ceiling),
        items=[fired_rule_line(f) for f in result["policy_rules_fired"]]
        or ["no policy rule fired - the shape is the assessment's default"],
        concerns=["%s is blocked until %s" % (b["phase"], b["until"])
                  for b in result["blocked_phases"]]
        + (["documents required: " + ", ".join(result["required_artifacts"])]
           if result["required_artifacts"] else []),
        next_step="nothing recorded - re-run with --write to fold this into the manifest")
    return emitter.rendered()


def test_up_2_a_5_6_0_project_with_old_governance_words_evaluates_the_same(
        release, tmp_path):
    old_cli = release / "cli" / "compass"
    root = tmp_path / "proj"
    root.mkdir()
    _seed(root)
    assert _cli(old_cli, root, "init").returncode == 0
    # The release's own governance files, copied in as a 5.6.0 project holds
    # them: they use the old route names.
    shutil.copytree(release / "governance", root / "governance")
    config = (root / ".compass" / "config.yml").read_bytes()
    governance = {p: p.read_bytes() for p in (root / "governance").rglob("*.yml")}
    assert governance, "the release shipped no governance files to copy"
    assert b"expedition" in (root / "governance" / "routing-policy.yml").read_bytes()

    _quick_fix_start(old_cli, root, "fix-greeting", risk="trivial - a text change",
                     familiarity="brownfield-mapped - known file",
                     size="atomic - one line")
    _quick_fix_start(old_cli, root, "add-farewell", risk="cross-cutting - touches auth",
                     familiarity="greenfield - new area", size="large - many files",
                     labels="auth", heavier=True)

    # Same name under the new word: 5.6.0 says what 5.6.0 called it.
    renamed = {"fix-greeting": ("quick fix", "quick fix"),
               "add-farewell": ("initiative", "full")}
    for slug, (old_name, new_name) in renamed.items():
        before = _cli(old_cli, root, "approach", "evaluate", "--issue", slug)
        after = _cli(CLI, root, "approach", "evaluate", "--issue", slug)
        assert before.returncode == 0, before.stdout + before.stderr
        assert after.returncode == 0, after.stdout + after.stderr
        assert before.stdout.startswith(old_name), before.stdout
        legacy = _legacy_view(root, slug)
        assert legacy.startswith(new_name), legacy
        # ADR-092 decision: no approaches. The CLI's view of the issue is the
        # path's: the one delivery approach and the evidence owed.
        assert re.match(r"delivery - \d+ gate\(s\), \d+ kinds of evidence owed\n",
                        after.stdout), after.stdout
        # 9.0.0 removed the drift report (ADR-098), so no concern line says the
        # 5.6.0 governance copy lacks what the framework ships.
        _, path_choices = _evaluate_lines(after.stdout)
        assert not [c for c in path_choices if "policy is missing" in c], (
            slug, path_choices)
        gates, choices = _evaluate_lines(legacy)
        # 9.0.0 drops the removed gate `verify.analyze` (ADR-091), which the copied
        # 5.6.0 rules `RP-REQUIRE-001` and `RP-REQUIRE-002` add; a rule that only adds it
        # no longer fires. That is one gate and one choice line for the `auth` issue.
        (count, rest), old_choices = _evaluate_lines(before.stdout)
        count = str(int(count) - (1 if slug == "add-farewell" else 0))
        old_choices = [c for c in old_choices
                       if "RP-REQUIRE-001" not in c and "RP-REQUIRE-002" not in c]
        # With those two lines gone, the output lists one more fired rule, `RP-REQUIRE-005`,
        # which the copied 5.6.0 rules fire for this issue too.
        new_choices = [c for c in choices
                       if not (slug == "add-farewell" and "RP-REQUIRE-005" in c)]
        assert (gates, new_choices) == ((count, rest), old_choices), (
            slug, sorted(set(new_choices) - set(old_choices)), sorted(set(old_choices) - set(new_choices)))
        lint = _cli(CLI, root, "issue", "lint", "--issue", slug)
        assert lint.returncode == 0, lint.stdout + lint.stderr

    # The old route names are read, with a notice on standard error that says
    # what to rename, and the files themselves are not rewritten.
    after = _cli(CLI, root, "approach", "evaluate", "--issue", "add-farewell")
    # The notice says "approach", because "route" is a verb only (ADR-044).
    assert "old approach names" in after.stderr and "expedition -> full" in after.stderr
    policy = _cli(CLI, root, "policy", "lint")
    assert policy.returncode == 0, policy.stdout + policy.stderr
    assert (root / ".compass" / "config.yml").read_bytes() == config
    assert {p: p.read_bytes() for p in (root / "governance").rglob("*.yml")} == governance
