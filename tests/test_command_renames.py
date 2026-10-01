"""The command files speak the v2 names.

The eight pipeline commands are assess, define, refine, plan, breakdown,
implement, verify, ship; the designer entry point is design; the retired
names were removed at 4.0.0; the vocabulary file names them; and no live
instruction surface may point at a retired name.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
COMMANDS = REPO_ROOT / "commands"

V2_COMMANDS = {
    "assess", "define", "refine", "plan", "breakdown", "implement",
    "verify", "ship", "design", "intent", "position", "consult",
    "status", "flow", "resume", "init",
    # docs-compass-artifacts: the quick-fix approach's single-command entry
    # point. It inlines assess, define, implement, verify and ship for a small,
    # safe change rather than delegating to the five stage commands, so the
    # light path costs one command file and one skill instead of thirteen files.
    "quick-fix",
    # one-entry-point: the single command for the ordinary path. It assesses
    # with quick-fix start and continues into the computed approach.
    "go",
}

# Retired name -> its replacement. The mapping stays so the test can assert
# no retired name is used. NOTE `plan` is absent, and `frame` points at the
# FINAL name. `plan` was a retired v1 command and is live again - ADR-014
# removes retired names, it does not reserve them - and `frame`'s
# replacement is `assess`, because `triage` is itself retired now. A stub
# naming a retired replacement sends a reader to a word they must rename
# again.
STUBS = {
    "frame": "assess",
    "triage": "assess",
    "specify": "define",
    "clarify": "refine",
    "wireframe": "design",
    "distribute": "breakdown",
    "build": "implement",
    "land": "ship",
    # ADR-023: the word Anthropic's platform docs use for consulting an
    # advisor mid-turn. Went at 4.0.0, like the two above it.
    "roundtable": "consult",
}

INLINE_CODE = re.compile(r"`[^`]*`")
DEAD_NAME = re.compile(
    r"/compass:(?:frame|triage|specify|clarify|wireframe|distribute|build|land"
    r"|roundtable)\b")


def test_the_command_set_carries_the_v2_names():
    """`TRC-1`: every shipped command exists, each with an H1 naming itself."""
    names = {p.stem for p in COMMANDS.glob("*.md")}
    missing = V2_COMMANDS - names
    assert not missing, f"missing v2 command files: {sorted(missing)}"
    # STUBS is not subtracted: a file bearing one of these names is a stub
    # that has come back, and this check must report it.
    stray = names - V2_COMMANDS
    assert not stray, f"unexpected command files: {sorted(stray)}"
    for name in sorted(V2_COMMANDS):
        text = (COMMANDS / f"{name}.md").read_text(encoding="utf-8")
        assert re.search(rf"^# .?/compass:{name}\b", text, re.M), (
            f"{name}.md lacks an H1 naming /compass:{name}")


# tests/test_no_deprecation_stubs.py asserts that no stub exists (RCD-F1).


def test_the_vocabulary_carries_the_command_names_and_a_version_bump():
    """`TRC-3`: terminology.yml is amended in the same diff that lands the
    names - version bumped past 2.0.0-pre5, the banned command entries name
    their exact replacement commands, and the recorded naming rule (anti-jargon,
    not grammatical purity) is present."""
    text = (REPO_ROOT / "governance" / "terminology.yml").read_text(
        encoding="utf-8")
    doc = yaml.safe_load(text)
    m = re.fullmatch(r"2\.0\.0-pre(\d+)", str(doc["version"]))
    assert m and int(m.group(1)) > 5, (
        f"terminology.yml version is {doc['version']} - the command renames "
        "must land with a version bump past 2.0.0-pre5")
    bans = {b["term"]: b for b in doc["banned"]}
    frame = bans["Frame / the Needle"]
    joined = frame.get("replacement", "") + frame.get("context", "")
    # The ban points at `assess`, the FINAL name. It mentions triage only to
    # explain why it does not send a reader there, so an assertion that
    # "triage" is present would pass on the sentence that explains why the
    # ban does not point there. Assert what the entry is actually for.
    assert "assess" in joined, (
        "the Frame ban entry does not name assess as the replacement. It has "
        "to point at the current name: a ban naming a banned replacement "
        "sends a reader to a word they must rename again")
    stages = bans["Specify / Clarify / Distribute / Land"]
    joined = stages.get("replacement", "") + stages.get("context", "")
    for cmd in ("define", "refine", "breakdown", "ship"):
        assert cmd in joined, (
            f"the stage-name ban entry does not name the '{cmd}' command")
    assert "anti-jargon" in text, (
        "the recorded reading of the naming rule (anti-jargon, not "
        "grammatical purity) is missing from terminology.yml")


def test_commands_and_manifests_are_enforced_surfaces():
    """`TRC-4`: commands/ and .claude-plugin/ leave pending_surfaces in the
    vocabulary file and the committed baseline in the same diff. Their
    cleanliness is then enforced by the existing terminology scan."""
    from test_terminology import PENDING_BASELINE
    scan = yaml.safe_load(
        (REPO_ROOT / "governance" / "terminology.yml").read_text(
            encoding="utf-8"))["scan"]
    for surface in ("commands/", ".claude-plugin/"):
        assert surface not in scan["pending_surfaces"], (
            f"{surface} is still pending in terminology.yml - slice 5a's "
            "definition of done includes de-pending it")
        assert surface not in PENDING_BASELINE, (
            f"{surface} is still in the committed baseline - the ratchet "
            "shrinks in the same diff that cleans the surface")


def test_no_live_surface_points_at_a_dead_command_name():
    """`TRC-5`: the surfaces that drive live sessions carry no retired command
    name."""
    surfaces: list[Path] = [
        REPO_ROOT / "CLAUDE.md",
        REPO_ROOT / "AGENTS.md",
        REPO_ROOT / "skills" / "compass-runtime" / "SKILL.md",
        REPO_ROOT / "cli" / "compass",
    ]
    surfaces += sorted((REPO_ROOT / "agents").glob("*.md"))
    surfaces += sorted((REPO_ROOT / "templates").rglob("*.md"))
    surfaces += sorted((REPO_ROOT / "cli").rglob("*.py"))
    surfaces += sorted((REPO_ROOT / "hooks").glob("*.sh"))
    surfaces += sorted((REPO_ROOT / ".claude-plugin").glob("*.json"))
    hits = []
    for path in surfaces:
        if not path.is_file():
            continue
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if DEAD_NAME.search(line):
                rel = path.relative_to(REPO_ROOT)
                hits.append(f"{rel}:{lineno}: {line.strip()[:80]}")
    assert not hits, (
        "retired command names on live surfaces:\n  " + "\n  ".join(hits[:20]))


def test_the_ruling_conditions_hold():
    """`TRC-6`: define's one-line description leads with 'Acceptance criteria';
    design's says it produces the UI contract; and the UI-contract
    template's producer line points at /compass:design."""
    def description(name: str) -> str:
        text = (COMMANDS / f"{name}.md").read_text(encoding="utf-8")
        m = re.search(r"^description:\s*(.+)$", text, re.M)
        assert m, f"{name}.md has no description line"
        return m.group(1)

    assert description("define").startswith("Acceptance criteria"), (
        "define's description must lead with 'Acceptance criteria' - the "
        "bare verb is the vaguest in the set")
    assert "UI contract" in description("design"), (
        "wireframe's description must state it produces the UI contract")
    assert "/compass:design" in (
        REPO_ROOT / "templates" / "ui-contract.md").read_text(
        encoding="utf-8"), (
        "templates/ui-contract.md's producer line must point at "
        "/compass:design")
