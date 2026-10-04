"""Every reference to the repository names its home, ayeo-io/compass.

The repository moved from a personal account to the ayeo-io organisation on
2026-10-04. GitHub redirects the old address, but an install instruction or
plugin manifest that names it would keep sending people through a redirect
that can break if the old name is ever reused.

Scenario id: RA-1 (issue `repoint-to-ayeo-io`).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = "jed72" + "/compass"   # assembled, so this file does not match itself


def test_ra_1_no_tracked_file_names_the_old_address():
    found = subprocess.run(["git", "grep", "-l", "-F", OLD], cwd=str(ROOT),
                           capture_output=True, text=True).stdout.split()
    # The derived living spec quotes landed issues' records as they were.
    found = [f for f in found if not f.startswith("docs/system-spec")]
    assert found == [], found


def test_ra_1_the_plugin_manifests_name_the_new_home():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["repository"] == "https://github.com/ayeo-io/compass"
    assert plugin["homepage"] == "https://github.com/ayeo-io/compass"
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert market["owner"]["url"] == "https://github.com/ayeo-io"
