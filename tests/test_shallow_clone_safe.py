"""The suite means the same thing on a shallow clone as on a full one.

Two tests assert what their own issue did by diffing a pinned commit range.
`actions/checkout` fetches shallow history by default, so those objects are
absent in continuous integration and `git diff` exits 128 - green on every
developer machine, and fails only in CI.

The range check can skip when the history is absent. The content assertion
beside it must not skip: it needs no history and carries the invariant that
matters now.

Scenario ids: see the issue's acceptance criteria (TRC-1).
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The two assertions that pin a commit range.
SHA_PINNED = [
    ("tests/test_human_voice.py", "trc_f3"),
    ("tests/test_voice_audition_standing.py", "trc_f1"),
]


@pytest.fixture(scope="module")
def shallow_clone(tmp_path_factory):
    """A depth-one checkout of the current commit - the shape CI works in.

    Built by init-and-fetch rather than `git clone -b <branch>`, because a
    pull-request checkout is a detached HEAD: there is no branch name to ask
    for, and `rev-parse --abbrev-ref HEAD` answers the literal string "HEAD".
    Fetching the commit sidesteps branch names altogether.

    Fails rather than skips if the shallow checkout cannot be built: a test
    that quietly stops proving the thing it exists to prove is how the defect
    it guards reached CI in the first place.
    """
    dest = tmp_path_factory.mktemp("shallow") / "repo"
    dest.mkdir()

    def run(*args, **kw):
        return subprocess.run(args, cwd=str(kw.pop("cwd", dest)),
                              capture_output=True, text=True, **kw)

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()

    init = run("git", "init", "-q")
    assert init.returncode == 0, f"git init failed:\n{init.stderr}"
    fetch = run("git", "fetch", "--depth", "1", "-q", f"file://{REPO_ROOT}", head)
    assert fetch.returncode == 0, (
        f"could not fetch {head[:8]} at depth 1, so the shallow-history claim "
        f"is unproven:\n{fetch.stderr}"
    )
    checkout = run("git", "checkout", "-q", "FETCH_HEAD")
    assert checkout.returncode == 0, f"checkout failed:\n{checkout.stderr}"

    # Precondition: the history really is absent. A full one would make every
    # assertion below empty.
    assert (dest / ".git" / "shallow").exists(), (
        "the checkout is not shallow - nothing below proves anything"
    )

    # Overlay the working tree's tests over the fetched ones. The fetch can
    # only carry committed state, so without this the test would report on the
    # last commit rather than on the code in front of us - it could never go
    # green before the fix was committed, which is the wrong way round. The
    # shallow *history* is what matters here, not the committed test bodies.
    for src in (REPO_ROOT / "tests").glob("*.py"):
        shutil.copyfile(src, dest / "tests" / src.name)
    return dest


@pytest.mark.parametrize("test_file,selector", SHA_PINNED)
def test_the_pinned_assertions_run_on_a_shallow_clone(shallow_clone, test_file, selector):
    """They can skip their range check; they must not fail on a missing
    object."""
    result = subprocess.run(
        ["python3", "-m", "pytest", test_file, "-k", selector, "-q"],
        cwd=str(shallow_clone), capture_output=True, text=True, timeout=300,
    )
    combined = result.stdout + result.stderr
    assert "CalledProcessError" not in combined, (
        f"{test_file} died on a missing git object instead of degrading:\n"
        f"{combined[-2000:]}"
    )
    assert result.returncode == 0, (
        f"{test_file} -k {selector} failed on a shallow clone:\n"
        f"{combined[-2000:]}"
    )
