"""`plugin.json` names the plugin's icon, in the shape the plugin directory
accepts, and the README header shows the icon beside the name.

The directory takes the listing icon from the `icon` field the first time the
plugin is submitted, and never again, so a missing or rejected icon cannot be
fixed later. Its validator accepts a square PNG or JPEG inside the plugin, 512
to 2048 px on each side and under 2 MB; SVG and WebP are refused.

Scenario id: `TRC-001`.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_size(path):
    head = path.read_bytes()[:24]
    assert head[:8] == PNG_SIGNATURE, f"{path} is not a PNG"
    return struct.unpack(">II", head[16:24])


def test_trc_001_plugin_json_names_a_square_png_icon_the_directory_accepts():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert "icon" in manifest, "plugin.json has no icon field"
    icon = (ROOT / manifest["icon"]).resolve()
    assert icon.is_relative_to(ROOT), icon
    assert icon.is_file(), icon
    width, height = _png_size(icon)
    assert width == height, (width, height)
    assert 512 <= width <= 2048, width
    assert icon.stat().st_size < 2 * 1024 * 1024, icon.stat().st_size


def test_trc_001_readme_header_shows_the_icon_beside_the_name():
    # GitHub markdown cannot size text to match an image, so the header is one
    # image per theme: the icon tile with the name outlined beside it.
    head = (ROOT / "README.md").read_text(encoding="utf-8").split("\n\n", 1)[0]
    assert head.startswith("<h1>"), head
    for theme in ("light", "dark"):
        name = f"assets/compass-header-{theme}.svg"
        assert name in head, name
        svg = (ROOT / name).read_text(encoding="utf-8")
        assert 'aria-label="Compass"' in svg, name
        assert 'fill="#0E3A5F"' in svg, f"{name} has no navy icon tile"
