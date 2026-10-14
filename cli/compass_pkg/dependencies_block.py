# compass_pkg.dependencies_block - the `dependencies` rendered block
"""The block that lists an issue's `depends_on` entries in the design's Risks and dependencies.

This module registers the kind with a fixed placeholder line so the design template's
marker pair parses. The renderer that reads `depends_on` through `lifecycle` replaces it.
"""
# DEPENDENCY: compass_pkg.render_inputs; block_renderers registers RENDERERS through _add_modules.
from __future__ import annotations

from compass_pkg.render_inputs import CROSS, Part

PLACEHOLDER = "Dependencies not rendered yet."


def dependencies(inputs, doc_rel):
    return Part(CROSS, [PLACEHOLDER])


RENDERERS = {"dependencies": dependencies}
