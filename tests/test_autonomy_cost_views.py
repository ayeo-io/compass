"""The views of the autonomy ratio and cost: diagnose, the delivery record, and
what must not change for an issue that holds none of the new fields.

Every test runs without a network: each fixture project leaves the GitHub
switches off and links no GitHub issue, a `gh` on PATH fails the test if
anything calls it, transcripts are fixture files under a temporary
`CLAUDE_CONFIG_DIR`, and git is a local repository only.

Scenario ids: ARC-6 and ARC-22 to ARC-24, in the acceptance criteria of the issue
`autonomy-ratio-and-cost`. Each test name starts with its id. ARC-29, a landed
issue with an empty `checkpoints:` list and no outcomes key, is declared on the
ARC-6 test.

Run as a script, this file writes the captures the comparisons read:

    python3 tests/test_autonomy_cost_views.py --capture <cli folder> <out folder>
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLI_DIR = ROOT / "cli"
FIXTURES = HERE / "fixtures" / "autonomy-ratio-and-cost-views"
sys.path.insert(0, str(CLI_DIR))
sys.path.insert(0, str(HERE))

import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
import yaml  # noqa: E402

import project_readiness_support as readiness_support  # noqa: E402

import test_checkpoint_outcomes as co  # noqa: E402
import test_issue_dependencies as dbi  # noqa: E402

#: Every command that is compared with the base commit runs at this instant.
FIXED_AT = dbi.FIXED_AT


# --- the projects the base commit is compared on ---------------------------------

def _masked(text, root):
    """The output with the project's own folder and every commit hash replaced,
    and the board page's Generated line, so two runs compare."""
    text = dbi._masked(text, root)
    return re.sub(r"\b[0-9a-f]{8,40}\b", "<sha>", text)


def _result(done, root):
    return _masked("exit %d\n--- stdout\n%s--- stderr\n%s" % (
        done.returncode, done.stdout, done.stderr), root)


def listed_project(root):
    """A project of three issues that name `checkpoints:` the way an issue did
    before outcomes were recorded, none holding `checkpoint_outcomes`: one landed
    and one in flight that list define and plan, and one in flight with no
    `checkpoints:` key. Both in-flight issues have every gate passed."""
    project = dbi.Project(root)
    project.issue("old-landed", at="ship", close="completed", checkpoints=["define", "plan"],
                  land_timestamp="2026-10-05T10:00:00+00:00")
    project.issue("old-flight", at="ship", checkpoints=["define", "plan"])
    project.issue("old-nokey", at="ship")
    return project


def listed_outputs(root, cli_dir=CLI_DIR):
    """What `compass check`, `compass issue lint` and `compass ci` print on the
    project of `listed_project`, by capture name."""
    root = Path(root)
    run = lambda *a: dbi.compass(root, *a, cli_dir=cli_dir, clock=FIXED_AT)  # noqa: E731
    out = {}
    for slug in ("old-landed", "old-flight", "old-nokey"):
        out[f"check-{slug}.txt"] = _result(run("check", "--issue", slug), root)
        out[f"lint-{slug}.txt"] = _result(run("issue", "lint", "--issue", slug), root)
    out["ci.txt"] = _result(run("ci"), root)
    return out


def views_project(tmp_path, cli_dir=CLI_DIR, compass_yml=co.BALANCED):
    """A git repository holding one regular issue at generation 1, written the way
    `co.project` writes it but with the assessed values justified on the command
    line, so the same builder runs under the base commit's command line."""
    cli = Path(cli_dir) / "compass"
    root = Path(tmp_path) / "repo"
    root.mkdir(parents=True)
    co.git(root, "init", "-q")
    (root / "README.md").write_text("base\n")
    (root / ".gitignore").write_text(".test-bin/\n.home/\n.gh-calls\n.claude-config/\n")
    co.git(root, "add", "-A")
    co.git(root, "commit", "-q", "-m", "base")
    assert co.run(root, "init", cli=cli).returncode == 0
    task_dir = root / ".compass" / "work" / co.SLUG
    task_dir.mkdir(parents=True)
    co.write_manifest(root, {"schema_version": "3.0", "issue": co.SLUG, "created": co.CREATED,
                             "assessment": dict(co.ASSESSMENT), "evidence": []})
    (root / ".compass" / "current-task").write_text(co.SLUG + "\n")
    (root / "compass.yml").write_text(yaml.safe_dump(compass_yml), encoding="utf-8")
    if compass_yml.get("autonomy") == "autonomous":
        # An autonomous issue is assessed only above the readiness floor.
        readiness_support.meet_readiness_floor(root)
    why = [word for name in ("risk", "familiarity", "size", "goal", "role")
           for word in ("--justify", f"{name}=Fixture: the {name} was judged.")]
    done = co.run(root, "approach", "evaluate", "--issue", co.SLUG, "--write", *why, cli=cli)
    assert done.returncode == 0, done
    (task_dir / "delivery-approach.md").write_text("# Delivery approach\n")
    (root / co.DOCS).mkdir(parents=True, exist_ok=True)
    return root


def ship_listed(tmp_path, cli_dir=CLI_DIR, keep_checkpoints=True):
    """`ship-commit` on a regular issue that lists define and plan and holds no
    `checkpoint_outcomes` key (or, with `keep_checkpoints` false, no `checkpoints:`
    key either), ready to ship: its exit code and output with hashes masked."""
    cli = Path(cli_dir) / "compass"
    root = views_project(tmp_path, cli_dir)
    body = co.manifest(root)
    body.pop("checkpoint_outcomes", None)
    if not keep_checkpoints:
        body.pop("checkpoints", None)
    else:
        assert body["checkpoints"] == ["define", "plan"]
    co.write_manifest(root, body)
    co.register(root, "acceptance-criteria", "approved", cli=cli)
    co._ready_to_ship(root, cli=cli)
    done = co.run(root, "ship-commit", "-m", "Ship it", "--issue", co.SLUG, cli=cli)
    assert co.manifest(root).get("land_timestamp"), done
    co.assert_no_gh_call(root)
    return {"exit": done.returncode, "stdout": _masked(done.stdout, root),
            "stderr": _masked(done.stderr, root)}


def state_outputs(root, cli_dir=CLI_DIR):
    """What `compass next`, `check`, `issue lint`, `flow --json` and `board render`
    print on the project `dbi.build_dbi5_project` writes: an issue at every
    workflow state, none holding a new field."""
    root = Path(root)
    run = lambda *a: dbi.compass(root, *a, cli_dir=cli_dir, clock=FIXED_AT)  # noqa: E731
    out = {}
    for slug in dbi._dbi5_slugs(root):
        out[f"next-{slug}.txt"] = _result(run("next", "--issue", slug), root)
        out[f"check-{slug}.txt"] = _result(run("check", "--issue", slug), root)
        out[f"lint-{slug}.txt"] = _result(run("issue", "lint", "--issue", slug), root)
    out["flow-json.txt"] = _result(run("flow", "--json"), root)
    page = root / "board.html"
    out["board-render.txt"] = _result(run("board", "render", "--no-open", "--out", str(page)),
                                      root)
    out["board-page.html"] = _masked(page.read_text(encoding="utf-8"), root)
    return out


# --- writing the captures ----------------------------------------------------------

def _capture(cli_dir, out_folder):
    """Write what the code at `cli_dir` prints for every comparison in this file."""
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="arc-views-"))
    listed = listed_outputs(listed_project(work / "listed").root, cli_dir)
    states = state_outputs(dbi.build_dbi5_project(work / "states"), cli_dir)
    ships = {"flight-listed": ship_listed(work / "ship-a", cli_dir),
             "flight-nokey": ship_listed(work / "ship-b", cli_dir, keep_checkpoints=False)}
    header = ("# Captured from the code before checkpoint outcomes and usage existed, under a\n"
              "# fixed clock. The project's own folder reads <ROOT>, commit hashes read <sha>\n"
              "# and the board page's Generated line is masked.\n")
    for name, body in (("listed", listed), ("states", states)):
        (out_folder / f"{name}.yml").write_text(
            header + yaml.dump({k: dbi._Block(v) for k, v in body.items()},
                               Dumper=dbi._CaptureDumper, sort_keys=False, width=1000,
                               allow_unicode=True), encoding="utf-8")
    (out_folder / "ships.json").write_text(json.dumps(ships, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)


# --- ARC-6 --------------------------------------------------------------------------

def captured(name):
    return yaml.safe_load((FIXTURES / name).read_text(encoding="utf-8"))


def test_arc_6_landed_issues_are_not_judged(tmp_path):
    # `compass check`, `compass issue lint` and `compass ci` print what the base
    # commit printed for the same project, and exit with the same code.
    project = listed_project(tmp_path / "listed")
    manifests = {p: p.read_bytes() for p in (project.root / ".compass" / "work").glob("*/manifest.yml")}
    was = captured("listed.yml")
    now = listed_outputs(project.root)
    assert list(now) == list(was)
    for name, text in now.items():
        assert text == was[name], name
    assert {p: p.read_bytes() for p in manifests} == manifests

    # `ship-commit` lands each issue in flight as the base commit lands it.
    ships = json.loads((FIXTURES / "ships.json").read_text(encoding="utf-8"))
    assert ship_listed(tmp_path / "ship-a") == ships["flight-listed"]
    assert ship_listed(tmp_path / "ship-b", keep_checkpoints=False) == ships["flight-nokey"]

    # A reassessment with a changed size does not add the key.
    root = views_project(tmp_path / "reassess")
    body = co.manifest(root)
    body.pop("checkpoint_outcomes")
    body["assessment"]["size"] = "large"
    co.write_manifest(root, body)
    assert "checkpoint_outcomes" not in co.manifest(root)
    done = co.run(root, "approach", "evaluate", "--issue", co.SLUG, "--write",
                  "--justify", "size=Fixture: it grew.",
                  "--reason", "The work grew past a medium change.")
    assert done.returncode == 0, done
    assert co.manifest(root)["assessment"]["size"] == "large"
    assert "checkpoint_outcomes" not in co.manifest(root)

    # The retro counts the landed issue as shipped and not measurable.
    done = dbi.compass(project.root, "retro", "--impact")
    assert done.returncode == 0, done
    lines = [line for line in done.stdout.splitlines() if line.startswith("  autonomy ")]
    assert lines == ["  autonomy      unmeasurable - 0 measurable shipped issue(s); 20 required "
                     "(1 shipped issue(s) not measurable)"], done.stdout
    row = json.loads(dbi.compass(project.root, "retro", "--impact", "--json").stdout)
    assert (row["autonomy_ratio"]["issues"], row["autonomy_ratio"]["not_measurable"]) == (0, 1)
    dbi.assert_no_gh_call(project.root)
    co.assert_no_gh_call(root)

    # A landed issue that lists no checkpoint and holds no `checkpoint_outcomes`
    # key is not judged: shipped, not measurable, and never autonomous.
    from compass_pkg import autonomy_cost
    before = rac.not_judged("before")
    assert autonomy_cost.shipped(before)
    assert not autonomy_cost.measurable(before) and not autonomy_cost.autonomous(before)
    empty = rac.write_project(tmp_path / "empty", {"before": before})
    row = json.loads(rac.retro(empty, "--impact", "--json").stdout)
    assert (row["autonomy_ratio"]["issues"], row["autonomy_ratio"]["not_measurable"]) == (0, 1)
    dbi.assert_no_gh_call(empty)


# --- ARC-22 -------------------------------------------------------------------------

import test_retro_autonomy_cost as rac  # noqa: E402

COUNTS = {"subagent_requests": 0, "input": 1, "output": 1, "cache_write": 1, "cache_read": 1}


def usage_with(**changes):
    """A complete usage block: 8 requests costing $4.25, of which define holds 3
    ($1.50), plan 4 ($2.25) and the requests after the last stage 1 ($0.50)."""
    block = {"sessions": ["sess-1"], "source": "claude-code", "skipped_lines": 0,
             "total": dict(COUNTS, requests=8, cost_usd=4.25),
             "unattributed": dict(COUNTS, requests=1, cost_usd=0.5),
             "stages": {"define": dict(COUNTS, requests=3, cost_usd=1.5),
                        "plan": dict(COUNTS, requests=4, cost_usd=2.25),
                        "implement": {"measured": False, "reason": "no-window"}}}
    block.update(changes)
    return block


def diagnose(root):
    done = co.run(root, "issue", "diagnose", "--issue", co.SLUG)
    assert done.returncode == 0, done
    return done.stdout


def section(text, title):
    """The lines of one section of the report, up to the next blank line."""
    lines = text.splitlines()
    start = lines.index(title)
    out = []
    for line in lines[start + 1:]:
        if not line.strip():
            break
        out.append(line)
    return out


def snapshot(root):
    skip = (".test-bin", ".home")
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(Path(root).rglob("*"))
            if p.is_file() and ".git" not in p.relative_to(root).parts
            and p.relative_to(root).parts[0] not in skip}


def test_arc_22_diagnose_shows_bands_and_cost(tmp_path):
    root, folder = rac.landed_fixture_issue(tmp_path / "balanced", "balanced")
    body = co.manifest(root)
    body["usage"] = usage_with()
    co.write_manifest(root, body)
    before = snapshot(root)
    text = diagnose(root)
    assert snapshot(root) == before

    outcomes = {e["stage"]: e for e in body["checkpoint_outcomes"]}
    shown = section(text, "Checkpoints and cost")
    expected = [f"  {stage:<8} {outcomes[stage]['outcome']:<8} by {outcomes[stage]['by']}  "
                f"at {outcomes[stage]['at']}" for stage in ("assess", "define", "refine", "plan")]
    assert shown[:4] == expected, shown
    assert shown[4:] == [
        "  bands: human judgement 2 (checkpoints and human checks), guardrailed 7 (gates), "
        "autonomous 5 (stages)",
        "  cost: $4.2500 over 8 request(s)",
        "    define       $1.5000  3 request(s)",
        "    plan         $2.2500  4 request(s)",
        "    implement    not measured (no-window)",
        "    unattributed $0.5000  1 request(s)"], shown

    # The retro's figures for the issue are the same functions' figures.
    from compass_pkg import autonomy_cost
    from compass_pkg.core import normalize_spine
    assert autonomy_cost.bands(normalize_spine(co.manifest(root)), str(folder)) == {
        "human_judgement": 2, "guardrailed": 7, "autonomous": 5}
    assert autonomy_cost.complete_cost(co.manifest(root)) == 4.25

    # An outcome is a dated event in the timeline.
    timeline = section(text, "Timeline")
    for stage, entry in outcomes.items():
        assert any(line.startswith(f"  {entry['at']}  checkpoint {stage} {entry['outcome']} "
                                   f"by {entry['by']}") for line in timeline), (stage, timeline)

    # The last thing the records cannot show is no longer token use.
    cannot = section(text, "The records cannot show")
    assert "  - token use of a session the hook did not record" in cannot, cannot
    assert not any("token use outside" in line for line in cannot)

    # Usage that was not recorded says why.
    body["usage"] = {"recorded": False, "reason": "no-transcript", "sessions": ["sess-1"]}
    co.write_manifest(root, body)
    again = section(diagnose(root), "Checkpoints and cost")
    assert again[4:] == ["  bands: human judgement 2 (checkpoints and human checks), "
                         "guardrailed 7 (gates), autonomous 5 (stages)",
                         "  cost: not recorded (no-transcript)"], again

    # An issue with no usage block and no outcomes still gets the section.
    body.pop("usage")
    body["checkpoint_outcomes"] = []
    co.write_manifest(root, body)
    bare = section(diagnose(root), "Checkpoints and cost")
    assert bare[0] == "  no checkpoint outcomes recorded", bare
    assert bare[-1] == "  cost: not recorded (no usage block)", bare
    co.assert_no_gh_call(root)


# --- ARC-23 -------------------------------------------------------------------------

import test_issue_usage as iu  # noqa: E402

APPROVAL = "EV-CHECKPOINT-define-1"


def answered_issue(tmp_path, paths):
    """A regular issue with complete usage whose define hand-off jed72 answered,
    landed with a record that copies `paths` to a bare repository. Returns the
    project and a clone of the record."""
    tmp_path.mkdir(parents=True)
    bare = tmp_path / "record.git"
    co.git(tmp_path, "init", "-q", "--bare", str(bare))
    root, _ = iu.regular_project(tmp_path / "work", compass_yml=dict(
        iu.AUTONOMOUS, record={"remote": str(bare), "paths": paths}))
    body = co.manifest(root)
    body["checkpoints"] = ["define"]
    body["evidence"] = body.get("evidence", []) + [{
        "id": APPROVAL, "type": "checkpoint-approval", "checkpoint": "define",
        "approver": "jed72", "role": "product-owner", "scope": "the define hand-off",
        "decision": "approved", "timestamp": "2026-10-13T09:30:00Z", "issue": co.SLUG,
        "generation": body.get("generation")}]
    for entry in body["checkpoint_outcomes"]:
        if entry["stage"] == "define":
            entry.update(outcome="waited", by="jed72", evidence=APPROVAL)
    co.write_manifest(root, body)
    done = iu.ship_at(root)
    assert done.returncode == 0, done
    clone = tmp_path / "record-copy"
    # The record pushes to main, but a bare repository's HEAD follows
    # init.defaultBranch, which is master on CI. A plain clone would then
    # check out nothing and exit 0; naming the branch makes it fail instead.
    co.git(tmp_path, "clone", "-q", "-b", "main", str(bare), str(clone))
    return root, clone


def test_arc_23_record_carries_fields_and_no_new_names(tmp_path):
    root, clone = answered_issue(tmp_path / "full", [".compass/work", "docs/compass"])
    landed = co.manifest(root)
    assert landed["usage"]["total"]["cost_usd"] and landed["usage"].get("recorded") is not False
    copied = yaml.safe_load((clone / ".compass" / "work" / co.SLUG / "manifest.yml").read_text())
    assert copied["usage"]["total"]["cost_usd"] == landed["usage"]["total"]["cost_usd"]
    assert copied["checkpoint_outcomes"] == landed["checkpoint_outcomes"]
    # Every name in a waited outcome is the approver of the record it cites,
    # in the same manifest.
    approvers = {e["id"]: e["approver"] for e in copied["evidence"]
                 if e.get("type") == "checkpoint-approval"}
    waited = [e for e in copied["checkpoint_outcomes"] if e["outcome"] == "waited"]
    assert waited and all(e["by"] == approvers[e["evidence"]] for e in waited), waited
    # The record holds only copies of files under the configured paths, and
    # each copy equals its source. The readiness catalogue in a generation's
    # provenance has a key with "secret" in its name: redaction must leave it.
    for path in sorted(clone.rglob("*")):
        relative = path.relative_to(clone)
        if path.is_file() and ".git" not in relative.parts:
            source = root / relative
            assert source.is_file() and path.read_text(encoding="utf-8") == (
                source.read_text(encoding="utf-8")), str(relative)

    # A record that lists only docs/compass holds neither field.
    root, clone = answered_issue(tmp_path / "docs-only", ["docs/compass"])
    assert not (clone / ".compass").exists()
    for path in sorted(clone.rglob("*")):
        if path.is_file() and ".git" not in path.relative_to(clone).parts:
            text = path.read_text(encoding="utf-8", errors="replace")
            assert "checkpoint_outcomes" not in text and "usage:" not in text, path
    co.assert_no_gh_call(root)


# --- the human-judgement band -------------------------------------------------------

def test_the_human_judgement_band_counts_a_human_check_whose_approval_passes(
        tmp_path, monkeypatch):
    """The band adds the human checks whose approval `approval_records.judge`
    passes to the `waited` outcomes: a check that lists approvers counts only
    with a current approval by one of them."""
    import test_human_checks as hc
    from compass_pkg import autonomy_cost
    root, task_dir = hc._config_project(tmp_path)
    view = hc._view(root, monkeypatch, hc._approver("alice"))

    def counted():
        task = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
        return autonomy_cost.human_checks_passed(view, task, str(task_dir))

    assert counted() == 0
    hc._add_records(task_dir, [hc._record()])
    assert counted() == 1
    # A later rejection withdraws it, and an approver who is not listed counts for nothing.
    hc._add_records(task_dir, [hc._record(id="EV-APPROVE-2", decision="rejected",
                                          timestamp="2026-10-08T10:00:00Z")])
    assert counted() == 0
    hc._add_records(task_dir, [hc._record(id="EV-APPROVE-3", approver="mallory",
                                          timestamp="2026-10-08T11:00:00Z")])
    assert counted() == 0
    # An issue read without a configuration has no human checks.
    assert autonomy_cost.human_checks_passed(None, {}, str(task_dir)) == 0


def test_the_bands_read_the_configuration_only_when_an_approval_could_count(
        tmp_path, monkeypatch):
    """A human check passes only with an approval record naming it, so an issue
    that holds none has no human check to count and its configuration is not
    read: a retro over a large archive does not read it once for each issue. An
    issue that holds one needs it, and is left out when it cannot be read."""
    from compass_pkg import autonomy_cost, effective
    task = rac.waited("shipped")
    folder = tmp_path / "shipped"
    folder.mkdir()

    def unreadable(*args, **kwargs):
        raise RuntimeError("the configuration cannot be read")

    monkeypatch.setattr(effective, "view_or_legacy", unreadable)
    assert autonomy_cost.bands(task, str(folder)) == WAITED_BANDS
    task["evidence"].append({"id": "EV-A", "type": "human-approval", "check": "dor-summary-filled",
                             "decision": "approved", "approver": "alice"})
    assert autonomy_cost.bands(task, str(folder)) is None
    task["evidence"][-1]["type"] = "artifact-approval"
    assert autonomy_cost.bands(task, str(folder)) is None
    task["evidence"][-1]["type"] = "checkpoint-approval"
    assert autonomy_cost.bands(task, str(folder)) == WAITED_BANDS


WAITED_BANDS = rac.WAITED_BANDS


# --- ARC-24 -------------------------------------------------------------------------

def _keys(node):
    """Every property name in a JSON Schema."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                yield from value
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)


def _words(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def test_arc_24_shape_and_compatibility(tmp_path):
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    outcomes = schema["properties"]["checkpoint_outcomes"]
    item = outcomes["items"]
    assert "checkpoint_outcomes" not in schema.get("required", [])
    assert outcomes["type"] == "array" and item["additionalProperties"] is False
    assert set(item["properties"]) == {"stage", "outcome", "by", "at", "evidence"}
    assert item["properties"]["outcome"]["enum"] == ["waited", "skipped"]
    assert item["required"] == ["stage", "outcome", "by", "at"]
    assert item["if"]["properties"]["outcome"]["const"] == "waited"
    assert item["then"]["required"] == ["evidence"]
    assert {"sessions", "total", "unattributed"} <= set(schema["properties"]["usage"]["properties"])
    assert "checkpoint-approval" in json.dumps(schema)
    derived = re.compile(r"(^|[_-])(bands?|ratio|median)([_-]|$)")
    assert not [k for k in _keys(schema) if derived.search(k.lower())]
    types = yaml.safe_load((ROOT / "governance" / "presets" / "default"
                            / "evidence-types.yml").read_text(encoding="utf-8"))
    described = " ".join(str(types["evidence_types"]["checkpoint-approval"]["description"]).split())
    assert "A person's answer to one checkpoint hand-off" in described
    assert "never meets guardrail `G5` or a human check" in described
    reference = (ROOT / "schemas" / "manifest.reference.yml").read_text(encoding="utf-8")
    assert "checkpoint_outcomes:" in reference and "sessions:" in reference
    root = views_project(tmp_path / "new-issue")
    assert co.manifest(root)["schema_version"] == "3.0"

    # The owning doc is in the Owning docs table and states what the issue added.
    readme = _words("docs/README.md")
    assert "`docs/autonomy-and-cost.md`" in readme
    row = [line for line in (ROOT / "docs" / "README.md").read_text(encoding="utf-8").splitlines()
           if "docs/autonomy-and-cost.md" in line and line.lstrip().startswith("|")]
    assert row and "autonomy_cost.py" in row[0] and "issue_usage.py" in row[0], row
    doc = _words("docs/autonomy-and-cost.md")
    for needed in ("checkpoint_outcomes", "checkpoint-approval", "`waited`", "`skipped`",
                   "compass evidence approve --checkpoint", "compass issue checkpoint add",
                   "checkpoint-no-outcome", "judged issue", "not judged",
                   "human judgement", "guardrailed", "autonomous", "autonomy ratio",
                   "complete usage", "cost per change", "usage.sessions", "too-large",
                   "no-window", "1 GiB", "USAGE_READ_LIMIT_BYTES", "IMPACT_SAMPLE_FLOOR",
                   "IMPACT_GROUP_FLOOR", "unmeasurable", "stage ends"):
        assert needed in doc, needed
    assert "--checkpoint" in _words("docs/entry-exit-evaluation.md")
    guardrails = _words("governance/guardrails.md")
    assert "checkpoint-approval" in guardrails and "does not clear" in guardrails

    # The glossary and the vocabulary file define the one new term.
    terms = yaml.safe_load((ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8"))
    assert "checkpoint-outcome" in terms["terms"]
    assert "### checkpoint-outcome" in (ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")

    # The CLI naming test passes with the new verb registered and no exception for it.
    import test_cli_renames as renames
    assert "issue checkpoint add" not in renames.EXCEPTIONS
    assert ("issue", "checkpoint", "add") in list(renames._leaf_paths(renames._load_root()))
    assert renames.convention_problems(renames._load_root()) == []

    # An issue at every workflow state, none holding a new field, reads as it did.
    states = dbi.build_dbi5_project(tmp_path / "states")
    manifests = {p: p.read_bytes() for p in (states / ".compass" / "work").glob("*/manifest.yml")}
    was = captured("states.yml")
    now = state_outputs(states)
    assert list(now) == list(was)
    for name, text in now.items():
        assert text == was[name], name
    assert {p: p.read_bytes() for p in manifests} == manifests
    assert not any("migrate" in text for text in now.values())
    dbi.assert_no_gh_call(states)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--capture":
        _capture(Path(sys.argv[2]), sys.argv[3])
    else:
        sys.exit(__doc__)
