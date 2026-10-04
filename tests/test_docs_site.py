"""Compass's main documents are published as a site, from the same files.

The site at https://docs.ayeo.io/compass/ is built by MkDocs Material from
pages in `docs/`, so every page stays under the repository's tests and its
pull-request rule; the build tool runs in CI only (#393).

Scenario id: DS-1 (issue `docs-site`).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CORE = ("five-minutes.md", "quickstart.md", "safety-contract.md",
        "refusal-codes.md", "methodology.md")


def _config():
    # MkDocs YAML may hold python tags for extensions; this config holds none.
    return yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))


def _nav_pages(nav):
    for item in nav:
        for value in (item.values() if isinstance(item, dict) else [item]):
            if isinstance(value, list):
                yield from _nav_pages(value)
            else:
                yield value


def test_ds_1_the_site_lists_the_core_pages_and_each_exists():
    config = _config()
    assert config["site_url"] == "https://docs.ayeo.io/compass/"
    assert config["docs_dir"] == "docs"
    pages = list(_nav_pages(config["nav"]))
    for core in CORE:
        assert core in pages, core
    for page in pages:
        assert (ROOT / "docs" / page).is_file(), page


def test_ds_1_every_relative_link_stays_inside_the_site():
    pages = set(_nav_pages(_config()["nav"]))
    for page in pages:
        text = (ROOT / "docs" / page).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#\s]+)", text):
            if re.match(r"[a-z]+:", target):
                continue
            assert target in pages, f"{page} links to {target}, not in the site"


def test_ds_1_the_build_is_pinned_and_publishes_from_main_only():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "docs.yml")
                              .read_text(encoding="utf-8"))
    text = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert re.search(r"mkdocs-material==\d+\.\d+\.\d+", text)
    assert "mkdocs build --strict" in text
    deploy = workflow["jobs"]["deploy"]
    assert "refs/heads/main" in deploy["if"]
    for line in re.findall(r"uses:\s*(\S+)", text):
        assert re.search(r"@[0-9a-f]{40}$", line), f"{line} is not pinned by SHA"
