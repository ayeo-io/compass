"""The frozen presets kept beside the live one, as data.

`governance/presets/default@6` and `default@7` stay after 9.0.0 (ADR-094):
`artifact_kinds`, `terminology_cmd`, `readiness_registry` and the
compatibility tests read them, and a stored generation names them. Each kept
folder must be the last preset its major shipped, byte for byte, and must match
the digests pinned in `tests/fixtures/preset-digests.yml`. The live preset
went in 9.0.0: the live major is the major of the check set
(`governance/check-set.yml`), and no frozen copy is made of the 8.x preset,
because a stored generation holds its own resolved policy.

These checks moved from the tests of `compass policy update`, which 9.0.0
removed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))


def _framework_root(base, version="7.0.0"):
    """A directory shaped like the framework after a release with a next major:
    `governance/presets/default@6` (the repository's kept folder) and a check
    set at `version`."""
    kept = ROOT / "governance" / "presets" / "default@6"
    presets = Path(base) / "governance" / "presets"
    presets.mkdir(parents=True)
    shutil.copytree(kept, presets / "default@6")
    (Path(base) / "governance" / "check-set.yml").write_text(
        f"id: compass-checks\nversion: {version}\n", encoding="utf-8")
    return Path(base)


def _preset_digests(folder):
    """`(pin key, {"preset": digest, "files": {file name: digest}})` for the
    preset files in `folder`. The pin key is the preset's id and version. A
    digest is over parsed content, as `tests/fixtures/preset-digests.yml` pins it."""
    from compass_pkg import atomic_io
    folder = Path(folder)
    parsed = {p.name: yaml.safe_load(p.read_text(encoding="utf-8"))
              for p in sorted(folder.iterdir()) if p.name.endswith(".yml")}
    meta = parsed["preset.yml"]
    return f"{meta['id']}@{meta['version']}", {
        "preset": atomic_io.digest(parsed),
        "files": {name: atomic_io.digest(doc) for name, doc in parsed.items()},
    }


def _digest_problems(folder, key, pins):
    """One line for each way the preset files in `folder` differ from the digests
    pinned under `key`: the file set, each file, then the whole preset. A file
    line names the file. Digests are over parsed content, so a comment-only edit
    gives no line; `_byte_problems` finds that."""
    folder, pin = Path(folder), pins[key]
    got_key, got = _preset_digests(folder)
    problems = []
    if got_key != key:
        problems.append(f"{folder.name}/preset.yml reads {got_key}, not {key}")
    for name in sorted(set(got["files"]) | set(pin["files"])):
        if name not in pin["files"]:
            problems.append(f"{folder.name}/{name} is in the folder but not pinned for {key}")
        elif name not in got["files"]:
            problems.append(f"{folder.name}/{name} is pinned for {key} but missing from the folder")
        elif got["files"][name] != pin["files"][name]:
            problems.append(f"{folder.name}/{name} differs from the digest pinned for {key}")
    if got_key != key or got["preset"] != pin["preset"]:
        major = key.split("@", 1)[1].split(".")[0]
        problems.append(f"{folder.name} is not the last preset shipped for major {major} ({key})")
    return problems


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True)


def _require_tag(repo, tag):
    """Return when `tag` is a release tag of `repo`. Skip when the checkout has no
    `v*` tag (a shallow clone) or git cannot read it. Fail when release tags
    exist and `tag` is not one of them, so a missing tag is never a silent pass."""
    try:
        done = _git(repo, "tag", "--list", "v*")
    except OSError as exc:
        pytest.skip(f"git cannot read {repo}: {exc}")
    if done.returncode != 0:
        pytest.skip(f"git cannot read {repo}: {done.stderr.decode(errors='replace').strip()}")
    tags = done.stdout.decode().split()
    if not tags:
        pytest.skip("no v* release tags in this checkout (a shallow clone?); "
                    f"fetch the tags to compare with {tag}")
    if tag not in tags:
        pytest.fail(f"release tags exist but {tag} is not one of them: {', '.join(tags)}")


def _byte_problems(folder, tag, repo=ROOT):
    """One line for each file of `folder` whose bytes, or whose name, differ from
    `governance/presets/default` at `tag` in `repo`."""
    folder = Path(folder)
    listed = _git(repo, "ls-tree", "-r", "--name-only", tag, "--", "governance/presets/default")
    if listed.returncode != 0:
        return [f"git cannot list governance/presets/default at {tag}: "
                f"{listed.stderr.decode(errors='replace').strip()}"]
    paths = {Path(line).name: line for line in listed.stdout.decode().splitlines()}
    here = {p.name for p in folder.iterdir() if p.is_file()}
    problems = [f"{folder.name}/{p.name} is a directory; {tag} has only files"
                for p in sorted(folder.iterdir()) if p.is_dir()]
    for name in sorted(set(paths) | here):
        if name not in here:
            problems.append(f"{folder.name}/{name} is missing but {tag} has it")
        elif name not in paths:
            problems.append(f"{folder.name}/{name} is not in {tag}")
        elif _git(repo, "show", f"{tag}:{paths[name]}").stdout != (folder / name).read_bytes():
            problems.append(f"{folder.name}/{name} differs byte for byte from {tag}")
    return problems


def _kept_problems(root):
    root = Path(root)
    pins = yaml.safe_load((ROOT / "tests" / "fixtures" / "preset-digests.yml")
                          .read_text(encoding="utf-8"))
    last = {}
    for key in pins:
        version = key.split("@", 1)[1]
        major = int(version.split(".")[0])
        if major not in last or tuple(map(int, version.split("."))) > last[major][0]:
            last[major] = (tuple(map(int, version.split("."))), key)
    live = yaml.safe_load((root / "governance/check-set.yml")
                          .read_text(encoding="utf-8"))["version"]
    live_major = int(str(live).split(".")[0])
    problems = []
    for major, (_, key) in sorted(last.items()):
        folder = root / "governance" / "presets" / f"default@{major}"
        if major >= live_major:
            continue
        if not folder.is_dir():
            problems.append(f"default@{major} was shipped and the live major is {live_major}, "
                            f"but {folder.name} is not kept")
            continue
        problems.extend(_digest_problems(folder, key, pins))
    for folder in sorted((root / "governance" / "presets").glob("default@*")):
        if int(folder.name.split("@")[1]) not in last:
            problems.append(f"{folder.name} is kept but no shipped version of it is pinned")
    return problems


def test_up_3_the_framework_keeps_every_earlier_major_it_has_shipped():
    assert _kept_problems(ROOT) == []


def test_up_3_the_kept_major_guard_fails_for_a_missing_or_changed_folder(tmp_path):
    base = _framework_root(tmp_path / "ok")
    assert _kept_problems(base) == []
    changed = _framework_root(tmp_path / "changed")
    path = changed / "governance/presets/default@6/approaches.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("subtask_ceiling: 2",
                                                            "subtask_ceiling: 9", 1),
                    encoding="utf-8")
    assert any("not the last preset" in p for p in _kept_problems(changed))
    missing = _framework_root(tmp_path / "missing")
    shutil.rmtree(missing / "governance/presets/default@6")
    assert any("is not kept" in p for p in _kept_problems(missing))


KEPT_6 = ROOT / "governance" / "presets" / "default@6"


KEPT_TAG = "v6.1.0"


KEPT_KEY = "default@6.0.0"


def _pins():
    return yaml.safe_load((ROOT / "tests" / "fixtures" / "preset-digests.yml")
                          .read_text(encoding="utf-8"))


def _fixture_kept(tmp_path):
    """A fixture framework (live default at 7.0.0) and its `default@6` folder."""
    base = _framework_root(tmp_path / "fw")
    return base, base / "governance" / "presets" / "default@6"


def test_trc_001_the_kept_default_6_folder_is_byte_identical_to_the_v6_1_0_tag():
    """Scenario id: `TRC-001` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    _require_tag(ROOT, KEPT_TAG)
    assert _byte_problems(KEPT_6, KEPT_TAG, ROOT) == []
    names = sorted(p.name for p in KEPT_6.iterdir())
    assert len(names) == 11 and "preset.yml" in names
    lines = (KEPT_6 / "preset.yml").read_text(encoding="utf-8").splitlines()
    assert "version: 6.0.0" in lines


def test_trc_002_the_kept_default_6_folder_matches_every_pinned_digest():
    """Scenario id: `TRC-002` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    pins = _pins()
    assert len(pins[KEPT_KEY]["files"]) == 11
    # Holds whatever major the live default has: the real folder, the real pins.
    assert _digest_problems(KEPT_6, KEPT_KEY, pins) == []


def test_trc_003_a_changed_value_in_the_kept_folder_is_reported_by_file(tmp_path):
    """Scenario id: `TRC-003` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    path = kept / "approaches.yml"
    text = path.read_text(encoding="utf-8")
    assert "subtask_ceiling: 2" in text
    path.write_text(text.replace("subtask_ceiling: 2", "subtask_ceiling: 9", 1),
                    encoding="utf-8")
    joined = "\n".join(_kept_problems(base))
    assert "approaches.yml" in joined and KEPT_KEY in joined
    for other in sorted(p.name for p in KEPT_6.iterdir()):
        if other != "approaches.yml":
            assert other not in joined, other


def test_trc_004_a_missing_file_in_the_kept_folder_is_reported(tmp_path):
    """Scenario id: `TRC-004` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    (kept / "vocabulary.yml").unlink()
    problems = _kept_problems(base)
    assert any("vocabulary.yml" in p for p in problems)
    assert any("not the last preset" in p and "vocabulary.yml" not in p for p in problems)


def test_trc_005_an_extra_file_in_the_kept_folder_is_reported(tmp_path):
    """Scenario id: `TRC-005` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    (kept / "extra.yml").write_text("schema: 1\n", encoding="utf-8")
    assert any("extra.yml" in p for p in _kept_problems(base))


def test_trc_006_a_comment_only_edit_passes_the_digest_check_and_fails_the_byte_check(
        tmp_path):
    """Scenario id: `TRC-006` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    _require_tag(ROOT, KEPT_TAG)
    copy_ = tmp_path / "default@6"
    shutil.copytree(KEPT_6, copy_)
    rules = copy_ / "rules.yml"
    rules.write_text("# a comment added later\n" + rules.read_text(encoding="utf-8"),
                     encoding="utf-8")
    assert _digest_problems(copy_, KEPT_KEY, _pins()) == []
    problems = _byte_problems(copy_, KEPT_TAG, ROOT)
    assert problems and all("rules.yml" in p for p in problems)


def test_trc_001_a_subdirectory_in_the_kept_folder_is_reported_by_name(tmp_path):
    """Scenario id: `TRC-001` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    assert KEPT_6.is_dir(), "governance/presets/default@6 does not exist"
    _require_tag(ROOT, KEPT_TAG)
    copy_ = tmp_path / "default@6"
    shutil.copytree(KEPT_6, copy_)
    (copy_ / "sub").mkdir()
    (copy_ / "sub" / "x.yml").write_text("schema: 1\n", encoding="utf-8")
    problems = _byte_problems(copy_, KEPT_TAG, ROOT)
    assert any("sub" in p for p in problems), problems


def _git_repo(path, monkeypatch):
    """An empty git repository at `path`, with no user or system git settings."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


def test_trc_007_the_byte_check_skips_when_no_release_tags_exist(tmp_path, monkeypatch):
    """Scenario id: `TRC-007` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    bare = _git_repo(tmp_path / "no-tags", monkeypatch)
    with pytest.raises(pytest.skip.Exception) as skipped:
        _require_tag(bare, KEPT_TAG)
    assert "v*" in str(skipped.value) and "tags" in str(skipped.value)
    # Not a git repository: git cannot read it, so the check skips too.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(pytest.skip.Exception):
        _require_tag(plain, KEPT_TAG)
    # Tags exist but the one the guard needs is missing: a failure, never a skip.
    other = _git_repo(tmp_path / "other-tag", monkeypatch)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit",
                    "-q", "--allow-empty", "-m", "x"], cwd=other, check=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=other, check=True)
    with pytest.raises(pytest.fail.Exception) as failed:
        _require_tag(other, KEPT_TAG)
    assert KEPT_TAG in str(failed.value)
    subprocess.run(["git", "tag", KEPT_TAG], cwd=other, check=True)
    assert _require_tag(other, KEPT_TAG) is None


def test_trc_010_with_the_live_default_at_major_7_a_faithful_kept_folder_raises_no_problem(
        tmp_path):
    """Scenario id: `TRC-010` in default-6-preset-for-7-0-0/acceptance-criteria.md"""
    base, kept = _fixture_kept(tmp_path)
    assert _digest_problems(kept, KEPT_KEY, _pins()) == []
    assert _kept_problems(base) == []


KEPT_7 = ROOT / "governance" / "presets" / "default@7"


KEPT_7_TAG = "v8.0.4"


KEPT_7_KEY = "default@7.0.0"


def test_the_kept_default_7_folder_is_byte_identical_to_the_v8_0_4_tag():
    assert KEPT_7.is_dir(), "governance/presets/default@7 does not exist"
    _require_tag(ROOT, KEPT_7_TAG)
    assert _byte_problems(KEPT_7, KEPT_7_TAG, ROOT) == []
    lines = (KEPT_7 / "preset.yml").read_text(encoding="utf-8").splitlines()
    assert "version: 7.0.0" in lines


def test_the_kept_default_7_folder_matches_every_pinned_digest():
    assert KEPT_7.is_dir(), "governance/presets/default@7 does not exist"
    pins = _pins()
    assert len(pins[KEPT_7_KEY]["files"]) == 11
    assert _digest_problems(KEPT_7, KEPT_7_KEY, pins) == []


def test_a_changed_value_in_the_kept_default_7_folder_is_reported(tmp_path):
    copy_ = tmp_path / "default@7"
    shutil.copytree(KEPT_7, copy_)
    path = copy_ / "checks.yml"
    path.write_text(path.read_text(encoding="utf-8").replace("severity: blocking",
                                                            "severity: advisory", 1),
                    encoding="utf-8")
    joined = "\n".join(_digest_problems(copy_, KEPT_7_KEY, _pins()))
    assert "checks.yml differs" in joined and KEPT_7_KEY in joined
