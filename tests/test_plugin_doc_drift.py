"""Acceptance tests for issue fix-plugin-doc-drift.

Each test_trc_* function asserts the fix for one scenario: the plugin install
path no longer needs a separate PyYAML step, and the shipped docs must say
so. The "production" change is text in README.md, AGENTS.md, and docs/*.md,
so these tests are grep/regex assertions over the published doc files.

Why this file exists separate from the rest of tests/: the existing test
suite defends the CLI's safety contract (see tests/README.md). These tests
defend a one-off documentation fix. They are still real tests - they run
under `pytest tests/`, they fail when the docs drift, and `compass tdd-red`
/ `compass tdd-green` write typed test-run evidence the verify gates accept.
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text()


# ---------------------------------------------------------------------------
# Group A - install-surface accuracy (D1)
# ---------------------------------------------------------------------------

def test_trc_a1_readme_source_install_has_path_note():
    """README's source-install paragraph tells the reader how to invoke the
    compass CLI - by adding bin/ to PATH or via `python3 cli/compass`."""
    readme = _read("README.md")

    # The source-install code block (clone -> bash install.sh). The block
    # ends at the install-script invocation.
    m = re.search(
        r"git clone https://github\.com/ayeo-io/compass\.git.*?"
        r"bash scripts/install\.sh --global",
        readme,
        re.DOTALL,
    )
    assert m, "Source-install code block not found in README.md"

    # Within 800 chars after the block, expect a CLI-invocation instruction.
    after = readme[m.end():m.end() + 800]
    has_path_note = bool(
        re.search(r"add\s+\S*bin\b[^.]*?\bPATH\b", after, re.IGNORECASE)
        or re.search(r"\bPATH\b[^.]*?\bbin\b", after)
        or re.search(r"python3\s+\S*cli/compass", after)
    )
    assert has_path_note, (
        "README's source-install paragraph does not tell the reader how to "
        "make `compass` invokable. Expected a phrase about adding `bin/` to "
        "PATH or invoking as `python3 cli/compass`. Looked in 800 chars "
        "following the source-install code block; got:\n"
        + after[:400]
    )


ON_PATH_CLAIM = re.compile(
    r"(?:puts|adds)\s+the\s+[`']?compass[`']?\s+CLI\s+(?:on|to)\s+your\s+path",
    re.IGNORECASE,
)


def _on_path_claims_about_install_sh(text):
    """Occurrences of "puts the compass CLI on your PATH" that are about install.sh.

    The plugin really does put the CLI on PATH, so the sentence is true when its
    subject is the plugin and false when its subject is install.sh. Matching the
    phrase alone cannot tell those apart, so this looks at what the sentence is
    talking about: the 200 characters before the claim.
    """
    found = []
    for m in ON_PATH_CLAIM.finditer(text):
        preceding = text[max(0, m.start() - 200):m.start()]
        if re.search(r"install\.sh", preceding) and not re.search(
            r"\bplugin\b", preceding[preceding.rfind("install.sh"):]
        ):
            found.append(text[max(0, m.start() - 120):m.end() + 60])
    return found


def test_trc_a2_quickstart_drops_install_sh_path_claim():
    """quickstart.md §1 must not claim install.sh changes PATH, and must
    explain how to invoke the CLI after a source install."""
    quickstart = _read("docs/quickstart.md")

    claims = _on_path_claims_about_install_sh(quickstart)
    assert not claims, (
        "quickstart.md claims install.sh puts the compass CLI on PATH. It does "
        "not; only the plugin install does.\nFound:\n" + "\n---\n".join(claims)
    )

    # And the disclaimer must be present, not merely the absence of the claim.
    assert re.search(
        r"install\.sh[^.]{0,80}does\s+\*{0,2}not\*{0,2}\s+change\s+your\s+PATH",
        quickstart, re.IGNORECASE,
    ), (
        "quickstart.md must say outright that install.sh does not change your "
        "PATH. Silence leaves a reader to assume it does, which is the "
        "misreading this test exists to prevent."
    )

    # And there must be a positive instruction about CLI invocation.
    has_invocation_note = bool(
        re.search(r"add\s+\S*bin\b[^.]*?\bPATH\b", quickstart, re.IGNORECASE)
        or re.search(r"\bPATH\b[^.]*?\bbin\b", quickstart)
        or re.search(r"python3\s+\$?\S*cli/compass", quickstart)
    )
    assert has_invocation_note, (
        "quickstart.md does not explain how to invoke the compass CLI after a "
        "source install. Expected a PATH note or a `python3 cli/compass` "
        "invocation hint."
    )


# ---------------------------------------------------------------------------
# Group B - adapter-layer file listings (D2)
# ---------------------------------------------------------------------------

def test_trc_b1_readme_tree_lists_bin_and_plugin_manifest():
    """README's 'What the repository contains' tree contains entries for
    bin/ and .claude-plugin/."""
    readme = _read("README.md")
    m = re.search(
        r"##\s+What the repository contains.*?(?=^##\s+|\Z)",
        readme,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "'What the repository contains' section not found in README.md"
    block = m.group(0)

    # The tree is the code block inside that section.
    code = re.search(r"```\n(.*?)\n```", block, re.DOTALL)
    assert code, "No fenced code block found in 'What's in the box'"
    tree = code.group(1)

    assert "bin/" in tree, "README's tree is missing the `bin/` entry"
    assert ".claude-plugin/" in tree, (
        "README's tree is missing the `.claude-plugin/` entry"
    )


def test_trc_b2_methodology_three_layers_names_bin_and_plugin_manifest():
    """methodology.md's adapter-layer paragraph names bin/compass and
    .claude-plugin/."""
    method = _read("docs/methodology.md")
    m = re.search(
        # Found by name, not section number, so renumbering does not break it.
        r"##\s+\d+\.\s+The three layers.*?(?=^##\s+\d+\.|\Z)",
        method,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "'The three layers' section not found in methodology.md"
    three_layers = m.group(0)
    assert "bin/compass" in three_layers, (
        "the methodology's three-layers section does not name `bin/compass` as "
        "an adapter-layer artifact"
    )
    assert ".claude-plugin/" in three_layers, (
        "the methodology's three-layers section does not name `.claude-plugin/` "
        "as an adapter-layer artifact"
    )


def test_trc_b3_portability_adapter_block_and_mapping_table():
    """portability.md's adapter-layer block lists bin/ and .claude-plugin/,
    and the mapping table has a row for the install surface."""
    port = _read("docs/portability.md")

    # The adapter-layer block - the fenced code listing that starts with
    # `commands/` and lists agents/, skills/, hooks/, etc.
    m = re.search(
        r"###\s+The Claude Code adapter layer.*?(?=^###\s|\Z)",
        port,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "'The Claude Code adapter layer' section not found in portability.md"
    adapter_section = m.group(0)
    code = re.search(r"```\n(.*?)\n```", adapter_section, re.DOTALL)
    assert code, "No fenced adapter-layer code block found in portability.md"
    block = code.group(1)
    assert "bin/" in block, "portability.md adapter-layer block missing `bin/`"
    assert ".claude-plugin/" in block, (
        "portability.md adapter-layer block missing `.claude-plugin/`"
    )

    # And there must be a mapping-table row about the install surface. The
    # row must reference the plugin shim or manifest.
    has_install_row = bool(
        re.search(r"\|\s*Install surface\s*\|", port, re.IGNORECASE)
        or (
            re.search(r"\|[^|\n]*bin/compass[^|\n]*\|", port)
            and re.search(r"\.claude-plugin", port)
        )
    )
    assert has_install_row, (
        "portability.md's mapping table does not have a row for the install "
        "surface. Expected either an explicit `| Install surface |` row, or a "
        "row mentioning `bin/compass` and `.claude-plugin/`."
    )


# ---------------------------------------------------------------------------
# Group C - runtime-neutral path string (D3)
# ---------------------------------------------------------------------------

def test_trc_c1_agents_uses_compass_prefix():
    """AGENTS.md's State on disk section uses .compass/work/<issue-slug>/ (not
    the unprefixed work/<issue-slug>/)."""
    agents = _read("AGENTS.md")
    m = re.search(
        r"##\s+State on disk.*?(?=^##\s+|\Z)",
        agents,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "'State on disk' section not found in AGENTS.md"
    section = m.group(0)
    assert ".compass/work/<issue-slug>/" in section, (
        "AGENTS.md State on disk does not use the `.compass/work/<issue-slug>/` form"
    )
    bare = re.search(r"(?<!\.compass/)\bwork/<issue-slug>/", section)
    assert bare is None, (
        "AGENTS.md State on disk still contains the unprefixed "
        "`work/<issue-slug>/` form (must be `.compass/work/<issue-slug>/`)"
    )


# ---------------------------------------------------------------------------
# Failure-mode coverage - no half-fix (F1)
# ---------------------------------------------------------------------------

def test_trc_f1_no_half_fix_misleading_phrases_removed():
    """No file contains its specific misleading phrase about install.sh and PATH."""
    quickstart = _read("docs/quickstart.md")
    bad_quickstart = _on_path_claims_about_install_sh(quickstart)
    assert not bad_quickstart, (
        "quickstart.md attributes the on-PATH behaviour to install.sh. Only "
        "the plugin install does that.\nFound:\n" + "\n---\n".join(bad_quickstart)
    )

    agents = _read("AGENTS.md")
    m = re.search(
        r"##\s+State on disk.*?(?=^##\s+|\Z)",
        agents,
        re.DOTALL | re.MULTILINE,
    )
    if m:
        bare = re.search(r"(?<!\.compass/)\bwork/<issue-slug>/", m.group(0))
        assert bare is None, (
            "AGENTS.md State on disk still has the unprefixed work/<issue-slug>/"
        )
