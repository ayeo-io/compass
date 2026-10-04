"""The plugin carries the display name and author chosen for its listing.

The maintainer chose, for the plugin directory listing: keep the name
`compass` (it is the command prefix), display it as "Compass Adaptive
Spec-Driven Development", and credit the organisation, ayeo.io. Claude
Code's strict plugin check, which rejects unknown fields, accepts both.

Scenario id: PN-1 (issue `plugin-display-name`).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pn_1_the_manifests_carry_the_listing_name_and_author():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert plugin["name"] == "compass"
    assert plugin["displayName"] == "Compass Adaptive Spec-Driven Development"
    assert plugin["author"]["name"] == "ayeo.io"
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "compass")
    assert entry["author"]["name"] == "ayeo.io"
