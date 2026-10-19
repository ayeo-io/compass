"""The retro's autonomy, band, cost and decisions rows (`compass retro --impact`).

The rows read what `checkpoint_outcomes` and `usage` record in each manifest,
count only shipped issues, and say "unmeasurable" with the count and the floor
when a sample is too small. Nothing is written and the exit code is 0.

Every fixture is a set of synthetic manifests under `.compass/work`, so the
tests run without git and without a network; a `gh` on PATH fails a test if
anything calls it.

Scenario ids: ARC-14, ARC-16 to ARC-21 and ARC-27, in the acceptance criteria
of the issue `autonomy-ratio-and-cost`. Each test name starts with its id.
ARC-28, the judged-only rule for the ratio, is declared on the ARC-16 test.

Run as a script, this file writes what the base commit printed for the retro
fixtures:

    python3 tests/test_retro_autonomy_cost.py --capture <cli folder> <out folder>
"""
from __future__ import annotations

import json
import subprocess
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

import test_issue_dependencies as dbi  # noqa: E402

#: The stage weights of every fixture issue: refine skipped and breakdown
#: collapsed, so the route runs six stages.
STAGES = {"assess": "thorough", "define": "thorough", "refine": "skipped",
          "plan": "thorough", "breakdown": "collapsed", "implement": "thorough",
          "verify": "thorough", "ship": "thorough"}


# --- the manifests ------------------------------------------------------------------

def _gates(passed=2, untyped=1):
    """`passed` gates that cite the typed record EV-1, then `untyped` gates that
    pass citing an id the evidence does not hold, and one that has not passed."""
    gates = [{"id": f"verify.g{i}", "status": "pass", "evidence": ["EV-1"]}
             for i in range(passed)]
    gates += [{"id": f"verify.u{i}", "status": "pass", "evidence": ["EV-NONE"]}
              for i in range(untyped)]
    gates.append({"id": "verify.pending", "status": "pending", "evidence": []})
    return gates


def manifest(slug, approach="regular", *, outcomes="absent", checkpoints=(), scenarios=2,
             state="shipped", usage=None, decisions=None, gates=None, **extra):
    """One synthetic manifest.

    `outcomes` is `absent` (no `checkpoint_outcomes` key), `none` (the key, an
    empty list), `skipped` (assess, define, refine and plan skipped) or `waited`
    (every listed checkpoint answered by a person)."""
    m = {"schema_version": "3.0", "issue": slug, "created": "2026-09-01",
         "delivery_approach": approach, "stages": dict(STAGES),
         "checkpoints": list(checkpoints),
         "scenarios": [{"id": f"{slug.upper()}-{i}", "title": "t", "intent": "INT-1"}
                       for i in range(scenarios)],
         "evidence": [{"id": "EV-1", "type": "test-run", "path": "evidence/green.json"}],
         "gates": gates if gates is not None else _gates()}
    if state == "shipped":
        m.update(status="done", close_reason="completed",
                 land_timestamp="2026-09-05T10:00:00Z")
    if outcomes == "none":
        m["checkpoint_outcomes"] = []
    elif outcomes == "skipped":
        m["checkpoint_outcomes"] = [
            {"stage": s, "outcome": "skipped", "by": "spec-author", "at": "2026-09-02T09:00:00Z"}
            for s in ("assess", "define", "refine", "plan")]
    elif outcomes == "waited":
        m["checkpoint_outcomes"] = [
            {"stage": s, "outcome": "waited", "by": "jed72", "at": "2026-09-02T09:00:00Z",
             "evidence": f"EV-CHECKPOINT-{s}-1"} for s in checkpoints]
    if usage is not None:
        m["usage"] = usage
    if decisions:
        m["decisions_taken"] = decisions
    m.update(extra)
    return m


def autonomous(slug, **more):
    """A measurable shipped issue with no waited outcome (it lists no checkpoint)."""
    return manifest(slug, outcomes=more.pop("outcomes", "skipped"), **more)


def waited(slug, **more):
    """A measurable shipped issue whose define and plan a person answered."""
    return manifest(slug, checkpoints=("define", "plan"), outcomes="waited", **more)


def unmeasurable(slug, **more):
    """A shipped issue that lists define and plan and holds no outcome."""
    return manifest(slug, checkpoints=("define", "plan"), outcomes="none", **more)


def in_flight(slug, **more):
    return manifest(slug, state="flight", **more)


# What the bands of each fixture issue are, counted by hand. Six stages run
# (assess, define, plan, implement, `verify`, ship) and `verify` owns passed gates.
# An autonomous issue: no waited outcome, two gates cite a typed record, so
# human judgement 0, guardrailed 2, autonomous 5 (`verify` owns a passed gate).
# A waited issue: define and plan waited, so human judgement 2, guardrailed 2,
# autonomous 3.
AUTONOMOUS_BANDS = {"human_judgement": 0, "guardrailed": 2, "autonomous": 5}
WAITED_BANDS = {"human_judgement": 2, "guardrailed": 2, "autonomous": 3}


def not_judged(slug, **more):
    """A shipped issue from before outcomes were recorded: it lists no checkpoint
    and holds no `checkpoint_outcomes` key."""
    return manifest(slug, checkpoints=(), outcomes="absent", **more)


def ratio_fixture():
    """20 shipped judged issues measurable for autonomy (12 autonomous, 8 with
    waited outcomes), 3 shipped judged issues that list checkpoints with no
    outcome, 4 shipped issues that are not judged, and 2 in flight."""
    issues = {}
    for i in range(12):
        issues[f"auto-{i:02d}"] = autonomous(f"auto-{i:02d}", outcomes="skipped" if i % 2 else "none")
    for i in range(8):
        issues[f"wait-{i:02d}"] = waited(f"wait-{i:02d}")
    for i in range(3):
        issues[f"old-{i}"] = unmeasurable(f"old-{i}")
    for i in range(4):
        issues[f"before-{i}"] = not_judged(f"before-{i}")
    for i in range(2):
        issues[f"flight-{i}"] = in_flight(f"flight-{i}", outcomes="waited",
                                          checkpoints=("define",))
    return issues


# Costs of the cost fixture, in dollars, and each issue's scenario count.
QUICK_COSTS = [round(0.10 + 0.01 * i, 2) for i in range(15)]
REGULAR_COSTS = [1.0, 2.0, 3.0, 4.0, 5.0, 7.0]
FULL_COSTS = [10.0, 20.0, 60.0]
SCENARIOS = {"quick-fix": [1] * 15, "regular": [4, 1, 3, 2, 2, 7], "full": [2, 4, 5]}


def complete_usage(cost):
    """A regular or full issue's usage block with a numeric total."""
    counts = {"requests": 3, "subagent_requests": 1, "input": 10, "output": 20,
              "cache_write": 30, "cache_read": 40}
    return {"sessions": ["sess-1"], "source": "claude-code", "skipped_lines": 0,
            "total": dict(counts, cost_usd=cost),
            "unattributed": dict(counts, cost_usd=0.0),
            "stages": {"define": dict(counts, cost_usd=cost),
                       "implement": {"measured": False, "reason": "no-window"}}}


def quick_fix_usage(cost):
    """A quick fix's block: no total, a cost in each measured stage."""
    half = round(cost / 2, 6)
    counts = {"requests": 1, "subagent_requests": 0, "input": 1, "output": 1,
              "cache_write": 1, "cache_read": 1}
    return {"session": "sess-q", "source": "claude-code", "skipped_lines": 0,
            "stages": {"assess": dict(counts, cost_usd=half),
                       "implement": dict(counts, cost_usd=round(cost - half, 6)),
                       "verify": {"measured": False, "reason": "inside one command"},
                       "ship": {"measured": False, "reason": "inside one command"}}}


def cost_fixture(extra_unmeasured=True):
    """24 shipped issues with complete usage (15 quick fixes, 6 regular, 3 full)
    and 5 shipped regular issues without it, one with a shared stage."""
    issues = {}
    for i, cost in enumerate(QUICK_COSTS):
        issues[f"qf-{i:02d}"] = manifest(f"qf-{i:02d}", "quick-fix",
                                         scenarios=SCENARIOS["quick-fix"][i],
                                         usage=quick_fix_usage(cost))
    for i, cost in enumerate(REGULAR_COSTS):
        issues[f"reg-{i}"] = manifest(f"reg-{i}", "regular", scenarios=SCENARIOS["regular"][i],
                                      usage=complete_usage(cost))
    for i, cost in enumerate(FULL_COSTS):
        issues[f"full-{i}"] = manifest(f"full-{i}", "full", scenarios=SCENARIOS["full"][i],
                                       usage=complete_usage(cost))
    if extra_unmeasured:
        shared = complete_usage(500.0)
        shared["stages"]["define"]["shared"] = True
        shared["total"]["shared"] = True
        for i, usage in enumerate([
                None,
                {"recorded": False, "reason": "no-transcript", "sessions": ["sess-1"]},
                dict(complete_usage(500.0), total=dict(complete_usage(1)["total"], cost_usd=None)),
                shared,
                {"recorded": False, "reason": "too-large", "sessions": ["sess-1"]}]):
            issues[f"gap-{i}"] = manifest(f"gap-{i}", "regular", usage=usage)
    return issues


def decision(ident, status="open", **more):
    return dict({"id": ident, "question": f"Q {ident}?", "resolution": f"A {ident}.",
                 "by": "builder", "stage": "define", "status": status}, **more)


def decisions_fixture():
    """20 issues that hold 30 decisions: 18 confirmed, 5 reopened, 4 open on a
    done issue and 3 open on an issue in flight."""
    issues = {}
    for i in range(20):
        issues[f"dec-{i:02d}"] = manifest(f"dec-{i:02d}", scenarios=1)
    held = []
    held += [("confirmed", decision(f"D-{n}", "confirmed")) for n in range(18)]
    held += [("changed", decision(f"R-{n}", "open", reason="a person reopened it"))
             for n in range(5)]
    held += [("never", decision(f"N-{n}", "open")) for n in range(4)]
    for number, (_, entry) in enumerate(held):
        issues[f"dec-{number % 19:02d}"].setdefault("decisions_taken", []).append(entry)
    # The twentieth issue is in flight and holds the three open decisions.
    flight = in_flight("dec-19", scenarios=1)
    flight["decisions_taken"] = [decision(f"F-{n}", "open") for n in range(3)]
    issues["dec-19"] = flight
    return issues


def floor_fixture():
    """19 shipped issues that are measurable, have complete usage and hold decisions."""
    issues = {}
    for i in range(19):
        issues[f"flo-{i:02d}"] = autonomous(
            f"flo-{i:02d}", outcomes="skipped", usage=complete_usage(1.0 + i),
            decisions=[decision(f"D-{i}", "confirmed")])
    return issues


def nothing_fixture():
    """No shipped issue: one in flight and one abandoned."""
    return {"flight": in_flight("flight"),
            "dropped": manifest("dropped", status="done", close_reason="not-planned")}


FIXTURES_BY_NAME = {"ratio": ratio_fixture, "cost": cost_fixture, "decisions": decisions_fixture,
                    "floors": floor_fixture, "nothing": nothing_fixture}


def write_project(root, issues):
    """The synthetic manifests under `root`, as a project the retro reads."""
    root = Path(root)
    for slug, body in issues.items():
        folder = root / ".compass" / "work" / slug
        folder.mkdir(parents=True)
        (folder / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                             encoding="utf-8")
    (root / ".compass" / "work").mkdir(parents=True, exist_ok=True)
    return root


def retro(root, *args, cli_dir=CLI_DIR):
    """`compass retro <args>` in `root`: no network, the clock not held (the
    retro reads no clock)."""
    return dbi.compass(root, "retro", *args, cli_dir=cli_dir)


# --- writing the base commit's captures ---------------------------------------------

def _capture(cli_dir, out_folder):
    """Write what the code at `cli_dir` prints for `retro --impact` on every fixture
    and for `retro --decisions` on the decisions fixture."""
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    out = {}
    work = Path(tempfile.mkdtemp(prefix="arc-retro-"))
    for name, build in FIXTURES_BY_NAME.items():
        root = write_project(work / name, build())
        done = retro(root, "--impact", cli_dir=cli_dir)
        out[f"impact-{name}"] = {"exit": done.returncode, "stdout": done.stdout,
                                 "stderr": done.stderr}
    root = work / "decisions"
    for flag, key in (((), "decisions"), (("--format", "json"), "decisions-json")):
        done = retro(root, "--decisions", *flag, cli_dir=cli_dir)
        out[key] = {"exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}
    (out_folder / "retro.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


# --- reading the output --------------------------------------------------------------

def impact(root, *args):
    done = retro(root, "--impact", *args)
    assert done.returncode == 0, done
    dbi.assert_no_gh_call(root)
    return done.stdout


def row_lines(text, name):
    """The lines of one new row: its first line and the indented lines that
    continue it."""
    lines = text.splitlines()
    found = [i for i, line in enumerate(lines) if line.startswith(f"  {name} ")]
    assert len(found) == 1, (name, text)
    out = [lines[found[0]]]
    for line in lines[found[0] + 1:]:
        if not line.startswith(" " * 16):
            break
        out.append(line)
    return out


def total(key, n_auto=12, n_waited=8):
    """A band over the fixture's autonomous and waited issues."""
    return n_auto * AUTONOMOUS_BANDS[key] + n_waited * WAITED_BANDS[key]


# --- ARC-16 -------------------------------------------------------------------------

def test_arc_16_autonomy_ratio_and_band_split(tmp_path):
    root = write_project(tmp_path / "p", ratio_fixture())
    text = impact(root)
    assert row_lines(text, "autonomy") == [
        "  autonomy      60.0% of 20 measurable shipped issue(s) ran with no waited "
        "checkpoint; 7 shipped issue(s) not measurable"]
    # Counted by hand over the 12 autonomous and 8 waited issues of the fixture.
    assert (total("human_judgement"), total("guardrailed"), total("autonomous")) == (16, 40, 84)
    assert row_lines(text, "bands") == [
        "  bands         human judgement 16 (checkpoints and human checks), guardrailed 40 "
        "(gates), autonomous 84 (stages); over 20 issue(s)"]
    # An issue in flight is in no count: dropping both changes nothing.
    issues = {k: v for k, v in ratio_fixture().items() if not k.startswith("flight")}
    assert len(issues) == 27
    other = write_project(tmp_path / "q", issues)
    again = impact(other)
    assert row_lines(again, "autonomy") == row_lines(text, "autonomy")
    assert row_lines(again, "bands") == row_lines(text, "bands")


# --- ARC-17 -------------------------------------------------------------------------

def test_arc_17_cost_per_change(tmp_path):
    import statistics
    # The medians, computed here from the fixture's constants.
    quick, regular, full = QUICK_COSTS, REGULAR_COSTS, FULL_COSTS
    per = lambda costs, counts: [c / n for c, n in zip(costs, counts)]  # noqa: E731
    assert statistics.median(quick) == 0.17 and statistics.median(regular) == 3.5
    assert statistics.median(per(regular, SCENARIOS["regular"])) == 1.5
    assert statistics.median(full) == 20.0 and statistics.median(per(full, SCENARIOS["full"])) == 5.0

    root = write_project(tmp_path / "p", cost_fixture())
    lines = row_lines(impact(root), "cost")
    assert lines == [
        "  cost          per delivery approach, over 24 shipped issue(s) with complete usage; "
        "5 shipped issue(s) unmeasured:",
        "                full       n=3  median $20.0000  per scenario $5.0000",
        "                quick-fix  n=15  median $0.1700  per scenario $0.1700",
        "                regular    n=6  median $3.5000  per scenario $1.5000"], lines

    # Take the 5 unmeasured issues away: only the unmeasured count changes.
    clean = write_project(tmp_path / "q", cost_fixture(extra_unmeasured=False))
    again = row_lines(impact(clean), "cost")
    assert again[1:] == lines[1:], again
    assert again[0] == lines[0].replace("5 shipped issue(s) unmeasured",
                                        "0 shipped issue(s) unmeasured"), again

    # A group of two measured issues is shown with its count and no median.
    small = cost_fixture(extra_unmeasured=False)
    del small["full-2"]
    other = write_project(tmp_path / "r", small)
    lines = row_lines(impact(other), "cost")
    assert lines[1] == "                full       n=2  (under 3 - not summarised)", lines
    assert "median" not in lines[1] and "$" not in lines[1]
    assert lines[2:] == again[2:], lines


# --- ARC-18 -------------------------------------------------------------------------

BASE = json.loads((FIXTURES / "retro.json").read_text(encoding="utf-8"))


def printed(done):
    return {"exit": done.returncode, "stdout": done.stdout, "stderr": done.stderr}


def test_arc_18_decisions_confirmed_row(tmp_path):
    root = write_project(tmp_path / "p", decisions_fixture())
    decisions = retro(root, "--decisions", "--format", "json")
    assert decisions.returncode == 0, decisions
    report = json.loads(decisions.stdout)
    assert (report["total"], report["issues"], report["confirmed"], report["changed"],
            report["never_confirmed"], report["open_in_flight"]) == (30, 20, 18, 5, 4, 3)

    done = retro(root, "--impact", "--json")
    assert done.returncode == 0, done
    row = json.loads(done.stdout)["decisions_confirmed"]
    assert row["issues"] == report["issues"] == 20
    assert row["withheld"] is None
    for key in ("confirmed", "changed", "never_confirmed", "total", "open_in_flight"):
        assert row["value"][key] == report[key], key

    # `retro --decisions` prints what the base commit printed for the same fixture.
    assert printed(decisions) == BASE["decisions-json"]
    assert printed(retro(root, "--decisions")) == BASE["decisions"]
    dbi.assert_no_gh_call(root)


# --- ARC-19 -------------------------------------------------------------------------

NEW_ROWS = ("autonomy", "bands", "cost", "decisions")


def tree(root):
    """Every file under the project, with its bytes, apart from the folders the
    test harness itself adds (the `gh` shim and the home folder)."""
    skip = (".test-bin", ".home")
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(Path(root).rglob("*"))
            if p.is_file() and p.relative_to(root).parts[0] not in skip}


def test_arc_19_floors_say_unmeasurable(tmp_path):
    import re
    root = write_project(tmp_path / "floors", floor_fixture())
    text = impact(root)
    expected = {
        "autonomy": "  autonomy      unmeasurable - 19 measurable shipped issue(s); 20 required "
                    "(0 shipped issue(s) not measurable)",
        "bands": "  bands         unmeasurable - 19 measurable shipped issue(s) with bands; "
                 "20 required (0 shipped issue(s) not counted)",
        "cost": "  cost          unmeasurable - 19 shipped issue(s) with complete usage; "
                "20 required (0 shipped issue(s) unmeasured)",
        "decisions": "  decisions     unmeasurable - 19 issue(s) hold decisions; 20 required"}
    for name in NEW_ROWS:
        assert row_lines(text, name) == [expected[name]], name
    new = "\n".join(line for name in NEW_ROWS for line in row_lines(text, name))
    assert not re.search(r"(?<![\d.])0(\.0)?%", text) and "$0" not in text
    assert "median" not in new and "$" not in new

    # No shipped issue: the base commit's text, and nothing more.
    nothing = write_project(tmp_path / "nothing", nothing_fixture())
    assert impact(nothing) == BASE["impact-nothing"]["stdout"]

    # Any fixture: the base commit's lines, unchanged and in order, with the
    # new rows added after the by-approach block; exit 0 and nothing written.
    for name, build in FIXTURES_BY_NAME.items():
        if name == "nothing":
            continue
        project = write_project(tmp_path / f"each-{name}", build())
        before = tree(project)
        done = retro(project, "--impact")
        assert done.returncode == 0 and done.stderr == "", (name, done)
        assert tree(project) == before, name
        base = BASE[f"impact-{name}"]["stdout"].splitlines()
        now = done.stdout.splitlines()
        # The blank line before the closing note is the last blank line of the base.
        cut = max(i for i, line in enumerate(base) if line == "")
        rows = len(now) - len(base) - 1
        assert rows >= 4, (name, now)
        assert now[:cut] == base[:cut], name
        assert now[cut] == "" and now[cut + 1 + rows:] == base[cut:], name
        starts = [line.split()[0] for line in now[cut + 1:cut + 1 + rows]
                  if not line.startswith(" " * 16)]
        assert starts == list(NEW_ROWS), (name, starts)
    dbi.assert_no_gh_call(tmp_path / "floors")


# --- ARC-20 -------------------------------------------------------------------------

ROW_KEYS = {"value", "issues", "not_measurable", "withheld"}


def test_arc_20_rows_in_json(tmp_path):
    from compass_pkg import calibration
    from compass_pkg.core import normalize_spine
    objects = {}
    for name in ("ratio", "cost", "floors"):
        root = write_project(tmp_path / name, FIXTURES_BY_NAME[name]())
        flag, fmt = retro(root, "--impact", "--json"), retro(root, "--impact", "--format", "json")
        assert flag.returncode == 0 and fmt.returncode == 0, (flag, fmt)
        assert flag.stdout == fmt.stdout and flag.stderr == fmt.stderr == "", name
        obj = json.loads(flag.stdout)
        objects[name] = obj
        assert "structured" not in obj and "output" not in obj, name
        for key in ("autonomy_ratio", "band_split", "cost_per_change", "decisions_confirmed"):
            assert set(obj[key]) == ROW_KEYS, (name, key)
            row = obj[key]
            # An unmeasurable value is null with a reason, never 0.
            assert (row["value"] is None) == bool(row["withheld"]), (name, key, row)
        # The numbers the base commit's compute_impact returns are in the object.
        tasks = [(slug, normalize_spine(yaml.safe_load(
            (root / ".compass" / "work" / slug / "manifest.yml").read_text())))
            for slug in sorted(FIXTURES_BY_NAME[name]())]
        expected = calibration._plain(calibration.compute_impact(tasks))
        assert expected and {k: obj[k] for k in expected} == expected, name
        assert obj["by_route"]["regular"]["gates"] == [4], name
        dbi.assert_no_gh_call(root)

    ratio = objects["ratio"]
    assert ratio["autonomy_ratio"]["value"] == 60.0
    assert (ratio["autonomy_ratio"]["issues"], ratio["autonomy_ratio"]["not_measurable"]) == (20, 7)
    assert ratio["band_split"]["value"]["human_judgement"] == 16
    assert ratio["cost_per_change"]["value"] is None and ratio["cost_per_change"]["issues"] == 0
    assert ratio["cost_per_change"]["withheld"] == "0 shipped issue(s) with complete usage; 20 required"
    cost = objects["cost"]["cost_per_change"]
    assert (cost["issues"], cost["not_measurable"]) == (24, 5)
    assert cost["value"]["quick-fix"]["median_usd"] == 0.17
    assert cost["value"]["regular"]["median_per_scenario_usd"] == 1.5
    for row in objects["floors"].values():
        if isinstance(row, dict) and ROW_KEYS <= set(row):
            assert row["value"] is None and "20 required" in row["withheld"], row


# --- ARC-27 -------------------------------------------------------------------------

def test_arc_27_format_help_names_impact(tmp_path):
    """`--format json` gives the --impact rows in JSON (ARC-20), so the help
    for --format names --impact among its readers."""
    tmp_path.mkdir(exist_ok=True)
    done = retro(tmp_path, "--help")
    assert done.returncode == 0, done
    assert "for --friction, --decisions and --impact" in " ".join(done.stdout.split()), done.stdout


# --- ARC-21 -------------------------------------------------------------------------

import test_checkpoint_outcomes as co  # noqa: E402


def landed_fixture_issue(tmp_path, autonomy):
    """The regular fixture issue taken through every hand-off on `autonomy`, with
    every gate passed on typed evidence, and landed by `ship-commit`. Returns
    the project and the issue's folder."""
    root = co.project(tmp_path, compass_yml=dict(co.BALANCED, autonomy=autonomy))
    folder = root / ".compass" / "work" / co.SLUG
    listed = co.manifest(root)["checkpoints"]
    assert listed == (["define", "plan"] if autonomy == "balanced" else [])
    stages = co.manifest(root)["stages"]
    assert [s for s, weight in stages.items() if weight not in ("skipped", "collapsed", "none")] \
        == ["assess", "define", "refine", "plan", "breakdown", "implement", "verify", "ship"]

    co.register(root, "acceptance-criteria")
    skipped = [("assess", "router")]
    if "define" in listed:
        assert co.approve(root, "define").returncode == 0
    else:
        skipped.append(("define", "spec-author"))
    co.refine_done(root)
    skipped.append(("refine", "spec-author"))
    co.register(root, "technical-design")
    if "plan" in listed:
        assert co.approve(root, "plan").returncode == 0
    else:
        skipped.append(("plan", "planner"))
    for stage, agent in skipped:
        done = co.skip(root, stage, agent)
        assert done.returncode == 0, (stage, done)

    body = co.manifest(root)
    # The default regular approach has six `verify` gates; a project that loads
    # its architecture has a seventh, which the fixture adds.
    assert len(body["gates"]) == 6
    body["gates"].append({"id": "verify.architecture", "status": "pending", "evidence": []})
    assert all(g["id"].startswith("verify.") for g in body["gates"])
    (folder / "evidence").mkdir(exist_ok=True)
    (folder / "evidence" / "gate.txt").write_text("passed\n")
    body["evidence"] = body.get("evidence", []) + [
        {"id": "EV-GATE", "type": "command-output", "path": "evidence/gate.txt"}]
    for gate in body["gates"]:
        gate["evidence"] = ["EV-GATE"]
    co.write_manifest(root, body)
    co._ready_to_ship(root)
    done = co.run(root, "ship-commit", "-m", "Ship it", "--issue", co.SLUG)
    assert done.returncode == 0, done
    co.assert_no_gh_call(root)
    return root, folder


def test_arc_21_balanced_and_autonomous_fixture(tmp_path):
    from compass_pkg import autonomy_cost
    from compass_pkg.core import normalize_spine

    def read(root):
        return normalize_spine(co.manifest(root))

    root, folder = landed_fixture_issue(tmp_path / "balanced", "balanced")
    task = read(root)
    assert autonomy_cost.bands(task, str(folder)) == {
        "human_judgement": 2, "guardrailed": 7, "autonomous": 5}
    assert autonomy_cost.measurable(task) and not autonomy_cost.autonomous(task)
    waits = {e["stage"]: e["outcome"] for e in task["checkpoint_outcomes"]}
    assert waits == {"define": "waited", "plan": "waited", "assess": "skipped",
                     "refine": "skipped"}

    root, folder = landed_fixture_issue(tmp_path / "autonomous", "autonomous")
    task = read(root)
    assert autonomy_cost.bands(task, str(folder)) == {
        "human_judgement": 0, "guardrailed": 7, "autonomous": 7}
    assert autonomy_cost.measurable(task) and autonomy_cost.autonomous(task)
    assert {e["outcome"] for e in task["checkpoint_outcomes"]} == {"skipped"}
    assert len(task["checkpoint_outcomes"]) == 4


# --- ARC-14 -------------------------------------------------------------------------

import test_issue_usage as iu  # noqa: E402


def other_issue_in_the_same_session(root):
    """Issue "other" records the first fixture session too, and answers its
    define and plan hand-offs at 10:20 and 10:40 - inside the implement window
    of the issue under test (10:00 to 11:00)."""
    folder = root / ".compass" / "work" / "other"
    folder.mkdir(parents=True)
    body = manifest("other", state="flight", usage={"sessions": [iu.S1]})
    body["checkpoint_outcomes"] = [
        {"stage": "define", "outcome": "skipped", "by": "spec-author", "at": "2026-10-13T10:20:00Z"},
        {"stage": "plan", "outcome": "skipped", "by": "planner", "at": "2026-10-13T10:40:00Z"}]
    (folder / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def test_arc_14_shared_session_is_marked(tmp_path):
    root, home = iu.regular_project(tmp_path / "shared")
    other_issue_in_the_same_session(root)
    done = iu.ship_at(root)
    assert done.returncode == 0, done
    usage = co.manifest(root)["usage"]
    # The three requests of the overlap are counted in implement, and marked.
    assert usage["stages"]["implement"]["shared"] is True, usage["stages"]
    assert usage["stages"]["implement"]["requests"] == 3
    assert usage["total"]["shared"] is True
    assert "shared" not in usage["stages"]["define"] and "shared" not in usage["unattributed"]
    text = impact(root)
    assert row_lines(text, "cost") == [
        "  cost          unmeasurable - 0 shipped issue(s) with complete usage; 20 required "
        "(1 shipped issue(s) unmeasured)"], text
    row = json.loads(impact(root, "--json"))["cost_per_change"]
    assert (row["issues"], row["not_measurable"]) == (0, 1), row

    # The same issue with no other issue in its session has complete usage.
    alone, _ = iu.regular_project(tmp_path / "alone")
    assert iu.ship_at(alone).returncode == 0
    usage = co.manifest(alone)["usage"]
    assert not any(b.get("shared") for b in [usage["total"], usage["unattributed"],
                                             *usage["stages"].values()])
    row = json.loads(impact(alone, "--json"))["cost_per_change"]
    assert (row["issues"], row["not_measurable"]) == (1, 0), row
    co.assert_no_gh_call(root)
    co.assert_no_gh_call(alone)


def test_arc_30_per_scenario_median_below_floor_is_withheld():
    """20 regular issues with complete usage, one with scenarios: the median
    cost shows, the per-scenario median is withheld with its reason."""
    from compass_pkg import autonomy_cost
    issues = [(f"r-{i}", manifest(f"r-{i}", "regular", scenarios=2 if i == 0 else 0,
                                  usage=complete_usage(1.0))) for i in range(20)]
    row = autonomy_cost.cost_row(issues, 20, 3)
    group = row["value"]["regular"]
    assert group["median_usd"] == 1.0, group
    assert group["per_scenario_issues"] == 1 and group["without_scenarios"] == 19, group
    assert group["median_per_scenario_usd"] is None, group
    assert group["per_scenario_withheld"] == "1 issue(s) with scenarios; 3 required", group
    stub = {"withheld": "stub", "not_measurable": 0}
    rows = {k: stub for k in ("autonomy_ratio", "band_split", "decisions_confirmed")}
    lines = autonomy_cost.render_rows({**rows, "cost_per_change": row})
    text = [line for line in lines if line.strip().startswith("regular")]
    assert len(text) == 1 and "per scenario unmeasurable" in text[0], text
    assert "1 issue(s) with scenarios; 3 required" in text[0], text
    ok = [(f"s-{i}", manifest(f"s-{i}", "regular", usage=complete_usage(1.0)))
          for i in range(3)]
    kept = autonomy_cost.cost_row(ok, 3, 3)["value"]["regular"]
    assert kept["median_per_scenario_usd"] == 0.5 and kept["per_scenario_withheld"] is None, kept


def test_retro_impact_reads_each_manifest_once(tmp_path, monkeypatch, capsys):
    """`compass retro --impact` reads each manifest.yml once, not twice, the
    decisions row stays as it was, and `decisions_taken.report` still reads
    the folder when it is given no issues (TRC-001)."""
    import argparse
    from collections import Counter
    from compass_pkg import calibration, core, decisions_taken, manifest_store

    write_project(tmp_path, decisions_fixture())
    work = tmp_path / ".compass" / "work"
    reads = Counter()

    def counted(module, name):
        original = getattr(module, name)

        def wrapper(path, *a, **k):
            reads[Path(path).parent.name] += 1
            return original(path, *a, **k)
        monkeypatch.setattr(module, name, wrapper)

    counted(core, "load_yaml")
    counted(manifest_store, "read")
    monkeypatch.setattr(calibration, "find_compass_dir", lambda: str(tmp_path / ".compass"))

    assert calibration._cmd_calibration_impact(argparse.Namespace(format="json")) == 0
    printed_json = json.loads(capsys.readouterr().out)
    assert dict(reads) == {slug: 1 for slug in decisions_fixture()}, reads
    # The row the unchanged code printed for this fixture.
    assert printed_json["decisions_confirmed"] == {
        "issues": 20, "not_measurable": 0, "withheld": None,
        "value": {"changed": 5, "confirmed": 18, "never_confirmed": 4, "open_in_flight": 3,
                  "share": {"changed": 17, "confirmed": 60, "never_confirmed": 13},
                  "total": 30}}, printed_json["decisions_confirmed"]
    # Alone, with no issues passed, the report reads the folder itself.
    alone = decisions_taken.report(str(work))
    assert (alone["total"], alone["issues"], alone["confirmed"], alone["changed"],
            alone["never_confirmed"], alone["open_in_flight"]) == (30, 20, 18, 5, 4, 3), alone


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--capture":
        _capture(Path(sys.argv[2]), sys.argv[3])
    else:
        sys.exit(__doc__)
