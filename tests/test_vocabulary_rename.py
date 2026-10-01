"""The vocabulary rename: assess, plan, intent, technical-design.

Five words in this framework named more than one thing, or named a thing whose
own output disagreed with them:

  the stage that produces an `assessment:` block was called `triage`
  the stage whose key, skill and agent all say `plan` was commanded as `design`
  `design` named a command, an artifact, an artifact kind, a CLI verb and a
      role, and was the only overloaded word with no glossary entry
  `/compass:intent` wrote a file called `prd.md` <!-- vocabulary-scan: allow - names the retired filename this migration test tracks -->
  `frame` was banned as a phase name and survived as a live machine key,
      because governance/*.yml is not a scanned surface

THE ORDER IS THE DESIGN. Every new spelling is accepted before any caller
switches to it - see design.md D2. These tests are written so the accept phase
can be green on its own.

Scenario ids trace to
the-vocabulary-rename/acceptance-criteria.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

MAP = REPO_ROOT / "cli" / "migrate-map.yml"

# The six that move. `plan` and `verify` are deliberately absent: `plan` stays
# because the command moves TO it, and `verify` already agrees.
STAGE_RENAMES = {
    "frame": "assess",
    "specify": "define",
    "clarify": "refine",
    "distribute": "breakdown",
    "build": "implement",
    "land": "ship",
}
STAGE_UNCHANGED = {"plan", "verify"}


def _map():
    import compass_pkg  # resolves the bundled yaml
    import yaml
    return yaml.safe_load(MAP.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Group C - the map, and any copy of it
# ---------------------------------------------------------------------------

def test_trc_c1():
    """The map carries the stage keys, and any copy is proven to match (`TRC-C1`).

    The second half is the point. The guard that existed before this asserted
    `migrate.artifact_name_map() == artifacts` - and that function reads the
    map file whenever it can, so it compared the file to itself and the
    in-module fallback was never exercised. They agreed, all six entries; but
    this change adds to both, which is when such a guard gets relied on.
    """
    import compass_pkg  # noqa: F401
    from compass_pkg import migrate

    data = _map()
    keys = data.get("stage_keys")
    assert keys, (
        "cli/migrate-map.yml has no `stage_keys:` section. The stage keys are "
        "the one set of renames the map never covered, which is why they were "
        "never migrated. Sections present: %s" % sorted(data))
    assert keys == STAGE_RENAMES, (
        "the stage-key map is not the six renames this issue makes:\n"
        "  expected: %s\n  found:    %s" % (STAGE_RENAMES, keys))
    for k in STAGE_UNCHANGED:
        assert k not in keys, (
            "%r is in the rename map and must not be. `plan` stays because the "
            "command moves TO it - migrate-map.yml records that the artifact "
            "was `plan.md` in v1, so a later reader may take the key for a "
            "vestige and 'fix' it. `verify` already agrees." % k)

    # THE FALLBACK, EXERCISED. Point the reader at a path that is not there so
    # the in-module copy is what answers.
    #
    # PATCH `core`, NOT `migrate`. `migrate` imports the name, but the reader
    # (`core.migrate_map_section`) calls `migrate_map_path()` resolved in
    # core's OWN namespace - so patching `migrate._map_path` is invisible to
    # it, the file answers anyway, and this guard goes back to comparing the
    # file with itself, which is the defect it exists for. It did exactly that
    # until 2026-08-25, including its own rigour assertion, which inspected
    # the patched lambda and confirmed nothing about what was read.
    from compass_pkg import core

    real_artifacts = migrate.artifact_name_map()
    real_stages = migrate.stage_key_map()
    original = core.migrate_map_path
    try:
        core.migrate_map_path = lambda: "/nonexistent/migrate-map.yml"
        # The positive control: with the file unreachable, a section asked for
        # with a sentinel fallback must come back as exactly that sentinel. If
        # the file is still answering, this fails here rather than silently
        # further down.
        sentinel = {"__unreachable__": "__sentinel__"}
        assert core.migrate_map_section("artifacts", sentinel) == sentinel, (
            "the map file still answered with the path patched out, so the "
            "in-module fallback was never reached and the comparison below "
            "would be the file against itself")
        fb_artifacts = migrate.artifact_name_map()
        fb_stages = migrate.stage_key_map()
    finally:
        core.migrate_map_path = original

    for name, from_file, from_code in (("artifacts", real_artifacts, fb_artifacts),
                                       ("stage_keys", real_stages, fb_stages)):
        assert from_code == from_file, (
            "the in-module fallback for `%s` has drifted from "
            "cli/migrate-map.yml, so a bare checkout would migrate differently "
            "from an installed one:\n  only in the file: %s\n"
            "  only in the code: %s"
            % (name, sorted(set(from_file) - set(from_code)),
               sorted(set(from_code) - set(from_file))))


def test_trc_e2_map_guard_declines_an_empty_input():
    """A scan handed nothing does not report a pass (`TRC-E2` for the map)."""
    from compass_pkg import migrate

    assert migrate.artifact_name_map(), (
        "the artifact map is empty, so every assertion about it above compares "
        "two empty things and passes")
    assert _map().get("stage_keys"), "the stage-key map is empty"


# ---------------------------------------------------------------------------
# Group B - nothing already written breaks
# ---------------------------------------------------------------------------

def test_trc_b1():
    """A manifest written before the rename still reads (`TRC-B1`).

    107 manifests carry the retired keys. ADR-006 makes this
    non-negotiable inside a major version.
    """
    from compass_pkg.core import normalize_spine

    old = {"schema_version": "2.0", "task": "t",
           "stages": {k: "full" for k in STAGE_RENAMES} | {"plan": "full",
                                                           "verify": "full"}}
    got = normalize_spine(old)["stages"]
    for retired, current in STAGE_RENAMES.items():
        assert current in got, (
            "a manifest holding the retired stage key %r did not resolve to %r - "
            "107 manifests carry these:\n  %s" % (retired, current, got))
        assert retired not in got, (
            "%r survived normalisation alongside %r" % (retired, current))
    for k in STAGE_UNCHANGED:
        assert k in got, "%r must survive normalisation unchanged" % k

    # A manifest already speaking the new keys normalises to itself.
    new = {"schema_version": "2.0", "task": "t",
           "stages": {v: "full" for v in STAGE_RENAMES.values()}}
    assert normalize_spine(new)["stages"] == new["stages"], (
        "a manifest holding the current keys did not survive normalisation")


def test_trc_b2():
    """A document written before the rename still resolves (`TRC-B2`).

    Also asserts the compatibility map has not collapsed to an identity. A
    blanket rename over the tree rewrote its values to the current filenames
    on 2026-08-25 - the map whose only job is to remember the old name had the
    old name renamed out of it, and every assertion below still passed because
    the fixture wrote whatever the map said.
    """
    from compass_pkg.core import _RENAMED_KIND_FILES

    assert _RENAMED_KIND_FILES, "the compatibility map is empty"
    for kind, filename in _RENAMED_KIND_FILES.items():
        assert filename != "%s.md" % kind, (
            "the compatibility entry for %r points at its own current "
            "filename, so it maps nothing and a landed issue holding the old "
            "name no longer resolves" % kind)
    import tempfile
    from compass_pkg.core import FOUND, resolve_artifact

    tmp = Path(tempfile.mkdtemp(prefix="compass-rename-"))
    (tmp / "design.md").write_text("# old name\n")
    (tmp / "prd.md").write_text("# old name\n")

    for kind, flat in (("technical-design", "design.md"), ("intent", "prd.md")):
        state, path, reason = resolve_artifact(str(tmp), kind)
        assert state == FOUND, (
            "asking for %r did not find the file a landed issue actually holds "
            "(%s): %s" % (kind, flat, reason))
        assert Path(path).name == flat, (
            "resolved to %s rather than the file on disk, %s"
            % (Path(path).name, flat))
        assert flat in reason or "flat" in reason, (
            "the reason does not say which route found it: " + reason)


# ---------------------------------------------------------------------------
# Group A - the names agree
# ---------------------------------------------------------------------------

COMMANDS = REPO_ROOT / "commands"

def _cli_stage_keys():
    """The stage keys the CLI itself writes into a manifest.

    Read from the machinery rather than restated here. A hand-written
    `{"assess": "assess", "define": "define", ...}` map stood in this file
    until 2026-08-25 and the test compared each key with itself - an identity
    dict makes `command == key` structurally incapable of failing, so the
    assertion read as the rule and checked nothing.

    NOT read from governance/routing-policy.yml: that file still declares the
    v1 keys (`frame`, `specify`, ...) and is migrated in its own slice. The
    manifest loader maps them forward, so what a manifest HOLDS is what matters
    here.
    """
    from compass_pkg.core import STAGE_DISPLAY
    return set(STAGE_DISPLAY)

# Retired command names that must answer with a pointer rather than vanish.
# `design` is NOT here: it is a retired name for the engineering stage AND the
# live name for the designer's, so a stub pointing at `/compass:plan` would
# take the designer's command away again.
RETIRED_COMMANDS = {"triage": "assess", "wireframe": "design"}


def _command_names():
    return {p.stem for p in COMMANDS.glob("*.md")}


def _is_removed(name):
    """A retired name that no longer ships at all.

    Through 3.x these names were redirect stubs - a file that named its
    replacement and did nothing else. 4.0.0 removed them at the major-version
    boundary ADR-019 scheduled them for, so the check is now absence.

    Inverted rather than deleted: a guard removed alongside its subject
    leaves nothing asserting the subject stays gone, and the next rename
    re-adds a stub with no test objecting.
    """
    return not (COMMANDS / ("%s.md" % name)).is_file()


def test_trc_a1():
    """A command, its machine key and its artifact name the same thing (`TRC-A1`).

    The rule is about an artifact CLAIMING another stage, not about sharing a
    word with one - four artifacts already differ from their stage's name and
    none is a defect (`define`/`acceptance-criteria`,
    `refine`/`requirements-review`, `assess`/`delivery-approach`,
    `verify`/`verification-report`).
    """
    names = _command_names()
    assert names, "no command files found, so this checks nothing"

    keys = _cli_stage_keys()
    assert keys, "the CLI declares no stage keys, so this checks nothing"
    missing = sorted(k for k in keys if k not in names)
    assert not missing, (
        "the manifest holds these stage keys and no command of the same name "
        "exists: %s. The word a person types and the word the manifest holds "
        "must be the same. Commands present: %s"
        % (missing, sorted(names)))

    # The two defects this rule exists for, asserted directly rather than left
    # to the general shape above.
    intent = (COMMANDS / "intent.md").read_text(encoding="utf-8")
    assert "prd.md" not in intent, (
        "`/compass:intent` still writes prd.md - a command and its own output "
        "naming different things is the defect this issue opened on")
    assert "intent.md" in intent, (
        "`/compass:intent` does not name intent.md as what it writes")
    assert _is_removed("triage"), (
        "`/compass:triage` still ships. It produces an `assessment:` block, "
        "and the command for that is `/compass:assess`; the retired name was "
        "removed at 4.0.0 (ADR-019, ADR-024).")


def test_trc_a2():
    """The designer's command is `design` again, and does not claim
    the engineering stage's job (`TRC-A2`)."""
    names = _command_names()
    for want in ("design", "plan"):
        assert want in names, "no `/compass:%s` command: %s" % (want, sorted(names))
    assert _is_removed("wireframe"), (
        "`/compass:wireframe` still ships - the designer's entry point is "
        "`/compass:design`, and the retired name was removed at 4.0.0")

    design = (COMMANDS / "design.md").read_text(encoding="utf-8")
    plan = (COMMANDS / "plan.md").read_text(encoding="utf-8")

    assert "ui-contract.md" in design, (
        "`/compass:design` does not produce the UI contract, so it is not the "
        "designer's entry point")
    assert "technical-design.md" in plan, (
        "`/compass:plan` does not produce technical-design.md")
    assert "ui-contract.md" not in plan, (
        "`/compass:plan` claims the designer's artifact")
    assert "technical-design.md" not in design, (
        "`/compass:design` claims the engineering stage's artifact")


def test_trc_b4():
    """A retired command no longer answers at all (`TRC-B4`).

    Through 3.x each of these was a redirect stub, and this scenario checked
    it pointed at its replacement. 4.0.0 removed them, so the scenario now
    checks the opposite - and checks that the replacement it used to name is
    still the live command, which is the half that still matters to a reader
    whose script broke.

    `design` is deliberately excluded: it is retired for one stage and live
    for another, and was never a stub.
    """
    names = _command_names()
    for retired, replacement in RETIRED_COMMANDS.items():
        assert not (COMMANDS / ("%s.md" % retired)).is_file(), (
            "`/compass:%s` still ships. It was a redirect stub through 3.x "
            "and was removed at 4.0.0 (ADR-019, ADR-024)." % retired)
        assert replacement in names, (
            "`/compass:%s` is gone but its replacement `/compass:%s` does "
            "not exist, so the rename left a reader nowhere to go"
            % (retired, replacement))

    assert "design" in names, "the design command vanished"
    design = (COMMANDS / "design.md").read_text(encoding="utf-8")
    assert "/compass:plan" not in design or "designer" in design.lower(), (
        "`/compass:design` reads as a stub pointing at `/compass:plan`. It is "
        "the designer's command now, not a redirect")


# ---------------------------------------------------------------------------
# Group B (continued) - a rename has two halves, and only one was tested
#
# `TRC-B2` proved a document written BEFORE the rename still resolves. Nothing
# asked the other question: does a document written AFTER it resolve? It did
# not. `_flat_name` replaced the current filename with the retired one instead
# of falling back to it, so `compass issue dashboard` reported a technical
# design that was sitting on disk as "not written yet" - the review page
# denying a document that exists.
# ---------------------------------------------------------------------------

def _issue_dir(**files):
    """A throwaway issue directory holding exactly the files named."""
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="compass-rename-"))
    for name, body in files.items():
        (tmp / name.replace("_", ".")).write_text(body, encoding="utf-8")
    return tmp


def test_trc_b5():
    """A document written after the rename resolves under its new name (`TRC-B5`).

    This is `TRC-B2` read the other way round. The compatibility map exists so a
    landed issue keeps working; it must not cost the framework the ability to
    find the file it writes today.
    """
    from compass_pkg.core import FOUND, artifact_path, resolve_artifact

    for kind, current in (("technical-design", "technical-design.md"),
                          ("intent", "intent.md")):
        tmp = _issue_dir(**{current.replace(".", "_"): "# written today\n"})
        state, path, reason = resolve_artifact(str(tmp), kind)
        assert state == FOUND, (
            "asking for %r did not find %s, the name this framework writes "
            "today: %s" % (kind, current, reason))
        assert Path(path).name == current
        assert Path(artifact_path(str(tmp), current)).name == current, (
            "artifact_path and resolve_artifact disagree about %r" % kind)


def test_trc_b6():
    """When both filenames are present, the current one wins (`TRC-B6`).

    Resuming a landed issue and re-running the plan stage writes the current
    name beside the retired one. Preferring the retired file would make every
    reader - the governance check, the review page, the design lint - quietly
    take the stale document, with nothing on screen to say so.
    """
    from compass_pkg.core import FOUND, artifact_path, resolve_artifact

    for kind, current, retired in (("technical-design", "technical-design.md",
                                    "design.md"),
                                   ("intent", "intent.md", "prd.md")):
        tmp = _issue_dir(**{current.replace(".", "_"): "# current\n",
                            retired.replace(".", "_"): "# stale\n"})
        state, path, _why = resolve_artifact(str(tmp), kind)
        assert state == FOUND and Path(path).name == current, (
            "resolve_artifact took %s over %s - every reader would get the "
            "stale document" % (Path(path).name if path else None, current))
        assert Path(artifact_path(str(tmp), current)).name == current, (
            "artifact_path took the retired %s over %s" % (retired, current))


def test_trc_b7():
    """`compass plan lint` still reads a landed issue's design (`TRC-B7`).

    Every other artifact reader goes through `artifact_path`, which knows both
    names. This one joined the filename itself, so it reported "no such file"
    on all 36 landed issues that have a design - and then explained the absence
    with a reason it could have checked and did not, that the design stage
    collapses on some approaches.
    """
    import subprocess
    import sys
    import tempfile

    project = Path(tempfile.mkdtemp(prefix="compass-rename-"))
    work = project / ".compass" / "work" / "landed"
    work.mkdir(parents=True)
    (project / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (project / ".compass" / "current-task").write_text("landed\n")
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: "landed"\ncreated: "2026-03-01"\n'
        "status: landed\ndelivery_approach: feature\n"
        "stages: {plan: full}\n")
    # The name 36 landed issue directories actually hold.
    (work / "design.md").write_text(
        "# Design - landed\n\n## DD-1\n\nChosen: this. Rejected: that.\n")

    # `compass design lint` was the spelling when this was written; the alias
    # was removed at 4.0.0 and the verb is `plan`. The defect guarded here -
    # joining the filename instead of going through `artifact_path` - is a
    # property of the reader, not of which name invoked it.
    run = subprocess.run([sys.executable, str(REPO_ROOT / "cli" / "compass"),
                          "plan", "lint"],
                         cwd=str(project), capture_output=True, text=True,
                         timeout=120)
    combined = run.stdout + run.stderr
    assert "no such file" not in combined.lower(), (
        "the design lint could not find the design.md sitting in a landed "
        "issue directory:\n" + combined)
    assert run.returncode == 0, combined


# ---------------------------------------------------------------------------
# Group A (continued) - the command moved; its call sites did not
# ---------------------------------------------------------------------------

def test_trc_a4():
    """The planning stage answers to `plan` in the CLI too (`TRC-A4`).

    `commands/design.md` was renamed to `commands/plan.md` while the CLI verb
    stayed `compass design lint` - the same word meaning the engineering
    design in the CLI and the designer's UI contract in the slash command, in
    one release. The verb moved to `plan` with a hidden `design` alias, and
    4.0.0 removed the alias - which is the exact ambiguity this rename exists
    to remove.
    """
    import subprocess
    import sys

    cli = REPO_ROOT / "cli" / "compass"
    run = subprocess.run([sys.executable, str(cli), "plan", "lint", "--help"],
                         capture_output=True, text=True)
    assert run.returncode == 0, (
        "`compass plan lint` is not a verb: " + (run.stderr or run.stdout))


# Files that may name `/compass:design` without saying which design they mean.
# Empty since 4.0.0: the two entries were the `wireframe` and `triage` redirect
# stubs, whose whole body was a pointer, and both were removed. An exemption
# naming a deleted file exempts nothing while reading as coverage, so it goes
# with the file rather than lingering.
_DESIGN_REF_EXEMPT: set[str] = set()

# `design` names the designer's command AND, until this rename, the
# engineering stage. A reference that does not say which one it means is the
# ambiguity itself, so the window around it must carry a designer marker - or
# name another role entry point, which makes it a roll-call of role commands.
_DESIGNER_MARKERS = ("designer", "Designer", "ui-contract", "UI contract",
                     "wireframe", "Wireframe")
_ROLE_ROLL_CALL = ("/compass:intent", "/compass:position")


# Directories that are not a shipped surface: version control, the framework's
# own issue archive (kept as written - ADR-014), the tests doing the checking,
# and the two untracked planning directories.
_SKIP_DIRS = {".git", "tests", "node_modules"}
# Only at the repo root. The worked examples under examples/ carry their own
# .compass/ tree, and those ARE a shipped surface - an adopter reads them to
# learn the pipeline, so a wrong command name there teaches the wrong command.
_SKIP_ROOTS = {".compass"}
_SKIP_DOCS = {"docs/proposals", "docs/analysis"}


def _is_own_issue_archive(rel):
    """This repository's own issue documents, at `docs/compass/<date>-<slug>/`.

    `.compass` is skipped at the root above because an issue's documents record
    the vocabulary in force when they were written, and rewriting them to match
    the present destroys the account. `docs-compass-artifacts` relocated those
    same documents here, so the exemption travels with them.

    ROOT ONLY, for the same reason `_SKIP_ROOTS` is root-only: the worked
    examples' documents moved too, to `examples/<x>/docs/compass/...`, and
    those ARE a shipped surface an adopter reads to learn the pipeline. A
    retired command name there teaches the wrong command.

    The per-issue SUBDIRECTORY, not `docs/compass/` itself: two hand-written
    documents sit flat in it and are live prose.
    """
    parts = rel.parts
    return (len(parts) > 3 and parts[0] == "docs" and parts[1] == "compass")
# Generated from governance/terminology.yml - fix the source, not the output.
_GENERATED = {"docs/system-spec.md", "docs/system-spec-archive.md", "docs/glossary.md"}


def _shipped_docs():
    """Every markdown surface a reader or a session actually reads."""
    for path in sorted(REPO_ROOT.rglob("*.md")):
        rel = path.relative_to(REPO_ROOT)
        if set(rel.parts) & _SKIP_DIRS or rel.parts[0] in _SKIP_ROOTS:
            continue
        if str(rel) in _GENERATED:
            continue
        if any(str(rel).startswith(d + "/") for d in _SKIP_DOCS):
            continue
        if _is_own_issue_archive(rel):
            continue
        yield rel, path


def test_trc_a5():
    """No live surface sends the engineering stage to `/compass:design` (`TRC-A5`).

    `/compass:design` was not retired - it was REPURPOSED, from the
    engineering design stage to the designer's UI-contract entry point. A
    redirect stub cannot catch that, and neither can a check that only asks
    whether a command name still exists: the name is live, under a new
    meaning. A reader following one of these lands in the designer's flow,
    writes `ui-contract.md` instead of the technical design, and is told it
    worked.

    The rule is a meaning check, not an existence check: a line naming
    `/compass:design` must say, within three lines, which design it means.
    """
    offenders = []
    for rel, path in _shipped_docs():
        if str(rel) in _DESIGN_REF_EXEMPT:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "/compass:design" not in line:
                continue
            if any(cmd in line for cmd in _ROLE_ROLL_CALL):
                continue
            window = "\n".join(lines[max(0, i - 3):i + 4])
            if any(m in window for m in _DESIGNER_MARKERS):
                continue
            offenders.append("%s:%d: %s" % (rel, i + 1, line.strip()))
    assert not offenders, (
        "these name `/compass:design` without saying which design they mean, "
        "so they read as the engineering stage and run the designer's "
        "command:\n  " + "\n  ".join(offenders))


# ---------------------------------------------------------------------------
# Group D - the frozen vocabulary must not contradict itself
# ---------------------------------------------------------------------------

TERMINOLOGY = REPO_ROOT / "governance" / "terminology.yml"


def _terminology():
    import compass_pkg  # resolves the bundled yaml
    import yaml
    return yaml.safe_load(TERMINOLOGY.read_text(encoding="utf-8"))


def _banned_spellings(doc):
    """Every individual word a `banned:` entry retires.

    A `term:` may name several at once - "Specify / Clarify / Distribute / <!-- vocabulary-scan: allow - quotes governance/terminology.yml's own term string as the example -->
    Land" is one entry retiring four words - so the slash-separated parts are <!-- vocabulary-scan: allow - quotes governance/terminology.yml's own term string as the example -->
    split out and lowercased.
    """
    out = {}
    for entry in doc.get("banned") or []:
        for part in str(entry.get("term", "")).split("/"):
            word = part.strip().lower()
            if word:
                out[word] = entry
    return out


def test_trc_d1():
    """A ban never points at a replacement that is itself banned (`TRC-D1`).

    A reader who hits a banned word looks up its replacement and uses it. If
    that replacement is also retired they rename twice, and the second rename
    is one nobody told them about - so the vocabulary reads as settled while
    handing out words it has already withdrawn.

    The rule was already written into one ban's own context line, as prose:
    "Points at the FINAL name, not at `triage` - a ban naming a banned
    replacement sends a reader to a word they must rename again." This is that
    sentence as a check.
    """
    doc = _terminology()
    banned = _banned_spellings(doc)
    offenders = []
    for entry in doc.get("banned") or []:
        for part in str(entry.get("replacement", "")).split("/"):
            word = part.strip().lower()
            if word and word in banned:
                offenders.append(
                    "%r is replaced by %r, which is itself retired (in favour "
                    "of %r)" % (entry.get("term"), part.strip(),
                                banned[word].get("replacement")))
    assert not offenders, (
        "these bans send a reader to a word they must rename again:\n  "
        + "\n  ".join(offenders))


def test_trc_d4_no_term_is_both_defined_and_banned():
    """A word cannot be the current vocabulary AND the retired vocabulary.

    `docs/glossary.md` is generated from the `terms:` block and titled "Every
    word and every id prefix Compass uses". A term defined there while banned
    below publishes the retired word as current, to the one document a reader
    consults to find out which word is current.
    """
    doc = _terminology()
    banned = _banned_spellings(doc)
    offenders = sorted(name for name in (doc.get("terms") or {})
                       if str(name).lower() in banned)
    assert not offenders, (
        "these are defined as live vocabulary and banned in the same file, so "
        "the generated glossary publishes a retired word as current: "
        + ", ".join(offenders))


def test_trc_d5_the_code_position_scan_knows_this_rename():
    """`retired_machine_names` must carry the filenames this cycle retired.

    That block is what `tests/test_terminology.py` scans Python string
    literals against - the check that exists specifically to catch a retired
    filename left in a code position. It carried the v1 filenames and was not
    extended when `design.md` became `technical-design.md` and `prd.md` became <!-- vocabulary-scan: allow - names the retired filename this migration test tracks -->
    `intent.md`, so it was blind to the rename it shipped beside.
    """
    doc = _terminology()
    retired = {str(e.get("name")): str(e.get("replacement"))
               for e in (doc.get("retired_machine_names") or [])}
    for old, new in (("design.md", "technical-design.md"),
                     ("prd.md", "intent.md")):
        assert retired.get(old) == new, (
            "retired_machine_names does not map %s to %s (it says %r), so the "
            "code-position scan cannot see this rename"
            % (old, new, retired.get(old)))



# ---------------------------------------------------------------------------
# Group C (continued) - two retired names, one current name
# ---------------------------------------------------------------------------

def test_trc_c5_migrate_refuses_a_many_to_one_collision():
    """Two retired filenames mapping to one current name must not race.

    `artifacts:` now has two such pairs, both created on 2026-08-25 when this
    rename was added beside the v2 freeze's:

        brief.md -> intent.md            prd.md    -> intent.md   <!-- vocabulary-scan: allow - names the retired filenames this migration test tracks -->
        plan.md  -> technical-design.md  design.md -> technical-design.md <!-- vocabulary-scan: allow - names the retired filenames this migration test tracks -->

    A directory holding BOTH members of a pair used to be resolved by dict
    insertion order: the first rename happened, the second silently did not,
    and the dry run had promised both. Insertion order puts the older v1 file
    first, so the STALE document won and the current one was left orphaned
    under a name nothing reads. Re-running then reported "nothing to do",
    which was a confident falsehood about a directory holding two designs.

    The archive in this repository has no `plan.md` or `brief.md` left, so it <!-- vocabulary-scan: allow - names the retired filenames this migration test tracks -->
    is latent here - and live for an adopter mid-upgrade, which is exactly who
    `compass migrate` is for.
    """
    import subprocess
    import sys
    import tempfile

    project = Path(tempfile.mkdtemp(prefix="compass-collide-"))
    work = project / ".compass" / "work" / "collide"
    work.mkdir(parents=True)
    (project / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (work / "brief.md").write_text("# v1 brief - stale\n")
    (work / "prd.md").write_text("# v2 intake - the real content\n")

    run = subprocess.run([sys.executable, str(REPO_ROOT / "cli" / "compass"),
                          "migrate", "--apply"],
                         cwd=str(project), capture_output=True, text=True,
                         timeout=120)
    combined = run.stdout + run.stderr

    assert run.returncode != 0, (
        "migrate silently picked one of two files that both claim the same "
        "current name:\n" + combined)
    assert "brief.md" in combined and "prd.md" in combined, (
        "the refusal does not name both files, so the reader cannot tell "
        "which two collided:\n" + combined)
    assert (work / "brief.md").is_file() and (work / "prd.md").is_file(), (
        "migrate renamed one of the colliding files before refusing - a "
        "refusal must leave the directory as it found it")


# ---------------------------------------------------------------------------
# Group C - the migrator, over a real archive
# ---------------------------------------------------------------------------

_V1_SPINE = """schema_version: "1.1"
task: "%s"
created: "2026-01-01"
status: landed
readings:
  blast_radius: contained
  terrain: brownfield-mapped
  size: small
  intent: delivery
route: standard
phases: {frame: full, specify: full, clarify: light, plan: full, distribute: solo, build: full, verify: full, land: full}
evidence: []
gates: []
scenarios: []
changed_files: []
"""


def _archive(root, *slugs, broken=None):
    """A work root of v1 issue directories, optionally with one broken manifest."""
    work = root / ".compass" / "work"
    work.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    for slug in slugs:
        d = work / slug
        d.mkdir()
        d.joinpath("manifest.yml").write_text(
            "task: [this is not\n  valid: yaml\n" if slug == broken
            else _V1_SPINE % slug)
        d.joinpath("plan.md").write_text("# the v1 design\n")
    return root


def _resolve(task_dir, kind):
    """The resolver's answer for one document kind.

    `compass migrate` renames a retired filename AND relocates the document to
    `docs/compass/<created>-<slug>/`, registering the path. So "the rename
    happened" is proved by the resolver finding the document, not by a file
    sitting beside the manifest - that is the location this change moves it
    out of.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "cli"))
    from compass_pkg.core import resolve_artifact
    return resolve_artifact(str(task_dir), kind)


def _migrate(project, *flags):
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "cli" / "compass"), "migrate", *flags],
        cwd=str(project), capture_output=True, text=True, timeout=180)


def test_trc_c2():
    """Migrate rewrites a stale reference, and is idempotent (`TRC-C2`).

    Both halves matter. The rename is only safe because a record written
    before it still reads (`TRC-B1`, `TRC-B2`); this is the other side of that -
    the archive is brought forward rather than left resolving through a
    compatibility path for ever. Running it twice must be a no-op, or nobody
    can re-run it after a failure without wondering what it will do.
    """
    import tempfile

    project = _archive(Path(tempfile.mkdtemp(prefix="compass-mig-")), "one", "two")
    work = project / ".compass" / "work"

    first = _migrate(project, "--apply")
    assert first.returncode == 0, first.stdout + first.stderr

    import yaml

    for slug in ("one", "two"):
        d = work / slug
        state, _path, reason = _resolve(d, "technical-design")
        assert state == "found", (
            "%s still holds the retired filename: technical-design resolves "
            "as %s (%s)" % (slug, state, reason))
        assert not (d / "plan.md").exists()
        manifest = yaml.safe_load((d / "manifest.yml").read_text())
        assert set(manifest["stages"]) == {"assess", "define", "refine", "plan",
                                        "breakdown", "implement", "verify",
                                        "ship"}, manifest["stages"]
        assert "phases" not in manifest and "readings" not in manifest
        assert str(manifest["schema_version"]).startswith("2")

    before = {p: p.read_bytes() for p in sorted(work.rglob("*")) if p.is_file()}
    second = _migrate(project, "--apply")
    assert second.returncode == 0, second.stdout + second.stderr
    assert "nothing to do" in second.stdout, second.stdout
    after = {p: p.read_bytes() for p in sorted(work.rglob("*")) if p.is_file()}
    assert before == after, "a second --apply changed the tree"


def test_trc_c3():
    """A dry run reports what would change and writes nothing (`TRC-C3`).

    The dry run is what a person reads before letting the tool touch an
    archive they cannot easily reconstruct, so "writes nothing" is the whole
    promise, and it is asserted by comparing the tree byte for byte rather
    than by trusting the wording.
    """
    import tempfile

    project = _archive(Path(tempfile.mkdtemp(prefix="compass-dry-")), "one", "two")
    work = project / ".compass" / "work"
    before = {p: p.read_bytes() for p in sorted(work.rglob("*")) if p.is_file()}

    run = _migrate(project)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "would change" in run.stdout and "dry run" in run.stdout.lower()
    for slug in ("one", "two"):
        assert slug in run.stdout, "the dry run does not name %r" % slug

    after = {p: p.read_bytes() for p in sorted(work.rglob("*")) if p.is_file()}
    assert before == after, "the dry run modified the tree"


def test_trc_c4():
    """A migration that stops says what it did and what remains (`TRC-C4`).

    A failure partway leaves some directories migrated and some not - and
    because both spellings stay accepted, that tree still WORKS, which is
    exactly why nobody would notice. The report is the only thing that would
    tell them.

    The notes were accumulated and printed after the loop, so an unparseable
    manifest raised out of the whole command and took the report with it: every
    rename already done stayed on disk, unnamed, under a raw traceback.
    """
    import tempfile

    project = _archive(Path(tempfile.mkdtemp(prefix="compass-stop-")),
                       "aaa", "bbb", "ccc", broken="bbb")
    work = project / ".compass" / "work"

    run = _migrate(project, "--apply")
    combined = run.stdout + run.stderr

    assert "Traceback" not in combined, (
        "the migration ended in a raw traceback rather than a report:\n"
        + combined)
    assert run.returncode != 0, (
        "a migration that could not finish reported success:\n" + combined)
    assert "bbb" in combined, (
        "the report does not name the directory it could not migrate:\n"
        + combined)
    for slug in ("aaa", "ccc"):
        assert slug in combined, (
            "the report does not name %r, which it did migrate - so a reader "
            "cannot tell what was changed:\n%s" % (slug, combined))
        # Renamed AND relocated: `migrate` moves a human document to
        # `docs/compass/<created>-<slug>/` and registers the path, so what
        # proves the rename is the resolver finding it, not a file beside the
        # manifest.
        state, path, reason = _resolve(work / slug, "technical-design")
        assert state == "found", (
            "%s: technical-design resolves as %s (%s)" % (slug, state, reason))

    # Re-running finishes the remainder rather than starting over: the two good
    # directories are already done and report nothing, and the broken one is
    # still named.
    again = _migrate(project, "--apply")
    combined2 = again.stdout + again.stderr
    assert "bbb" in combined2 and again.returncode != 0, combined2
    assert "renamed" not in combined2, (
        "a re-run redid work it had already done:\n" + combined2)


def test_trc_d2():
    """The vocabulary file's own prose is scanned (`TRC-D2`).

    This is how the retired stage keys survived the v2 freeze unremarked for
    months: `governance/*.yml` was not a scanned surface. Three of its YAML
    files were named individually afterwards; `terminology.yml` was not, and
    `_surface_files` drops every non-`.md` file under `governance/` besides.

    Exempting it whole is the wrong fix and the scenario says so: the
    glossary's prose is where a retired name is MOST likely to be taught,
    because `docs/glossary.md` is generated from it and is titled "Every word
    and every id prefix Compass uses". When this was written, `terms:` and
    `codes:` between them carried 13 retired names, several of which the
    glossary was publishing as current.

    So: scanned, with the blocks whose JOB is to name retired terms exempt as
    REGIONS - `banned:` and `retired_machine_names:` - and every other block
    read like any other surface.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "terminology_scan", REPO_ROOT / "tests" / "test_terminology.py")
    tt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tt)

    scan = tt._terminology()["scan"]
    files = [f for surface in scan["surfaces"] for f in tt._surface_files(surface)]
    rels = {str(f.relative_to(REPO_ROOT)) for f in files}
    assert "governance/terminology.yml" in rels, (
        "the vocabulary file is not among the files the scan reads, so the "
        "one document that defines the vocabulary is the one document nobody "
        "checks it against")

    hits = tt._scan_files([REPO_ROOT / "governance" / "terminology.yml"])
    assert not hits, tt._report(
        hits, "governance/terminology.yml teaches a retired name outside the "
              "blocks whose job is to name one")


def test_trc_d2b_the_region_exemption_is_a_region_not_a_file():
    """The control: the scan must still READ the file it region-exempts.

    A region exemption that quietly widened to the whole file would leave this
    test passing and check nothing - the exact shape this repository found
    four of in one release. So: plant a retired name in the `terms:` block and
    need the scan to catch it.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "terminology_scan", REPO_ROOT / "tests" / "test_terminology.py")
    tt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tt)

    rel = "governance/terminology.yml"
    text = (REPO_ROOT / "governance" / rel.split("/")[-1]).read_text(
        encoding="utf-8") if False else (REPO_ROOT / rel).read_text(
        encoding="utf-8")
    lines = text.splitlines()

    def _first_line_of(block):
        for i, line in enumerate(lines, 1):
            if line.startswith(block + ":"):
                return i
        raise AssertionError("no top-level %r block in %s" % (block, rel))

    exempt = tt._region_exempt_linenos(rel, lines)
    assert exempt, "no region is exempt, so the banned: block will fail the scan"

    # Inside `banned:` - naming retired terms is the job.
    assert _first_line_of("banned") + 2 in exempt

    # Inside `terms:` - the glossary's prose, and NOT exempt. If the region
    # ever widens to the whole file this is the assertion that notices.
    terms_start = _first_line_of("terms")
    assert terms_start + 2 not in exempt, (
        "a line inside the terms: block is region-exempt, so the exemption "
        "has widened past the blocks that need it")
    assert not any(n in exempt for n in range(terms_start, terms_start + 40)), (
        "the terms: block is region-exempt - that is a whole-file exemption "
        "wearing a region's name")


def test_trc_b8_a_policy_floor_written_with_a_retired_stage_key_still_applies():
    """A floor must not go quiet because it names the stage by its old word.

    `evaluate_route` canonicalises the stage keys a SHAPE declares, so
    `phases` holds `refine`. `require_phase` was looked up in that map
    unchanged, so a floor saying `clarify` asked for a key that is never
    there, found `None`, and raised nothing. No error, no warning - the floor
    is still reported as fired.

    `never_skip`, seven lines below it, was canonicalised in the same rename.
    This one was missed, and the shipped policy has said `require_phase:
    specify` ever since - a floor that has never had any effect.

    Both spellings, same outcome. That is the whole compatibility promise
    (ADR-006): an adopter's policy written before the v2 freeze keeps working.
    """
    import copy
    import os

    from compass_pkg import core
    from compass_pkg.routing import evaluate_route

    policy = core.load_yaml(
        os.path.join(core.find_governance(), "routing-policy.yml"))
    assessment = {"risk": "contained", "familiarity": "brownfield-unmapped",
                  "size": "small", "goal": "delivery", "role": "engineer",
                  "labels": []}

    def refine_weight(spelling):
        p = copy.deepcopy(policy)
        for floor in p["routing_guardrails"]["floors"]:
            if floor.get("require_phase"):
                floor["require_phase"] = spelling
        result = evaluate_route(assessment, p)
        stages = (result[0] if isinstance(result, tuple) else result)["stages"]
        return stages.get("refine")

    assert refine_weight("refine") == "full", (
        "the control failed: `require_phase` does not raise the stage even "
        "under its current name, so this test proves nothing")
    assert refine_weight("clarify") == "full", (
        "a floor naming the retired stage key raised nothing - it was looked "
        "up in a map whose keys have already been canonicalised, so it found "
        "no entry and silently did not apply")


def test_trc_c6_migrate_repoints_the_spine_at_the_files_it_renamed():
    """A manifest that names a renamed file must be repointed with it.

    The migrator renamed the files and left every reference to them inside
    `manifest.yml` untouched - so `evidence:` entries, artifact `path:` fields and
    `changed_files:` all went on naming a document that is no longer there.
    `compass check`'s gate-evidence-present then fails with "path does not
    resolve" on an issue nothing is wrong with.

    22 manifests in this repository were in that state, and some of them name
    `route.md` and `plan.md` - retired at the v2 freeze - so the freeze's own <!-- vocabulary-scan: allow - names the retired filenames this migration test tracks -->
    migration left the same wreckage a cycle earlier and nobody looked.
    """
    import subprocess
    import sys
    import tempfile

    import yaml

    project = Path(tempfile.mkdtemp(prefix="compass-repoint-"))
    work = project / ".compass" / "work" / "one"
    work.mkdir(parents=True)
    (project / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (work / "plan.md").write_text("# the v1 design\n")
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "1.1", "task": "one", "created": "2026-01-01",
        "status": "landed",
        "readings": {"blast_radius": "contained", "terrain": "brownfield-mapped",
                     "size": "small", "intent": "delivery"},
        "route": "standard",
        "phases": {"frame": "full", "specify": "full", "plan": "full",
                   "build": "full", "verify": "full", "land": "full"},
        "evidence": [{"id": "EV-DESIGN", "type": "artifact", "path": "plan.md"}],
        "artifacts": [{"kind": "technical-design", "status": "draft",
                       "path": "plan.md", "reason": "every feature carries one"}],
        "changed_files": ["plan.md"],
        "gates": [], "scenarios": [],
    }, sort_keys=False))

    run = subprocess.run(
        [sys.executable, str(REPO_ROOT / "cli" / "compass"), "migrate", "--apply"],
        cwd=str(project), capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr

    state, _path, reason = _resolve(work, "technical-design")
    assert state == "found", (
        "technical-design resolves as %s (%s) after the rename" % (state, reason))
    manifest = yaml.safe_load((work / "manifest.yml").read_text())

    # Both records are repointed twice in one run: at the renamed filename, and
    # then at where the document was relocated to. The two registries are
    # measured from different places on purpose - `artifacts:` from the project
    # root, `evidence:` from the issue directory - so the same document is
    # named two different ways, and re-anchoring the evidence registry would
    # break every gate in a repository at once.
    assert manifest["artifacts"][0]["path"] == (
        "docs/compass/2026-01-01-one/technical-design.md"), (
        "the artifact registry does not name the relocated document: %r"
        % manifest["artifacts"][0]["path"])
    assert manifest["evidence"][0]["path"] == (
        "../../../docs/compass/2026-01-01-one/technical-design.md"), (
        "the evidence record still points at the file the migration moved "
        "away, so `compass check` fails on an issue nothing is wrong with: %r"
        % manifest["evidence"][0]["path"])
    assert not (work / "technical-design.md").exists(), (
        "the document is still beside the manifest as well")
    assert manifest["changed_files"] == ["technical-design.md"], (
        "changed_files still names the retired filename")


def test_trc_c6b_a_reference_to_a_file_that_is_still_there_is_left_alone():
    """The control: repointing must be driven by the rename, not the name.

    A directory that legitimately still holds `plan.md` - because nothing
    renamed it - must keep its reference. Rewriting every occurrence of a
    retired name would break exactly the records this compatibility path
    exists to preserve.
    """
    import sys
    import tempfile

    sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg.migrate import repoint_spine_references

    tmp = Path(tempfile.mkdtemp(prefix="compass-repoint-"))
    (tmp / "plan.md").write_text("# still here\n")
    manifest = {"evidence": [{"path": "plan.md"}]}
    changed = repoint_spine_references(str(tmp), manifest, {})
    assert not changed and manifest["evidence"][0]["path"] == "plan.md", (
        "a reference to a file that is still on disk was rewritten")


def test_trc_a3():
    """Every word this rename touches carries a glossary entry (`TRC-A3`).

    This is the root cause, not a tidiness rule. `design` named a command, an
    artifact, an artifact kind, a CLI verb and a role - five things - and was
    the only one of them with no entry, while `intent`, `prd`, `triage` and
    `rollback-plan` all had one. A word stays ambiguous exactly as long as
    nobody writes down which meaning is which.

    `docs/glossary.md` is generated from these entries, so an unglossed word
    is one a reader cannot look up anywhere.
    """
    doc = _terminology()
    terms = doc.get("terms") or {}

    # Every word this change renamed, freed, or gave a second meaning.
    touched = ["assess", "plan", "technical-design", "intent", "design"]
    missing = [w for w in touched if w not in terms]
    assert not missing, (
        "these words are renamed or freed by this change and have no glossary "
        "entry, so a reader has nowhere to look up which meaning is meant: %s"
        % missing)

    for word in touched:
        entry = terms[word]
        assert str(entry.get("means", "")).strip(), (
            "the entry for %r says nothing about what it means" % word)

    # `design` is the word that caused this. Its entry has to say what it is
    # NOT, or it is a definition of one of five meanings.
    assert str(terms["design"].get("not", "")).strip(), (
        "the `design` entry does not say what it is NOT - and naming five "
        "things without saying which is which is how it stayed ambiguous")

    # The engineering artifact. `TDD` in this repository is red-green-refactor
    # and nothing else, so the abbreviation is banned in the entry itself.
    td = " ".join(str(v) for v in terms["technical-design"].values())
    assert "TDD" in td and "NEVER" in td.upper(), (
        "the technical-design entry does not warn against abbreviating it to "
        "TDD, which already means red-green-refactor here")

    # The intake document. Most teams arrive with a brief written elsewhere,
    # so a definition that presumes authorship would contradict
    # `ingest-an-existing-brief` before that issue starts.
    intent = " ".join(str(v) for v in terms["intent"].values()).lower()
    assert "ingest" in intent, (
        "the `intent` entry presumes the document is authored here. It may "
        "also be INGESTED from a brief that already exists, and the "
        "definition has to leave room for that")


def test_trc_b3():
    """The retired spelling is still accepted after the switch (`TRC-B3`).

    The ordering rule as a criterion rather than as advice: accept both
    spellings everywhere, THEN switch the writers. Switching first breaks the
    tree between two commits, and whoever does it finds out halfway through a
    rename.

    The switch has landed, so what is checkable now is the second half - that
    accepting the retired spelling survived it. Every reader below is one an
    adopter's un-migrated tree depends on (ADR-006), and each is asserted
    against the retired spelling AND the current one, so a reader that
    silently stopped accepting either fails here.
    """
    from compass_pkg.core import normalize_spine, shape_stages

    # 1. The manifest loader: a 1.x manifest still reads.
    v1 = normalize_spine({"schema_version": "1.1", "route": "standard",
                          "readings": {"blast_radius": "contained"},
                          "phases": {"frame": "full", "specify": "light"}})
    # `standard` is the v1 SHAPE name; the freeze renamed the value to
    # `feature` as well as the key, and the loader maps both.
    assert v1.get("delivery_approach") == "feature"
    assert v1.get("stages", {}).get("assess") == "full"
    assert v1.get("stages", {}).get("define") == "light"
    assert "phases" not in v1 and "route" not in v1

    v2 = normalize_spine({"schema_version": "2.0", "delivery_approach": "feature",
                          "stages": {"assess": "full", "define": "light"}})
    assert v2["stages"] == {"assess": "full", "define": "light"}, (
        "the loader changed a manifest that was already current")

    # 2. The policy reader: a project routing policy written before the freeze.
    assert shape_stages({"phases": {"clarify": "light"}}) == {"refine": "light"}
    assert shape_stages({"stages": {"refine": "light"}}) == {"refine": "light"}

    # 3. The artifact resolver: both filenames, current preferred.
    from compass_pkg.core import FOUND, resolve_artifact

    old = _issue_dir(design_md="# landed before the rename\n")
    state, path, _why = resolve_artifact(str(old), "technical-design")
    assert state == FOUND and Path(path).name == "design.md"

    # 4. The migrator's maps still carry every retired spelling.
    import compass_pkg.migrate as migrate

    artifacts = migrate.artifact_name_map()
    for retired in ("spec.feature.md", "route.md", "plan.md", "design.md",
                    "brief.md", "prd.md", "clarifications.md"):
        assert retired in artifacts, (
            "%s dropped out of the migration map, so a tree still holding it "
            "can no longer be brought forward" % retired)
    for retired in ("frame", "specify", "clarify", "distribute", "build",
                    "land"):
        assert retired in migrate.stage_key_map(), (
            "the stage key %r dropped out of the migration map" % retired)


def test_the_own_archive_exemption_does_not_reach_the_examples():
    """The control. The worked examples' documents moved to
    `examples/<x>/docs/compass/` in the same change, and they stay scanned:
    an adopter reads them to learn the pipeline, so a retired command name
    there teaches the wrong command.
    """
    from pathlib import Path as P
    assert _is_own_issue_archive(P("docs/compass/2026-08-03-a-slug/plan.md"))
    for scanned in ("examples/quick-fix-typo/docs/compass/2026-05-04-x/a.md",
                    "docs/compass/2026-08-26-first-hour-intent.md",
                    "docs/methodology.md"):
        assert not _is_own_issue_archive(P(scanned)), (
            f"{scanned} is exempt from the vocabulary scan, and should not be")

    # The examples really are there, so this is not checked against a path
    # that has gone.
    got = sorted(REPO_ROOT.glob("examples/*/docs/compass/*/*.md"))
    assert got, "no example documents under docs/compass - the check is moot"
    scanned = {rel for rel, _p in _shipped_docs()}
    assert any(str(p.relative_to(REPO_ROOT)) in {str(r) for r in scanned}
               for p in got), (
        "no example document reaches the scan, so the root-only scoping is "
        "not doing what it says")
