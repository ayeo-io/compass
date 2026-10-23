"""`plugin.json` names the plugin's icon, in the shape the plugin directory accepts.

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
