"""What the framework asks an agent to read, and what it costs.

Scenario group F of `docs-compass-artifacts`, first half: the two skill merges
(TRC-F3), the framework's own documents coming off the adopter's reading path
(TRC-F4), and the resident cost pinned in a stated unit (TRC-F5).

`tests/test_instruction_volume.py` already pins the totals. This file pins the
three things that are about SHAPE rather than size: which skills exist, which
documents a delivery approach points an adopter at, and whether the ceiling
is expressed in a unit a reader can check against the intake.
"""

import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Words per token, the ratio this project has used since the instruction-volume
#: work. Recorded here rather than inlined so the two files cannot disagree
#: about the conversion while both claiming to measure the same thing.
TOKENS_PER_WORD = 1.35


def _words(path):
    return len(path.read_text(encoding="utf-8").split())


def _description_words(path):
    """The frontmatter `description:` - what the runtime keeps loaded."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return 0
    d = re.search(r"description:\s*(.+?)(?=\n[a-z_-]+:|\Z)", m.group(1), re.S)
    return len(d.group(1).split()) if d else 0


# ---------------------------------------------------------------------------
# `TRC-F3` - two skills merge into their neighbours
# ---------------------------------------------------------------------------

#: The merges the intake asks for: (absorbed skill, the skill that absorbs it).
#: The intake names `intent-elicitation` as the second target; no skill has ever
#: had that name and the requirements review settled it as `intent-interview`.
MERGES = [
    ("traceability", "evidence-gates"),
    ("role-translation", "intent-interview"),
]


@pytest.mark.parametrize("absorbed,host", MERGES)
def test_trc_f3_the_absorbed_skill_is_gone(absorbed, host):
    """The skill directory no longer exists as a skill of its own."""
    assert not (ROOT / "skills" / absorbed / "SKILL.md").is_file(), (
        f"skills/{absorbed}/SKILL.md still exists, so the skill count has not "
        f"dropped and its description is still resident on every turn")


@pytest.mark.parametrize("absorbed,host", MERGES)
def test_trc_f3_nothing_it_taught_was_deleted(absorbed, host):
    """Merging, not deleting. The content has to be somewhere in the host.

    Checked by asking whether the host skill's directory carries a file for the
    absorbed subject and whether the host's SKILL.md points at it. A merge that
    quietly drops the content would pass a test that only asserted the old
    directory is gone - which is why that assertion is not on its own.
    """
    host_dir = ROOT / "skills" / host
    part = host_dir / f"{absorbed}.md"
    assert part.is_file(), (
        f"skills/{absorbed}/ was removed but skills/{host}/{absorbed}.md does "
        f"not exist, so its content was deleted rather than merged")
    assert _words(part) > 300, (
        f"skills/{host}/{absorbed}.md is only {_words(part)} words - too short "
        f"to be what the {absorbed} skill taught")
    skill_md = (host_dir / "SKILL.md").read_text(encoding="utf-8")
    assert f"{absorbed}.md" in skill_md, (
        f"skills/{host}/SKILL.md does not mention {absorbed}.md, so the merged "
        f"content is on disk and unreachable - which is deletion with extra "
        f"steps")


def test_trc_f3_the_merge_removes_resident_cost():
    """The point of merging is that two descriptions become one.

    Without this, a merge that left both skills registered would satisfy every
    assertion above and save nothing, which is the whole reason the intake asks
    for it.
    """
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    names = {p.parent.name for p in skills}
    for absorbed, _ in MERGES:
        assert absorbed not in names, (
            f"{absorbed} is still a registered skill, so its description is "
            f"still paid for on every turn")
    # 15 before this issue, minus the two merges above, plus `quick-fix`:
    # the inlined light path is a skill of its own so a quick fix reads one
    # command and one skill rather than five commands and three skills. A
    # count rather than a floor, so a skill cannot creep back in unnoticed.
    assert len(skills) == 14, (
        f"expected 14 skills - 15, less the two merges, plus quick-fix - "
        f"found {len(skills)}: " + ", ".join(sorted(names)))


def test_trc_f3_nothing_names_a_skill_that_does_not_exist():
    """A merged-away skill must not still be named as one to load.

    `tests/test_documented_slash_commands_exist.py` exists because shipped
    prose named three slash commands that had been removed three major versions
    earlier, and nothing caught it. There was no equivalent guard for skills -
    and merging two skills is exactly the move that leaves ten files telling an
    agent to load a name that no longer resolves.

    A skill named but absent is not a typo an agent recovers from: the load
    fails, and whatever the instruction was about does not happen.
    """
    existing = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}

    # Matches any backticked name after "load". Every match now is a skill.
    # Do not narrow it: a hyphen filter skipped every single-word skill.
    pattern = re.compile(r"[Ll]oad(?:s|ing)?\s+(?:the\s+)?`([a-z0-9-]+)`")
    searched = (
        sorted((ROOT / "commands").glob("*.md"))
        + sorted((ROOT / "skills").glob("*/*.md"))
        + sorted((ROOT / "agents").glob("*.md"))
        + sorted((ROOT / "approaches").glob("*.md"))
        + [ROOT / "CLAUDE.md", ROOT / "compass-contract.md"]
    )

    offenders = []
    for path in searched:
        if not path.is_file():
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in pattern.finditer(line):
                name = match.group(1)
                if name not in existing:
                    offenders.append(f"{path.relative_to(ROOT)}:{n} -> `{name}`")

    assert not offenders, (
        "files tell an agent to load a skill that does not exist:\n  "
        + "\n  ".join(offenders)
        + "\n\nSkills that do exist: " + ", ".join(sorted(existing)))


# ---------------------------------------------------------------------------
# `TRC-F4` - the framework's own documents are off the adopter's reading path
# ---------------------------------------------------------------------------

#: Documents about DEVELOPING Compass rather than about USING it. An adopter
#: following a pointer to one of these lands in someone else's project.
#: Listed rather than derived: "is this document about the framework itself" is
#: a judgement, and a rule that tried to infer it would be guessing.
FRAMEWORK_INTERNAL = {
    "docs/system-spec.md",          # the framework's own dev history, current part
    "docs/system-spec-archive.md",  # and its archived part
    "docs/releasing.md",            # how to cut a Compass release
    "docs/install-smoke-test.md",   # run after changing Compass's installation
    "docs/desired-state.md",        # where Compass is going
    "docs/case-study-compass-rebuilt-itself.md",   # about Compass's development
    "docs/launch-article.md",       # marketing copy for Compass
}

#: Everything an agent reads while doing an issue, on any delivery approach.
#: These are the files that may point an adopter somewhere.
READING_PATH = (
    sorted((ROOT / "commands").glob("*.md"))
    + sorted((ROOT / "skills").glob("*/*.md"))
    + sorted((ROOT / "approaches").glob("*.md"))
    + sorted((ROOT / "agents").glob("*.md"))
    + [ROOT / "CLAUDE.md", ROOT / "compass-contract.md"]
)


def test_trc_f4_framework_documents_are_off_the_adopter_path():
    """No file an agent reads points at a document about building Compass."""
    offenders = []
    for path in READING_PATH:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for doc in sorted(FRAMEWORK_INTERNAL):
            if doc in text:
                rel = path.relative_to(ROOT)
                for n, line in enumerate(text.splitlines(), 1):
                    if doc in line:
                        offenders.append(f"{rel}:{n} -> {doc}")
    assert not offenders, (
        "files an agent reads point at documents about developing Compass "
        "rather than using it:\n  " + "\n  ".join(offenders))


def test_trc_f4_the_list_names_documents_that_exist():
    """A guard over a list of filenames is only as good as the list.

    A renamed or deleted document would leave an entry that can never match,
    and the check above would pass while guarding less.
    """
    missing = [d for d in sorted(FRAMEWORK_INTERNAL) if not (ROOT / d).is_file()]
    assert not missing, (
        "FRAMEWORK_INTERNAL names documents that do not exist, so those "
        f"entries guard nothing: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# `TRC-F5` - the resident cost is pinned in a stated unit
# ---------------------------------------------------------------------------

def test_trc_f5_the_resident_ceiling_is_stated_in_tokens_as_well_as_words():
    """The intake's target is in tokens; the guard counts words.

    The requirements review settled that the target names the DESCRIPTION cost -
    the frontmatter the runtime keeps loaded - and not the injected contract,
    which is a separate, deliberately-sized thing. Both are measured here, both
    are reported, and the test names its own conversion so a reader can check
    the intake's "about 1k tokens" against a number rather than reconstruct it.
    """
    volume = (ROOT / "tests" / "test_instruction_volume.py").read_text(
        encoding="utf-8")
    assert "token" in volume.lower(), (
        "tests/test_instruction_volume.py pins the resident ceiling in words "
        "only, so nobody can check it against the intake's target without "
        "doing the conversion by hand")


def test_trc_f5_description_cost_is_at_or_under_the_intake_target():
    """The number the intake actually names: about 1,000 tokens."""
    parts = {}
    for label, paths in (
        ("skills", sorted((ROOT / "skills").glob("*/SKILL.md"))),
        ("commands", sorted((ROOT / "commands").glob("*.md"))),
        ("agents", sorted((ROOT / "agents").glob("*.md"))),
    ):
        parts[label] = sum(_description_words(p) for p in paths)
    words = sum(parts.values())
    tokens = round(words * TOKENS_PER_WORD)
    assert tokens <= 1000, (
        f"resident description cost is {words} words, about {tokens} tokens, "
        f"over the intake's ~1,000-token target: "
        + ", ".join(f"{k} {v}w" for k, v in sorted(parts.items())))


def test_trc_f5_the_contract_is_measured_separately_and_reported():
    """The contract is resident too, and hiding it inside one number is how a
    target gets met by choosing what to count."""
    contract = ROOT / "compass-contract.md"
    contract_words = _words(contract)
    assert contract_words <= 450, (
        f"compass-contract.md is {contract_words} words. It is injected on "
        f"every session start, so it is resident cost even though the intake's "
        f"description target does not include it.")


# ---------------------------------------------------------------------------
# `TRC-F1` - a quick fix reads one command file and one skill file
# ---------------------------------------------------------------------------

#: The two files a quick fix reads. The five stage commands and the three
#: skills they load stay on disk and are read on the heavier delivery
#: approaches; the quick-fix path inlines what it needs instead of
#: delegating to them.
QUICK_FIX_COMMAND = ROOT / "commands" / "quick-fix.md"
QUICK_FIX_SKILL = ROOT / "skills" / "quick-fix" / "SKILL.md"

#: From the scenario. The path these two replace measures 11,203 words.
QUICK_FIX_WORD_CEILING = 3000


def test_trc_f1_a_quick_fix_reads_one_command_and_one_skill():
    """One command file, one skill file, and both together under the ceiling."""
    missing = [str(p.relative_to(ROOT)) for p in (QUICK_FIX_COMMAND, QUICK_FIX_SKILL)
               if not p.is_file()]
    assert not missing, (
        "the quick-fix reading path does not exist yet: " + ", ".join(missing))

    command_words = _words(QUICK_FIX_COMMAND)
    skill_words = _words(QUICK_FIX_SKILL)
    total = command_words + skill_words
    assert total <= QUICK_FIX_WORD_CEILING, (
        f"a quick fix reads {total} words - commands/quick-fix.md "
        f"({command_words}) and skills/quick-fix/SKILL.md ({skill_words}) - "
        f"over the {QUICK_FIX_WORD_CEILING}-word ceiling")


#: `compass` verbs named in the five stage commands that a quick fix does not
#: run, each with the reason. Every entry is checked below for still being in
#: the stage commands, so an entry cannot quietly stop guarding anything.
NOT_ON_THE_LIGHT_PATH = {
    "_friction-capture": "friction capture is a step of the full ship, which a quick fix collapses",
    "follow-up": "a quick fix borrows no process weight, so it owes nothing to pay back",
    "retro": "cross-issue aggregation, not a step of any one issue",
    "lesson": "offered beside friction capture in the full ship, which a quick fix collapses",
}

#: The five stage commands the quick-fix command inlines.
STAGE_COMMANDS = [
    ROOT / "commands" / name for name in
    ("assess.md", "define.md", "implement.md", "verify.md", "ship.md")
]

_VERB = re.compile(r"`compass ([a-z_][a-z-]*)")


def _stage_command_verbs():
    verbs = {}
    for path in STAGE_COMMANDS:
        for verb in _VERB.findall(path.read_text(encoding="utf-8")):
            verbs.setdefault(verb, path.name)
    return verbs


def test_trc_f1_the_quick_fix_command_names_every_cli_call_it_inlines():
    """The cost of inlining: two files now describe the quick-fix path.

    Inlining the light path means a change to how the framework records
    evidence has two places to land, and duplicated instructions drift - the
    framework had this defect before, with three copies of the contract
    closed at 4.0.0. Counting files and words cannot see drift.

    So this pins the two descriptions against each other: every `compass` verb
    the five stage commands run must be named in the inlined command, or be
    listed above as deliberately off the light path.
    """
    assert QUICK_FIX_COMMAND.is_file(), "commands/quick-fix.md does not exist"
    inlined = QUICK_FIX_COMMAND.read_text(encoding="utf-8")

    missing = []
    for verb, source in sorted(_stage_command_verbs().items()):
        if verb in NOT_ON_THE_LIGHT_PATH:
            continue
        if f"compass {verb}" not in inlined:
            missing.append(f"`compass {verb}` (from commands/{source})")
    assert not missing, (
        "commands/quick-fix.md inlines the light path but does not name every "
        "CLI call the stage commands make, so the two descriptions have "
        "drifted:\n  " + "\n  ".join(missing)
        + "\n\nIf a call genuinely does not belong on the light path, add it "
          "to NOT_ON_THE_LIGHT_PATH with the reason.")


def test_trc_f1_the_off_path_list_names_verbs_that_still_exist():
    """An exclusion list is only as good as its entries.

    A verb that has been renamed leaves an entry that excludes nothing, and
    the drift check above goes quietly greener over time.
    """
    verbs = _stage_command_verbs()
    stale = [v for v in sorted(NOT_ON_THE_LIGHT_PATH) if v not in verbs]
    assert not stale, (
        "NOT_ON_THE_LIGHT_PATH names verbs the stage commands no longer run, "
        f"so those entries exclude nothing: {', '.join(stale)}")


def test_trc_f1_the_quick_fix_command_sends_the_agent_nowhere_else():
    """One command file and one skill file is a count of what it TELLS you to
    read, not of what happens to exist.

    A 200-word command whose first line is "now read commands/assess.md" would
    satisfy every word count above and change nothing about what a session
    actually loads.
    """
    assert QUICK_FIX_COMMAND.is_file(), "commands/quick-fix.md does not exist"
    text = QUICK_FIX_COMMAND.read_text(encoding="utf-8")
    others = sorted(
        p.name for p in ROOT.glob("commands/*.md") if p.name != "quick-fix.md")

    offenders = []
    for n, line in enumerate(text.splitlines(), 1):
        for name in others:
            if f"commands/{name}" in line:
                offenders.append(f"{n}: commands/{name}")
        for match in re.finditer(r"[Ll]oad(?:s|ing)?\s+(?:the\s+)?`([a-z0-9-]+)`", line):
            if match.group(1) != "quick-fix":
                offenders.append(f"{n}: load `{match.group(1)}`")
        # Naming a slash command is a pointer too, and a file listing five of
        # them sends the agent everywhere while matching neither pattern
        # above. Exactly one is allowed: the way back out when the CLI says
        # the work is heavier than a quick fix.
        for match in re.finditer(r"/compass:([a-z-]+)", line):
            if match.group(1) not in ("quick-fix", "assess"):
                offenders.append(f"{n}: /compass:{match.group(1)}")
    assert not offenders, (
        "commands/quick-fix.md points the agent at other commands or skills, "
        "so the quick-fix path is not one command and one skill:\n  "
        + "\n  ".join(offenders))


# ---------------------------------------------------------------------------
# `TRC-F2` - a quick fix writes only the delivery-approach record
# ---------------------------------------------------------------------------

#: The routing policy's internal name for the quick-fix shape.
QUICK_FIX_SHAPE = "express"


def _routing_policy():
    import yaml
    return yaml.safe_load(
        (ROOT / "governance" / "routing-policy.yml").read_text(encoding="utf-8"))


def test_trc_f2_the_quick_fix_shape_requires_no_document():
    """`delivery-approach.md` is written by assess on every approach, so a
    shape that needs no artifact of its own needs only that one.

    The quick-fix shape needs no light acceptance-criteria.md or
    verification-report.md, because the manifest and the test-run evidence
    carry the same records.
    """
    shapes = _routing_policy()["route_shapes"]
    assert QUICK_FIX_SHAPE in shapes, (
        f"the routing policy has no `{QUICK_FIX_SHAPE}` shape - the quick-fix "
        f"approach has been renamed and this check is measuring nothing. "
        f"Shapes: {', '.join(sorted(shapes))}")
    artifacts = shapes[QUICK_FIX_SHAPE].get("artifacts") or {}
    assert set(artifacts) == {"delivery-approach"}, (
        "the quick-fix shape does not require exactly delivery-approach.md: "
        + (", ".join(f"{k} ({v})" for k, v in sorted(artifacts.items()))
           or "it requires nothing at all, so nothing checks that a quick fix "
              "wrote anything down"))


def _quick_fix_issue(project, with_green):
    """A quick-fix issue with delivery-approach.md and nothing else written."""
    import yaml
    task_dir = project / ".compass" / "work" / "a-quick-fix"
    (task_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (task_dir / "delivery-approach.md").write_text(
        "# Delivery approach - a-quick-fix\n\nQuick fix. One scenario, QF-1.\n",
        encoding="utf-8")
    manifest = {
        "schema_version": "2.0",
        "issue": "a-quick-fix",
        "created": "2026-09-10",
        "status": "active",
        "assessment": {"risk": "trivial", "familiarity": "brownfield-mapped",
                       "size": "atomic", "goal": "delivery", "role": "engineer"},
        "delivery_approach": QUICK_FIX_SHAPE,
        "stages": {"assess": "full", "define": "light", "refine": "collapsed",
                   "plan": "collapsed", "breakdown": "skipped",
                   "implement": "full", "verify": "light", "ship": "light"},
        "evidence": [],
        "gates": [{"id": g, "status": "pending", "evidence": []} for g in
                  ("verify.correctness", "verify.governance", "verify.traceability")],
        "scenarios": [{"id": "QF-1", "title": "the defect is fixed",
                       "intent": "INT-1", "tests": ["tests/test_x.py::test_qf_1"]}],
        "changed_files": [], "claims": [], "follow_ups": [], "artifacts": [],
    }
    if with_green:
        (task_dir / "evidence" / "green-QF-1.json").write_text(json.dumps({
            "command": "pytest tests/test_x.py -q", "scenario": "QF-1",
            "exit_code": 0, "passed": True, "attempts": 1,
            "timestamp": "2026-09-10T09:00:00+00:00", "log_excerpt": "1 passed",
        }), encoding="utf-8")
        manifest["evidence"] = [{"id": "EV-T-QF-1", "type": "test-run",
                                 "path": "evidence/green-QF-1.json",
                                 "scenario": "QF-1"}]
    (task_dir / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    (project / ".compass" / "current-task").write_text("a-quick-fix\n",
                                                       encoding="utf-8")
    return task_dir


def _check(project):
    import subprocess
    import sys
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "check",
         "--issue", "a-quick-fix", "--verbose"],
        capture_output=True, text=True, timeout=120, cwd=str(project))


def test_trc_f2_compass_check_passes_with_no_other_document_written(tmp_path):
    """Run it rather than reason about it, and prove the pass is not free.

    The same issue is checked twice: once without the recorded green, where
    the check must FAIL, and once with it, where it must pass. Without the
    first half this is a green line that asserts nothing.
    """
    _quick_fix_issue(tmp_path, with_green=False)
    without = _check(tmp_path)
    assert without.returncode != 0, (
        "compass check passed on a quick-fix issue with no recorded test run, "
        "so this check cannot tell a complete issue from an empty one:\n"
        + without.stdout[-1500:])
    assert "suite-passed" in without.stdout, (
        "the failure was not the missing green, so this fixture is not "
        "exercising what it claims:\n" + without.stdout[-1500:])

    _quick_fix_issue(tmp_path, with_green=True)
    with_green = _check(tmp_path)
    assert with_green.returncode == 0, (
        "compass check fails on a quick-fix issue that has written only "
        "delivery-approach.md:\n" + with_green.stdout[-2000:])

    written = sorted(p.name for p in
                     (tmp_path / ".compass" / "work" / "a-quick-fix").glob("*.md"))
    assert written == ["delivery-approach.md"], (
        f"the fixture wrote more than the delivery-approach record: {written}")


def test_trc_f1_the_quick_fix_entry_point_is_reachable():
    """A command file nobody is pointed at is a command nobody runs.

    `commands/quick-fix.md` becomes `/compass:quick-fix` because the runtime
    globs `commands/*.md`, but nothing tells an agent that the light path has
    a single-command entry point. The two places an agent looks are the
    stage-to-command map it loads when an issue begins, and the approach
    description assess lands on.
    """
    signposts = {
        "skills/compass-runtime/SKILL.md":
            "the stage-to-command map an agent loads when an issue begins",
        "approaches/quick-fix.md":
            "the approach description assess lands on",
    }
    missing = [f"{path} ({why})" for path, why in sorted(signposts.items())
               if "/compass:quick-fix" not in (ROOT / path).read_text(encoding="utf-8")]
    assert not missing, (
        "nothing points an agent at /compass:quick-fix, so the inlined light "
        "path is a file that exists and never gets read:\n  "
        + "\n  ".join(missing))
