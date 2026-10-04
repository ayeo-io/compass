"""Each worker scans its terminology samples in a folder of its own.

`_scan_text` in `tests/test_terminology.py` wrote samples under one fixed
folder and removed it afterwards, so under `pytest -n 8` one worker removed
the folder another was writing into, and the file failed at random (#371).

Scenario id: TV-1 (issue `terminology-test-shares-a-folder`).
"""
from __future__ import annotations

import os

import test_terminology


def test_tv_1_the_sample_folder_is_this_process_own():
    holder = test_terminology._sample_holder()
    assert str(os.getpid()) in holder.name
    assert holder.parent == test_terminology.REPO_ROOT
    assert holder.name.startswith(".")
