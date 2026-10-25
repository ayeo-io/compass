"""`compass record sync` pushes to the delivery record's repository.

The private repository was renamed from compass-delivery-record to
compass-delivery. GitHub redirects the old name, but a redirect can be taken
by a new repository of that name, so the setting names the current one.

The single scenario, `TRC-001`, is in record-remote-rename/delivery-approach.md.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_record_remote_names_the_renamed_repository():
    """Scenario `TRC-001`: the remote names ayeo-io/compass-delivery."""
    settings = yaml.safe_load((ROOT / "compass.yml").read_text(encoding="utf-8"))
    assert settings["record"]["remote"] == "https://github.com/ayeo-io/compass-delivery.git"
