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


# --- TRC-S4: the front pages route a reader to compass.yml and the upgrade page

# 6.0.0 verbs the README command list had left out.
S4_VERBS = ("approach show", "approach render", "policy migrate", "policy update",
            "evidence approve", "evidence review", "issue blocked remove")


def s4_findings(readme, index, docs_readme, upgrade):
    found = []
    start = readme[:readme.index("## What Compass changes")]
    for needle in ("compass.yml", "docs/configuration.md", "docs/upgrade-6-0-0.md",
                   "docs/github-labels.md"):
        if needle not in start:
            found.append(f"README 'Start here' does not name {needle}")
    block = readme[readme.index("## The CLI"):readme.index("## What the repository contains")]
    for verb in S4_VERBS:
        if not re.search(rf"^compass {re.escape(verb)}\s", block, re.M):
            found.append(f"README command list lacks compass {verb}")
    for needle in ("configuration.md", "upgrade-6-0-0.md"):
        if f"]({needle})" not in index:
            found.append(f"docs/index.md does not link {needle}")
    if re.search(r"roll back", docs_readme, re.I):
        found.append("docs/README.md promises a rollback")
    if re.search(r"how to roll back", upgrade, re.I):
        found.append("docs/upgrade-6-0-0.md promises a rollback")
    for page, text in (("docs/README.md", docs_readme), ("docs/upgrade-6-0-0.md", upgrade)):
        if "no supported rollback" not in _flat(text):
            found.append(f"{page} does not say there is no supported rollback")
    return found


def test_trc_s4_front_pages_route_to_compass_yml():
    found = s4_findings(_read("README.md"), _read("docs/index.md"),
                        _read("docs/README.md"), _read("docs/upgrade-6-0-0.md"))
    assert not found, found
    for verb in S4_VERBS:
        assert not _verb_missing(verb.split()), verb


def test_trc_s4_the_scan_reports_the_old_front_pages():
    readme = ("## Start here\nx\n## What Compass changes\n## The CLI\n"
              "compass init   x\n## What the repository contains\n")
    found = s4_findings(readme, "# Compass\n", "how to roll back.", "6.0.0 has no rollback")
    assert any("compass.yml" in f for f in found)
    assert any("compass approach show" in f for f in found)
    assert any("configuration.md" in f for f in found)
    assert any("promises a rollback" in f for f in found)
    assert any("docs/upgrade-6-0-0.md does not say" in f for f in found)


# --- TRC-S8: the configuration, upgrade, migrate and CI pages match the code ---

def _cli(tmp_path, *argv):
    import subprocess
    import sys
    return subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv],
                          cwd=tmp_path, capture_output=True, text=True, timeout=120)


def _scratch_issue(tmp_path, slug="scratch-issue"):
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert _cli(tmp_path, "init").returncode == 0
    start = _cli(tmp_path, "quick-fix", "start", slug, "--risk", "trivial - scratch",
                 "--familiarity", "greenfield - scratch", "--size", "atomic - scratch",
                 "--intent", "scratch", "--scenario", "Given a When b Then c",
                 "--test", "tests/test_x.py::test_a")
    assert start.returncode == 0, start.stdout + start.stderr
    return slug


S8_OLD_TEXT = (
    ("docs/configuration.md", "the hooks detect npm, Make and pytest conventions",
     "says the hooks detect a test command"),
    ("docs/policy-migrate.md", "change nothing in `compass check` or the evaluator yet",
     "says editing compass.yml changes nothing yet"),
    ("docs/generation-store.md", "It refuses a landed issue", "uses the retired word 'landed'"),
    ("docs/releasing.md", "A landed issue keeps the configuration it landed under",
     "uses the retired word 'landed'"),
    ("docs/entry-exit-evaluation.md", "A landed issue has every list due",
     "uses the retired word 'landed'"),
    ("ci/README.md", "Change to `mode: enforced`", "names the key `mode` for compass.yml"),
)

S8_NEW_TEXT = (
    ("docs/configuration.md", "`tdd-red` and `tdd-green` need the command after `--`"),
    ("docs/configuration.md", "`scripts/integrate.sh` falls back to `npm test` or `make test`"),
    ("docs/policy-migrate.md", "an issue with no stored generation is judged by it at once"),
    ("docs/generation-store.md", "It refuses a closed issue"),
    ("docs/releasing.md", "A closed issue keeps the configuration it closed under"),
    ("docs/entry-exit-evaluation.md", "A closed issue has every list due"),
    ("ci/README.md", "Change to `adoption: enforced`"),
)


def s8_findings(rel, text):
    flat = _flat(text)
    found = [why for r, phrase, why in S8_OLD_TEXT if r == rel and phrase in flat]
    found += [f"lacks {phrase!r}" for r, phrase in S8_NEW_TEXT if r == rel and phrase not in flat]
    return found


def test_trc_s8_the_scan_reports_the_old_text():
    assert s8_findings("ci/README.md", "Change to `mode:\nenforced` when ready")
    assert s8_findings("docs/generation-store.md", "- It refuses a landed issue and")
    assert not s8_findings("ci/README.md", "Change to `adoption: enforced` when ready")


def test_trc_s8_configuration_upgrade_migrate_and_ci_pages_match_the_code(tmp_path):
    report = {rel: s8_findings(rel, _read(rel)) for rel in sorted({r for r, *_ in S8_OLD_TEXT})}
    report = {rel: found for rel, found in report.items() if found}
    assert not report, report

    # With no command and no project.test_command, tdd-red refuses.
    slug = _scratch_issue(tmp_path)
    red = _cli(tmp_path, "tdd-red", "--scenario", "TRC-001")
    assert red.returncode != 0 and "needs a test command" in red.stdout + red.stderr

    # In compass.yml the key is `adoption`; a `mode` key there is ignored.
    (tmp_path / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nowner: me\nadoption: advisory\nmode: enforced\n",
        encoding="utf-8")
    check = _cli(tmp_path, "check", "--issue", slug)
    assert "[mode: advisory]" in check.stdout and check.returncode == 0, check.stdout

    # A closed issue keeps the configuration it closed under, whatever the reason.
    closed = _cli(tmp_path, "issue", "status", "set", "done", "--close-reason", "not-planned",
                  "--issue", slug)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    refused = _cli(tmp_path, "issue", "migrate", "--config", "--issue", slug)
    assert "is closed and keeps the configuration it closed under" in refused.stdout + refused.stderr

    # issue migrate --apply needs --i-have-a-copy when .compass/work is not tracked.
    apply_ = _cli(tmp_path, "issue", "migrate", "--apply")
    assert apply_.returncode == 2 and "--i-have-a-copy" in apply_.stdout + apply_.stderr


def test_trc_s8_the_migrate_closing_note_says_compass_yml_is_read_at_once(tmp_path):
    import shutil
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "governance").mkdir()
    for name in ("guardrails.yml", "routing-policy.yml"):
        shutil.copy(ROOT / "governance" / name, tmp_path / "governance" / name)
    assert _cli(tmp_path, "init").returncode == 0
    dry = _cli(tmp_path, "policy", "migrate")
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert "an issue with no stored generation is judged by it at once" in dry.stdout


# --- TRC-S7: the quickstart, five-minutes and portability pages match the code --

def _policy_line_with_compass_yml(tmp_path):
    import subprocess
    import sys
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nowner: me\n", encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "approach", "evaluate", "--verbose",
         "--assessment", "risk=contained", "--assessment", "familiarity=brownfield-mapped",
         "--assessment", "size=atomic", "--assessment", "goal=delivery",
         "--assessment", "role=engineer"],
        cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    return next(line for line in run.stdout.splitlines() if line.strip().startswith("policy"))


def skills_listed(text):
    """The skill names in the `skills/` entry of the adapter layer listing."""
    block = text[text.index("\nskills/ "):text.index("\nhooks/ ")]
    return sorted(re.findall(r"[a-z]+(?:-[a-z]+)*", block.replace("skills/", "")))


def test_trc_s7_quickstart_five_minutes_and_portability_match_the_code(tmp_path):
    import yaml
    # five-minutes shows the line a project with a compass.yml gets.
    line = _policy_line_with_compass_yml(tmp_path)
    five = _read("docs/five-minutes.md")
    assert line in five.splitlines() or line.strip() in five, line
    assert "<your project>/governance/routing-policy.yml" not in five

    # A regular approach under `balanced` does not wait at assess.
    policy = yaml.safe_load(_read("governance/routing-policy.yml"))
    balanced = policy["autonomy_checkpoints"]["balanced"]["regular"]
    assert balanced == ["define", "plan"]
    quickstart = _flat(_read("docs/quickstart.md"))
    assert "presents the delivery approach and waits" not in quickstart
    assert "a regular approach goes on and logs that it did not wait" in quickstart
    assert "it waits at define and plan" in quickstart

    # portability lists the skill directories there are.
    real = sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir())
    assert len(real) == 14
    assert skills_listed(_read("docs/portability.md")) == real


def test_trc_s7_the_skills_scan_reports_the_old_list():
    old = "\nskills/          adaptive-routing, traceability, role-translation\nhooks/ x"
    assert "traceability" in skills_listed(old)
    assert skills_listed(old) != sorted(p.name for p in (ROOT / "skills").iterdir()
                                        if p.is_dir())


# --- TRC-S5: an issue's documents are found where the CLI writes them ---------

# `delivery-approach.md` is left out on purpose: only a quick fix earns it as a
# registered document, so any other approach keeps it beside the manifest.
S5_DOCUMENTS = ("acceptance-criteria.md", "technical-design.md", "requirements-review.md",
                "intent.md", "verification-report.md", "distribution-map.md",
                "positioning.md", "launch-readiness.md", "ui-contract.md")
S5_PAGES = ("README.md", "docs/five-minutes.md", "docs/methodology.md",
            "skills/compass-runtime/SKILL.md")


def s5_findings(text):
    """Documents shown inside a `.compass/work/<issue>/` listing, and the
    sentences that say the issue's documents are stored there."""
    found = []
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.S):
        work = re.split(r"\ndocs/compass/", block)[0]
        if re.search(r"\.compass/\s*\n|^\.compass/work/", work, re.M):
            found += [f"{doc} listed under .compass/work" for doc in S5_DOCUMENTS if doc in work]
    flat = _flat(text)
    for old in ("Compass stores each issue beneath `.compass/work/<issue>/`.",
                "It writes the result under `.compass/work/<issue>/`",
                "leaves a reviewable record under `.compass/work/<issue>/`"):
        if old in flat:
            found.append(old)
    return found


def test_trc_s5_documents_are_not_placed_in_the_work_directory():
    from importlib import import_module
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        layout = import_module("compass_pkg.issue_layout")
    finally:
        sys.path.pop(0)
    assert layout.docs_dir_for("2026-10-09", "my-issue") == "docs/compass/2026-10-09-my-issue"

    report = {rel: s5_findings(_read(rel)) for rel in S5_PAGES}
    report = {rel: found for rel, found in report.items() if found}
    assert not report, report
    for rel in S5_PAGES:
        assert "docs/compass/<" in _read(rel), f"{rel} does not name docs/compass/<created>-<slug>/"


def test_trc_s5_the_scan_reports_the_old_listing():
    old = "```text\n.compass/work/<issue>/\n├── manifest.yml\n├── acceptance-criteria.md\n```\n"
    assert s5_findings(old) == ["acceptance-criteria.md listed under .compass/work"]
    new = ("```text\n.compass/work/<issue>/\n├── manifest.yml\n```\n\n"
           "```text\ndocs/compass/<date>-<issue>/\n├── acceptance-criteria.md\n```\n")
    assert not s5_findings(new)
    assert s5_findings("Compass stores each issue beneath\n`.compass/work/<issue>/`.")


# --- TRC-S3: the routing deep dive matches the evaluator ----------------------

def _evaluate_verbose(**assessment):
    import subprocess
    import sys
    args = [sys.executable, str(ROOT / "cli" / "compass"), "approach", "evaluate", "--verbose"]
    for key, value in assessment.items():
        args += ["--assessment", f"{key}={value}"]
    run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout


def _case_3(text):
    start = text.index("## Case 3 ")
    return text[start:text.index("## Case 4 ")]


def test_trc_s3_routing_deep_dive_matches_the_evaluator():
    import yaml
    text = _flat(_read("docs/routing-deep-dive.md"))

    # The floor list names the labels the floor reads, and no others.
    policy = yaml.safe_load(_read("governance/routing-policy.yml"))
    floor = next(r for r in policy["routing_guardrails"]["floors"] if r["id"] == "RP-FLOOR-003")
    labels = floor["when"]["labels_any"]
    listed = re.search(r"floor list \(([^)]*)\)", text)
    assert listed, "the floor list sentence is gone"
    assert re.findall(r"`([a-z-]+)`", listed.group(1)) == labels, listed.group(1)

    # The CSV quick fix has as many gates as the CLI gives a quick fix.
    csv = _evaluate_verbose(risk="contained", familiarity="brownfield-mapped",
                            size="small", goal="delivery", role="engineer")
    gates = len(re.search(r"gate set\s+:\s+(.*)", csv).group(1).split(","))
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    section = text[text.index('"Add a CSV export" - engineer'):]
    section = section[:section.index('"Add a CSV export" - product owner')]
    assert f"{words[gates]} gates" in section, (gates, section)

    # Case 3 names every rule the CLI says fires, and not a floor that does not.
    out = _evaluate_verbose(risk="critical", familiarity="brownfield-mapped", size="small",
                            goal="delivery", role="engineer", labels="payments,migrations")
    fired = re.findall(r"\((RP-[A-Z]+-\d+),", out)
    case = _case_3(_read("docs/routing-deep-dive.md"))
    assert "RP-FLOOR-001" in fired and "RP-FLOOR-003" not in fired
    for rule in fired:
        assert rule in case, f"Case 3 does not name {rule}, which fires"
    assert re.search(r"RP-FLOOR-003.{0,200}does not list it", _flat(case)), (
        "Case 3 must say the label floor is not among the rules the CLI lists")
    assert "Two floors fire" not in case

    # A routing change is a change to compass.yml, not to the generated file.
    assert "amending that file" not in text
    assert "amendment to `governance/routing-policy.yml`" not in text
    assert "bounded by the routing policy rules in `governance/routing-policy.yml`" not in text
    assert "`compass.yml`" in text and "`docs/configuration.md`" in text


def test_trc_s3_the_case_3_scan_would_report_the_old_text():
    old = "## Case 3 - x\nTwo floors fire, and they reinforce each other.\n## Case 4 - y"
    case = _case_3(old)
    assert "Two floors fire" in case
    assert "RP-FLOOR-001" not in case


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
