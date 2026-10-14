# compass_pkg.header_block - the `document-header` rendered block
"""The block that opens every catalogue document written from a template.

This module registers the kind with a fixed placeholder line so the templates'
marker pairs parse. The renderer that reads the facts of the header from the
records replaces it.
"""
# DEPENDENCY: compass_pkg.render_inputs; block_renderers registers RENDERERS through _add_modules.
from __future__ import annotations

from compass_pkg.render_inputs import OWN, Part

PLACEHOLDER = "Header not rendered yet."


def document_header(inputs, doc_rel):
    return Part(OWN, [PLACEHOLDER])


RENDERERS = {"document-header": document_header}
