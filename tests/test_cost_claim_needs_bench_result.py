"""No shipped text states a cost or token ratio until a bench run passes.

The 9.0.0 positioning names a target: Compass costs at most one and a half
times what the same agent costs on its own. That is a target, not a measured
fact, until #361 [Run the pre-registered sdd-bench measurement on the 9.0.0
release candidate] records a passing run in `docs/sdd-bench-9-0-0.md`. Until
then no shipped text may state a cost, token or spend ratio. After a pass,
every paragraph that states one must link that record, so a reader can see
the measurement behind the number.

What the scan reads: the tracked files a user or the plugin directory sees
(`SHIPPED`), listed with `git ls-files` so an untracked planning file cannot
fail a local run. What it leaves out:

- `docs/compass/`, the dated 8.x measurement reports. They are history, and
  `tests/test_rival_names_never_committed.py` pins their content hashes;
- `architecture/decisions/`, `governance/decisions/` and `tests/`, which
  discuss the rule rather than state a ratio to a user;
- the record itself, which holds the measured numbers.

A sentence can carry `<!-- cost-claim: allow - <reason> -->` on one of its
lines when it discusses the rule itself. As with the other allow markers
(`tests/allow_marker.py`), the reason must start with a letter, so the `-->`
that closes the comment does not count as a reason. The real-tree test
prints every allowed sentence, so a reviewer sees each one.

Plan: `docs/analysis/360-plan.md`, section 9 (not committed).
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

RECORD = "docs/sdd-bench-9-0-0.md"
RECORD_NAME = "sdd-bench-9-0-0.md"

# The files that ship or that a reader of the project sees first. `docs/*.md`
# is the top level only: fnmatch's `*` crosses `/`, so `_in_scope` checks
# the depth separately.
SHIPPED = (
    "README.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "compass-contract.md",
    "docs/*.md",
    "commands/*.md",
    "skills/*.md",
    "templates/*.md",
    ".claude-plugin/*.json",
)
TOP_LEVEL_ONLY = ("docs/*.md", "commands/*.md", ".claude-plugin/*.json")
LEFT_OUT = (
    "docs/compass/",
    "architecture/decisions/",
    "governance/decisions/",
    "tests/",
)

# Same rule as `tests/allow_marker.py`: a letter after the dash.
COST_CLAIM_MARKER_RE = re.compile(r"cost-claim:\s*allow\s*-\s*[A-Za-z]")

# A word ceiling, not a cost: "over 1.5 times its limit" and "over 1.5 times
# its word limit" describe the removed `design-within-word-ceiling` check.
_NOT_A_COST = r"(?!\s+its\s+(?:word\s+)?limit)"

# The target sentence in any of its spellings, wherever it appears.
TARGET_RE = re.compile(
    r"at\s+most\s+1\.5"
    r"|1\.5\s*(?:times" + _NOT_A_COST + r"|x\b|×)"
    r"|one\s+and\s+a\s+half\s+times" + _NOT_A_COST,
    re.IGNORECASE,
)

# Any other ratio counts only in a sentence that also names a cost and the
# thing Compass is compared with.
MULTIPLIER_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?|\bone\s+and\s+a\s+half|\btwice|\bdouble|\bhalf)"
    r"\s*(?:x\b|×|times\b|%\s*(?:more|less|fewer|cheaper))"
    r"|\b(?:twice|double|half)\s+(?:the|as)\b",
    re.IGNORECASE,
)
COST_WORD_RE = re.compile(
    r"\b(?:costs?|tokens?|spend|price|cheaper|more\s+expensive)\b",
    re.IGNORECASE,
)
COMPARED_WITH_RE = re.compile(
    r"\b(?:agent|bare|on\s+its\s+own|no\s+framework|without\s+Compass)\b",
    re.IGNORECASE,
)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def is_claim(sentence: str) -> bool:
    """True when one sentence states a cost or token ratio."""
    if TARGET_RE.search(sentence):
        return True
    return bool(MULTIPLIER_RE.search(sentence)
                and COST_WORD_RE.search(sentence)
                and COMPARED_WITH_RE.search(sentence))


def _in_scope(rel: str) -> bool:
    if rel == RECORD or any(rel.startswith(p) for p in LEFT_OUT):
        return False
    for pattern in SHIPPED:
        if not fnmatch.fnmatch(rel, pattern):
            continue
        if pattern in TOP_LEVEL_ONLY and rel.count("/") != pattern.count("/"):
            continue
        return True
    return False


def shipped_files(root: Path) -> list[str]:
    """The tracked shipped files, as paths relative to `root`."""
    out = subprocess.run(["git", "ls-files"], cwd=root, check=True,
                         capture_output=True, text=True).stdout
    return sorted(rel for rel in out.splitlines() if _in_scope(rel))


def _paragraphs(text: str):
    """Yield each paragraph as a list of (line number, line)."""
    para: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip():
            para.append((n, line))
        elif para:
            yield para
            para = []
    if para:
        yield para


def _sentences(para):
    """Yield (first line, sentence, the lines it spans) for one paragraph.

    Markdown wraps a sentence over several lines, so the paragraph is joined
    before it is split into sentences, and each sentence keeps the source
    lines it came from, so a marker on any of them applies to it.
    """
    joined, starts = "", []
    for n, line in para:
        starts.append((len(joined), n, line))
        joined += line.strip() + " "
    pos = 0
    for sentence in _SENTENCE_END.split(joined):
        begin = joined.index(sentence, pos)
        end = begin + len(sentence)
        pos = end
        spanned = [(n, line) for start, n, line in starts
                   if start < end and start + len(line.strip()) >= begin]
        if sentence.strip():
            yield spanned[0][0], sentence.strip(), spanned


def find_claims(root: Path):
    """Return (claims, allowed).

    Each claim is (path, line, sentence, paragraph text); each allowed entry
    is (path, line, sentence).
    """
    claims, allowed = [], []
    for rel in shipped_files(root):
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for para in _paragraphs(text):
            para_text = "\n".join(line for _, line in para)
            for n, sentence, spanned in _sentences(para):
                if not is_claim(sentence):
                    continue
                if any(COST_CLAIM_MARKER_RE.search(line) for _, line in spanned):
                    allowed.append((rel, n, sentence))
                else:
                    claims.append((rel, n, sentence, para_text))
    return claims, allowed


def record_passes(root: Path) -> bool:
    """True when the bench record exists and its front matter says pass."""
    path = root / RECORD
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    front = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not front:
        return False
    return bool(re.search(r"^verdict:\s*pass\s*(?:#.*)?$", front.group(1), re.M))


def violations(root: Path) -> list[str]:
    """Every claim the current state of the record does not allow."""
    claims, _ = find_claims(root)
    if not claims:
        return []
    if not record_passes(root):
        return [f"{rel}:{n}: {sentence}\n    {RECORD} does not record "
                f"`verdict: pass`, so no cost or token ratio may ship"
                for rel, n, sentence, _ in claims]
    return [f"{rel}:{n}: {sentence}\n    the paragraph must link {RECORD}"
            for rel, n, sentence, para in claims if RECORD_NAME not in para]


# ---------------------------------------------------------------------------
# The real tree
# ---------------------------------------------------------------------------

def test_the_scan_reads_the_shipped_files():
    files = shipped_files(ROOT)
    assert "README.md" in files
    assert "compass-contract.md" in files
    assert "docs/releasing.md" in files
    assert any(f.startswith("commands/") for f in files)
    assert any(f.startswith("skills/") for f in files)
    assert not any(f.startswith("docs/compass/") for f in files)
    assert not any(f.startswith("tests/") for f in files)


def test_no_shipped_text_states_a_cost_ratio_without_a_passing_record():
    _, allowed = find_claims(ROOT)
    # Listed so a reviewer sees every exempted sentence (`pytest -s`).
    for rel, n, sentence in allowed:
        print(f"cost-claim allowed: {rel}:{n}: {sentence}")
    found = violations(ROOT)
    assert not found, (
        "a shipped file states a cost or token ratio. Remove it, or wait for "
        f"#361 to record a pass in {RECORD} and link that file from the "
        "paragraph:\n  " + "\n  ".join(found))


def test_the_release_procedure_says_to_check_the_unscanned_places():
    text = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    procedure = text.split("## The release procedure", 1)[1].split("\n## ", 1)[0]
    flat = " ".join(procedure.split())
    # The line names the record without its directory, because
    # `tests/test_writing_style.py` (PBW-A8) refuses a path to a file that
    # does not exist yet, and #361 writes the record.
    assert f"`{RECORD_NAME}` in `docs/` must record a pass" in flat
    for place in ("GitHub release body", "repository description", "ayeo.io page"):
        assert place in flat, f"the release procedure no longer names the {place}"


# ---------------------------------------------------------------------------
# Planted claims, in temporary repositories this file builds
# ---------------------------------------------------------------------------

TARGET = "It costs at most 1.5 times what the same agent costs on its own."

PLANTED = [
    TARGET,
    "Compass uses 1.5x the tokens of a bare agent.",
    "It runs at about one and a half times the cost of no framework.",
    "A change spends\n2.3 times the tokens\nof the agent on its own.",
]

PASSING_RECORD = "---\nissue: 361\nverdict: pass\n---\n\nThe run.\n"
FAILING_RECORD = "---\nissue: 361\nverdict: fail\n---\n\nThe run.\n"


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


@pytest.mark.parametrize("claim", PLANTED)
def test_a_planted_claim_fails_without_a_record(tmp_path, claim):
    root = _repo(tmp_path, {"README.md": f"# Compass\n\n{claim}\n"})
    assert violations(root), f"the guard missed: {claim!r}"


def test_a_claim_fails_when_the_record_says_fail(tmp_path):
    root = _repo(tmp_path, {
        "README.md": f"# Compass\n\n{TARGET} See [the run]({RECORD_NAME}).\n",
        RECORD: FAILING_RECORD,
    })
    assert violations(root)


def test_a_claim_fails_after_a_pass_when_its_paragraph_does_not_link_the_record(tmp_path):
    root = _repo(tmp_path, {
        "docs/index.md": f"{TARGET}\n",
        RECORD: PASSING_RECORD,
    })
    assert violations(root)


def test_a_claim_passes_after_a_pass_when_its_paragraph_links_the_record(tmp_path):
    root = _repo(tmp_path, {
        "README.md": f"# Compass\n\n{TARGET}\nSee [the run](docs/{RECORD_NAME}).\n",
        RECORD: PASSING_RECORD,
    })
    assert violations(root) == []


@pytest.mark.parametrize("text", [
    "The design is refused over 1.5 times its limit.",
    "Refuse a design over 1.5 times its word limit after plan.",
    "The agent reads 600 words, and the token budget is 1,000.",
    "Run the suite 3 times before you ship.",
])
def test_a_sentence_that_is_not_a_cost_ratio_passes(tmp_path, text):
    root = _repo(tmp_path, {"README.md": f"{text}\n"})
    assert violations(root) == []


def test_files_outside_the_shipped_text_are_not_scanned(tmp_path):
    root = _repo(tmp_path, {
        "docs/compass/2026-10-04-report.md": f"{TARGET}\n",
        "docs/analysis/plan.md": f"{TARGET}\n",
        "governance/decisions/d.md": f"{TARGET}\n",
        "tests/test_x.py": f"# {TARGET}\n",
    })
    assert violations(root) == []


def test_an_untracked_file_is_not_scanned(tmp_path):
    root = _repo(tmp_path, {"README.md": "# Compass\n"})
    (root / "docs").mkdir()
    (root / "docs" / "draft.md").write_text(f"{TARGET}\n", encoding="utf-8")
    assert violations(root) == []


def test_a_marker_with_a_reason_allows_the_sentence_and_is_listed(tmp_path):
    root = _repo(tmp_path, {"docs/releasing.md": (
        f"Intro.\n\n{TARGET} <!-- cost-claim: allow - quotes the target to forbid it -->\n")})
    claims, allowed = find_claims(root)
    assert claims == []
    assert [(rel, n) for rel, n, _ in allowed] == [("docs/releasing.md", 3)]


@pytest.mark.parametrize("marker", [
    "<!-- cost-claim: allow -->",
    "<!-- cost-claim: allow - -->",
    "<!-- cost-claim: allow -- -->",
])
def test_a_marker_without_a_reason_does_not_allow_the_sentence(tmp_path, marker):
    root = _repo(tmp_path, {"README.md": f"{TARGET} {marker}\n"})
    assert violations(root)
