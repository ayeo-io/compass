"""`TRC-F6` - the distributed plugin actually contains the bundled copy.

The working tree is not the artifact. This repository has already shipped a
tarball missing files it contained once (`examples/<x>/.compass/work/` was
silently stripped by a BSD-tar exclude bug) - `scripts/release.sh`'s
examples-integrity check exists because of it. Under bundling, the same class
of miss would turn every install back into the exact "PyYAML required" error
this issue removes. This test exercises the real selection logic
(`release_file_list()`, sourced unmodified from `scripts/release.sh`)
against a real git index: it tars exactly what it selects, unpacks that
tarball somewhere clean, and reaches its first assessment from there on a
genuinely bare interpreter.

`release_file_list()` selects from `git ls-files`, so a temporary clone
holding everything this repository has on disk - tracked and
not-yet-tracked alike - committed into a fresh index lets the real,
unmodified function answer honestly, rather than a copy of its logic.
"""
from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
RELEASE_SH = FRAMEWORK_ROOT / "scripts" / "release.sh"

REQUIRED_VENDOR_PATHS = (
    "cli/vendor/yaml/__init__.py",
    "cli/vendor/LICENSE-PyYAML",
    "THIRD-PARTY-NOTICES.md",
)


def _git(cwd, *args, **kw):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True, **kw)


@pytest.fixture(scope="module")
def source_clone(tmp_path_factory):
    """A fresh git repository holding everything this repository's working
    tree now has - tracked (with any uncommitted edits) and untracked-
    but-not-ignored alike - so `release_file_list()` can be run for real
    against a committed index that matches what the implement stage
    produced, without staging or committing anything in the real
    repository."""
    clone_dir = tmp_path_factory.mktemp("release-source-clone")

    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=str(FRAMEWORK_ROOT), capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    for rel in listing:
        src = FRAMEWORK_ROOT / rel
        if not src.is_file():
            continue
        dst = clone_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())

    _git(clone_dir, "init", "-q")
    _git(clone_dir, "config", "user.email", "t@example.com")
    _git(clone_dir, "config", "user.name", "t")
    _git(clone_dir, "add", "-A")
    _git(clone_dir, "commit", "-q", "-m", "snapshot of the working tree under test")
    return clone_dir


def _release_file_list(clone_dir: Path) -> list[str]:
    driver = (
        f'set -eu\n'
        f'. "{RELEASE_SH}" --source-only\n'
        f'cd "{clone_dir}"\n'
        f'release_file_list\n'
    )
    r = subprocess.run(["bash", "-c", driver], capture_output=True, text=True)
    assert r.returncode == 0, f"release_file_list failed:\n{r.stdout}\n{r.stderr}"
    return [l.strip().lstrip("./") for l in r.stdout.splitlines() if l.strip()]


def test_release_sh_refuses_a_tarball_missing_the_vendored_copy():
    """`vendor_integrity_missing()` in scripts/release.sh, sourced for real:
    a tarball listing missing the vendored copy is flagged; a complete one
    is not. This is the hard-fail release.sh does next to its existing
    examples-integrity check - factored into a sourceable function so this
    one `grep` can be driven red-to-green without running a full
    `make release`."""
    driver_missing = (
        f'set -eu\n'
        f'. "{RELEASE_SH}" --source-only\n'
        f'fake_listing="compass-9.9.9/README.md\\ncompass-9.9.9/cli/compass"\n'
        f'vendor_integrity_missing "$(printf \'%b\' "$fake_listing")" "9.9.9"\n'
    )
    r = subprocess.run(["bash", "-c", driver_missing], capture_output=True, text=True)
    assert r.returncode == 0, f"vendor_integrity_missing itself errored:\n{r.stdout}{r.stderr}"
    for expected in REQUIRED_VENDOR_PATHS:
        assert expected in r.stdout, (
            f"a tarball listing missing {expected} was not flagged:\n{r.stdout}")

    fake_complete = "\\n".join(
        f"compass-9.9.9/{p}" for p in REQUIRED_VENDOR_PATHS
    ) + "\\ncompass-9.9.9/README.md"
    driver_complete = (
        f'set -eu\n'
        f'. "{RELEASE_SH}" --source-only\n'
        f'fake_listing="{fake_complete}"\n'
        f'vendor_integrity_missing "$(printf \'%b\' "$fake_listing")" "9.9.9"\n'
    )
    r2 = subprocess.run(["bash", "-c", driver_complete], capture_output=True, text=True)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert r2.stdout.strip() == "", (
        f"a complete tarball listing was flagged as missing something: {r2.stdout!r}")


def test_the_packaged_plugin_contains_the_bundled_copy(source_clone, bare_interpreter, tmp_path):
    paths = _release_file_list(source_clone)

    missing = [p for p in REQUIRED_VENDOR_PATHS if p not in paths]
    assert not missing, (
        f"the vendored PyYAML copy is not in the release file list: {missing}\n"
        f"(release_file_list() selects from git ls-files - a file that is not "
        f"tracked never ships)"
    )

    # Tar exactly what the real function selected, unpack it somewhere clean.
    unpack_dir = tmp_path / "unpacked"
    unpack_dir.mkdir()
    tar_path = tmp_path / "release.tar"
    with tarfile.open(tar_path, "w") as tf:
        for rel in paths:
            full = source_clone / rel
            if full.is_file():
                tf.add(full, arcname=rel)
    with tarfile.open(tar_path, "r") as tf:
        tf.extractall(unpack_dir)

    for rel in REQUIRED_VENDOR_PATHS:
        assert (unpack_dir / rel).is_file(), (
            f"{rel} was selected but did not survive tar/untar")

    # First assessment from the unpacked tree, on a genuinely bare interpreter
    # - the distributed artifact, not the working tree, is what has to work.
    cli_path = unpack_dir / "cli" / "compass"
    assert cli_path.is_file(), "cli/compass missing from the unpacked release"

    project = tmp_path / "project"
    gov_dst = project / "governance"
    gov_dst.mkdir(parents=True)
    for name in ("routing-policy.yml", "guardrails.yml"):
        (gov_dst / name).write_bytes((unpack_dir / "governance" / name).read_bytes())
    (project / ".compass" / "work").mkdir(parents=True)
    (project / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")

    slug = "released-issue"
    task_dir = project / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    import yaml as _yaml_for_fixture_only  # test-harness use only; not the CLI's own import path
    with (task_dir / "manifest.yml").open("w", encoding="utf-8") as fh:
        _yaml_for_fixture_only.safe_dump({
            "task": slug, "created": "2026-08-10",
            "assessment": {"risk": "contained", "familiarity": "greenfield",
                          "size": "small", "goal": "delivery"},
        }, fh, sort_keys=False)

    env = bare_interpreter.env()
    result = subprocess.run(
        [str(bare_interpreter.python_path), str(cli_path),
         "approach", "evaluate", "--issue", slug, "--write",
         "--justify", "risk=A fixture.", "--justify", "familiarity=A fixture.",
         "--justify", "size=A fixture.", "--justify", "goal=A fixture."],
        cwd=str(project), capture_output=True, text=True, env=env, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    combined = (result.stdout + result.stderr).lower()
    assert "pip install pyyaml" not in combined, combined
    assert "is required but not installed" not in combined, combined
    assert (task_dir / "manifest.yml").is_file()
