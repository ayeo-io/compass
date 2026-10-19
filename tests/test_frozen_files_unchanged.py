"""Frozen and exempt files stay as they are on main (issue
language-key-and-us-english).

The word pass changes the spelling of many files. Six classes must not move:

- the merged decision records under `governance/decisions/` and
  `architecture/decisions/`;
- the files of `governance/presets/default@6`;
- `governance/shipped-releases.tar.xz`;
- the compatibility corpora under `tests/fixtures/compat/`, except the one
  stdout pin that the CLI message pass changes;
- `cli/vendor`;
- GitHub's own status value `cancelled`.

`tests/fixtures/frozen-digests.yml` holds a digest for each file of the
tarball, the corpus folder and `cli/vendor`, taken from main before the word
pass. The preset keeps its existing digest file. A merged record is checked
against the base ref with git. Each check is run on a copy with one planted
respelling, to show that it fails.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import atomic_io  # noqa: E402  (puts the bundled yaml first)
import yaml  # noqa: E402

DIGESTS = ROOT / "tests" / "fixtures" / "frozen-digests.yml"
PRESET_DIGESTS = ROOT / "tests" / "fixtures" / "preset-digests.yml"
PRESET = "governance/presets/default@6"
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


def preset_problems(root, pins):
    """One line for each file of `default@6` that differs from its pin."""
    folder = Path(root) / PRESET
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
    A new record is fine."""
    out = _git(root, "diff", "--name-status", "-M", base, "--", *DECISIONS)
    assert out.returncode == 0, out.stderr
    problems = []
    for line in out.stdout.splitlines():
        status, *names = line.split("\t")
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
    pins = yaml.safe_load(PRESET_DIGESTS.read_text(encoding="utf-8"))["default@6.0.0"]
    assert preset_problems(ROOT, pins) == []
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
    assert 'stdout_contains: "initialised Compass"' in text
    path.write_text(text.replace('"initialised Compass"', '"initialized Compass"'),
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
    pins = yaml.safe_load(PRESET_DIGESTS.read_text(encoding="utf-8"))["default@6.0.0"]
    assert preset_problems(root, pins) == []
    target = root / PRESET / "rules.yml"
    target.write_text(target.read_text(encoding="utf-8").replace(
        "rationale:", "rationale: behaviour", 1), encoding="utf-8")
    assert preset_problems(root, pins), "the respelling went unseen"


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
