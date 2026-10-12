"""Shared fixtures for the issue page, project index and whole-archive tests (issue
`documents-carry-judgement`, groups D to H).

Every project is a temporary git repository built by `rendered_blocks_support`.
No helper here reads or writes this checkout's own `.compass/work` or
`docs/compass` (DCJ-63).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rendered_blocks_support as sup  # noqa: E402
from rendered_blocks_support import DOCS, SLUG, WORK, add_records, manifest, run  # noqa: E402,F401

CREATED = sup.base.CREATED


def rb():
    from compass_pkg import rendered_blocks
    return rendered_blocks


def docs_of(slug, created=CREATED):
    return f"docs/compass/{created}-{slug}"


def work_of(root, slug):
    return Path(root) / ".compass" / "work" / slug


def add_issue(root, slug, created=CREATED, approach="regular", **fields):
    """A second issue in the project: its manifest only. The first render
    creates its page."""
    folder = work_of(root, slug)
    (folder / "evidence").mkdir(parents=True, exist_ok=True)
    body = {"schema_version": "2.0", "issue": slug, "created": created,
            "delivery_approach": approach,
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "medium", "goal": "delivery", "role": "engineer",
                           "labels": []},
            "evidence": []}
    body.update(fields)
    (folder / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return folder


def close_issue(root, slug, when="2026-10-05T10:00:00+00:00", reason="completed", **fields):
    """Mark an added issue done."""
    body = yaml.safe_load((work_of(root, slug) / "manifest.yml").read_text(encoding="utf-8"))
    body.update({"status": "done", "close_reason": reason, "land_timestamp": when,
                 "gates": [{"id": f"verify.g{n}", "status": "pass", "evidence": []}
                           for n in range(3)]})
    body.update(fields)
    (work_of(root, slug) / "manifest.yml").write_text(
        yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def set_fields(root, slug, **fields):
    path = work_of(root, slug) / "manifest.yml"
    body = yaml.safe_load(path.read_text(encoding="utf-8"))
    body.update(fields)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def page(root, slug=SLUG, created=CREATED):
    return Path(root) / docs_of(slug, created) / "README.md"


def blocks(path):
    """`[(kind, [interior lines])]` of the document at `path`."""
    text = Path(path).read_bytes().decode("utf-8")
    found = rb().parse(text, str(path))
    return [(b.kind, [x.rstrip("\r\n") for x in found.lines[b.start + 1:b.end]])
            for b in found.blocks]


def block(path, kind):
    for name, lines in blocks(path):
        if name == kind:
            return lines
    raise AssertionError(f"{path} has no {kind} block: {[k for k, _ in blocks(path)]}")


def text_of(path):
    return Path(path).read_text(encoding="utf-8")


def render_all(root, *extra):
    return run(root, "issue", "render", "--all", *extra)


def full_issue(tmp_path):
    """A regular issue with intent.md, three scenarios of which two have passed,
    one depends_on link, one raised_by link, two design decisions and one
    decision taken."""
    root = sup.rich_issue(tmp_path)
    add_records(root, **{"green-TRC-2": "TRC-2"})
    docs = Path(root) / DOCS
    (docs / "intent.md").write_text(
        "# Intent - feature\n\n## Problem\n\nPeople cannot find the state.\n\n"
        "## Desired outcome\n\nOne page shows it.\n\n"
        "## Success signals\n\n- The page opens first.\n\n"
        "## Constraints\n\nNone.\n\n## Non-goals\n\n- No new dependency.\n", encoding="utf-8")
    (docs / "technical-design.md").write_text(
        "# Plan\n\n## 6. Design decisions\n\n### `DD-1` - One module owns the grammar\n\n"
        "- **Context:** a thing.\n- **Governance tie:** ADR-049.\n\n"
        "### `DD-2` - A second choice\n\n- **Scope:** project\n- **Context:** another.\n",
        encoding="utf-8")
    add_issue(root, "base-work")
    add_issue(root, "origin-work")
    body = manifest(root)
    body["depends_on"] = ["base-work"]
    body["raised_by"] = {"issue": "origin-work", "found_at": "verify"}
    sup.base.write_manifest(root, body)
    return root


def environment(tmp_path):
    """The CI conditions: no global git identity."""
    return {"HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
