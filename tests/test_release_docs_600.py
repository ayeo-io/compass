"""The owning docs say what 6.0.0 does with the settings file.

6.0.0 keeps a project's settings in `compass.yml`, reads `.compass/config.yml`
for a project that has not moved, and moves it with `compass policy migrate`.
The docs that own those facts say so, and `docs/releasing.md` records what the
release contains, the checks to run and the four compatibility configurations.

Scenario ids: IDR-8 and IDR-9, in the acceptance criteria of the issue
`init-docs-release`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _section(text, heading):
    """The body under the `### heading` line, up to the next heading of the
    same or a higher level."""
    m = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert m, f"no heading {heading!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[:end.start()] if end else rest


# --- IDR-8: the owning docs ---------------------------------------------------

def test_idr_8_configuration_md_says_what_writes_compass_yml_and_how_to_move():
    text = _read("docs/configuration.md")
    assert "compass policy migrate" in text
    assert "/compass:init" in text
    assert "because none exists yet" not in text
    assert "nothing writes it yet" not in text
    assert "rewritten `init` will" not in text


def test_idr_8_the_settings_conflict_way_out_is_not_a_command_that_refuses():
    """`policy migrate` refuses while a `compass.yml` holds the project's
    settings, so the doc must not send a conflicted project to it."""
    text = _read("docs/configuration.md")
    way_out = text[text.index("**The way out.**"):]
    way_out = way_out[:way_out.index("\n- **")]
    assert "delete them from `.compass/config.yml`" in way_out
    assert "refuses" in way_out


def test_idr_8_security_md_places_the_project_command_setting_beside_its_checks():
    text = _read("docs/security.md")
    assert re.search(r"same file|beside the checks", text), (
        "docs/security.md does not say allow_project_commands now shares a file "
        "with the checks it authorises")
    assert "compass.yml" in text[text.index("### Safer default"):]


def test_idr_8_safety_contract_states_the_three_new_limits():
    text = _read("docs/safety-contract.md").lower()
    assert "not authenticated" in text, "approvals are a name and a date"
    assert "conformance" in text
    assert "corpus" in text, "implementation compatibility holds on the corpus only"


def test_idr_8_runtime_skill_lays_out_the_project_files_as_6_does():
    text = _read("skills/compass-runtime/SKILL.md")
    assert "compass.yml" in text.split("## Where state lives", 1)[1][:600]
    assert "if `/compass:init` copied one in" not in text


def test_idr_8_receipt_md_describes_the_conformance_line():
    assert "Conformance" in _read("docs/receipt.md")


# --- IDR-9: the release entry -------------------------------------------------

def test_idr_9_releasing_md_has_a_6_0_0_entry_with_the_contents():
    text = _read("docs/releasing.md")
    body = _section(text, "What changed at 6.0.0")
    for needle in ("compass.yml", "policy lint", "policy show", "policy diff",
                   "policy migrate", "generation", "`.compass/config.yml`",
                   "7.0.0"):
        assert needle in body, f"the 6.0.0 entry does not mention {needle!r}"


def test_idr_9_the_entry_lists_the_behaviour_changes():
    body = _section(_read("docs/releasing.md"), "What changed at 6.0.0")
    assert re.search(r"fails .{0,40}lint.{0,100}--write.{0,20}refuse", body, re.S | re.I)
    assert re.search(r"landed.{0,80}(cannot|refus)", body, re.S | re.I)
    assert re.search(r"unreferenced|leftover", body, re.I)
    assert re.search(r"without a generation|no (stored )?generation", body, re.I)


def test_idr_9_the_release_checks_name_the_full_archive_run_and_contracts_a_to_d():
    text = _read("docs/releasing.md")
    body = _section(text, "Checks for 6.0.0")
    assert "COMPASS_FULL_ARCHIVE=1" in body
    assert "tests/test_compat_contracts.py" in body
    for letter in "ABCD":
        assert re.search(rf"\*\*{letter}\.\*\*", body), f"configuration {letter} missing"
    assert "test_framework_compass_yml" in body
    for rel in ("tests/test_compat_contracts.py", "tests/test_framework_compass_yml.py"):
        assert (ROOT / rel).is_file(), rel


# --- the verbs the 6.0.0 entry names exist ------------------------------------

def _named_verbs(entry):
    """Each `compass <verb> [<subverb>]` code span in `entry`."""
    spans = re.findall(r"`compass\s+([a-z][a-z-]*(?:\s+[a-z][a-z-]*)?)", entry)
    return sorted({" ".join(span.split()) for span in spans})


def _runs(argv):
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv,
                        "--help"], capture_output=True, text=True, timeout=60)
    return r.returncode == 0, r.stdout


def _verb_missing(words):
    """True when `compass <words> --help` fails, treating a trailing word as an
    argument only for a verb that has no subcommands."""
    ok, _ = _runs(words)
    if ok:
        return False
    ok_one, out = _runs(words[:1])
    return not (ok_one and "{" not in out)


def test_the_6_0_0_entry_names_only_verbs_the_cli_has():
    entry = _section(_read("docs/releasing.md"), "What changed at 6.0.0")
    verbs = [v.split() for v in _named_verbs(entry)]
    assert len(verbs) >= 8, verbs
    missing = [" ".join(v) for v in verbs if _verb_missing(v)]
    assert not missing, f"the entry names verbs the CLI lacks: {missing}"


def test_the_verb_check_fails_on_a_verb_the_cli_lacks():
    assert _verb_missing(["policy", "no-such-verb"])
    assert "policy update" in _named_verbs("`compass policy update` moves")


# --- TRC-S1: plugin instructions read the shipped governance from the plugin --
# Issue `six-zero-docs-sweep`. A 6.0.0 project has no `governance/` directory,
# so an instruction to read `governance/strategies.md` finds nothing. The shipped
# prose is in the plugin, and the files below are the ones the documentation
# review found still pointing at a project copy.

PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}/"

S1_FILES = (
    "agents/router.md", "agents/reviewer.md", "agents/verifier.md",
    "agents/planner.md", "agents/product-owner.md", "agents/product-marketer.md",
    "commands/consult.md", "commands/design.md", "commands/intent.md",
    "commands/position.md", "commands/refine.md", "commands/plan.md",
    "commands/verify.md", "commands/flow.md",
    "skills/governance-check/SKILL.md", "skills/adaptive-routing/SKILL.md",
    "skills/adaptive-routing/composition.md",
    "skills/evidence-gates/review-dimensions.md",
    "skills/receiving-code-review/SKILL.md",
    "skills/tdd-discipline/test-surface-and-worktrees.md",
    "approaches/assess-procedure.md", "approaches/rubric.md",
    "templates/delivery-approach.md",
)

# A paragraph that says one of these is about a project's own files, so a bare
# `governance/` in it is accurate.
S1_PROJECT_COPY = re.compile(
    r"copied|5\.x|if the project has `governance/(?:review-rules\.yml|decisions/)`"
    r"|`governance/decisions/` if the project has one", re.I)

S1_BARE_GOVERNANCE = re.compile(r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)(?<![\w/.-])governance/")

# Wording that sends a project to the generated view or to a copy that no
# 6.0.0 project has.
S1_OLD_WORDING = (
    (re.compile(r"/compass:init` (?:has|had) not (?:been )?run", re.I),
     "applies the shipped governance only 'if /compass:init has not run'"),
    (re.compile(r"amend(?:ing)? `?governance/", re.I),
     "changes a rule by amending a governance file"),
    (re.compile(r"change to `governance/routing-policy", re.I),
     "changes a rule by editing the generated routing-policy.yml"),
    (re.compile(r"fix is in `governance/routing-policy", re.I),
     "sends the fix to the generated routing-policy.yml"),
    (re.compile(r"bump(?:ing)? `guardrails\.yml`", re.I),
     "bumps the version of a copied guardrails.yml"),
    (re.compile(r"tuned `governance/`", re.I),
     "assumes the project tuned a governance directory"),
    (re.compile(r"Read the \*current\* `governance/` files at the project root"),
     "reads governance files at the project root"),
)


def s1_findings(text):
    """What in `text` points a 6.0.0 project at a `governance/` it does not
    have: a bare `governance/` outside a paragraph about a copied directory,
    and the wording that edits the generated view."""
    found = []
    for para in re.split(r"\n\s*\n", text):
        for m in S1_BARE_GOVERNANCE.finditer(para):
            if not S1_PROJECT_COPY.search(para):
                found.append("bare governance/: " + para.strip().splitlines()[0][:80])
                break
        for pattern, why in S1_OLD_WORDING:
            if pattern.search(para):
                found.append(why)
    return found


def test_trc_s1_plugin_instructions_read_governance_from_the_plugin():
    report = {rel: s1_findings(_read(rel)) for rel in S1_FILES}
    report = {rel: found for rel, found in report.items() if found}
    assert not report, "plugin instructions that point at a project governance/:\n" + \
        "\n".join(f"  {rel}: {found}" for rel, found in report.items())


def test_trc_s1_the_scan_reports_the_old_text_and_passes_the_new():
    old = "Read `governance/strategies.md` before you start."
    assert s1_findings(old)
    assert s1_findings("If `/compass:init` has not run, the shipped defaults apply.")
    assert s1_findings("A floor changes by amending `governance/routing-policy.yml`.")
    new = f"Read `{PLUGIN_ROOT}governance/strategies.md` before you start."
    assert not s1_findings(new)
    assert not s1_findings("A project that copied `governance/` under 5.x keeps it.")


def test_trc_s1_the_plugin_ships_the_governance_prose_the_instructions_name():
    """`${CLAUDE_PLUGIN_ROOT}` is the repository root, so the prose is there."""
    for name in ("strategies.md", "guardrails.md", "routing-policy.md"):
        assert (ROOT / "governance" / name).is_file(), name
    import json
    manifest = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert [p["source"] for p in manifest["plugins"]] == ["./"], (
        "the plugin is the whole repository, which is why governance/ ships")


# --- TRC-S9: instructions use evidence types, verbs and fields that exist -----

def _evidence_types():
    import yaml
    preset = yaml.safe_load(_read("governance/presets/default/evidence-types.yml"))
    return set(preset["evidence_types"])


def s9_findings(text, known_types):
    """Instructions a 6.0.0 CLI refuses or that a later check rejects."""
    found = []
    for m in re.finditer(r"--type\s+([a-z][a-z-]*)", text):
        if m.group(1) not in known_types:
            found.append(f"evidence type {m.group(1)!r} does not exist")
    for m in re.finditer(r"^\s*type:\s*([a-z][a-z-]*)\s*$", text, re.M):
        if m.group(1) not in known_types and m.group(1) == "architect-notes":
            found.append(f"evidence type {m.group(1)!r} does not exist")
    if re.search(r"points? (?:its )?`evidence:` at", text):
        found.append("points a gate's evidence at a file path, not an evidence id")
    if re.search(r"`update` for the report", text):
        found.append("names the subtask verb `update`, which is now `set`")
    if re.search(r"`orchestration`,\s+and `policy_rules_fired`|"
                 r"`orchestration`\s+and `policy_rules_fired`", text):
        found.append("says approach evaluate writes `orchestration`")
    return found


S9_FILES = (
    "agents/architect.md", "agents/verifier.md", "agents/router.md",
    "commands/verify.md", "approaches/assess-procedure.md",
    "skills/worktree-multiagent/SKILL.md",
)


def test_trc_s9_plugin_instructions_use_real_types_verbs_and_fields():
    known = _evidence_types()
    assert {"artifact", "test-run"} <= known and "architect-notes" not in known
    report = {rel: s9_findings(_read(rel), known) for rel in S9_FILES}
    report = {rel: found for rel, found in report.items() if found}
    assert not report, report

    verify = _read("commands/verify.md") + _read("agents/verifier.md")
    assert "compass evidence add <EV-id> --type <type> --path <file>" in verify
    assert "compass gate pass <gate> --evidence <EV-id>" in verify

    for rel in ("agents/router.md", "approaches/assess-procedure.md"):
        text = _read(rel)
        assert "`subtask_ceiling`" in text, rel
        assert "Breakdown records the" in text, rel
    assert "`set` for the report" in _read("skills/worktree-multiagent/SKILL.md")

    runtime = _read("skills/compass-runtime/SKILL.md")
    assert "keeps working through\nan alias until 7.0.0" in runtime
    assert "unknown command rather than a\npointer" not in runtime
    assert "docs/upgrade-6-0-0.md" in runtime


def test_trc_s9_the_scan_reports_the_old_text():
    known = _evidence_types()
    assert s9_findings("compass evidence add EV-1 --type architect-notes --path x", known)
    assert s9_findings("     type: architect-notes\n", known)
    assert s9_findings("sets its `status` to `pass` and point its `evidence:` at the artifact",
                       known)
    assert s9_findings("`add` at dispatch, `update` for the report", known)
    assert s9_findings("`gates`, `orchestration`, and `policy_rules_fired`", known)
    assert not s9_findings("compass evidence add EV-1 --type artifact --path x", known)


# --- TRC-S10: stage-weight tables use the stored words -------------------------

S10_FILES = tuple(f"approaches/{name}.md"
                  for name in ("quick-fix", "regular", "full", "hotfix", "spike"))
STAGES = ("Assess", "Define", "Refine", "Plan", "Breakdown", "Implement", "Verify", "Ship")


def s10_findings(text):
    """Weight cells that open with a retired depth word, and the line that
    opens the hotfix gate set with one."""
    found = []
    for line in text.splitlines():
        cell = re.match(r"\|\s*(" + "|".join(STAGES) + r")\s*\|\s*(.*?)\s*\|", line)
        if cell and re.match(r"\W*(Full|Light)\b", cell.group(2)):
            found.append(f"{cell.group(1)}: {cell.group(2)[:40]}")
        if re.match(r"Full Verify gate", line):
            found.append(line[:40])
    return found


def test_trc_s10_stage_weight_tables_use_the_stored_words():
    report = {rel: s10_findings(_read(rel)) for rel in S10_FILES}
    report = {rel: found for rel, found in report.items() if found}
    assert not report, report
    regular = _read("approaches/regular.md")
    assert "**Lightweight pass.**" in regular
    assert "Light-to-full" not in regular


def test_trc_s10_the_scan_reports_the_old_words():
    assert s10_findings("| Assess | Full. Always runs. |")
    assert s10_findings("| Refine | **Light-to-full pass.** Resolve. |")
    assert s10_findings("| Verify | Light gate: run it. |")
    assert s10_findings("Full Verify gate. Review dimensions: x")
    assert not s10_findings("| Assess | Thorough. Always runs. |")
    assert not s10_findings("| Verify | Lightweight gate: run it. |")


# --- TRC-S2: the governance prose describes the 6.0.0 model -------------------

def _flat(text):
    """`text` with every run of whitespace as one space, so a phrase matches
    across a line break."""
    return re.sub(r"\s+", " ", text)


# Each entry: the file, a phrase it must not hold, and why.
S2_OLD_TEXT = (
    ("governance/README.md", "Copy the shipped `guardrails.yml` and edit it rather",
     "tells a 6.0.0 project to copy the shipped guardrails"),
    ("governance/README.md", "adds strategies as it forms opinions",
     "says a team adds strategies in compass.yml, which cannot hold them"),
    ("governance/guardrails.md", "it can also remove one",
     "says a project can remove a locked guardrail"),
    ("governance/guardrails.md", "`policy effective` will print",
     "names a command that is only a hint to `policy show`"),
    ("governance/routing-policy.md", "changing one means amending this file",
     "sends a routing change to a generated file"),
    ("governance/routing-policy.md", "Adjust `default_shapes` and `biases` freely",
     "sends a routing change to a generated file"),
    ("governance/routing-policy.md", "`compass approach evaluate` still reads `routing-policy.yml`",
     "says evaluate reads the generated view, not the configuration"),
)

# Each entry: the file and a phrase it must hold.
S2_NEW_TEXT = (
    ("governance/README.md", "## A project that copied governance under 5.x"),
    ("governance/README.md", "`compass.yml` cannot hold strategies"),
    ("governance/guardrails.md", "`K-LOCK-REFUSED`"),
    ("governance/guardrails.md", "`compass policy show` prints the resolved configuration"),
    ("governance/routing-policy.md", "Routing changes go in the project's `compass.yml`"),
    ("governance/routing-policy.md", "reads the same resolved configuration"),
)


def s2_findings(rel, text):
    flat = _flat(text)
    found = [why for r, phrase, why in S2_OLD_TEXT if r == rel and phrase in flat]
    found += [f"lacks {phrase!r}" for r, phrase in S2_NEW_TEXT
              if r == rel and phrase not in flat]
    return found


def test_trc_s2_governance_prose_describes_compass_yml():
    report = {rel: s2_findings(rel, _read(rel))
              for rel in sorted({r for r, *_ in S2_OLD_TEXT})}
    report = {rel: found for rel, found in report.items() if found}
    assert not report, report


def test_trc_s2_the_scan_reports_the_old_text():
    assert s2_findings("governance/guardrails.md",
                       "A project can add guardrails; it can also remove one, and more.")
    assert s2_findings("governance/routing-policy.md",
                       "changing one means amending\nthis file.")
    assert s2_findings("governance/README.md", "Copy the shipped `guardrails.yml`\nand edit it rather")


def test_trc_s2_a_locked_guardrail_cannot_be_removed_in_compass_yml(tmp_path):
    """The claim the guardrails page now makes: `compass policy lint` refuses a
    `compass.yml` that removes a check from a locked guardrail."""
    import subprocess
    import sys
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nowner: me\n"
        "gates:\n  G2:\n    set:\n      checks:\n"
        "        remove: [scenario-has-id-and-intent]\n", encoding="utf-8")
    cli = [sys.executable, str(ROOT / "cli" / "compass")]
    lint = subprocess.run(cli + ["policy", "lint"], cwd=tmp_path, capture_output=True,
                          text=True, timeout=60)
    assert lint.returncode != 0 and "K-LOCK-REFUSED" in lint.stdout, lint.stdout
    (tmp_path / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nowner: me\nstrategies:\n  - id: X\n",
        encoding="utf-8")
    lint = subprocess.run(cli + ["policy", "lint"], cwd=tmp_path, capture_output=True,
                          text=True, timeout=60)
    assert "L-SCHEMA" in lint.stdout and "strategies" in lint.stdout, lint.stdout
