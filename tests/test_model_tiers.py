"""Each seat of an issue runs on a model tier the routing policy computes.

The shipped preset holds two rule sets: `model_tiers`, the default tier of
each seat, and `model_floors`, which raise a seat when the assessment warrants
it. `compass approach evaluate --write` records the result in the manifest's
`models:` key, `compass approach show --model <seat>` resolves a tier to a model name
through the `models` setting, the subtask record keeps the builder's tier and
raises it on the second try, and `compass retro --models` reports review
rounds by tier.

Scenario ids: MT-1 to MT-20, in the acceptance criteria of the issue
`model-tier-from-assessment`.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "tiers"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
STRONG_SEATS = ("assess", "define", "refine", "plan", "breakdown", "review")
JUSTIFY = ["--justify", "risk=r", "--justify", "familiarity=f",
           "--justify", "size=s", "--justify", "goal=g"]


# --- helpers ----------------------------------------------------------------------------

def _preset_config():
    from compass_pkg import catalogue_spec, merge
    preset = ROOT / "governance" / "presets" / "default"
    parts = []
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((preset / f"{name}.yml").read_text(encoding="utf-8"))
        parts.append({k: v for k, v in part.items() if k != "schema"})
    config, _ = merge.apply({}, {"schema": 1, **merge.combine(parts)}, "parent", "default")
    return config


@pytest.fixture(scope="module")
def policy():
    from compass_pkg import obligations
    return obligations.policy_adapter(_preset_config())


def _route(policy, **assessment):
    from compass_pkg.routing import evaluate_route
    readings = {"risk": "contained", "familiarity": "brownfield-mapped",
                "size": "medium", "goal": "delivery", **assessment}
    return evaluate_route(readings, policy)


def _cli(root, *args, check=False):
    proc = subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root),
                               "COMPASS_ISSUE": SLUG})
    if check:
        assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _project(tmp_path, settings="", **assessment):
    """A project with a compass.yml and one issue, evaluated with --write."""
    root = tmp_path / "proj"
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\n" + settings, encoding="utf-8")
    readings = {"risk": "contained", "familiarity": "brownfield-mapped",
                "size": "medium", "goal": "delivery", "labels": [], **assessment}
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "3.0", "issue": SLUG, "created": "2026-10-17",
        "assessment": readings}), encoding="utf-8")
    _cli(root, "approach", "evaluate", "--issue", SLUG, "--write", *JUSTIFY, check=True)
    return root


def _manifest(root):
    return yaml.safe_load((root / ".compass" / "work" / SLUG / "manifest.yml")
                          .read_text(encoding="utf-8"))


def _save_manifest(root, data):
    (root / ".compass" / "work" / SLUG / "manifest.yml").write_text(
        yaml.safe_dump(data), encoding="utf-8")


# --- group A: the tiers the evaluator computes -------------------------------------------

def test_mt_1(tmp_path):
    root = _project(tmp_path)
    models = _manifest(root)["models"]
    for seat in STRONG_SEATS:
        assert models[seat]["tier"] == "strong", seat
    assert models["implement"]["tier"] == "standard"
    assert models["verify"]["tier"] == "fast"
    assert models["ship"]["tier"] == "fast"
    assert all(re.fullmatch(r"RP-(TIER|MODEL)-\d{3}", m["by"]) for m in models.values())
    assert models["implement"]["by"] == "RP-TIER-006"


def test_mt_2(policy):
    result = _route(policy, risk="critical")
    assert result["models"]["implement"]["tier"] == "strong"
    assert result["models"]["implement"]["by"] == "RP-MODEL-001"


def test_mt_3(policy):
    for familiarity in ("greenfield", "brownfield-unmapped"):
        implement = _route(policy, familiarity=familiarity)["models"]["implement"]
        assert implement == {"tier": "strong", "by": "RP-MODEL-002",
                             "not_fired": ["RP-MODEL-001", "RP-MODEL-003"]}, familiarity
    small = _route(policy, familiarity="greenfield", size="small")["models"]["implement"]
    assert small["tier"] == "standard"
    assert "RP-MODEL-002" in small["not_fired"]


def test_mt_4(policy):
    implement = _route(policy, urgency="live-defect")["models"]["implement"]
    assert implement["tier"] == "strong" and implement["by"] == "RP-MODEL-003"


def test_mt_5(policy):
    lowered = copy.deepcopy(policy)
    lowered["model_rules"]["floors"].append(
        {"id": "RP-MODEL-900", "when": {"risk": "contained"}, "seat": "review",
         "tier": "fast", "rationale": "a floor that names a lower tier"})
    review = _route(lowered)["models"]["review"]
    assert review["tier"] == "strong" and review["by"] == "RP-TIER-008"


def test_mt_6(policy):
    result = _route(policy, risk="trivial", size="small")
    assert result["delivery_approach"] == "quick-fix"
    seats = set(result["models"])
    assert not seats & {"refine", "plan", "breakdown"}
    assert {"assess", "define", "implement", "verify", "review", "ship"} <= seats


def test_mt_7(policy):
    from compass_pkg import governance, legacy_views
    from compass_pkg.core import load_yaml
    from compass_pkg.routing import evaluate_route
    assert legacy_views.stale_views(str(ROOT)) == []
    view = load_yaml(str(ROOT / "governance" / "routing-policy.yml"))
    rules = view["model_rules"]
    assert [r["id"] for r in rules["default_tiers"]] == [
        f"RP-TIER-00{n}" for n in range(1, 10)]
    assert [r["id"] for r in rules["floors"]] == ["RP-MODEL-001", "RP-MODEL-002",
                                                  "RP-MODEL-003"]
    errors, _ = governance.legacy_structure(str(ROOT / "governance"))
    assert errors == []
    schema = json.loads((ROOT / "schemas" / "routing-policy.schema.json").read_text())
    assert "model_rules" in schema["properties"]
    for assessment in ({}, {"risk": "critical"}, {"familiarity": "greenfield"},
                       {"urgency": "live-defect"}, {"risk": "trivial", "size": "small"}):
        readings = {"risk": "contained", "familiarity": "brownfield-mapped",
                    "size": "medium", "goal": "delivery", **assessment}
        assert evaluate_route(readings, view)["models"] == \
            evaluate_route(readings, policy)["models"], assessment


def test_mt_20(policy):
    from compass_pkg.core import CompassError
    wrong = copy.deepcopy(policy)
    wrong["model_rules"]["default_tiers"][0]["tier"] = "premium"
    with pytest.raises(CompassError) as caught:
        _route(wrong)
    message = str(caught.value)
    assert "premium" in message
    assert all(t in message for t in ("strong", "standard", "fast"))


# --- group B: the models setting ---------------------------------------------------------

def test_mt_8(tmp_path):
    root = _project(tmp_path)
    printed = {seat: _cli(root, "approach", "show", "--model", seat, check=True).stdout.strip()
               for seat in ("implement", "verify", "plan")}
    assert printed == {"implement": "sonnet", "verify": "haiku", "plan": "inherit"}


def test_mt_9(tmp_path):
    root = _project(tmp_path, settings="models:\n  standard: opus\n")
    assert _cli(root, "approach", "show", "--model", "implement", check=True).stdout.strip() == "opus"
    assert _cli(root, "approach", "show", "--model", "verify", check=True).stdout.strip() == "haiku"
    assert _cli(root, "approach", "show", "--model", "plan", check=True).stdout.strip() == "inherit"


def test_mt_10(tmp_path):
    root = _project(tmp_path)
    with open(root / "compass.yml", "a", encoding="utf-8") as fh:
        fh.write("models:\n  premium: opus\n")
    proc = _cli(root, "approach", "show", "--model", "implement")
    assert proc.returncode != 0
    assert all(t in proc.stderr for t in ("premium", "strong", "standard", "fast")), proc.stderr


def test_mt_11():
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text())
    text = schema["properties"]["models"]["description"]
    assert all(word in text for word in ("strong", "standard", "fast", "inherit"))
    from compass_pkg import catalogue_spec
    assert "models" in catalogue_spec.SETTINGS_KEYS


# --- group C: passing the model and showing it -------------------------------------------

def test_mt_12(tmp_path):
    from compass_pkg import rendered_blocks
    assert "model-tiers" in rendered_blocks.KINDS
    template = (ROOT / "templates" / "delivery-approach.md").read_text(encoding="utf-8")
    assert "<!-- compass:render model-tiers -->" in template
    root = _project(tmp_path)
    docs = root / "docs" / "compass" / f"2026-10-17-{SLUG}"
    docs.mkdir(parents=True)
    rel = f"docs/compass/2026-10-17-{SLUG}/delivery-approach.md"
    (root / rel).write_text("# Delivery approach\n\n<!-- compass:render model-tiers -->\n"
                            "<!-- /compass:render -->\n", encoding="utf-8")
    _cli(root, "issue", "artifact", "set", "delivery-approach", "--status", "draft",
         "--path", rel, check=True)
    _cli(root, "issue", "render", check=True)
    text = (root / rel).read_text(encoding="utf-8")
    block = text.split("<!-- compass:render model-tiers -->")[1].split("<!-- /compass:render -->")[0]
    rows = [line for line in block.splitlines() if line.startswith("| ")]
    seats = [row.split("|")[1].strip() for row in rows[1:]]
    assert seats == ["assess", "define", "refine", "plan", "breakdown", "implement",
                     "verify", "review", "ship"]
    implement = next(r for r in rows if r.startswith("| implement "))
    assert "standard" in implement and "RP-TIER-006" in implement
    assert all(rule in implement for rule in ("RP-MODEL-001", "RP-MODEL-002",
                                              "RP-MODEL-003"))


SEAT_FILES = {
    "approaches/assess-procedure.md": ["assess"],
    "commands/define.md": ["define"],
    "commands/refine.md": ["refine"],
    "commands/plan.md": ["plan"],
    "commands/implement.md": ["implement"],
    "commands/verify.md": ["verify", "review"],
    "commands/breakdown.md": ["breakdown", "implement"],
}


def test_mt_13():
    for rel, seats in SEAT_FILES.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for seat in seats:
            assert f"compass approach show --model {seat}" in text, (rel, seat)
        assert "`model`" in text, rel
    orchestrator = (ROOT / "agents" / "orchestrator.md").read_text(encoding="utf-8")
    assert "compass approach show --model implement" in orchestrator
    assert "compass approach show --model" in (ROOT / "docs" / "multiagent-protocol.md").read_text(
        encoding="utf-8")


def _frontmatter_model(name):
    text = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
    head = text.split("---", 2)[1]
    return yaml.safe_load(head)["model"]


def test_mt_14():
    for name in ("router", "spec-author", "planner", "orchestrator", "reviewer"):
        assert _frontmatter_model(name) == "inherit", name
    assert _frontmatter_model("builder") == "sonnet"
    assert _frontmatter_model("verifier") == "haiku"


def test_mt_15(tmp_path):
    root = _project(tmp_path)
    data = _manifest(root)
    data.pop("models")
    _save_manifest(root, data)
    proc = _cli(root, "approach", "show", "--model", "implement")
    assert proc.returncode == 1
    assert "frontmatter" in proc.stderr
    assert proc.stdout.strip() == ""


# --- group D: the subtask record and retro -----------------------------------------------

@pytest.fixture
def repo(tmp_path):
    root = _project(tmp_path, risk="cross-cutting", size="large")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    brief = root / "docs" / "briefs"
    brief.mkdir(parents=True)
    (brief / "S1.md").write_text("Implement scenario A-1.\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _subtask(root, sid):
    return next(s for s in _manifest(root)["subtasks"] if s["id"] == sid)


def test_mt_16(repo):
    _cli(repo, "issue", "subtask", "add", "S1", "--brief", "docs/briefs/S1.md",
         "--budget", "1000", check=True)
    s1 = _subtask(repo, "S1")
    assert s1["tiers"] == ["standard"]
    assert s1["model"] == "sonnet"
    # A model named alone decides the dispatch, so no tier is recorded for it.
    _cli(repo, "issue", "subtask", "add", "S3", "--brief", "docs/briefs/S1.md",
         "--budget", "1000", "--model", "opus", check=True)
    s3 = _subtask(repo, "S3")
    assert s3["model"] == "opus" and "tiers" not in s3


def test_mt_17(repo):
    _cli(repo, "issue", "subtask", "add", "S1", "--brief", "docs/briefs/S1.md",
         "--budget", "1000", check=True)
    out = _cli(repo, "issue", "subtask", "set", "S1", "--attempt", check=True).stdout
    s1 = _subtask(repo, "S1")
    assert s1["tiers"] == ["standard", "strong"]
    assert s1["model"] == "inherit"
    assert "strong" in out
    _cli(repo, "issue", "subtask", "add", "S2", "--brief", "docs/briefs/S1.md",
         "--budget", "1000", "--tier", "strong", check=True)
    _cli(repo, "issue", "subtask", "set", "S2", "--attempt", check=True)
    assert _subtask(repo, "S2")["tiers"] == ["strong", "strong"]


def _issue(root, slug, risk, subtasks):
    task = root / ".compass" / "work" / slug
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "3.0", "issue": slug, "created": "2026-10-17",
        "assessment": {"risk": risk, "familiarity": "brownfield-mapped",
                       "size": "large", "goal": "delivery"},
        "subtasks": subtasks}), encoding="utf-8")


def _rounds(n):
    return [{"round": i + 1, "verdict": "changes"} for i in range(n)]


def test_mt_18(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass" / "work").mkdir(parents=True)
    _issue(root, "one", "cross-cutting", [
        {"id": "S1", "tiers": ["standard"], "review_rounds": _rounds(1)},
        {"id": "S2", "tiers": ["standard", "strong"], "review_rounds": _rounds(2)}])
    _issue(root, "two", "critical", [
        {"id": "S1", "tiers": ["strong"], "review_rounds": _rounds(1)},
        {"id": "S2", "model": "sonnet", "review_rounds": _rounds(4)}])
    proc = _cli(root, "retro", "--models", check=True)
    lines = proc.stdout.splitlines()
    assert any(re.search(r"standard\s+cross-cutting\s+2\s+1\.5", l) for l in lines), proc.stdout
    assert any(re.search(r"strong\s+critical\s+1\s+1\.0", l) for l in lines), proc.stdout
    assert "3 subtask(s)" in proc.stdout


def test_mt_19(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass" / "work").mkdir(parents=True)
    _issue(root, "one", "contained", [{"id": "S1", "model": "sonnet"}])
    proc = _cli(root, "retro", "--models")
    assert proc.returncode == 0
    assert "no subtask records a tier" in proc.stdout


# --- group E: effort beside the model ----------------------------------------------------

def test_mt_21(policy):
    implement = _route(policy, risk="critical")["models"]["implement"]
    assert implement["effort"] == "high" and implement["effort_by"] == "RP-MODEL-001"
    assert "effort" not in _route(policy)["models"]["implement"]


def test_mt_22(tmp_path):
    root = _project(tmp_path)
    printed = {seat: _cli(root, "approach", "show", "--effort", seat, check=True).stdout.strip()
               for seat in ("implement", "verify", "plan")}
    assert printed == {"implement": "medium", "verify": "low", "plan": "high"}
    critical = _project(tmp_path / "c", risk="critical")
    assert _cli(critical, "approach", "show", "--effort", "implement",
                check=True).stdout.strip() == "high"


def test_mt_23(tmp_path):
    root = _project(tmp_path, settings="models:\n  standard: opus\n")
    proc = _cli(root, "approach", "show", "--effort", "implement")
    assert proc.returncode == 1 and proc.stdout.strip() == ""
    assert "effort" in proc.stderr and "leave" in proc.stderr.lower()
    assert _cli(root, "approach", "show", "--model", "implement",
                check=True).stdout.strip() == "opus"


def test_mt_24(tmp_path):
    root = _project(tmp_path)
    with open(root / "compass.yml", "a", encoding="utf-8") as fh:
        fh.write("models:\n  standard: {model: sonnet, effort: extreme}\n")
    proc = _cli(root, "approach", "show", "--model", "implement")
    assert proc.returncode != 0
    assert all(level in proc.stderr for level in ("low", "medium", "high", "xhigh", "max")), \
        proc.stderr


def _frontmatter(name):
    text = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1])


def test_mt_25():
    for name in ("router", "spec-author", "planner", "orchestrator", "reviewer"):
        assert _frontmatter(name).get("effort") == "high", name
    assert _frontmatter("builder").get("effort") == "medium"
    assert _frontmatter("verifier").get("effort") == "low"


def test_mt_26(repo):
    _cli(repo, "issue", "subtask", "add", "S1", "--brief", "docs/briefs/S1.md",
         "--budget", "1000", check=True)
    assert _subtask(repo, "S1")["effort"] == "medium"
    _cli(repo, "issue", "subtask", "set", "S1", "--attempt", check=True)
    assert _subtask(repo, "S1")["effort"] == "high"


def test_mt_27():
    for rel, seats in SEAT_FILES.items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for seat in seats:
            assert f"compass approach show --effort {seat}" in text, (rel, seat)
        assert "`effort`" in text, rel
    assert "compass approach show --effort implement" in (
        ROOT / "agents" / "orchestrator.md").read_text(encoding="utf-8")
    for rel in ("governance/routing-policy.md", "docs/configuration.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "CLAUDE_CODE_EFFORT_LEVEL" in text and "v2.1.292" in text, rel


def test_mt_28(policy):
    """A layer that lowers the reviewer's tier and drops a floor owes the same at
    every point of the grid, so it classifies as equivalent and needs no waiver."""
    from compass_pkg import classify
    parent = _preset_config()
    child = copy.deepcopy(parent)
    child["rules"]["model_tiers"]["rules"]["RP-TIER-008"]["then"]["tier"] = "fast"
    del child["rules"]["model_floors"]["rules"]["RP-MODEL-001"]
    lowered = classify.classify(parent, child)
    bare = copy.deepcopy(parent)
    for name in ("model_tiers", "model_floors"):
        del bare["rules"][name]
    assert lowered.result == "equivalent", lowered.reason
    # The tier rules' conditions add no point: the grid is the one a
    # configuration without them has.
    assert lowered.grid.points == classify.classify(bare, bare).grid.points


def _git_project(tmp_path, **assessment):
    root = _project(tmp_path, **assessment)
    brief = root / "docs" / "briefs"
    brief.mkdir(parents=True)
    (brief / "S1.md").write_text("Implement scenario A-1.\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def test_mt_29(tmp_path):
    """A subtask records the model the call passed, and `inherit` only when the
    call passed none."""
    strong = _git_project(tmp_path / "strong", risk="critical")
    add = ["issue", "subtask", "add"]
    _cli(strong, *add, "S1", "--brief", "docs/briefs/S1.md", "--budget", "10", check=True)
    _cli(strong, *add, "S2", "--brief", "docs/briefs/S1.md", "--budget", "10",
         "--model", "opus", "--tier", "strong", check=True)
    _cli(strong, *add, "S3", "--brief", "docs/briefs/S1.md", "--budget", "10",
         "--model", "haiku", check=True)
    assert _subtask(strong, "S1")["model"] == "inherit"
    s2 = _subtask(strong, "S2")
    assert s2["model"] == "opus" and s2["tiers"] == ["strong"]
    # A model named without --tier is not counted as the seat's tier.
    s3 = _subtask(strong, "S3")
    assert s3["model"] == "haiku" and "tiers" not in s3
    _cli(strong, "issue", "subtask", "set", "S2", "--attempt", "--model", "opus", check=True)
    s2 = _subtask(strong, "S2")
    assert s2["model"] == "opus" and s2["tiers"] == ["strong", "strong"]
    _cli(strong, "issue", "subtask", "set", "S1", "--attempt", check=True)
    assert _subtask(strong, "S1")["model"] == "inherit"
    # A try the ceiling refuses records no model: the model never ran.
    _cli(strong, "issue", "subtask", "set", "S1", "--attempt", check=True)
    refused = _cli(strong, "issue", "subtask", "set", "S1", "--attempt", "--model", "sonnet")
    assert refused.returncode != 0
    assert _subtask(strong, "S1")["model"] == "inherit"
    standard = _git_project(tmp_path / "standard")
    _cli(standard, *add, "S1", "--brief", "docs/briefs/S1.md", "--budget", "10",
         "--model", "sonnet", "--tier", "standard", check=True)
    assert _subtask(standard, "S1")["tiers"] == ["standard"]


def test_mt_30():
    """A planted process tier in model_rules fails the tier-ladder guard and the
    routing-policy schema."""
    import importlib.util
    import jsonschema
    spec = importlib.util.spec_from_file_location(
        "stream_d", ROOT / "tests" / "cross_cutting" / "test_stream_d_invariants.py")
    stream_d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stream_d)
    from compass_pkg.core import load_yaml
    shipped = load_yaml(str(ROOT / "governance" / "routing-policy.yml"))
    assert stream_d.model_rules_problems(shipped) == []
    schema = json.loads((ROOT / "schemas" / "routing-policy.schema.json").read_text())
    jsonschema.validate(shipped, schema)
    planted = copy.deepcopy(shipped)
    planted["model_rules"]["process_tiers"] = [
        {"tier": "heavy", "gates": ["verify.security"], "stages": {"plan": "thorough"}}]
    assert stream_d.model_rules_problems(planted)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(planted, schema)
    rule = copy.deepcopy(shipped)
    rule["model_rules"]["floors"][0]["gates"] = ["verify.security"]
    assert stream_d.model_rules_problems(rule)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rule, schema)


def test_mt_31(tmp_path):
    """An effort outside the five levels in the manifest is an error, not a
    silent fall-back to the frontmatter."""
    root = _project(tmp_path)
    data = _manifest(root)
    data["models"]["implement"]["effort"] = "turbo"
    _save_manifest(root, data)
    for flag in ("--effort", "--model"):
        proc = _cli(root, "approach", "show", flag, "implement")
        assert proc.returncode == 2, (flag, proc.returncode, proc.stderr)
        assert "turbo" in proc.stderr and "xhigh" in proc.stderr


def test_mt_32(tmp_path):
    """`--model` and `--effort` together are refused."""
    root = _project(tmp_path)
    proc = _cli(root, "approach", "show", "--model", "implement", "--effort", "implement")
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
