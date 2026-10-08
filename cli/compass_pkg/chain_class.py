# compass_pkg.chain_class - classify a git parent chain against the shipped default
"""The classification a generation stores for each git parent (ADR-037).

`classify_chain` merges the shipped default and then each git parent, furthest
first, and classifies the shipped default against the result after each
parent. The block for a parent therefore says what the chain through that
parent owes compared with the shipped default.

The classification is the raw one, before any waiver. A parent's own waivers
were approved by the parent's maintainers, which tells a project that extends
the parent nothing, so the stored result does not use them. This is the one
function a caller needs; it reads no file and runs no git.
"""
# DEPENDENCY: compass_pkg.classify, merge.
from __future__ import annotations

from compass_pkg import classify, merge


def _capabilities(docs):
    """The capability switches that are on after `docs`; a later layer
    overrides an earlier one."""
    state = {}
    for doc in docs:
        state.update(doc.get("capabilities") or {})
    return tuple(sorted(name for name, on in state.items() if on is True))


def _block(against, got):
    """The stored block: the verdict, the grid size, and the first assessment
    at which the chain owes less, or None."""
    shown = got.to_json()
    first = shown["first_looser"]
    return {
        "against": against,
        "result": shown["result"],
        "points": shown["grid"]["points"],
        "raw_points": shown["grid"]["raw_points"],
        "complete": shown["complete"],
        "first_looser": None if first is None else {
            "assessment": first["assessment"], "summary": first["summary"]},
    }


def classify_chain(shipped, git_parents, against):
    """One block for each layer of `git_parents` (root first), in order.
    `shipped` is the layer under them and `against` names it in each block,
    such as `compass:default@6`. Raises what `merge.apply` and `classify`
    raise; the chain was merged once already, so a failure is a real fault."""
    base, provenance = merge.apply({}, shipped.doc, shipped.kind, shipped.name, {})
    base_capabilities = _capabilities([shipped.doc])
    config, docs, out = base, [shipped.doc], []
    for layer in git_parents:
        config, provenance = merge.apply(config, layer.doc, layer.kind, layer.name, provenance)
        docs.append(layer.doc)
        got = classify.classify(base, config, parent_capabilities=base_capabilities,
                                child_capabilities=_capabilities(docs),
                                parent_name=against, child_name=layer.name)
        out.append(_block(against, got))
    return out
