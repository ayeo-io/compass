"""The archive tests read a tracked, scrubbed sample of real issues.

Compass keeps each issue's records out of git, so the tests that read
them skipped in CI and gave a result that depended on which ignored
folders a machine held. `scripts/build-archive-sample.py` copies a fixed
list of real issues, scrubbed, into `tests/fixtures/archive-sample.tar.gz`,
and those tests read it, unpacked by `tests/archive.py`, by default. The full local archive stays an opt-in,
`COMPASS_FULL_ARCHIVE=1`.

Scenario ids: AS-A to AS-F, in the acceptance criteria of the issue
`archive-sample` (GitHub issue #244).
"""
from __future__ import annotations

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
BUILDER = ROOT / "scripts" / "build-archive-sample.py"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
import archive  # noqa: E402
from archive import SHAPE_TESTS  # noqa: E402

SAMPLE = archive.sample_root()

# The seven tests that read the archive's shape, which read the sample by
# default, are listed in tests/archive.py as SHAPE_TESTS, because
# tests/shape_skip_guard.py reads the same list. These two are about the real
# archive, and are opt-in.
REAL_ARCHIVE_TESTS = ("test_system_spec_currency.py",
                      "test_archive_citations_resolve.py")

#: What must never reach a tracked file.
PRIVATE = (
    ("a local home path", re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+/")),
    ("a local temporary path", re.compile(r"/(?:private/)?(?:tmp|var/folders)/[A-Za-z0-9._-]+")),
    ("a private planning path", re.compile(r"docs/(?:analysis|proposals)/")),
    ("an email address", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # Compass never quotes another product in what it commits. The sample
    # needs none of them, so even a name is a sign a quotation came in.
    ("another product", re.compile(r"(?i)R1|R3|R9|R8|tessl")),
)


def _git_user_name():
    """The name git records for the person building the sample, which the
    builder replaces with the GitHub username."""
    found = subprocess.run(["git", "config", "user.name"], cwd=ROOT,
                           capture_output=True, text=True)
    return found.stdout.strip()


def _sample_files():
    return sorted(p for p in SAMPLE.rglob("*") if p.is_file())


def _issues(checkable=False):
    """The sample's issues; with `checkable`, without those that have not
    started or will not finish, which the real archive's sweep leaves out
    too: they have no green run by definition."""
    work = SAMPLE / ".compass" / "work"
    found = []
    for p in sorted(work.iterdir()):
        if not (p / "manifest.yml").is_file():
            continue
        status = (yaml.safe_load((p / "manifest.yml").read_text()) or {}).get("status")
        if checkable and status in ("queued", "parked", "abandoned"):
            continue
        found.append(p.name)
    return found


# --- AS-A: the builder --------------------------------------------------------

def _fake_archive(root, digest_of):
    """One landed issue whose evidence names local paths and is stamped."""
    task = root / ".compass" / "work" / "probe"
    (task / "evidence").mkdir(parents=True)
    record = {"command": "pytest /Users/someone/dev/compass/tests/test_x.py",
              "cwd": "/private/tmp/claude-501/abc/scratchpad",
              "exit_code": 0, "record_id": "abc123"}
    record["content_digest"] = digest_of(record)
    (task / "evidence" / "green-P-1.json").write_text(json.dumps(record))
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "probe", "created": "2026-10-01",
        "status": "landed",
        "evidence": [{"id": "EV-1", "type": "test-run",
                      "path": "evidence/green-P-1.json",
                      "record_id": "abc123",
                      "content_digest": record["content_digest"]}]}))
    docs = root / "docs" / "compass" / "2026-10-01-probe"
    docs.mkdir(parents=True)
    (docs / "notes.md").write_text(
        "From docs/analysis/2026-09-01-spec-b9-thing.md, spec B9, by "
        "Ada Example <someone@example.com>.\n")


def _unpack(tarball, into):
    import tarfile
    with tarfile.open(tarball) as tar:
        tar.extractall(into)
    return into


def _build(source, dest, *slugs):
    return subprocess.run(
        [sys.executable, str(BUILDER), "--source", str(source), "--dest",
         str(dest), "--name", "Ada Example",
         *[a for s in slugs for a in ("--only", s)]],
        capture_output=True, text=True)


def test_as_a_the_builder_scrubs_and_restamps(tmp_path):
    from compass_pkg.red_first import content_digest
    _fake_archive(tmp_path / "src", content_digest)
    result = _build(tmp_path / "src", tmp_path / "out.tar.gz", "probe")
    assert result.returncode == 0, result.stderr
    out = _unpack(tmp_path / "out.tar.gz", tmp_path / "out")
    record = json.loads((out / ".compass" / "work" / "probe" / "evidence"
                         / "green-P-1.json").read_text())
    assert "/Users/" not in record["command"] and "<project>" in record["command"]
    assert record["cwd"] == "<tmp>"
    assert record["content_digest"] == content_digest(record)
    manifest = yaml.safe_load((out / ".compass" / "work" / "probe"
                               / "manifest.yml").read_text())
    assert manifest["evidence"][0]["content_digest"] == record["content_digest"]
    notes = (out / "docs" / "compass" / "2026-10-01-probe" / "notes.md").read_text()
    for gone in ("docs/analysis", "spec B9", "Ada Example", "example.com"):
        assert gone not in notes, gone


def test_as_a_a_record_already_broken_is_not_made_valid(tmp_path):
    """Only the scrub's own changes are restamped: a record whose digest was
    already wrong stays wrong, so the check still catches it."""
    from compass_pkg.red_first import content_digest
    _fake_archive(tmp_path / "src", lambda record: "sha256:" + "0" * 64)
    assert _build(tmp_path / "src", tmp_path / "out.tar.gz", "probe").returncode == 0
    out = _unpack(tmp_path / "out.tar.gz", tmp_path / "out")
    record = json.loads((out / ".compass" / "work" / "probe" / "evidence"
                         / "green-P-1.json").read_text())
    assert record["content_digest"] != content_digest(record)


def test_as_a_the_builder_is_deterministic(tmp_path):
    from compass_pkg.red_first import content_digest
    _fake_archive(tmp_path / "src", content_digest)
    for out in ("one.tar.gz", "two.tar.gz"):
        assert _build(tmp_path / "src", tmp_path / out, "probe").returncode == 0
    one = (tmp_path / "one.tar.gz").read_bytes()
    assert one and one == (tmp_path / "two.tar.gz").read_bytes()


# --- AS-B: every issue in the sample checks ------------------------------------

def test_as_b_the_sample_holds_the_issues_the_tests_need():
    issues = _issues()
    assert len(issues) >= 15
    for needed in ("the-human-review-pack", "publish-the-archive",
                   "compass-self-architecture",
                   "assess-before-edit-under-conflict"):
        assert needed in issues, needed


@pytest.fixture(scope="module")
def rendered_sample():
    """A copy of the sample as an adopter has it after `compass issue migrate --apply
    --i-have-a-copy` and `compass issue render --all` (`archive.checkable_root`). The sample
    holds issues from before the records and the pages existed: `dod-evidence-typed` finds an
    item open until migration writes the records its pages held, and `rendered-blocks-current`
    fails a done issue with no page (ADR-051). The copy sits inside this checkout, as the
    contract copies do, because the check reads the project's mode and asks git about the
    commits an issue names. The shared unpacked sample is never written."""
    return archive.checkable_root()


@pytest.mark.parametrize("slug", _issues(checkable=True))
def test_as_b_every_issue_in_the_sample_passes_compass_check(slug, rendered_sample):
    assert slug != "<no sample>", "tests/fixtures/archive-sample.tar.gz is missing"
    result = subprocess.run([sys.executable, str(CLI), "check", "--issue", slug],
                            cwd=rendered_sample, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-500:]


# --- AS-C: nothing private ------------------------------------------------------

def test_as_c_the_sample_holds_nothing_private():
    from compass_pkg.redact import redact
    files = _sample_files()
    assert files, "tests/fixtures/archive-sample.tar.gz is missing or empty"
    name = _git_user_name()
    found = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for what, pattern in PRIVATE:
            match = pattern.search(text)
            if match:
                found.append(f"{path.relative_to(SAMPLE)}: {what}: {match.group(0)!r}")
        if name and name in text:
            found.append(f"{path.relative_to(SAMPLE)}: the git user name")
        if redact(text, env={}) != text:
            found.append(f"{path.relative_to(SAMPLE)}: a credential shape")
    assert not found, "\n".join(found[:30])


# --- AS-D: the shape tests read the sample ----------------------------------------

def test_as_d_the_shape_tests_read_the_archive_through_one_helper():
    for name in SHAPE_TESTS:
        text = (ROOT / "tests" / name).read_text(encoding="utf-8")
        assert "archive_root" in text, f"{name} does not read the sample"
        direct = re.findall(r'(?:ROOT|REPO_ROOT|FRAMEWORK_ROOT) / "\.compass" / "work"'
                            r'|ROOT / "\.compass/work"', text)
        assert not direct, f"{name} still reads the local archive directly"


def test_as_d_the_shape_tests_run_and_do_not_skip(request, monkeypatch):
    """The shape tests already run in this session. What this proves is that a
    skip in one of them fails the session that skipped it: the guard's two hooks
    are registered here, and every file the list names exists. It starts no
    process; the guard's behaviour is proved by the planted-skip test below."""
    def no_process(*args, **kwargs):
        raise AssertionError("this test must not start a process")

    monkeypatch.setattr(subprocess, "Popen", no_process)
    import shape_skip_guard
    plugins = request.config.pluginmanager.get_plugins()
    for hook in ("pytest_runtest_makereport", "pytest_make_collect_report"):
        impl = getattr(shape_skip_guard, hook)
        assert any(getattr(plugin, hook, None) is impl for plugin in plugins), (
            f"this session did not register the shape-test guard's {hook}")
    assert SHAPE_TESTS and all((ROOT / "tests" / name).is_file() for name in SHAPE_TESTS)


# test_artifact_registry.py is the shape module copied for the planted runs below. All
# seven collect in 0.6 to 0.7 s, so collection time does not separate them. This one has
# the fewest tests (12), light imports, and a test_a1 that reads only a schema file.
GUARDED_COPY = "test_artifact_registry.py"
GUARDED_REAL_TEST = "test_a1_entry_declares_kind_path_status_reason"

#: Three ways a test ends up skipped, each as the lines added to the copy.
PLANTED_SKIPS = {
    "skip-marker": (
        "\n\nimport pytest as _pytest\n\n\n"
        "@_pytest.mark.skip(reason=\"planted skip marker\")\n"
        "def test_planted_skip():\n    pass\n",
        "planted skip marker", "test_planted_skip"),
    "skip-call": (
        "\n\nimport pytest as _pytest\n\n\n"
        "def test_planted_skip():\n    _pytest.skip(\"planted skip call\")\n",
        "planted skip call", "test_planted_skip"),
    "importorskip": (
        "\n\nimport pytest as _pytest\n\n_pytest.importorskip(\"no_such_module_planted\")\n",
        "no_such_module_planted", GUARDED_COPY),
}


def _run_pytest_on_copies(tmp_path, files, parallel, full_archive=False):
    """Run pytest over `files` ({name: text}) in a folder laid out like this
    checkout's (tests/ beside schemas/), loading only the skip guard from here."""
    folder = tmp_path / "tests"
    folder.mkdir(parents=True)
    (tmp_path / "schemas").symlink_to(ROOT / "schemas")
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if k not in ("COMPASS_FULL_ARCHIVE", "PYTEST_ADDOPTS")}
    env["PYTHONPATH"] = str(ROOT / "tests") + os.pathsep + str(ROOT / "cli")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # CI sets this, so xdist is only there when asked for with -p. Setting it here
    # gives the same command on a machine that autoloads xdist.
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    if full_archive:
        env["COMPASS_FULL_ARCHIVE"] = "1"
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", "-p", "no:cacheprovider",
               "-p", "shape_skip_guard", "-q", "-rs",
               "-k", f"test_planted_skip or {GUARDED_REAL_TEST}", str(folder)]
    if parallel:
        command[3:3] = ["-p", "xdist.plugin", "-n", "2"]
    return subprocess.run(command, cwd=tmp_path, capture_output=True, text=True,
                          env=env, timeout=300)


@pytest.mark.parametrize("parallel", [False, True], ids=["alone", "xdist"])
@pytest.mark.parametrize("case", sorted(PLANTED_SKIPS))
def test_as_d_the_skip_guard_fails_on_a_planted_skip(case, parallel, tmp_path):
    original = (ROOT / "tests" / GUARDED_COPY).read_text(encoding="utf-8")
    addition, reason, named = PLANTED_SKIPS[case]
    result = _run_pytest_on_copies(tmp_path, {GUARDED_COPY: original + addition}, parallel)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output[-2000:]
    # The guard's own text, not only the skip report: a run that collects nothing
    # also exits non-zero and prints the skip reason under -rs.
    assert "a shape test must not skip" in output, output[-2000:]
    assert named in output and reason in output, output[-2000:]


@pytest.mark.parametrize("parallel", [False, True], ids=["alone", "xdist"])
def test_as_d_the_skip_guard_leaves_a_clean_copy_and_an_unlisted_module_alone(parallel, tmp_path):
    original = (ROOT / "tests" / GUARDED_COPY).read_text(encoding="utf-8")
    clean = _run_pytest_on_copies(tmp_path / "clean", {GUARDED_COPY: original}, parallel)
    assert clean.returncode == 0, clean.stdout[-2000:] + clean.stderr[-1000:]
    # The same skips in a module the list does not name: they report as skips.
    unlisted = {GUARDED_COPY: original,
                "test_unlisted_one.py": original + PLANTED_SKIPS["skip-marker"][0]
                + PLANTED_SKIPS["skip-call"][0].replace("test_planted_skip", "test_planted_skip_too"),
                "test_unlisted_two.py": original + PLANTED_SKIPS["importorskip"][0]}
    other = _run_pytest_on_copies(tmp_path / "other", unlisted, parallel)
    assert other.returncode == 0, other.stdout[-2000:] + other.stderr[-1000:]
    # With the switch on for a release run, the guard is off.
    planted = {GUARDED_COPY: original + PLANTED_SKIPS["skip-marker"][0]}
    full = _run_pytest_on_copies(tmp_path / "full", planted, parallel, full_archive=True)
    assert full.returncode == 0, full.stdout[-2000:] + full.stderr[-1000:]


def test_as_d_the_switch_points_the_helper_at_the_real_archive(monkeypatch):
    monkeypatch.delenv("COMPASS_FULL_ARCHIVE", raising=False)
    assert archive.archive_root() == SAMPLE
    monkeypatch.setenv("COMPASS_FULL_ARCHIVE", "1")
    assert archive.archive_root() == ROOT


# --- AS-E: the real-archive tests are an opt-in ------------------------------------

def test_as_e_the_real_archive_tests_skip_naming_the_switch():
    env = {k: v for k, v in os.environ.items() if k != "COMPASS_FULL_ARCHIVE"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider",
         *[f"tests/{n}" for n in REAL_ARCHIVE_TESTS]],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=600)
    skipped = [l for l in result.stdout.splitlines() if l.startswith("SKIPPED")]
    assert skipped, result.stdout[-2000:]
    assert all("COMPASS_FULL_ARCHIVE=1" in l for l in skipped), "\n".join(skipped)
    releasing = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert "COMPASS_FULL_ARCHIVE=1" in releasing


# --- AS-F: no test returns early on a stale name -------------------------------------

def test_as_f_no_archive_test_names_an_issue_or_file_that_is_gone():
    arch = (ROOT / "tests" / "test_self_architecture.py").read_text()
    assert '"compass-self-architecture"' in arch
    assert '/ "self-architecture" /' not in arch
    readable = (ROOT / "tests" / "test_readable_specs_and_flow.py").read_text()
    body = readable.split("def test_trc_f1_pre_existing_specs_still_pass")[1].split("\ndef ")[0]
    assert '.glob("*/spec.feature.md")' not in body
    assert '"*/acceptance-criteria.md"' in body
