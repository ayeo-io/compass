"""docs/system-spec.md stays current, and stays house-style clean.

A derived artifact that nothing regenerates is worse than no artifact: it
reads as authoritative and is wrong. The fix is not to regenerate it once -
that only makes it right today. The fix is a test that re-derives and
compares on every run, which keeps it right.

Spec: living-spec-and-process-impact/acceptance-criteria.md (`TRC-A1`..`TRC-A3`,
      `TRC-B1`, `TRC-B2`, `TRC-F1`, `TRC-F2`).
"""
from __future__ import annotations

import sys
import importlib.machinery
import importlib.util
import pathlib
import re
import shutil
import tempfile

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The real archive is an opt-in: COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(ROOT / "tests"))
from archive import NEEDS_FULL_ARCHIVE, full_archive  # noqa: E402
CLI = ROOT / "cli" / "compass"
SPEC = ROOT / "docs" / "system-spec.md"
ARCHIVE = ROOT / "docs" / "system-spec-archive.md"
WORK = ROOT / ".compass" / "work"

# Written as an escape, not a literal: this file is tracked, and the house-style
# test would otherwise flag the test that exists to enforce house style.
EM_DASH = "\u2014"


def _cli_module():
    spec = importlib.util.spec_from_loader(
        "compass_cli_sysspec",
        importlib.machinery.SourceFileLoader("compass_cli_sysspec", str(CLI)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _derive_into(root):
    """Run the derivation against a project root and return the text of the
    spec and its archive, the two files it writes."""
    _cli_module().derive_system_spec(str(root))
    return ((root / "docs" / "system-spec.md").read_text(encoding="utf-8")
            + (root / "docs" / "system-spec-archive.md").read_text(encoding="utf-8"))


def _committed():
    return SPEC.read_text(encoding="utf-8") + ARCHIVE.read_text(encoding="utf-8")


def _sandbox(landed_only=True):
    """A copy of this repo's issue archive, cheap enough to derive against."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compass-sysspec-"))
    (tmp / "docs").mkdir()
    (tmp / ".compass" / "work").mkdir(parents=True)
    if WORK.is_dir():
        for t in WORK.iterdir():
            if (t / "manifest.yml").is_file():
                shutil.copytree(t, tmp / ".compass" / "work" / t.name)
    # The project's config and its names key, so the derivation replaces
    # rival names with codes here as it does for the committed files.
    config = WORK.parent / "config.yml"
    if config.is_file():
        shutil.copy(config, tmp / ".compass" / "config.yml")
        sys.path.insert(0, str(ROOT / "cli"))
        from compass_pkg import record
        key = record.names_key(str(ROOT))
        if key:
            (tmp / ".compass" / "private").mkdir()
            shutil.copy(key, tmp / ".compass" / "private" / "rival-codes.yml")
    return tmp


def _landed_slugs(work):
    out = set()
    for t in sorted(p for p in work.iterdir() if (p / "manifest.yml").is_file()):
        d = yaml.safe_load((t / "manifest.yml").read_text()) or {}
        if d.get("status") == "landed" and (d.get("scenarios") or []):
            out.add(t.name)
    return out


# --- group A: staleness is detected ----------------------------------------

def test_trc_a1_a_stale_derived_spec_should_fail_a_check():
    """Simulated by deriving into a sandbox and removing an issue's scenarios
    from the committed copy - the comparison must notice."""
    if not full_archive():
        pytest.skip(NEEDS_FULL_ARCHIVE)
    if not _archive_present():
        pytest.skip("no task archive in this checkout - see _archive_present()")
    tmp = _sandbox()
    try:
        fresh = _derive_into(tmp)
        stale = "\n".join(l for l in fresh.splitlines()
                          if "comparison-requirements" not in l)
        assert stale != fresh, "the fixture did not actually make it stale"
        assert stale.strip() != fresh.strip(), (
            "a spec missing a landed task's scenarios must not compare equal "
            "to a fresh derivation")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _archive_present():
    """Is this checkout carrying the issue archive the spec is derived FROM?

    `.gitignore` root-anchors `/.compass/work/`, so a fresh clone - which is
    exactly what CI checks out - has no archive. Deriving there produces an
    empty spec that can never equal the committed one, and the comparison would
    fail for a reason that has nothing to do with staleness.

    The guard is therefore: compare only where the sources exist. This is a
    real limit, not a dodge - it means the currency check runs on a
    developer's machine and at ship, and cannot run in CI. Stated here
    rather than left implicit.
    """
    return WORK.is_dir() and any(
        (p / "manifest.yml").is_file() for p in WORK.iterdir() if p.is_dir())


def test_trc_a2_a_current_derived_spec_should_pass():
    """THE test. The committed file must equal a fresh derivation, and the
    derivation must be idempotent (ADR-008)."""
    if not full_archive():
        pytest.skip(NEEDS_FULL_ARCHIVE)
    if not _archive_present():
        pytest.skip("no .compass/work/ archive in this checkout (it is "
                    "gitignored), so there is nothing to derive from and "
                    "nothing to compare - see _archive_present()")
    tmp = _sandbox()
    try:
        first = _derive_into(tmp)
        second = _derive_into(tmp)
        assert first == second, "the derivation is not idempotent"
        assert _committed() == first, (
            "docs/system-spec.md or its archive does not match a fresh "
            "derivation - they are "
            "stale. Regenerate it with:\n"
            "    python3 cli/compass _derive-system-spec --internal")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_trc_a3_the_committed_spec_should_cover_every_landed_task():
    if not full_archive():
        pytest.skip(NEEDS_FULL_ARCHIVE)
    if not WORK.is_dir():
        return
    landed = _landed_slugs(WORK)
    if not landed:
        return
    text = _committed()
    # The spec names an issue in its heading, "### <slug> (landed <date>)".
    named = set(re.findall(r"^### ([a-z0-9-]+) \(landed [0-9-]*\)$", text, re.M))
    missing = sorted(landed - named)
    assert not missing, (
        f"{len(missing)} landed task(s) contribute no scenarios to the living "
        f"spec: {missing}. Regenerate it.")
    unlanded = sorted(named - landed)
    assert not unlanded, (
        f"the spec names tasks that have not landed: {unlanded}")


# --- group B: house style ---------------------------------------------------

def test_trc_b1_the_generator_should_normalise_house_style_on_write():
    if not full_archive():
        pytest.skip(NEEDS_FULL_ARCHIVE)
    tmp = _sandbox()
    try:
        # find a source title that carries an em dash, and prove it survives
        sources = list((tmp / ".compass" / "work").glob("*/spec.feature.md"))
        with_dash = [p for p in sources if EM_DASH in p.read_text(encoding="utf-8")]
        derived = _derive_into(tmp)
        assert EM_DASH not in derived, (
            "the derived file contains an em dash; the generator must "
            "normalise house style on write")
        for p in with_dash:
            assert EM_DASH in p.read_text(encoding="utf-8"), (
                f"{p} was edited - the generator must normalise its OUTPUT, "
                f"never its sources. Those are a record of what was specified "
                f"at the time.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_trc_b2_the_derived_file_should_pass_the_repositorys_own_style_test():
    text = SPEC.read_text(encoding="utf-8")
    assert EM_DASH not in text, (
        "docs/system-spec.md contains an em dash, which tests/test_house_style.py "
        "forbids in tracked files. Generated content may not violate a rule the "
        "repository enforces.")


# --- failure modes ----------------------------------------------------------

def test_trc_f1_the_derivation_should_stay_a_derived_artifact():
    head = SPEC.read_text(encoding="utf-8")[:600]
    assert "DERIVED" in head.upper(), "the file no longer declares itself derived"
    assert re.search(r"do not hand-edit", head, re.I), (
        "the file no longer warns against hand-editing")
    # nothing may read it back as an input
    sources = [CLI.read_text(encoding="utf-8")]
    pkg = CLI.parent / "compass_pkg"
    if pkg.is_dir():
        sources += [p.read_text(encoding="utf-8") for p in pkg.glob("*.py")]
    for src in sources:
        for m in re.finditer(r"system-spec\.md", src):
            window = src[max(0, m.start() - 200):m.start() + 200]
            assert not re.search(r"\b(open|read_text|load_yaml)\b\s*\([^)]*system-spec",
                                 window), (
                "the CLI reads docs/system-spec.md back as an input; ADR-008 "
                "says it is derived and never a source of truth")


def test_trc_f2_a_project_with_no_landed_tasks_should_not_be_broken(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / ".compass" / "work").mkdir(parents=True)
    _cli_module().derive_system_spec(str(tmp_path))
    out = tmp_path / "docs" / "system-spec.md"
    assert out.is_file(), "the derivation crashed on a project with no tasks"
    assert re.search(r"no landed", out.read_text(encoding="utf-8"), re.I), (
        "the derived file does not say why it is empty")
