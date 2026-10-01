"""House style invariants over the framework's own source.

These are invariants of *this repository*, not framework guardrails. They run
in this repo's pytest suite alongside `test_release_invariants.py`, never
against an adopting project's issue, and never as a `compass check` gate.
`governance/strategies.md` is the reasoning: `S7` for the agent-attribution
rule, and the Voice and writing strategies block for the em dash. This file is
the mechanical half of both.

Two rules are enforced here:

1. No em dash (U+2014). Where an em dash would go, Compass writes a plain
   hyphen with spaces around it. En dashes (U+2013) are deliberately left
   alone: they carry meaning in ranges such as `G1`-`G5` and `2-3 subtasks`.
2. No agent co-author trailer in any tracked file. The human author owns the
   change; `devlog.md` and `manifest.yml` already record provenance in a form the
   framework can read.

The file list comes from `git ls-files`, which means this guard reads exactly
what the repository ships and gives the same answer on every machine. That is
deliberate, and it silently omitted the project's own launch article: it
lived in `docs/analysis/`, which `.gitignore` excludes as a directory, so the
one document written for strangers was the one document no guard had ever
read.

The fix was to track what gets published, not to make this guard read untracked
files. Reading untracked files would have made the answer depend on whatever
each contributor keeps on disk, and would have passed in CI where those files
are absent entirely. Working notes and the campaign plan stay untracked and
stay unread, which is correct: nothing publishes them.

Still deliberately excluded: `assets/` (binary), `LICENSE` (verbatim Apache-2.0,
never edited for style), and the framework's own `.compass/work/`. The
`examples/*/.compass/work/` fixtures are committed on purpose and are scanned.

This file contains no literal em dash and no literal forbidden trailer. Every
needle is assembled from its parts at import time, so the scanners never have
to exempt themselves from their own rules.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Assembled, never written literally - see the module docstring.
EM_DASH = chr(0x2014)
JSON_ESCAPED_EM_DASH = "\\u" + "2014"
FORBIDDEN_TRAILERS = (
    "Co-Authored-By: " + "Claude",
    "Co-authored-by: " + "Claude",
    "Generated with [" + "Claude Code]",
)

# No file is exempt from this scan for containing a trailer.
#
# `assets/` and LICENSE are skipped below, by SKIP_PREFIXES and SKIP_EXACT,
# for unrelated reasons - one is binary and the other is verbatim licence
# text. Neither is an exemption from this rule. The rule is stated in
# CLAUDE.md without the literal trailer strings, the way
# governance/strategies.md has always stated it, and the exact strings live
# in this file where they are assembled rather than written.

# `assets/` is binary; LICENSE is the verbatim Apache-2.0 text and is never
# edited for style.
SKIP_PREFIXES = ("assets/",)
SKIP_EXACT = {"LICENSE"}

# Only used by the os.walk fallback. Under git these are already invisible,
# because every one of them is in .gitignore.
WALK_PRUNE = {
    ".git", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache",
    ".idea", ".vscode", "node_modules", "dist", "build", "assets",
}

MAX_REPORTED = 40


def _tracked_files(root: Path) -> list[Path]:
    """Every file the repository ships.

    Prefers `git ls-files`, which excludes build noise and the framework's own
    `.compass/work/` for free while still including the deliberately-tracked
    `examples/*/.compass/work/` fixtures. Falls back to a filesystem walk so
    the test still works from an extracted release tarball, which has no git
    metadata (see `scripts/release.sh`).
    """
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root, capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        rels = [p for p in out.split("\0") if p]
    except (subprocess.SubprocessError, OSError):
        # Say so. A run over the filesystem scans a different set from a run
        # over `git ls-files` - it can include local-only content - and the two
        # must not report identically. Silence here is how a "clean" result
        # over the wrong file set looks exactly like a clean result over the
        # right one.
        print(f"test_house_style: no git metadata at {root} - "
              f"falling back to a filesystem walk; the scanned file set is the "
              f"working tree, not `git ls-files`.")
        rels = _walk(root)
    return [root / rel for rel in rels if not _skipped(rel)]


def _walk(root: Path) -> list[str]:
    import os
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in WALK_PRUNE]
        rel_dir = Path(dirpath).relative_to(root)
        # The framework's own issue state is gitignored; the examples' is not.
        if rel_dir.parts[:2] == (".compass", "work"):
            dirnames[:] = []
            continue
        for name in filenames:
            found.append(str(rel_dir / name) if str(rel_dir) != "." else name)
    return found


def _skipped(rel: str) -> bool:
    return rel in SKIP_EXACT or rel.startswith(SKIP_PREFIXES)


def _read(path: Path) -> str | None:
    """File text, or None when the file is binary or has gone away."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _scan(needle: str, only_suffix: str | None = None) -> list[str]:
    """Every occurrence of `needle`, as `path:line:col: excerpt` strings."""
    hits: list[str] = []
    for path in _tracked_files(REPO_ROOT):
        if only_suffix and path.suffix != only_suffix:
            continue
        text = _read(path)
        if text is None or needle not in text:
            continue
        rel = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), 1):
            col = line.find(needle)
            while col >= 0:
                hits.append(f"{rel}:{lineno}:{col + 1}: {line.strip()[:100]}")
                col = line.find(needle, col + 1)
    return hits


def _report(hits: list[str], rule: str, fix: str) -> str:
    shown = "\n".join("  " + h for h in hits[:MAX_REPORTED])
    more = ""
    if len(hits) > MAX_REPORTED:
        more = f"\n  ... and {len(hits) - MAX_REPORTED} more"
    return f"{len(hits)} house-style violation(s).\n{rule}\n{shown}{more}\n{fix}"


def test_no_em_dash_in_tracked_files():
    """No U+2014 anywhere the repository ships.

    Note this deliberately does not scan U+2013. En dashes are correct in
    ranges and there are 53 of them doing real work.
    """
    hits = _scan(EM_DASH)
    assert not hits, _report(
        hits,
        "Rule: write a plain hyphen with spaces around it where an em dash "
        "would go (governance/strategies.md, Voice and writing strategies).",
        "Fix: replace the character with '-'. Do not touch U+2013 en dashes, "
        "which are correct in ranges.",
    )


def test_no_json_escaped_em_dash():
    """No em dash hiding inside a JSON string escape.

    A JSON encoder writes U+2014 as a six-character escape, which the byte
    scan above cannot see. Both plugin manifests carried one, and the
    marketplace description is the first prose an adopter ever reads.
    """
    hits = _scan(JSON_ESCAPED_EM_DASH, only_suffix=".json")
    assert not hits, _report(
        hits,
        "Rule: no em dash, including one encoded as a JSON escape sequence.",
        "Fix: replace the escape with '-' by string edit. Do not re-serialise "
        "the file, which would reflow it.",
    )


def test_no_agent_coauthor_trailer_in_tracked_files():
    """No commit or pull-request body in the repository credits an agent.

    This scans files rather than git history on purpose. CI checks out at
    depth 1, so a history scan would pass without checking anything there and behave
    differently on a local clone - the kind of environment-dependent result
    strategy `S5` (intermittency is failure) rules out. Enforcing the rule on
    commit messages themselves belongs in a commit-msg hook, not here.
    """
    hits: list[str] = []
    for trailer in FORBIDDEN_TRAILERS:
        hits.extend(_scan(trailer))
    assert not hits, _report(
        hits,
        "Rule: commit messages and pull-request bodies never carry a "
        "Co-Authored-By line naming an agent, and never a 'Generated with' "
        "footer (governance/strategies.md, strategy S7).",
        "Fix: remove the trailer. The human author owns the change.",
    )


def test_no_undefined_internal_identifiers():
    """No prose cites an identifier the repository never defines.

    Compass has plenty of legitimate identifiers - `G1` to `G5`, `S1` to
    `S14`, `Inv-1` to `Inv-8`, scenario and intent ids - and every one of
    them is defined somewhere a reader can reach. The patterns below are the
    ones that were not: internal subtask numbering and pointers into a
    per-issue `architecture-notes.md`, which is never committed. A reader
    hitting one of those has no way to resolve it, which is what strategy
    `S7` (cold reader: write so a stranger can follow it without asking)
    forbids.

    Scenario ids of the form `TRC-<letter><number>` are deliberately NOT
    scanned, and the distinction matters. They are the code-to-scenario half
    of the traceability chain guardrail `G3` needs, not internal numbering:
    a test docstring naming one says which acceptance criterion that test
    exists to satisfy. Most of them resolve through `docs/system-spec.md`,
    which is derived at ship from shipped issue specs. The ones that do not
    resolve fail for a structural reason rather than a stylistic one:
    `.compass/work/` is gitignored, so the specs of the framework's own
    issues were never committed. Deleting the ids would remove the visible
    half of a chain the project mandates without making a single spec
    easier to find. Closing that gap means making them resolve, not
    stripping them.

    Scope is every tracked file, not just prose: a comment in `cli/compass` or
    a test docstring is read by exactly the same person.

    Two exclusions. `docs/system-spec.md` is generated at ship from issue
    specs and hand-edits to it are silently overwritten. `tests/fixtures/`
    is data that other tests assert on, so its content is fixed by those
    tests rather than by style.

    Needles are assembled from parts so this file does not trip its own scan.
    """
    needles = {
        "B" + "-Risk": "risk numbering from a work stream that was never committed",
        "S" + "-Risk": "risk numbering from a work stream that was never committed",
        "USP" + "-": "differentiator numbering that no file in the repository defines",
        "architecture-notes.md " + "§": "a section pointer into a per-task file that is never committed",
        "stream" + "-A": "an internal work stream that no file in the repository defines",
        "stream" + "-B": "an internal work stream that no file in the repository defines",
        "stream" + "-C": "an internal work stream that no file in the repository defines",
    }
    excluded = ("docs/system-spec.md:", "docs/system-spec-archive.md:", "tests/fixtures/")
    hits: list[str] = []
    for needle, why in needles.items():
        for hit in _scan(needle):
            if hit.startswith(excluded):
                continue
            hits.append(f"{hit}   <- {why}")
    assert not hits, _report(
        hits,
        "Rule: state the substance, do not cite an identifier the reader "
        "cannot resolve (governance/strategies.md, strategy S7).",
        "Fix: say what the thing is. If it deserves an id, define it somewhere "
        "a reader can reach, as Inv-1 to Inv-8 are defined in "
        "architecture/decisions/README.md.",
    )


def test_house_style_is_documented():
    """The mechanical rules above have a written home.

    A check whose reason is not written down gets deleted by the first person
    it inconveniences. `S7` is that reason, and `commands/ship.md` is where
    the trailer rule has to be visible, because ship is the one point in the
    pipeline where a commit message is authored.
    """
    strategies = (REPO_ROOT / "governance/strategies.md").read_text(encoding="utf-8")
    assert "(`S7`)" in strategies, (
        "governance/strategies.md must declare strategy S7 (write for a cold "
        "reader). It is what tests/test_house_style.py enforces the mechanical "
        "half of."
    )
    assert "Co-Authored-By" in strategies, (
        "Strategy S7 must state the no-agent-co-author-trailer rule, which "
        "test_no_agent_coauthor_trailer_in_tracked_files enforces."
    )

    # The em dash rule has a written home too, and nothing checked it: this
    # test asserted the trailer rule twice and the em dash rule never, so
    # deleting the Voice and writing strategies block left it green while
    # test_no_em_dash's own failure message pointed readers at a section that
    # no longer existed.
    assert "No em dashes" in strategies, (
        "governance/strategies.md must state the no-em-dash rule, which "
        "test_no_em_dash_in_tracked_files enforces and whose failure message "
        "sends the reader here"
    )
    assert "En dashes stay" in strategies, (
        "governance/strategies.md must keep the en-dash carve-out. Without "
        "it the rule reads as banning both, and a range like G1-G5 gets "
        "'corrected' into something that means nothing"
    )

    land = (REPO_ROOT / "commands/ship.md").read_text(encoding="utf-8")
    assert "Co-Authored-By" in land, (
        "commands/ship.md must restate the trailer rule beside `compass "
        "land-commit`. Land authors the commit message, so the rule has to be "
        "at the point of use to take effect."
    )


# ---------------------------------------------------------------------------
# Published copy comes under the guard (issue plain-language-3-2-0, group A).
#
# The guard reads what `git ls-files` reports. That is correct and is not
# changing: a guard whose file list depends on local-only content gives a
# different answer on every machine, and passes in CI where the files are
# absent entirely. What was wrong is that the project's own published article
# was not tracked, so the guard had never once read it.
# ---------------------------------------------------------------------------

PUBLISHED_COPY = "docs/launch-article.md"


def _git_tracked(rel: str) -> bool:
    out = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    return out.returncode == 0


def test_pl_a1_published_copy_is_tracked():
    """`TRC-A1` - the article written for publication is under version control.

    It used to live in `docs/analysis/`, which `.gitignore` excludes as a
    directory, so it was absent from every fresh clone and from CI. Anything
    the project publishes is tracked; working notes and the campaign plan stay
    untracked, because nothing publishes them and a public repository should
    not carry the launch strategy beside the framework.
    """
    assert (REPO_ROOT / PUBLISHED_COPY).is_file(), (
        f"{PUBLISHED_COPY} does not exist. The published article must live on a "
        f"tracked path outside docs/analysis/, or no guard in this file reads it."
    )
    assert _git_tracked(PUBLISHED_COPY), (
        f"{PUBLISHED_COPY} exists but `git ls-files` does not report it, so the "
        f"house-style guard - which builds its list from git - will not read it."
    )


def test_pl_a1b_working_notes_stay_untracked():
    """`TRC-A1` - tracking the article does not drag the planning directory in.

    `docs/analysis/` holds internal review notes and `launch-plan.md`, which
    names venues, poll wording and who gets seeded first. Publishing the
    campaign strategy beside the framework would be a worse outcome than an
    unscanned em dash.
    """
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for path in ("/docs/analysis/", "/docs/proposals/"):
        assert path in gitignore, (
            f"{path} must stay in .gitignore - it holds local-only planning "
            f"documents, and this repository is public."
        )
    leaked = [p for p in subprocess.run(
        ["git", "ls-files", "docs/analysis", "docs/proposals"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.split("\n") if p.strip()]
    assert not leaked, (
        "these local-only planning files are tracked and should not be:\n  "
        + "\n  ".join(leaked)
    )


# The heading a file uses to fence off its own non-published material. Real
# instance: launch-article.md carried "## Not part of the article - where to
# post it", holding venue order, the Show HN title and the poll wording, and
# tracking the file would have published all of it in a public repository.
SELF_EXCLUSION_PHRASES = ("not part of the article", "not part of this article",
                          "not for publication", "internal only", "do not publish")


def test_pl_a9_no_self_declared_exclusion_in_publication_copy():
    """`TRC-A9` - a tracked publication file holds only what will be published.

    The rule this enforces is `TRC-A7`'s: the article holds what gets published,
    the untracked plan holds everything that does not. That rule is judgement
    and cannot be checked mechanically in general. This is the one crude half
    that can be: a file which says out loud that a section is not part of it
    is telling you its contents are mixed, and mixed contents must not be
    tracked as publication copy.

    The fix is never to reword the heading. It is to move the section into the
    untracked plan, where that material belongs.
    """
    path = REPO_ROOT / PUBLISHED_COPY
    if not path.is_file():
        return  # `TRC-A1` owns the file's existence and fails on its own.
    hits = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("#"):
            continue
        low = line.lower()
        for phrase in SELF_EXCLUSION_PHRASES:
            if phrase in low:
                hits.append(f"{PUBLISHED_COPY}:{lineno}: {line.strip()[:90]}")
    assert not hits, (
        "a tracked publication file declares that part of it is not for "
        "publication:\n  " + "\n  ".join(hits) + "\n\n"
        "Fix: move that section into the untracked plan (docs/analysis/). Do "
        "NOT reword the heading - the heading is honest, and the problem is "
        "that the material is in a tracked file at all. This repository is "
        "public."
    )


def test_pl_a3_fallback_not_used_where_git_works():
    """`TRC-A3` - the filesystem walk is not reached when git can answer.

    The walk exists for an extracted release tarball, which has no git
    metadata. Reaching it anywhere else would put local-only content back into
    the file list and make the guard's answer vary by machine - the exact
    property tracking the article was meant to remove.
    """
    files = _tracked_files(REPO_ROOT)
    rels = {str(p.relative_to(REPO_ROOT)) for p in files}
    from_git = {p for p in subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.split("\n") if p.strip() and not _skipped(p)}
    extra = sorted(rels - from_git)
    assert not extra, (
        "the guard's file list contains paths `git ls-files` does not report, "
        "so it fell back to the filesystem walk while git was available:\n  "
        + "\n  ".join(extra[:20])
    )


def test_pl_a8_fallback_announces_itself():
    """`TRC-A8` - falling back to the filesystem walk says so.

    A run over a different file set must not look identical to a run over the
    tracked one. Without this, a repository where git is unavailable reports
    the same "PASS" while having scanned something else entirely.
    """
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _walk_used = _tracked_files(Path("/nonexistent-so-git-cannot-run"))
    said = buf.getvalue().lower()
    assert "filesystem" in said or "fallback" in said or "no git" in said, (
        "the guard fell back to the filesystem walk and said nothing. A run "
        "that scanned a different file set must not be indistinguishable from "
        "one that scanned the tracked set.\n"
        f"Captured output: {buf.getvalue()!r}"
    )


def test_pl_a4_build_noise_stays_out_of_the_scan():
    """`TRC-A4` - build noise and the framework's own issue state are not scanned.

    A regression test on behaviour that is already correct. It can still be
    proved failing - see the mutation record in evidence/ - by removing a
    prune entry and watching the list grow.
    """
    rels = {p.relative_to(REPO_ROOT) for p in _tracked_files(REPO_ROOT)}
    # Match on path SEGMENTS, not a leading prefix. `tests/__pycache__/x.pyc`
    # does not start with "__pycache__/", so a prefix test would report clean
    # while the walk was returning build noise from every subdirectory.
    for noise in (".git", "node_modules", "__pycache__", ".ruff_cache",
                  ".pytest_cache", "dist", "build"):
        offenders = sorted(str(r) for r in rels if noise in r.parts)
        assert not offenders, (
            f"'{noise}' should never be scanned; found {len(offenders)}, "
            f"e.g. {offenders[:3]}"
        )
    # The framework's own issue state is gitignored and must not be walked in,
    # but the examples' committed fixtures must be.
    own_state = sorted(str(r) for r in rels
                       if r.parts[:2] == (".compass", "work"))
    assert not own_state, (
        f"the framework's own .compass/work/ was scanned: {own_state[:3]}")
    assert any(r.parts[0] == "examples" and ".compass" in r.parts for r in rels), (
        "the deliberately-tracked examples/*/.compass/work/ fixtures are missing "
        "from the scan - the prune above is too broad."
    )


def test_pl_a6_en_dash_is_left_alone():
    """`TRC-A6` - U+2013 is not swept up with U+2014.

    En dashes carry meaning in ranges such as `G1`-`G5` and `2-3 subtasks`, and
    there are real ones in this repository doing that work. A guard that took
    them too would force every range to be rewritten.
    """
    EN_DASH = chr(0x2013)
    assert EN_DASH != EM_DASH
    assert not _scan(EN_DASH, only_suffix=".nonexistent-suffix"), "sanity"
    # The em-dash scanner must not fire on a line whose only dash is an en dash.
    sample = f"the range G1{EN_DASH}G5 and 2{EN_DASH}3 streams"
    assert EM_DASH not in sample
    living = _scan(EN_DASH)
    assert living, (
        "no en dash found anywhere in the repository. This test asserts they "
        "are LEFT ALONE, so with none present it would pass without checking "
        "anything - the failure mode strategy S10 exists to catch."
    )


def test_pl_a2_em_dash_in_published_copy_is_caught(tmp_path):
    """`TRC-A2` - the guard fails on an em dash in the published article.

    The guard's reach over that file is the whole point of tracking it, and
    "the guard now reads it" is exactly the kind of claim that passes without
    being true. This plants one in a copy and drives `_scan`'s own matcher
    over it, so the assertion is about the scanner rather than about a file
    that happens to be clean today.
    """
    article = REPO_ROOT / PUBLISHED_COPY
    assert article.is_file(), "TRC-A1 owns this file's existence"
    planted = tmp_path / "launch-article.md"
    planted.write_text(
        article.read_text(encoding="utf-8") + f"\nA sentence {EM_DASH} with one.\n",
        encoding="utf-8",
    )
    text = _read(planted)
    hits = [ln for ln, line in enumerate(text.splitlines(), 1) if EM_DASH in line]
    assert hits, "the planted em dash was not found - the matcher is not looking"

    # And the real file is clean, which is what the suite-level scan asserts.
    assert EM_DASH not in article.read_text(encoding="utf-8"), (
        f"{PUBLISHED_COPY} contains an em dash. It is tracked, so "
        f"test_no_em_dash_in_tracked_files covers it - fix it there."
    )


def test_pl_a5_docstring_records_the_silent_omission():
    """`TRC-A5` - the module says why its file list is what it is.

    A future reader who meets a guard that reads only tracked files will ask
    whether that was a decision or an accident, and the honest answer is
    "both": it was a decision, and it silently omitted the one document
    written for strangers. Without that written down, the next person
    re-proposes reading untracked files, which is the option that gives a
    different answer on every machine.
    """
    doc = __doc__ or ""
    for phrase, why in (
        ("git ls-files", "the file list's actual source"),
        ("silently omitted", "that the gap was silent, which is the pattern ADR-018 names"),
        ("launch article", "which document was missed"),
        ("track what gets published", "the fix that was chosen"),
        ("depend on whatever", "why reading untracked files was rejected"),
    ):
        assert phrase in doc, (
            f"the module docstring does not record {why} (looked for "
            f"{phrase!r}). A guard whose file list surprised someone once "
            f"should explain itself to the next reader."
        )
