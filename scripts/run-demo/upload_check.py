"""The demo project's test. scripts/run-demo.sh copies it to tests/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from upload import size_error


def test_the_error_names_the_limit_in_megabytes():
    assert size_error(30) == "Upload too large: the limit is 25 MB."


def test_a_file_within_the_limit_has_no_error():
    assert size_error(10) is None
