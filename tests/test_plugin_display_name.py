"""The plugin carries the name, author and description chosen for its listing.

The maintainer chose, for the plugin directory listing: keep the name
`compass` (it is the command prefix), display it as "Compass", and credit the
organisation as `ayeo`, lower case as the brand writes it, with its site. The
homepage is the Compass section of that site. The Claude Code plugin, its
marketplace entry and the Codex plugin carry one description, so the listings
do not drift apart. Claude Code's strict plugin check, which rejects unknown
fields, accepts every field here.

Scenario ids: the listing name and author is PN-1 (issue
`plugin-display-name`), and the shared description with the findable
marketplace entry is `TRC-001` (issue `listing-copy`).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _manifests():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    entry = next(p for p in market["plugins"] if p["name"] == "compass")
    codex = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    return plugin, market, entry, codex


def test_pn_1_the_manifests_carry_the_listing_name_and_author():
    plugin, _, entry, _ = _manifests()
    assert plugin["name"] == "compass"
    assert plugin["displayName"] == "Compass"
    for manifest in (plugin, entry):
        assert manifest["author"] == {"name": "ayeo", "url": "https://ayeo.io"}
        assert manifest["homepage"] == "https://ayeo.io/#compass"


def test_trc_001_the_listings_share_one_description():
    plugin, market, entry, codex = _manifests()
    text = plugin["description"]
    assert text.startswith("Enough process for the work at hand. No more."), text
    assert entry["description"] == text
    assert codex["description"] == text
    assert market["metadata"]["description"] == "Adaptive spec-driven development for Claude Code."


def test_trc_001_the_marketplace_entry_is_findable():
    plugin, _, entry, _ = _manifests()
    assert entry["category"] == "development"
    assert entry["repository"] == plugin["repository"]
    for word in ("specs", "planning", "testing", "code-review"):
        assert word in plugin["keywords"], word
    assert entry["keywords"] == plugin["keywords"]
    assert entry["tags"]


def test_trc_001_the_listing_names_its_privacy_terms_and_support_pages():
    """The directory's listing step shows "Not set" for each link the
    manifest leaves out. The pages are on ayeo.io, with the trailing slash:
    without it each address answers with a redirect."""
    plugin, _, _, _ = _manifests()
    assert plugin["privacyPolicyUrl"] == "https://ayeo.io/privacy/"
    assert plugin["termsOfServiceUrl"] == "https://ayeo.io/terms/"
    assert plugin["supportUrl"] == "https://ayeo.io/support/"
