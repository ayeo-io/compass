"""Where the tests that read the issue archive find it.

Compass keeps each issue's records out of git, so a test that read the
local archive skipped in CI and gave a result that depended on the machine.
By default those tests read a tracked, scrubbed sample of real issues,
`tests/fixtures/archive-sample.tar.gz`, built by
`scripts/build-archive-sample.py`. With `COMPASS_FULL_ARCHIVE=1` they read
this checkout's own archive instead: every local issue, which a release run
should check.

The sample is unpacked once into `.compass/archive-sample-cache/`, which is
ignored. It stays inside the repository because some checks ask git about
the commits an issue names, and under `.compass/` because the tests that
walk the repository's files already leave that folder out.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_ARCHIVE = REPO_ROOT / "tests" / "fixtures" / "archive-sample.tar.gz"
CACHE = REPO_ROOT / ".compass" / "archive-sample-cache"

#: The switch, and the reason a test that needs the real archive gives
#: when it is off.
FULL_ARCHIVE = "COMPASS_FULL_ARCHIVE"
NEEDS_FULL_ARCHIVE = ("reads every issue in this checkout's own archive; set "
                      "COMPASS_FULL_ARCHIVE=1 to run it, as a release does")


def full_archive():
    """Is the switch on?"""
    return os.environ.get(FULL_ARCHIVE) == "1"


def sample_root():
    """The unpacked sample: a project root holding `.compass/work/` and
    `docs/compass/`. Unpacked once per version of the archive file; parallel
    test workers race safely, because each unpacks into its own folder and
    only the first rename wins."""
    digest = hashlib.sha256(SAMPLE_ARCHIVE.read_bytes()).hexdigest()[:16]
    target = CACHE / digest
    if target.is_dir():
        return target
    CACHE.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=CACHE, prefix="unpacking-"))
    with tarfile.open(SAMPLE_ARCHIVE) as tar:
        for member in tar.getmembers():
            # Only plain files with paths inside the folder: the archive is
            # tracked data, but an unpacker that trusts names is a hole.
            if not member.isfile() or member.name.startswith(("/", "..")) \
                    or "/../" in member.name:
                raise ValueError(f"unexpected entry in the sample: {member.name}")
        tar.extractall(staging)
    try:
        os.rename(staging, target)
    except OSError:
        shutil.rmtree(staging, ignore_errors=True)
        if not target.is_dir():
            # Not another worker winning the race: fail loudly, because a
            # test that returns early on a missing folder would pass on it.
            raise
    return target


def archive_root():
    """The project root whose `.compass/work/` and `docs/compass/` the
    archive tests read: the sample, or this checkout with the switch on."""
    return REPO_ROOT if full_archive() else sample_root()
