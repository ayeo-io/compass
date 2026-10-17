"""Tests for `compass next` - `TRC-C4` through `C10`, `TRC-F6`.

`compass next` is a pure read-only subcommand that reads manifest.yml +
delivery-approach.md and prints exactly one line: the next stage, the
next-uncleared gate, and delivery-approach-aware optional markers.

Design decisions honoured:
  - Pure read-only (TRC-C7): no files in .compass/work/<task>/ are touched.
  - Derives from manifest.yml + delivery-approach.md only (TRC-C8).
  - cost within a multiple of a reference command, and under a ceiling
    (TRC-C10, BF-1: the 200 ms target scaled by measured machine speed).
  - Reports missing assessment when manifest.yml absent (TRC-C9).
  - Reports missing delivery-approach.md when it is absent (TRC-F6).
  - Reports nothing-remains on a completed issue (TRC-C6).
  - Shows collapsed stages on quick-fix delivery approaches (TRC-C5).
  - One line output (TRC-C4).

Output format chosen (devlog entry):
  "<NextPhase> [gate: <next-gate>][ | <phase> collapsed on this route]"
  Examples:
    "Define [gate: verify.correctness]"
    "Plan [gate: verify.correctness] | Define collapsed on this route"
    "all phases complete"   <- when the issue has landed
  This is deliberately plain (no colour escapes) so it is clear in a terminal
  and in logged output.
"""
from __future__ import annotations

import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import pytest
import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_next(cwd: Path, *, task: Optional[str] = None,
             extra_env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Run `compass next` in cwd and return the CompletedProcess."""
    cmd = [sys.executable, str(CLI_PATH), "next"]
    if task:
        cmd.extend(["--issue", task])
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          env=env, timeout=10)


def make_project(tmp_path: Path) -> Path:
    """Minimal Compass project layout."""
    compass = tmp_path / ".compass"
    (compass / "work").mkdir(parents=True)
    (compass / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    # Copy shipped governance
    gov_src = FRAMEWORK_ROOT / "governance"
    gov_dst = tmp_path / "governance"
    gov_dst.mkdir()
    for f in gov_src.glob("*.yml"):
        shutil.copyfile(f, gov_dst / f.name)
    return tmp_path


def make_task(project: Path, slug: str, task_body: dict,
              route_md: Optional[str] = None) -> Path:
    """Create .compass/work/<slug>/manifest.yml and optionally delivery-approach.md."""
    task_dir = project / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)
    task_path = task_dir / "manifest.yml"
    with task_path.open("w") as fh:
        yaml.safe_dump(task_body, fh, sort_keys=False)
    if route_md is not None:
        (task_dir / "delivery-approach.md").write_text(route_md, encoding="utf-8")
    (project / ".compass" / "current-task").write_text(slug, encoding="utf-8")
    return task_dir


STANDARD_ROUTE_MD = """# Route - test-task

## 4. The final route

### 4a. Per-phase weight

| Phase | Weight |
|---|---|
| Frame | Full |
| Specify | Full |
| Clarify | Full |
| Plan | Full |
| Distribute | skipped |
| Build | Full |
| Verify | Full |
| Land | Full |
"""

EXPRESS_ROUTE_MD = """# Route - express-task

## 4. The final route

### 4a. Per-phase weight

| Phase | Weight |
|---|---|
| Frame | Full |
| Specify | light |
| Clarify | collapsed |
| Plan | light |
| Distribute | skipped |
| Build | Full |
| Verify | Full |
| Land | Full |
"""

STANDARD_TASK = {
    "schema_version": "1.0",
    "task": "test-task",
    "created": "2026-05-25",
    "delivery_approach": "standard",
    "assessment": {
        "risk": "contained",
        "familiarity": "greenfield",
        "size": "small",
        "intent": "delivery",
    },
    "stages": {
        "frame": "full",
        "specify": "full",
        "clarify": "full",
        "plan": "full",
        "distribute": "skipped",
        "build": "full",
        "verify": "full",
        "land": "full",
    },
    "gates": [
        {"id": "verify.correctness", "status": "pending", "evidence": []},
        {"id": "verify.governance", "status": "pending", "evidence": []},
        {"id": "verify.traceability", "status": "pending", "evidence": []},
    ],
    "evidence": [],
    "scenarios": [],
    "changed_files": [],
    "claims": [],
    "follow_ups": [],
    "reassessments": [],
}


# ---------------------------------------------------------------------------
# Next reports the upcoming stage and gate in one line (`TRC-C4`)
# ---------------------------------------------------------------------------

class TestNextReportsPhaseAndGate:
    def test_next_outputs_exactly_one_line(self, tmp_path):
        """stdout is exactly one non-empty line (`TRC-C4`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        # An earlier stage completed: mark it so the next stage is the one after it <!-- vocabulary-scan: allow - "clarify" is the old stage-key value this backward-compat fixture passes through unmapped -->
        task_body["stages"] = dict(STANDARD_TASK["stages"])
        # stages with "current" indicated by issue progression field
        # We express progress via a `current_phase` field that `next` reads.
        task_body["current_phase"] = "clarify"
        make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0, f"Unexpected failure:\n{result.stderr}"
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        assert len(lines) == 1, (
            f"Expected exactly one output line, got {len(lines)}:\n{result.stdout}"
        )

    def test_next_names_next_phase(self, tmp_path):
        """The single line names the next stage (`TRC-C4`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "clarify"
        make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0
        assert "Clarify" in result.stdout

    def test_next_names_next_uncleared_gate(self, tmp_path):
        """The single line names the next uncleared gate (`TRC-C4`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "verify"
        make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0
        # Should mention a pending gate
        assert "verify." in result.stdout or "gate" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Next states which stages are optional on this route (`TRC-C5`)
# ---------------------------------------------------------------------------

class TestNextShowsCollapsedPhases:
    def test_express_clarify_marked_collapsed(self, tmp_path):
        """On a quick-fix delivery approach, Refine is marked as collapsed
        (`TRC-C5`)."""
        project = make_project(tmp_path)
        task_body = {
            "schema_version": "1.0",
            "task": "express-task",
            "created": "2026-05-25",
            "delivery_approach": "express",
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
                "intent": "delivery",
            },
            "stages": {
                "frame": "full",
                "specify": "light",
                "clarify": "collapsed",
                "plan": "light",
                "distribute": "skipped",
                "build": "full",
                "verify": "full",
                "land": "full",
            },
            "current_phase": "plan",
            "gates": [
                {"id": "verify.correctness", "status": "pending", "evidence": []},
            ],
            "evidence": [],
            "scenarios": [],
            "changed_files": [],
            "claims": [],
            "follow_ups": [],
            "reassessments": [],
        }
        make_task(project, "express-task", task_body, EXPRESS_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0
        output = result.stdout
        # Must mention that Refine is collapsed
        assert "collapsed" in output.lower() or "Refine" in output

    def test_express_names_plan_as_next_running_phase(self, tmp_path):
        """On a quick-fix delivery approach, once Define is done, Plan is
        named as the actual next stage (`TRC-C5`)."""
        project = make_project(tmp_path)
        task_body = {
            "schema_version": "1.0",
            "task": "express-task",
            "created": "2026-05-25",
            "delivery_approach": "express",
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
                "intent": "delivery",
            },
            "stages": {
                "frame": "full",
                "specify": "light",
                "clarify": "collapsed",
                "plan": "light",
                "distribute": "skipped",
                "build": "full",
                "verify": "full",
                "land": "full",
            },
            "current_phase": "plan",
            "gates": [
                {"id": "verify.correctness", "status": "pending", "evidence": []},
            ],
            "evidence": [],
            "scenarios": [],
            "changed_files": [],
            "claims": [],
            "follow_ups": [],
            "reassessments": [],
        }
        make_task(project, "express-task", task_body, EXPRESS_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0
        assert "Plan" in result.stdout


# ---------------------------------------------------------------------------
# Next on a completed issue reports nothing remains (`TRC-C6`)
# ---------------------------------------------------------------------------

class TestNextCompletedTask:
    def test_completed_task_reports_nothing_remains(self, tmp_path):
        """When the issue has landed, next reports no stage remains (`TRC-C6`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "land"
        task_body["gates"] = [
            {"id": "verify.correctness", "status": "pass", "evidence": ["EV-1"]},
            {"id": "verify.governance", "status": "pass", "evidence": ["EV-2"]},
            {"id": "verify.traceability", "status": "pass", "evidence": ["EV-3"]},
        ]
        task_body["status"] = "landed"
        make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0
        output = result.stdout.lower()
        # Must show completion
        assert ("no phase" in output or "complete" in output
                or "nothing remains" in output or "all phases" in output)

    def test_completed_task_exit_zero(self, tmp_path):
        """Exit code is 0 for a completed issue (`TRC-C6`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "land"
        task_body["status"] = "landed"
        task_body["gates"] = [
            {"id": "verify.correctness", "status": "pass", "evidence": ["EV-1"]},
        ]
        make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        result = run_next(project)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Next writes no new issue state (`TRC-C7`)
# ---------------------------------------------------------------------------

class TestNextIsReadOnly:
    def test_no_file_modified_after_next(self, tmp_path):
        """No file under .compass/work/<task>/ is changed by next (`TRC-C7`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "clarify"
        task_dir = make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        # Capture all mtimes before
        def collect_mtimes(d: Path) -> dict:
            result = {}
            if d.is_dir():
                for p in d.rglob("*"):
                    if p.is_file():
                        result[str(p)] = p.stat().st_mtime
            return result

        before = collect_mtimes(task_dir)

        # Small sleep to make sure any write would change mtime
        time.sleep(0.05)

        proc = run_next(project)
        assert proc.returncode == 0

        after = collect_mtimes(task_dir)

        # Check no new files were created
        new_files = set(after.keys()) - set(before.keys())
        assert not new_files, f"compass next created new files: {new_files}"

        # Check no existing file was changed
        for path, mtime in before.items():
            if path in after:
                assert after[path] == mtime, (
                    f"compass next modified {path} (mtime changed from "
                    f"{mtime} to {after[path]})"
                )

    def test_no_new_file_created_after_next(self, tmp_path):
        """No new file is created under .compass/work/<task>/ by next (`TRC-C7`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "build"
        task_dir = make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        files_before = set(str(p) for p in task_dir.rglob("*") if p.is_file())
        run_next(project)
        files_after = set(str(p) for p in task_dir.rglob("*") if p.is_file())

        new_files = files_after - files_before
        assert not new_files, f"compass next created: {new_files}"


# ---------------------------------------------------------------------------
# Next derives its answer only from manifest.yml and the delivery approach (`TRC-C8`)
# ---------------------------------------------------------------------------

class TestNextDerivesFromTaskYmlOnly:
    def test_next_works_from_scratch_dir(self, tmp_path):
        """Moved manifest.yml + delivery-approach.md to scratch dir gives the
        same answer (`TRC-C8`)."""
        # Build original project
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "plan"
        task_dir = make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        result_original = run_next(project)
        assert result_original.returncode == 0
        original_output = result_original.stdout.strip()

        # Build scratch project with identical manifest.yml + delivery-approach.md
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        scratch_compass = scratch / ".compass"
        (scratch_compass / "work" / "test-task").mkdir(parents=True)
        # Copy governance
        for f in (project / "governance").glob("*.yml"):
            dst_gov = scratch / "governance"
            dst_gov.mkdir(exist_ok=True)
            shutil.copyfile(f, dst_gov / f.name)
        # Copy only manifest.yml and delivery-approach.md
        shutil.copyfile(task_dir / "manifest.yml",
                        scratch_compass / "work" / "test-task" / "manifest.yml")
        shutil.copyfile(task_dir / "delivery-approach.md",
                        scratch_compass / "work" / "test-task" / "delivery-approach.md")
        (scratch_compass / "config.yml").write_text(
            "version: 1.0.0\nmode: enforced\n"
        )
        (scratch_compass / "current-task").write_text("test-task")

        result_scratch = run_next(scratch)
        assert result_scratch.returncode == 0
        scratch_output = result_scratch.stdout.strip()

        assert original_output == scratch_output, (
            f"compass next gave different output from scratch dir.\n"
            f"  original : {original_output!r}\n"
            f"  scratch  : {scratch_output!r}\n"
            "The command must derive its answer from manifest.yml + route.md only."
        )


# ---------------------------------------------------------------------------
# Next on an issue with no assessment reports that assessment is needed (`TRC-C9`)
# ---------------------------------------------------------------------------

class TestNextNoFrame:
    def test_no_task_yml_reports_frame_needed(self, tmp_path):
        """When manifest.yml is absent, next reports assess has not run (`TRC-C9`)."""
        project = make_project(tmp_path)
        # Create issue directory but NO manifest.yml
        task_dir = project / ".compass" / "work" / "unframed-task"
        task_dir.mkdir(parents=True)
        (project / ".compass" / "current-task").write_text("unframed-task")

        result = run_next(project)
        assert result.returncode != 0, (
            "compass next should exit non-zero when Frame has not run"
        )
        combined = result.stdout + result.stderr
        assert "frame" in combined.lower() or "manifest.yml" in combined.lower(), (
            "compass next should mention Frame or manifest.yml when it is absent"
        )

    def test_no_task_yml_exit_nonzero(self, tmp_path):
        """Exit code is non-zero when manifest.yml absent (`TRC-C9`)."""
        project = make_project(tmp_path)
        task_dir = project / ".compass" / "work" / "no-frame"
        task_dir.mkdir(parents=True)
        (project / ".compass" / "current-task").write_text("no-frame")

        result = run_next(project)
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# The latency measurement resists runner noise and still fails a slowdown
# ---------------------------------------------------------------------------

def measure_interleaved(names, rounds, run):
    """Median time in ms of each named command, over `rounds` interleaved
    rounds.

    Each round runs every command once, rotating which goes first. A load
    burst on a shared runner then slows all of them alike rather than the one
    whose block it lands in, and no command is always the first call after a
    pause. One warm-up round runs first and is discarded, because the first
    calls pay for a cold file cache.

    `run(name, first_in_round)` runs one command and returns seconds.
    """
    times = {name: [] for name in names}
    for i in range(rounds + 1):
        shift = i % len(names)
        order = names[shift:] + names[:shift]
        for position, name in enumerate(order):
            elapsed = run(name, position == 0)
            if i:
                times[name].append(elapsed)
    return {name: statistics.median(t) * 1000 for name, t in times.items()}


def latency_ratio(medians):
    """The cost of `compass next` above bare Python start-up, as a multiple of
    the reference command's cost above the same start-up."""
    marginal = medians["next"] - medians["baseline"]
    reference = medians["reference"] - medians["baseline"]
    return marginal / max(reference, 1.0)


def judge_latency(measure, *, limit, borderline, ratio_of=lambda m: m):
    """Pass, or fail, a latency measurement, measuring once more only when
    the first ratio is borderline.

    A borderline ratio is at the limit or above but below `limit +
    borderline`. Runner noise moves the ratio by a few hundredths, so a
    second measurement settles it. A real slowdown fails both. A ratio past
    the borderline band fails at once. Returns the verdict and every
    measurement taken.
    """
    measured = [measure()]
    ratio = ratio_of(measured[0])
    if ratio < limit:
        return "pass", measured
    if ratio >= limit + borderline:
        return "fail", measured
    measured.append(measure())
    return ("pass" if ratio_of(measured[-1]) < limit else "fail"), measured


class FakeRunner:
    """Stands in for running a command: each call costs the command's fixed
    time, scaled by a load factor that depends on when the call happens."""

    def __init__(self, costs_ms, load=lambda call: 1.0, first_in_round_ms=0.0):
        self.costs_ms = costs_ms
        self.load = load
        self.first_in_round_ms = first_in_round_ms
        self.calls = 0
        self.order = []

    def __call__(self, name, first_in_round):
        cost = self.costs_ms[name] * self.load(self.calls)
        if first_in_round:
            cost += self.first_in_round_ms
        self.calls += 1
        self.order.append(name)
        return cost / 1000


class TestLatencyMeasurement:
    COSTS = {"baseline": 30.0, "reference": 90.0, "next": 120.0}
    TRUE_RATIO = (120.0 - 30.0) / (90.0 - 30.0)   # 1.5

    def test_a_load_burst_does_not_move_the_ratio(self):
        # The burst slows every call in the middle 40% of the measurement.
        # Measured in blocks, it would land on one command and move the ratio.
        rounds = 20
        total_calls = (rounds + 1) * 3
        burst = range(int(total_calls * 0.3), int(total_calls * 0.7))
        run = FakeRunner(self.COSTS, load=lambda c: 1.6 if c in burst else 1.0)
        medians = measure_interleaved(list(self.COSTS), rounds, run)
        ratio = latency_ratio(medians)
        assert abs(ratio - self.TRUE_RATIO) / self.TRUE_RATIO < 0.02, medians

    def test_the_first_call_in_a_round_does_not_favour_one_command(self):
        run = FakeRunner(self.COSTS, first_in_round_ms=25.0)
        medians = measure_interleaved(list(self.COSTS), 21, run)
        assert abs(latency_ratio(medians) - self.TRUE_RATIO) < 0.02, medians

    def test_the_rounds_are_interleaved_and_the_warm_up_is_discarded(self):
        run = FakeRunner(self.COSTS)
        measure_interleaved(list(self.COSTS), 4, run)
        assert run.calls == 15
        # Each round runs every command once, in a rotated order.
        rounds = [run.order[i:i + 3] for i in range(0, 15, 3)]
        assert all(sorted(r) == sorted(self.COSTS) for r in rounds)
        assert len({tuple(r) for r in rounds}) == 3

    def test_a_planted_delay_raises_the_ratio_past_the_limit(self):
        slow = dict(self.COSTS, next=self.COSTS["next"] + 50.0)
        ratio = latency_ratio(measure_interleaved(list(slow), 20, FakeRunner(slow)))
        assert ratio >= TestNextLatency.MAX_RATIO

    @pytest.mark.parametrize("ratios, verdict, attempts", [
        ([1.60], "pass", 1),            # within the limit: measured once
        ([1.85, 1.70], "pass", 2),      # borderline, then within: noise
        ([1.85, 1.83], "fail", 2),      # borderline twice: a real slowdown
        ([2.30], "fail", 1),            # well past the limit: no second chance
    ])
    def test_only_a_borderline_ratio_is_measured_again(self, ratios, verdict, attempts):
        results = iter(ratios)
        got, measured = judge_latency(lambda: next(results), limit=1.8, borderline=0.2)
        assert (got, len(measured)) == (verdict, attempts)


# ---------------------------------------------------------------------------
# Next stays within its latency budget, relative to a reference command (`TRC-C10`)
# ---------------------------------------------------------------------------

class TestNextLatency:
    # `compass next` mostly loads modules, so its cost scales with how fast the
    # machine loads and runs Python. A reference command that loads the same
    # kind of modules and runs a small fixed loop measures that speed in the
    # same run. Subtracting bare `python -c pass` does not: on a GitHub runner
    # `compass next` costs about 207ms above start-up against about 95ms here,
    # so a fixed 200ms limit failed on slow runners for a reason it does not
    # care about.
    #
    # The three commands run in interleaved rounds (`measure_interleaved`), so
    # a load burst on a shared runner slows all three alike. A ratio from the
    # limit up to the limit plus BORDERLINE is measured once more
    # (`judge_latency`), and fails only if the second ratio is also at the
    # limit or above.
    #
    # A fixed 50ms delay adds about 0.4 to the ratio on a GitHub runner: it
    # failed there at 1.92 when the ratio was 1.53. So the limit stays at 1.8.
    # By 16 October 2026 the ratio on GitHub runners was 1.72 to 1.78, because
    # the CLI loads every command module at start-up and has gained modules.
    # The same delay on top of that is past the borderline band, so it fails
    # without a second measurement. The absolute ceiling stops a large
    # regression on a fast machine.
    MAX_RATIO = 1.8
    BORDERLINE = 0.2
    ROUNDS = 20
    CEILING_MS = 400
    REFERENCE = (
        "import sys; sys.path.insert(0, {vendor!r})\n"
        "import argparse, datetime, hashlib, json, re, shlex, subprocess, "
        "tempfile, fnmatch, shutil, glob, inspect, dataclasses, typing, uuid, "
        "urllib.request, http.client, yaml\n"
        "yaml.safe_load('a: [1, 2, {{b: c}}]\\n' * 200)\n"
        "for i in range(200000):\n"
        "    x = i * i % 7\n"
    )

    @pytest.mark.serial
    def test_next_latency_relative_to_reference(self, tmp_path, request):
        """Median cost of `compass next` is within a multiple of a reference
        command's cost, and under an absolute ceiling (`TRC-C10`, NLB-1).

        The original BF-1 target was 200ms. That figure holds on a development
        machine; this test now scales it by measured runner speed.
        """
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "build"
        make_task(project, "test-task", task_body, STANDARD_ROUTE_MD)

        vendor = str(Path(CLI_PATH).parent / "vendor")
        commands = {
            "baseline": [sys.executable, "-c", "pass"],
            "reference": [sys.executable, "-c",
                          self.REFERENCE.format(vendor=vendor)],
            "next": [sys.executable, str(CLI_PATH), "next"],
        }

        def run(name, first_in_round):
            t0 = time.monotonic()
            subprocess.run(commands[name], cwd=str(project),
                           capture_output=True, timeout=15)
            return time.monotonic() - t0

        # pytest hides captured output unless a test fails. Suspending the
        # capture while printing puts the figures in the CI log on a pass.
        capture = request.config.pluginmanager.getplugin("capturemanager")

        def measure():
            medians = measure_interleaved(list(commands), self.ROUNDS, run)
            ratio = latency_ratio(medians)
            marginal_ms = medians["next"] - medians["baseline"]
            reference_ms = medians["reference"] - medians["baseline"]
            line = (
                f"compass next latency: marginal {marginal_ms:.1f}ms "
                f"(total {medians['next']:.1f}ms, "
                f"bare python {medians['baseline']:.1f}ms), "
                f"reference {reference_ms:.1f}ms, ratio {ratio:.2f} "
                f"(limit {self.MAX_RATIO}, borderline below "
                f"{self.MAX_RATIO + self.BORDERLINE:.1f}), "
                f"ceiling {self.CEILING_MS}ms"
            )
            with capture.global_and_fixture_disabled():
                print("\n" + line, flush=True)
            return {"ratio": ratio, "marginal_ms": marginal_ms, "line": line}

        verdict, measured = judge_latency(
            measure, limit=self.MAX_RATIO, borderline=self.BORDERLINE,
            ratio_of=lambda m: m["ratio"],
        )
        lines = "; then ".join(m["line"] for m in measured)
        last = measured[-1]

        assert last["marginal_ms"] < self.CEILING_MS, (
            f"{lines} - exceeds the absolute ceiling (TRC-C10 / BF-1)."
        )
        assert verdict == "pass", (
            f"{lines} - compass next is slow relative to the reference "
            "command (TRC-C10 / BF-1). Investigate the performance path."
        )


# ---------------------------------------------------------------------------
# Next on an issue whose delivery-approach.md is missing reports the artifact (`TRC-F6`)
# ---------------------------------------------------------------------------

class TestNextMissingRouteMd:
    def test_missing_route_md_reported(self, tmp_path):
        """When delivery-approach.md is absent, next names the missing artifact (`TRC-F6`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        task_body["current_phase"] = "plan"
        # make_task with route_md=None leaves delivery-approach.md absent
        make_task(project, "test-task", task_body, route_md=None)

        result = run_next(project)
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "delivery-approach.md" in combined, (
            "compass next must name route.md as the missing artifact. "
            f"Got: {combined!r}"
        )

    def test_missing_route_md_exit_nonzero(self, tmp_path):
        """Exit code is non-zero when delivery-approach.md is absent (`TRC-F6`)."""
        project = make_project(tmp_path)
        task_body = dict(STANDARD_TASK)
        make_task(project, "test-task", task_body, route_md=None)

        result = run_next(project)
        assert result.returncode != 0
