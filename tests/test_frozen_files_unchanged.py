"""Frozen and exempt files stay as they are on main (issue
language-key-and-us-english).

The word pass changes the spelling of many files. Seven classes must not move:

- the merged decision records under `governance/decisions/` and
  `architecture/decisions/`;
- the frozen 8.x presets `default@6` and `default@7`, kept since 9.0.0 only as
  test data under `tests/fixtures/presets/` (VD-055);
- `governance/artifacts-8.0.4.yml`, the artifacts catalogue as 8.0.4 shipped it,
  which `artifact_kinds.shipped()` reads (VD-055);
- `governance/shipped-releases.tar.xz`;
- the compatibility corpora under `tests/fixtures/compat/`, except the one
  stdout pin that the CLI message pass changes;
- `cli/vendor`;
- GitHub's own status value `cancelled`.

`tests/fixtures/frozen-digests.yml` holds a digest for each file of the
tarball, the corpus folder and `cli/vendor`, taken from main before the word
pass. The two presets and the 8.0.4 catalogue are pinned here, in
`PRESET_PINS` and `CATALOGUE_8_0_4_PIN`, and compared byte for byte with the
release that shipped them when the release tags are present. A merged record
is checked against the base ref with git. Each check is run on a copy with one planted
respelling, to show that it fails.
"""
from __future__ import annotations

import hashlib
import re
import pytest
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import atomic_io  # noqa: E402  (puts the bundled yaml first)
import yaml  # noqa: E402

DIGESTS = ROOT / "tests" / "fixtures" / "frozen-digests.yml"
# The frozen presets, kept as test data since 9.0.0 (VD-055). Each is the last
# preset its major shipped: `default@6` as v6.1.0 shipped `governance/presets/
# default/`, and `default@7` as v8.0.4 shipped it. A digest is over the parsed
# content of a file, so a comment or layout change does not move it; the byte
# check against the release tag finds that.
PRESET = "tests/fixtures/presets/default@6"
PRESET_7 = "tests/fixtures/presets/default@7"
PRESET_TAGS = {PRESET: "v6.1.0", PRESET_7: "v8.0.4"}
PRESET_PINS = {
    PRESET: {
        "files": {
            "approaches.yml": "sha256:9c76a01450517f511cd1f6ee624ef3d34fc5114734f6509c1cca375a3c9d1cff",
            "artifacts.yml": "sha256:a434417c8f0551b4c837ab4af2c42d64ea646eed715b98181b5633f00a800b69",
            "checks.yml": "sha256:0281a6f3227b0386039bc3e0f6ec15feb0fd0eb0c7f44361ac92e8c444de50d1",
            "dimensions.yml": "sha256:401eb199005f3f59a0de898a6e804301df7056727336581bfa0e5a396ef1467c",
            "evidence-types.yml": "sha256:d56f9caa383f0481f3c62ee693c8f0d73cd0a162d3da73201574f9a4b2419207",
            "gates.yml": "sha256:3737c10ec386c344c67b3f104e2ad63bf7b17d13a3ec54b9ed1150c3a7250660",
            "preset.yml": "sha256:a006de6765ae230c2e95f355eee962360f1989602ac54f50180627afeb57b369",
            "readiness.yml": "sha256:2b420d6d890b687e8e39750caa8ee3a96d0c9b359f8a8b61ab436994eb160cad",
            "rules.yml": "sha256:b2e9f953d13fc05c6b0189e0af62cfecb77ed4d2f7235e3dd97561f516c49d76",
            "stages.yml": "sha256:ae48f1af2f41356057eef5661512b664feac27c284dc065d069571446f4345e0",
            "vocabulary.yml": "sha256:2aaa873481f45ca0f64091c0a623cd7b37942501b179730f0775eb593c7ccc24",
        },
        "preset": "sha256:c1aa3ce5989b37b3a92bd29a9b9533888fb1ca9df7ff065ddfa400bd47f9d330",
    },
    PRESET_7: {
        "files": {
            "approaches.yml": "sha256:603f45e38f0b0a594e7e16fd68a4874ec851ce27faec97f057f626952798379d",
            "artifacts.yml": "sha256:0daaed5944cb0507f329d8bed740f5933d77ecfefb348241cd4bccf6888577eb",
            "checks.yml": "sha256:bb7e76e1360aa0d7f9b4384f181fee093556b0d108cc30d76cfbc07f00d7129a",
            "dimensions.yml": "sha256:401eb199005f3f59a0de898a6e804301df7056727336581bfa0e5a396ef1467c",
            "evidence-types.yml": "sha256:aab3aa2e58f835e8b98f0c91e7f7ba9d64a6dd9121a74b29f6f3cc0626dfe95a",
            "gates.yml": "sha256:3737c10ec386c344c67b3f104e2ad63bf7b17d13a3ec54b9ed1150c3a7250660",
            "preset.yml": "sha256:b26ee0e76cc1e453f237c480231cd6eb8a4f1029cb63529c582f4386de68fcf9",
            "readiness.yml": "sha256:2b420d6d890b687e8e39750caa8ee3a96d0c9b359f8a8b61ab436994eb160cad",
            "rules.yml": "sha256:5000d6ec64a350bcd96d250bde9fae3bff92d107253c248560dbdac2a7fd4b54",
            "stages.yml": "sha256:31b45fd40d19e23dfaba50fe9b454314362db500a2d3a878ba2bffe46890851e",
            "vocabulary.yml": "sha256:2aaa873481f45ca0f64091c0a623cd7b37942501b179730f0775eb593c7ccc24",
        },
        "preset": "sha256:0cdafd87d6908e0cc80df8760fa61651fb865abb235aed6b5a3234ef7d469ed6",
    },
}
# The one 8.x data file the CLI still reads (VD-055): the bytes of the default
# preset's `artifacts.yml` as the v8.0.4 tag holds it.
CATALOGUE_8_0_4 = "governance/artifacts-8.0.4.yml"
CATALOGUE_8_0_4_TAG = ("v8.0.4", "/".join(("governance", "presets", "default", "artifacts.yml")))
CATALOGUE_8_0_4_PIN = "sha256:b0e00b7d26b1399040859df0f7cd425d862e0dcd0387f7a8fb804f5f3f5a8e3f"
TARBALL = "governance/shipped-releases.tar.xz"
CORPORA = "tests/fixtures/compat"
VENDOR = "cli/vendor"
DECISIONS = ("governance/decisions", "architecture/decisions")
CASE_PIN_FILE = "tests/fixtures/compat/contract-4-commands.yml"
# The one stdout pin that the CLI message pass changes. The line is removed
# before the digest, in either spelling, so the rest of the file stays frozen.
CASE_PIN = re.compile(r'^\s*stdout_contains: "initiali[sz]ed Compass"\s*$')

# The guard excludes these same paths. test_us_english_guard.py compares.
FROZEN_PATHS = (
    "governance/decisions/",
    "architecture/decisions/",
    PRESET,
    PRESET_7,
    CATALOGUE_8_0_4,
    TARBALL,
    CORPORA + "/",
    VENDOR,
)


def _tracked(root, folder):
    """The tracked files under `folder`, or the files on disk when `root` is
    a plain copy that is not a repository."""
    base = Path(root) / folder
    if base.is_file():
        return [folder]
    return sorted(p.relative_to(root).as_posix() for p in base.rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts)


def digest_of(root, path):
    data = (Path(root) / path).read_bytes()
    if path == CASE_PIN_FILE:
        lines = data.decode("utf-8").splitlines(keepends=True)
        data = "".join(line for line in lines if not CASE_PIN.match(line)).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def frozen_paths(root):
    return _tracked(root, TARBALL) + _tracked(root, CORPORA) + _tracked(root, VENDOR)


def digest_problems(root, pinned):
    """One line for each frozen file whose digest differs from the pinned one."""
    problems = []
    now = frozen_paths(root)
    for path in sorted(set(now) | set(pinned)):
        if path not in pinned:
            problems.append(f"{path} is frozen but has no pinned digest")
        elif path not in now:
            problems.append(f"{path} is pinned but missing")
        elif digest_of(root, path) != pinned[path]:
            problems.append(f"{path} changed")
    return problems


def preset_problems(root, pins, preset=PRESET):
    """One line for each file of a frozen preset that differs from its pin."""
    folder = Path(root) / preset
    parsed = {p.name: yaml.safe_load(p.read_text(encoding="utf-8"))
              for p in sorted(folder.glob("*.yml"))}
    now = {name: atomic_io.digest(doc) for name, doc in parsed.items()}
    problems = [f"{name} changed" for name, pin in pins["files"].items()
                if now.get(name) != pin]
    problems += [f"{name} is not pinned" for name in now if name not in pins["files"]]
    if atomic_io.digest(parsed) != pins["preset"]:
        problems.append("the whole preset changed")
    return problems


def _git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                           *args], cwd=root, capture_output=True, text=True)


def base_ref(root=ROOT):
    """origin/main when it exists, else HEAD."""
    found = _git(root, "rev-parse", "--verify", "--quiet", "origin/main")
    return "origin/main" if found.returncode == 0 else "HEAD"


def decision_problems(root, base):
    """One line for each merged record that is changed or removed since `base`.
    A new record is fine. The index `README.md` is not a record: a new record
    adds a row to it."""
    out = _git(root, "diff", "--name-status", "-M", base, "--", *DECISIONS)
    assert out.returncode == 0, out.stderr
    problems = []
    for line in out.stdout.splitlines():
        status, *names = line.split("\t")
        if Path(names[0]).name == "README.md":
            continue
        if status[0] in "MDRT":
            problems.append(f"{names[0]} was changed or removed ({status})")
    return problems


def _pinned():
    return yaml.safe_load(DIGESTS.read_text(encoding="utf-8"))["files"]


def _copy(tmp_path, *folders):
    for folder in folders:
        source, target = ROOT / folder, tmp_path / folder
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy(source, target)
    return tmp_path


def _respell(path):
    """Plant a respelling in a text file: one word changes."""
    text = Path(path).read_text(encoding="utf-8")
    Path(path).write_text(text + "\nbehaviour\n", encoding="utf-8")


def test_trc_039():
    """Each class is unchanged against main, and a planted respelling in a
    copy fails the check of its class."""
    assert decision_problems(ROOT, base_ref()) == []
    for preset, pins in PRESET_PINS.items():
        assert preset_problems(ROOT, pins, preset) == [], preset
    assert digest_of(ROOT, CATALOGUE_8_0_4) == CATALOGUE_8_0_4_PIN
    assert digest_problems(ROOT, _pinned()) == []


def test_trc_039_a_planted_respelling_in_the_tarball_fails(tmp_path):
    root = _copy(tmp_path, TARBALL)
    assert digest_problems(root, {TARBALL: _pinned()[TARBALL]}) == []
    with open(root / TARBALL, "ab") as handle:
        handle.write(b"x")
    assert digest_problems(root, {TARBALL: _pinned()[TARBALL]}) == [f"{TARBALL} changed"]


def test_trc_039_a_planted_respelling_in_a_corpus_fails(tmp_path):
    root = _copy(tmp_path, CORPORA)
    pinned = {p: d for p, d in _pinned().items() if p.startswith(CORPORA)}
    assert digest_problems(root, pinned) == []
    other = root / CORPORA / "contract-2-owed.yml"
    _respell(other)
    assert digest_problems(root, pinned) == [f"{CORPORA}/contract-2-owed.yml changed"]


def test_trc_039_only_the_one_pin_line_of_the_command_corpus_may_move(tmp_path):
    root = _copy(tmp_path, CORPORA)
    pinned = {p: d for p, d in _pinned().items() if p.startswith(CORPORA)}
    path = root / CASE_PIN_FILE
    text = path.read_text(encoding="utf-8")
    assert 'stdout_contains: "initialized Compass"' in text
    path.write_text(text.replace('"initialized Compass"', '"initialised Compass"'),
                    encoding="utf-8")
    assert digest_problems(root, pinned) == [], "the pin line may change"
    path.write_text(text.replace("already a Compass project", "already a Compass projekt"),
                    encoding="utf-8")
    assert digest_problems(root, pinned) == [f"{CASE_PIN_FILE} changed"]


def test_trc_039_a_planted_respelling_in_vendor_fails(tmp_path):
    root = _copy(tmp_path, VENDOR)
    pinned = {p: d for p, d in _pinned().items() if p.startswith(VENDOR)}
    assert digest_problems(root, pinned) == []
    target = sorted((root / VENDOR).rglob("*.py"))[0]
    _respell(target)
    assert digest_problems(root, pinned) == [f"{target.relative_to(root).as_posix()} changed"]


def test_trc_039_a_planted_respelling_in_the_preset_fails(tmp_path):
    root = _copy(tmp_path, PRESET)
    pins = PRESET_PINS[PRESET]
    assert preset_problems(root, pins) == []
    target = root / PRESET / "rules.yml"
    target.write_text(target.read_text(encoding="utf-8").replace(
        "rationale:", "rationale: behaviour", 1), encoding="utf-8")
    assert preset_problems(root, pins), "the respelling went unseen"


def test_trc_039_a_planted_respelling_in_the_8_0_4_catalogue_fails(tmp_path):
    root = _copy(tmp_path, CATALOGUE_8_0_4)
    assert digest_of(root, CATALOGUE_8_0_4) == CATALOGUE_8_0_4_PIN
    _respell(root / CATALOGUE_8_0_4)
    assert digest_of(root, CATALOGUE_8_0_4) != CATALOGUE_8_0_4_PIN


def _release_tags():
    """The `v*` tags of this checkout. Skip when there are none (a shallow
    clone), so a missing tag is named rather than passed in silence."""
    done = _git(ROOT, "tag", "--list", "v*")
    tags = done.stdout.split() if done.returncode == 0 else []
    if not tags:
        pytest.skip("no v* release tags in this checkout; fetch the tags to compare")
    return tags


def _shown(tag, path):
    done = subprocess.run(["git", "show", f"{tag}:{path}"], cwd=ROOT, capture_output=True)
    assert done.returncode == 0, done.stderr.decode(errors="replace")
    return done.stdout


def test_the_8_0_4_catalogue_is_the_one_v8_0_4_shipped_byte_for_byte():
    tag, path = CATALOGUE_8_0_4_TAG
    assert tag in _release_tags(), f"release tags exist but {tag} is not one of them"
    assert _shown(tag, path) == (ROOT / CATALOGUE_8_0_4).read_bytes()


@pytest.mark.parametrize("preset", sorted(PRESET_TAGS))
def test_each_frozen_preset_is_the_one_its_release_shipped_byte_for_byte(preset):
    tag = PRESET_TAGS[preset]
    assert tag in _release_tags(), f"release tags exist but {tag} is not one of them"
    listed = _git(ROOT, "ls-tree", "-r", "--name-only", tag, "--", "governance/presets/default")
    assert listed.returncode == 0, listed.stderr
    shipped = {Path(line).name: line for line in listed.stdout.split()}
    here = {p.name: p for p in (ROOT / preset).iterdir() if p.is_file()}
    assert set(here) == set(shipped), (preset, sorted(set(here) ^ set(shipped)))
    for name, path in sorted(here.items()):
        assert _shown(tag, shipped[name]) == path.read_bytes(), f"{preset}/{name}"


def test_trc_039_a_planted_respelling_in_a_merged_record_fails(tmp_path):
    for folder in DECISIONS:
        repo = tmp_path / folder.replace("/", "-")
        record = repo / folder / "2026-01-01-a-record.md"
        record.parent.mkdir(parents=True)
        record.write_text("# A record\n\nIt is fine.\n", encoding="utf-8")
        _git(repo, "init", "-q")
        _git(repo, "add", "-A")
        assert _git(repo, "commit", "-q", "-m", "base").returncode == 0
        assert decision_problems(repo, "HEAD") == []
        added = repo / folder / "2026-02-02-new.md"
        added.write_text("A new record.\n", encoding="utf-8")
        assert decision_problems(repo, "HEAD") == [], "a new record is allowed"
        index = repo / folder / "README.md"
        index.write_text("| A record |\n", encoding="utf-8")
        assert decision_problems(repo, "HEAD") == [], "a new index file is allowed"
        _git(repo, "add", "-A")
        assert _git(repo, "commit", "-q", "-m", "index").returncode == 0
        index.write_text("| A record |\n| A new record |\n", encoding="utf-8")
        assert decision_problems(repo, "HEAD") == [], "a new row in the index is allowed"
        record.write_text("# A record\n\nIt is behaviour.\n", encoding="utf-8")
        assert decision_problems(repo, "HEAD") == [
            f"{folder}/2026-01-01-a-record.md was changed or removed (M)"]


def test_trc_039_the_compass_decision_check_refuses_a_changed_record(tmp_path):
    """The CLI check of the same class fails on the planted respelling."""
    repo = tmp_path / "repo"
    record = repo / "governance" / "decisions" / "2026-01-01-a-record.md"
    record.parent.mkdir(parents=True)
    record.write_text("# A record\n\nIt is fine.\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    assert _git(repo, "commit", "-q", "-m", "base").returncode == 0
    (repo / ".compass").mkdir()
    cli = ROOT / "cli" / "compass"
    ok = subprocess.run([sys.executable, str(cli), "decision", "check", "--base", "HEAD"],
                        cwd=repo, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    record.write_text("# A record\n\nIt is behaviour.\n", encoding="utf-8")
    bad = subprocess.run([sys.executable, str(cli), "decision", "check", "--base", "HEAD"],
                         cwd=repo, capture_output=True, text=True)
    assert bad.returncode != 0 and "2026-01-01-a-record.md" in bad.stdout + bad.stderr


def test_trc_039_the_github_status_cancelled_is_still_read():
    """`cancelled` is GitHub's own value, so it is not in the word list and the
    script that reads it still compares with it."""
    sys.path.insert(0, str(ROOT / "tests"))
    import us_english_words as words
    assert "cancelled" not in words.WORDS
    source = (ROOT / "scripts" / "ci-already-tested.py").read_text(encoding="utf-8")
    assert 'run.get("conclusion") == "cancelled"' in source
    assert words.scan_python(source) == []


def test_the_pins_cover_each_file_of_the_three_classes():
    pinned = _pinned()
    assert TARBALL in pinned
    assert any(p.startswith(CORPORA + "/") for p in pinned)
    assert any(p.startswith(VENDOR + "/") for p in pinned)
    assert "tests/fixtures/compat/contract-4-commands.yml" in pinned
    assert set(pinned) == set(frozen_paths(ROOT))
