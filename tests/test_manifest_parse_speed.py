"""Reading many manifests fast, without changing what any command reads.

Scenario ids `TRC-A1` to `TRC-F3` (issue `manifest-parse-speed`). Each test
name starts with its scenario id.

- Group A pins what callers of `core.load_yaml` and `core.load_manifest` rely
  on. It is green before the change and must stay green after it.
- Groups B to F guard the parse cache that `compass flow` reads through.
- A few tests at the end check the test support itself: the fixed clock, the
  runner for the code before the change, and the callers of the cache.

The tests that compare with the code before the change run only when
`COMPASS_BEFORE_COMMIT` names a commit (the check stage sets it to the merge
base of the branch and main). Unset, they skip. Set to a commit that cannot be read,
they fail.
"""
from __future__ import annotations

import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLI_DIR = ROOT / "cli"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CLI_DIR))
import compass_pkg  # noqa: E402,F401  (puts the bundled PyYAML first)
import yaml  # noqa: E402
from compass_pkg import core, generation  # noqa: E402
from compass_pkg.core import CompassError  # noqa: E402

import archive  # noqa: E402
import parse_speed_support as support  # noqa: E402
from parse_speed_support import exact_difference, parity_failures  # noqa: E402

UTC = datetime.timezone.utc

#: Which readers the group A tests run against. `core` is `core.load_yaml`.
READER_KINDS = ["core", "cache"]


class Reader:
    """A way to read a manifest, with files in a project's `.compass/work`."""

    def __init__(self, kind, project):
        self.kind = kind
        self.project = Path(project)
        self.work = self.project / ".compass" / "work"
        self.work.mkdir(parents=True, exist_ok=True)
        self._cache = None
        if kind == "cache":
            from compass_pkg import parse_cache
            self._cache = parse_cache.for_work_root(str(self.work))

    def path(self, issue="probe", name="manifest.yml"):
        folder = self.work / issue
        folder.mkdir(parents=True, exist_ok=True)
        return folder / name

    def write(self, issue, content, name="manifest.yml"):
        path = self.path(issue, name)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def read(self, path):
        if self._cache is not None:
            return self._cache.load_yaml(str(path))
        return core.load_yaml(str(path))

    def read_manifest(self, task_dir):
        """Read an issue folder as `load_manifest` does (for the cache, the
        cache's read followed by the same key normalisation)."""
        if self._cache is None:
            return core.load_manifest(str(task_dir))[0]
        return core.normalize_spine(self._cache.load_yaml(core.manifest_path(str(task_dir))))


@pytest.fixture(params=READER_KINDS)
def reader(request, tmp_path):
    return Reader(request.param, tmp_path / "proj")


GATE_MANIFEST = ("schema_version: '2.0'\nissue: probe\ngates:\n"
                 "- id: verify.correctness\n  status: pending\n  evidence: []\n")


def _walk_containers(value, found):
    if isinstance(value, (dict, list)):
        found.append(value)
        for item in (value.values() if isinstance(value, dict) else value):
            _walk_containers(item, found)
    return found


# --- group A: what callers rely on today -------------------------------------

def test_trc_a1_second_read_sees_write(reader):
    path = reader.write("probe", "status: in-progress\n")
    assert reader.read(path)["status"] == "in-progress"
    path.write_text("status: in-review\n", encoding="utf-8")
    assert reader.read(path)["status"] == "in-review"


def test_trc_a2_same_size_and_mtime_replace_is_seen(reader, tmp_path):
    path = reader.write("probe", "status: ready-one\nkeep: same\n")
    reader.read(path)
    before = os.stat(path)
    second = tmp_path / "second.yml"
    second.write_bytes(b"status: ready-two\nkeep: same\n")
    os.utime(second, ns=(before.st_atime_ns, before.st_mtime_ns))
    shutil.copy2(second, path)                                  # as `cp -p` leaves it
    after = os.stat(path)
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert exact_difference(reader.read(path), yaml.safe_load(second.read_bytes())) is None
    assert reader.read(path)["status"] == "ready-two"


def test_trc_a3_new_object_each_read(reader):
    path = reader.write("probe", GATE_MANIFEST)
    task_dir = path.parent
    first = reader.read_manifest(task_dir)
    first["gates"][0]["status"] = "pass"
    second = reader.read_manifest(task_dir)
    assert second["gates"][0]["status"] == "pending"
    first_ids = {id(c) for c in _walk_containers(first, [])}
    assert not [c for c in _walk_containers(second, []) if id(c) in first_ids]


def test_trc_a4_read_after_save_same_process(reader):
    path = reader.write("probe", "schema_version: '2.0'\nissue: probe\nevidence:\n"
                                 "- id: EV-1\n  type: test-run\n  path: evidence/a.txt\n")
    task_dir = path.parent
    task = reader.read_manifest(task_dir)
    assert task["evidence"][0]["id"] == "EV-1"
    task["evidence"][0]["id"] = "EV-2"
    core.save_manifest(task, str(path))
    assert reader.read_manifest(task_dir)["evidence"][0]["id"] == "EV-2"


SCALARS = [
    ("2026-10-09", datetime.date(2026, 10, 9)),
    ("2026-06-04T09:10:00Z", datetime.datetime(2026, 6, 4, 9, 10, tzinfo=UTC)),
    ("'2026-10-09'", "2026-10-09"),
    ("1", 1),
    ("010", 8),
    ("1:30", 90),
    ("1.5", 1.5),
    ("1e3", "1e3"),
    ("yes", True),
    ("~", None),
    ("", None),
]


@pytest.mark.parametrize("text,expected", SCALARS, ids=[s[0] or "nothing" for s in SCALARS])
def test_trc_a5_scalar_types(reader, text, expected):
    path = reader.write("probe", f"value: {text}\n")
    result = reader.read(path)
    assert result["value"] == expected and type(result["value"]) is type(expected)
    if isinstance(expected, datetime.datetime):
        assert result["value"].tzinfo is UTC
    assert exact_difference(result, support.safe_load_file(path)) is None


def test_trc_a6_alias_is_one_object(reader):
    path = reader.write("probe", "assessment:\n  labels: &id001\n  - performance\n"
                                 "evaluated_assessment:\n  labels: *id001\n")
    result = reader.read(path)
    assert result["assessment"]["labels"] is result["evaluated_assessment"]["labels"]


EMPTY = [b"", b"# only a comment\n", b"~\n", b"null\n", b"false\n", b"0\n", b"[]\n"]


@pytest.mark.parametrize("content", EMPTY, ids=[repr(c) for c in EMPTY])
def test_trc_a7_empty_or_falsy_is_empty_mapping(reader, content):
    result = reader.read(reader.write("probe", content))
    assert result == {} and type(result) is dict


def test_trc_a8_list_document(reader):
    assert reader.read(reader.write("probe", "- a\n- b\n")) == ["a", "b"]


def test_trc_a9_malformed_refused(reader):
    path = reader.write("probe", "status: [unclosed\n")
    with pytest.raises(CompassError) as caught:
        reader.read(path)
    assert str(caught.value).startswith(f"invalid YAML in {path}:")


@pytest.mark.parametrize("situation", ["no file", "a directory", "no manifest in folder"])
def test_trc_a10_missing_path_refused(reader, tmp_path, situation):
    if situation == "no manifest in folder":
        if reader.kind != "core":
            pytest.skip("load_manifest reads through core.load_yaml only")
        folder = tmp_path / "empty-issue"
        folder.mkdir()
        with pytest.raises(CompassError) as caught:
            core.load_manifest(str(folder))
        assert f"no manifest.yml in {folder}" in str(caught.value)
        return
    path = reader.path("probe", "missing.yml")
    if situation == "a directory":
        path.mkdir()
    with pytest.raises(CompassError) as caught:
        reader.read(path)
    assert f"not found: {path}" in str(caught.value)


def test_trc_a11_duplicate_key_last_wins(reader):
    result = reader.read(reader.write("probe", "status: in-progress\nstatus: in-review\n"))
    assert result == {"status": "in-review"}


def test_trc_a12_python_tag_refused(reader, tmp_path):
    marker = tmp_path / "marker-a12"
    path = reader.write("probe", f"x: !!python/object/apply:os.system ['touch {marker}']\n")
    with pytest.raises(CompassError) as caught:
        reader.read(path)
    assert str(caught.value).startswith(f"invalid YAML in {path}:")
    assert not marker.exists()


def test_trc_a13_not_utf8_raises(reader):
    path = reader.write("probe", b"status: caf\xe9\n")
    with pytest.raises(UnicodeDecodeError):
        reader.read(path)


@pytest.mark.parametrize("entry_point", ["write_proposal", "commit"])
def test_trc_a14_locked_reread_refuses_change(tmp_path, entry_point):
    task_dir = tmp_path / ".compass" / "work" / "probe"
    task_dir.mkdir(parents=True)
    path = task_dir / "manifest.yml"
    path.write_text("schema_version: '2.0'\nissue: probe\ngeneration: 1\n", encoding="utf-8")
    manifest, _ = core.load_manifest(str(task_dir))
    before = os.stat(path)
    other = ("import os, sys; p = sys.argv[1]; ns = int(sys.argv[2]); "
             "open(p, 'w').write('schema_version: \\'2.0\\'\\nissue: probe\\ngeneration: 2\\n'); "
             "os.utime(p, ns=(ns, ns))")
    subprocess.run([sys.executable, "-c", other, str(path), str(before.st_mtime_ns)], check=True)
    after = os.stat(path)
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    written = path.read_bytes()
    with pytest.raises(CompassError) as caught:
        if entry_point == "write_proposal":
            generation.write_proposal(str(task_dir), manifest, {"checks": {}})
        else:
            generation.commit(str(task_dir), None, manifest)
    assert "changed since it was read" in str(caught.value)
    assert path.read_bytes() == written


def test_trc_a15_retired_name_and_keys(reader):
    if reader.kind != "core":
        pytest.skip("load_manifest reads through core.load_yaml only")
    retired = core.MANIFEST_NAMES[1]
    path = reader.write("probe", "schema_version: '1.0'\ntask: probe\nroute: standard\n",
                        name=retired)
    task, found = core.load_manifest(str(path.parent))
    assert found == str(path)
    assert task["delivery_approach"] == "regular" and "route" not in task


def test_trc_a16_unknown_schema_major_refused(reader):
    if reader.kind != "core":
        pytest.skip("load_manifest reads through core.load_yaml only")
    path = reader.write("probe", "schema_version: '9.0'\nissue: probe\n")
    with pytest.raises(CompassError) as caught:
        core.load_manifest(str(path.parent))
    assert "schema_version is '9.0'" in str(caught.value)


def test_trc_a17_symlink_reads_target(reader, tmp_path):
    target = tmp_path / "target.yml"
    target.write_text("status: in-progress\n", encoding="utf-8")
    link = reader.path("probe")
    os.symlink(target, link)
    assert reader.read(link)["status"] == "in-progress"
    target.write_text("status: in-review\n", encoding="utf-8")
    assert reader.read(link)["status"] == "in-review"


# --- group B: speed ---------------------------------------------------------

@pytest.mark.serial
def test_trc_b1_flow_within_two_seconds_on_this_repository(tmp_path):
    if not archive.full_archive():
        pytest.skip(archive.NEEDS_FULL_ARCHIVE)
    work = ROOT / ".compass" / "work"
    manifests = list(work.glob("*/manifest.yml"))
    assert len(manifests) >= 484, f"only {len(manifests)} manifests"
    times = [support.time_flow(CLI_DIR, work, ROOT, tmp_path) for _ in range(3)]
    median = sorted(times)[1]
    assert median <= 2.0, (f"compass flow took {times} s over {len(manifests)} manifests; "
                           f"median {median:.2f} s is over 2.0 s")


@pytest.mark.serial
def test_trc_b2_flow_faster_than_one_parse_on_sample(tmp_path):
    project = tmp_path / "proj"
    work = support.build_project(project, archive.sample_root(), 484)
    parse = support.median_of(3, lambda: support.parse_time(CLI_DIR, work, tmp_path))
    flow = support.median_of(3, lambda: support.time_flow(CLI_DIR, work, project, tmp_path))
    assert flow <= 0.85 * parse, (f"compass flow took {flow:.2f} s (median of three); "
                                  f"parsing the same manifests once took {parse:.2f} s; "
                                  f"the limit is {0.85 * parse:.2f} s")


# --- test support: the comparison, the fixed clock, the runner for old code ---

#: One value of each kind the archive sample does not hold (it holds no date,
#: float or boolean), added to a copy of a sample manifest so the parity
#: checks have something to catch.
PROBE_LINES = (b"parity_date: 2026-10-09\n"
               b"parity_int: 3\n"
               b"parity_float: 1.5\n"
               b"parity_bool: yes\n"
               b"parity_nan: .nan\n"
               b"parity_negzero: -0.0\n"
               b"parity_labels: &parity_a\n- x\n"
               b"parity_alias: *parity_a\n"
               b"parity_map:\n  first: 1\n  second: 2\n"
               b"parity_stamp: 2026-06-04T09:10:00+01:00\n"
               b"parity_utc: 2026-06-04T09:10:00Z\n"
               b"parity_naive: 2026-06-04 09:10:00\n"
               b"parity_frac: 2026-06-04T09:10:00.123456-05:30\n")


def _probe_manifest(tmp_path):
    """A sample manifest with the probe values added."""
    first = support.sample_manifests(archive.sample_root())[0]
    probe = tmp_path / "probe-manifest.yml"
    probe.write_bytes(first.read_bytes().rstrip(b"\n") + b"\n" + PROBE_LINES)
    return probe


def _sample_project(tmp_path, name="proj", probe=True):
    """A copy of the unpacked archive sample, so a cache folder never lands in
    the shared unpacked sample. With `probe`, one more issue holds the probe
    values. Returns (project, work root)."""
    project = tmp_path / name
    shutil.copytree(archive.sample_root(), project)
    work = project / ".compass" / "work"
    if probe:
        folder = work / "parity-probe"
        folder.mkdir()
        shutil.copyfile(_probe_manifest(tmp_path), folder / "manifest.yml")
    return project, work


def _cache_folder(project):
    return Path(project) / ".compass" / "cache" / "parsed_yaml"


def _entries(project):
    folder = _cache_folder(project)
    return sorted(p for p in folder.glob("*.json")) if folder.is_dir() else []


def _flow(project, tmp_path, *extra, clock=support.FIXED_AT, cli=CLI_DIR, **env):
    work = Path(project) / ".compass" / "work"
    return support.run_compass(cli, ["flow", "--work-root", str(work), *extra], project,
                               tmp_path, clock=clock, **env)


def _alter_date(doc):
    doc["parity_date"] = "2026-10-09"


def _alter_int(doc):
    doc["parity_int"] = float(doc["parity_int"])


def _alter_alias(doc):
    doc["parity_alias"] = list(doc["parity_labels"])


def _alter_order(doc):
    doc["parity_map"] = dict(reversed(list(doc["parity_map"].items())))


def _alter_offset(doc):
    doc["parity_stamp"] = doc["parity_stamp"].astimezone(UTC)


PLANTED = [
    (_alter_date, "parity_date"),
    (_alter_int, "parity_int"),
    (_alter_alias, "parity_alias"),
    (_alter_order, "parity_map"),
    (_alter_offset, "parity_stamp"),
]


@pytest.mark.parametrize("alter,key", PLANTED, ids=[k for _, k in PLANTED])
def test_trc_c2_parity_fails_on_planted_difference(tmp_path, alter, key):
    probe = _probe_manifest(tmp_path)

    def altered(path):
        doc = support.safe_load_file(path)
        alter(doc)
        return doc

    assert parity_failures(support.safe_load_file, [probe]) == []
    failures = parity_failures(altered, [probe])
    assert len(failures) == 1
    assert str(probe) in failures[0] and key in failures[0]


def test_trc_c4_parity_check_matches_nan(tmp_path):
    path = tmp_path / "nan.yml"
    path.write_text("ratio: .nan\nneg: -0.0\n", encoding="utf-8")
    assert parity_failures(support.safe_load_file, [path]) == []


def test_fixed_clock_holds_the_date_and_time(tmp_path):
    project = tmp_path / "proj"
    work = support.build_project(project, archive.sample_root(), 2)
    code, out, err = support.run_compass(
        CLI_DIR, ["flow", "--digest", "--work-root", str(work)], project, tmp_path,
        clock="2001-02-03T04:05:06Z")
    assert code == 0, err
    assert out.startswith("# Flow digest - 2001-02-03\n"), out[:80]


def test_fixed_clock_leaves_parsed_dates_real(tmp_path):
    project = tmp_path / "proj"
    work = support.build_project(project, archive.sample_root(), 2)
    code, out, err = support.run_compass(
        CLI_DIR, ["flow", "--json", "--work-root", str(work)], project, tmp_path,
        clock="2001-02-03T04:05:06Z")
    assert code == 0 and "Traceback" not in err, err


def test_fixed_clock_leaves_the_cache_able_to_store_dates(tmp_path):
    import hashlib
    project, _work = _sample_project(tmp_path)
    code, _out, err = _flow(project, tmp_path)
    assert code == 0, err
    probe = project / ".compass" / "work" / "parity-probe" / "manifest.yml"
    digest = hashlib.sha256(probe.read_bytes()).hexdigest()
    assert (_cache_folder(project) / f"{digest}.json").is_file(), (
        "a manifest holding dates was not stored while the clock was fixed")


def test_no_shipped_file_names_the_fixed_clock():
    named = [str(p.relative_to(ROOT)) for p in CLI_DIR.rglob("*")
             if p.is_file() and p.suffix != ".pyc" and "fixed_clock" in p.read_text(
                 encoding="utf-8", errors="ignore")]
    assert named == []


def test_base_code_is_read_from_a_reachable_commit(tmp_path):
    cli = support.extract_base_code("HEAD", tmp_path)
    assert (cli / "compass").is_file() and (cli / "compass_pkg" / "core.py").is_file()


def test_base_code_from_an_unreachable_commit_fails(tmp_path):
    with pytest.raises(support.BaseCodeUnavailable):
        support.extract_base_code("0" * 40, tmp_path)


# --- group C: parity ---------------------------------------------------------

def test_trc_c1_parity_over_archive_sample(tmp_path):
    project, work = _sample_project(tmp_path)
    code, _out, err = _flow(project, tmp_path)
    assert code == 0, err
    assert _entries(project), "compass flow stored nothing, so the reads below are not warm"
    from compass_pkg import parse_cache
    cache = parse_cache.for_work_root(str(work))
    manifests = sorted(work.glob("*/manifest.yml"))
    assert len(manifests) == 17
    for round_number in range(3):
        failures = parity_failures(lambda p: cache.load_yaml(str(p)), manifests)
        assert failures == [], f"read {round_number + 1}: {failures}"


def test_trc_c3_bundled_pure_python_parser_only():
    names = ("CSafeLoader", "CLoader", "CParser", "__with_libyaml__")
    found = [f"{p.name}: {name}" for p in sorted((CLI_DIR / "compass_pkg").glob("*.py"))
             for name in names if name in p.read_text(encoding="utf-8")]
    assert found == []
    done = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); import compass_pkg, yaml; "
         "print(yaml.__file__)", str(CLI_DIR)],
        capture_output=True, text=True, check=True)
    assert Path(done.stdout.strip()).resolve().is_relative_to((CLI_DIR / "vendor" / "yaml").resolve())


# --- group D: freshness ------------------------------------------------------

def test_trc_d1_malformed_after_read_refused(reader):
    path = reader.write("probe", "status: in-progress\n")
    assert reader.read(path) == {"status": "in-progress"}
    path.write_text("status: [unclosed\n", encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        reader.read(path)
    assert str(caught.value).startswith(f"invalid YAML in {path}:")
    with pytest.raises(CompassError) as from_core:
        core.load_yaml(str(path))
    assert str(caught.value) == str(from_core.value)


def test_trc_d2_removed_after_read_missing(reader):
    path = reader.write("probe", "status: in-progress\n")
    assert reader.read(path) == {"status": "in-progress"}
    path.unlink()
    with pytest.raises(CompassError) as caught:
        reader.read(path)
    assert str(caught.value) == f"not found: {path}"


# --- group E: the stored cache ----------------------------------------------

_READ_PROBE = """
import sys
sys.path.insert(0, sys.argv[1])
import compass_pkg, yaml
from compass_pkg import parse_cache
cache = parse_cache.for_work_root(sys.argv[2])
sys.stdout.write(yaml.safe_dump(cache.load_yaml(sys.argv[3]), sort_keys=False))
"""


def _read_in_new_process(work, path):
    """What a new process reads through the cache, as safe_dump text."""
    done = subprocess.run([sys.executable, "-c", _READ_PROBE, str(CLI_DIR), str(work), str(path)],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _expected_text(path):
    return yaml.safe_dump(support.safe_load_file(path), sort_keys=False)


def _one_manifest(tmp_path, text="status: in-progress\nname: probe\n"):
    work = tmp_path / "proj" / ".compass" / "work"
    path = work / "probe" / "manifest.yml"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return tmp_path / "proj", work, path


@pytest.mark.parametrize("mismatch", ["digest", "format", "parser-version"])
def test_trc_e1_mismatched_cache_entry_unused(tmp_path, mismatch):
    import hashlib
    project, work, path = _one_manifest(tmp_path)
    assert _read_in_new_process(work, path) == _expected_text(path)
    (entry,) = _entries(project)
    original = entry.read_text(encoding="utf-8")
    assert '"in-progress"' in original
    if mismatch == "digest":
        path.write_text("status: in-review\nname: probe\n", encoding="utf-8")
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.copyfile(entry, entry.with_name(current + ".json"))
    else:
        planted = original.replace('"in-progress"', '"planted"')
        if mismatch == "format":
            planted = planted.replace('"format":1', '"format":99')
        else:
            planted = planted.replace(f'"pyyaml":"{yaml.__version__}"', '"pyyaml":"0.0.0"')
        assert planted != original.replace('"in-progress"', '"planted"')
        entry.write_text(planted, encoding="utf-8")
    assert _read_in_new_process(work, path) == _expected_text(path)


def _damage(entry, kind):
    data = entry.read_bytes()
    if kind == "half":
        entry.write_bytes(data[: len(data) // 2])
    elif kind == "zero":
        entry.write_bytes(b"")
    elif kind == "random":
        entry.write_bytes(os.urandom(4096))
    else:
        entry.write_text("kind: some other format\nrows: [1, 2, 3]\n", encoding="utf-8")


@pytest.mark.parametrize("damage", ["half", "zero", "random", "other-format"])
def test_trc_e2_corrupt_cache_ignored(tmp_path, damage):
    project, _work = _sample_project(tmp_path)
    assert _flow(project, tmp_path)[0] == 0
    entries = _entries(project)
    assert entries
    for entry in entries:
        _damage(entry, damage)
    damaged = _flow(project, tmp_path)
    shutil.rmtree(project / ".compass" / "cache")
    clean = _flow(project, tmp_path)
    assert damaged == clean
    assert "cache" not in damaged[2].lower()


def _planted_payload(kind, marker):
    if kind == "pickle":
        import pickle

        class Boom:
            def __reduce__(self):
                return (os.system, (f"touch {marker}",))

        return pickle.dumps(Boom())
    return f"x: !!python/object/apply:os.system ['touch {marker}']\n".encode("utf-8")


@pytest.mark.parametrize("payload", ["pickle", "yaml-python-tag"])
def test_trc_e3_planted_cache_runs_nothing(tmp_path, payload):
    project, work, path = _one_manifest(tmp_path)
    _read_in_new_process(work, path)
    (entry,) = _entries(project)
    marker = tmp_path / "marker-e3"
    entry.write_bytes(_planted_payload(payload, marker))
    assert _read_in_new_process(work, path) == _expected_text(path)
    assert not marker.exists()


def _blocked_cache(project, how):
    cache = project / ".compass" / "cache"
    if how == "a file where the folder goes":
        cache.write_text("not a folder\n", encoding="utf-8")
    else:
        cache.mkdir(parents=True)
        cache.chmod(0o500)


@pytest.mark.parametrize("how", ["a file where the folder goes", "a read-only folder"])
def test_trc_e4_unwritable_cache_same_output(tmp_path, how):
    if how == "a read-only folder" and os.geteuid() == 0:
        pytest.skip("a superuser can write to a read-only folder")
    good, _ = _sample_project(tmp_path, "good")
    blocked, _ = _sample_project(tmp_path, "blocked")
    _blocked_cache(blocked, how)
    try:
        result = _flow(blocked, tmp_path)
        expected = _flow(good, tmp_path)
    finally:
        cache = blocked / ".compass" / "cache"
        if cache.is_dir():
            cache.chmod(0o700)
    assert result == expected


def _snapshot(root):
    state = {}
    for path in Path(root).rglob("*"):
        if path.is_file() and not path.is_symlink():
            stat = path.stat()
            state[path.relative_to(root).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return state


def test_trc_e5_cache_stays_inside_project(tmp_path):
    project, _work = _sample_project(tmp_path)
    home, temp = tmp_path / "home", tmp_path / "temp"
    home.mkdir()
    temp.mkdir()
    before = _snapshot(project)
    for _ in range(2):
        code, _out, err = support.run_compass(
            CLI_DIR, ["flow", "--work-root", str(project / ".compass" / "work")], project, home,
            TMPDIR=str(temp))
        assert code == 0, err
    assert list(home.iterdir()) == [] and list(temp.iterdir()) == []
    after = _snapshot(project)
    touched = [name for name, info in after.items() if before.get(name) != info]
    assert touched and all(name.startswith(".compass/") for name in touched), touched


# --- group B again: the cold run, against the code before the change ---------

def _need_before():
    commit = support.before_commit()
    if commit is None:
        pytest.skip(f"set {support.BEFORE_COMMIT} to the commit before the change to run this")
    return commit


def _both_codes(tmp_path):
    commit = _need_before()
    base = support.extract_base_code(commit, tmp_path / "base")
    current = support.copy_current_code(tmp_path / "current")
    return support.SwappableCode(tmp_path / "run", base, current)


@pytest.mark.serial
@pytest.mark.parametrize("state", ["no stored state", "stale stored state"])
def test_trc_b3_cold_flow_within_ten_percent_of_before(tmp_path, state):
    (tmp_path / "run").mkdir()
    code = _both_codes(tmp_path)
    warm = tmp_path / "warm-up"
    warm_work = support.build_project(warm, archive.sample_root(), 4)
    for which in ("base", "current"):                 # compile bytecode before timing
        support.time_flow(code.use(which), warm_work, warm, tmp_path)
    project = tmp_path / "proj"
    work = support.build_project(project, archive.sample_root(), 484)
    if state == "stale stored state":
        support.time_flow(code.use("current"), work, project, tmp_path)
    times = {"base": [], "current": []}
    for round_number in range(3):
        for which in ("current", "base"):
            support.append_comment(work, f"round {round_number} {which}")
            if state == "no stored state" and (project / ".compass" / "cache").exists():
                shutil.rmtree(project / ".compass" / "cache")
            times[which].append(support.time_flow(code.use(which), work, project, tmp_path))
    median = {which: sorted(values)[1] for which, values in times.items()}
    assert median["current"] <= 1.10 * median["base"], (
        f"{state}: changed code {times['current']} s, code before {times['base']} s")


# --- group F: no command's output changes ------------------------------------

def _read_only_commands(slugs):
    commands = [["flow"], ["flow", "--json"], ["flow", "--digest"], ["retro"]]
    for slug in slugs:
        commands += [["next", "--issue", slug], ["check", "--issue", slug],
                     ["issue", "lint", "--issue", slug]]
    return commands


def test_trc_f1_read_only_output_unchanged(tmp_path):
    (tmp_path / "run").mkdir()
    code = _both_codes(tmp_path)
    slugs = sorted(p.parent.name for p in support.sample_manifests(archive.sample_root()))
    commands = _read_only_commands(slugs)
    project = tmp_path / "proj"
    results = {}
    for which in ("base", "current"):
        if project.exists():
            shutil.rmtree(project)
        shutil.copytree(archive.sample_root(), project)
        cli = code.use(which)
        results[which] = [support.run_compass(cli, args, project, tmp_path, clock=support.FIXED_AT)
                          for args in commands]
        if which == "current":
            # The same flow commands again, now that the first run stored its parses.
            results["warm"] = [support.run_compass(cli, args, project, tmp_path,
                                                   clock=support.FIXED_AT)
                               for args in commands[:4]]
    assert all(code == 0 and out for code, out, _err in results["base"][:4])
    for index, args in enumerate(commands):
        assert results["current"][index] == results["base"][index], " ".join(args)
    assert results["warm"] == results["base"][:4]


SAVING_PROBE = (b"parity_labels: &parity_a\n- x\nparity_alias: *parity_a\n"
                b"parity_date: 2026-10-09\n")


def test_trc_f2_saved_manifest_bytes_unchanged(tmp_path):
    (tmp_path / "run").mkdir()
    code = _both_codes(tmp_path)
    slug = "accept-adr-030"
    project = tmp_path / "proj"
    sequence = [["scenario", "add", "TRC-ZZ1", "--title", "probe", "--intent", "INT-1"],
                ["evidence", "add", "EV-ZZ1", "--type", "command-output", "--path",
                 "evidence/probe.txt"],
                ["gate", "pass", "verify.traceability", "--evidence", "EV-ZZ1"]]
    results = {}
    for which in ("base", "current"):
        if project.exists():
            shutil.rmtree(project)
        shutil.copytree(archive.sample_root(), project)
        folder = project / ".compass" / "work" / slug
        manifest = folder / "manifest.yml"
        manifest.write_bytes(manifest.read_bytes().rstrip(b"\n") + b"\n" + SAVING_PROBE)
        (folder / "evidence").mkdir(exist_ok=True)
        (folder / "evidence" / "probe.txt").write_text("probe\n", encoding="utf-8")
        cli = code.use(which)
        steps = []
        for args in sequence:
            outcome = support.run_compass(cli, [*args, "--issue", slug], project, tmp_path,
                                          clock=support.FIXED_AT)
            devlog = folder / "devlog.md"
            steps.append((outcome, manifest.read_bytes(),
                          devlog.read_bytes() if devlog.exists() else None))
        results[which] = steps
    assert all(outcome[0] == 0 for outcome, _manifest, _devlog in results["base"])
    assert len({manifest for _outcome, manifest, _devlog in results["base"]}) == 3
    for index, args in enumerate(sequence):
        assert results["current"][index] == results["base"][index], " ".join(args)


def _status(repo):
    done = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo,
                          capture_output=True, text=True, check=True)
    return done.stdout


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
                    *args], cwd=repo, check=True, capture_output=True)


def test_trc_f3_flow_leaves_git_status_unchanged_in_a_clean_checkout(tmp_path):
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", "--local", str(ROOT), str(clone))
    work = clone / ".compass" / "work"
    shutil.copytree(archive.sample_root() / ".compass" / "work", work, dirs_exist_ok=True)
    before = _status(clone)
    code, _out, err = support.run_compass(
        CLI_DIR, ["flow", "--work-root", str(work)], clone, tmp_path)
    assert code == 0, err
    assert _entries(clone), "the run stored nothing, so this checks nothing"
    assert _status(clone) == before


def test_trc_f3_flow_leaves_git_status_unchanged_where_work_is_committed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", ".")
    code, _out, err = support.run_compass(CLI_DIR, ["init"], repo, tmp_path)
    assert code == 0, err
    slug = "accept-adr-030"
    shutil.copytree(archive.sample_root() / ".compass" / "work" / slug,
                    repo / ".compass" / "work" / slug)
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "probe")
    assert _status(repo) == ""
    code, _out, err = support.run_compass(
        CLI_DIR, ["flow", "--work-root", str(repo / ".compass" / "work")], repo, tmp_path)
    assert code == 0, err
    assert _entries(repo), "the run stored nothing, so this checks nothing"
    assert _status(repo) == ""


@pytest.mark.parametrize("state", ["a dangling link", "an empty file"])
def test_trc_f3_the_folders_own_gitignore_is_written_whole_and_not_through_a_link(
        tmp_path, state):
    project, work, path = _one_manifest(tmp_path)
    folder = _cache_folder(project)
    folder.mkdir(parents=True)
    outside = tmp_path / "outside-target"
    if state == "a dangling link":
        os.symlink(outside, folder / ".gitignore")
    else:
        (folder / ".gitignore").write_bytes(b"")
    _read_in_new_process(work, path)
    assert not outside.exists()
    ignore = folder / ".gitignore"
    assert ignore.is_file() and not ignore.is_symlink()
    assert ignore.read_bytes() == b"*\n"


def test_trc_e4_a_leftover_temporary_entry_is_pruned_when_old(tmp_path):
    import time
    from compass_pkg import parse_cache
    project, work, path = _one_manifest(tmp_path)
    cache = parse_cache.for_work_root(str(work))
    cache.load_yaml(str(path))
    folder = _cache_folder(project)
    old, fresh = folder / ".tmp-old", folder / ".tmp-fresh"
    old.write_text("half an entry", encoding="utf-8")
    fresh.write_text("a write in progress", encoding="utf-8")
    long_ago = time.time() - 120
    os.utime(old, (long_ago, long_ago))
    for index in range(3):
        (folder / (f"{index:064x}" + ".json")).write_text("{}", encoding="utf-8")
    cache.finish()
    assert not old.exists()
    assert fresh.exists()
    assert len(_entries(project)) == 1


# --- who may use the cache, and what it may import ----------------------------

def test_trc_a14_only_flow_reads_through_the_parse_cache():
    users = []
    for path in sorted((CLI_DIR / "compass_pkg").glob("*.py")) + [CLI_DIR / "compass"]:
        if path.name != "parse_cache.py" and re.search(r"\bparse_cache\b",
                                                      path.read_text(encoding="utf-8")):
            users.append(path.name)
    assert users == ["flow.py"]


def test_trc_e3_parse_cache_loads_nothing_but_json_and_safe_load():
    text = (CLI_DIR / "compass_pkg" / "parse_cache.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(pickle|marshal|shelve)\b", text)
    assert set(re.findall(r"\byaml\.(\w+)", text)) <= {"safe_load", "YAMLError", "__version__"}
