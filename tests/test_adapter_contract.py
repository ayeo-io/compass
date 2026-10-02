"""The runtime adapter contract is a table a test enforces: the
adapter-contract-gate issue, GitHub issue #256.

`schemas/adapter-contract.yml` holds one row per capability in the mapping
table of `docs/portability.md`, and one cell per adapter saying `full`,
`partial` or `none` with a path. A second adapter must add a column before
it can land, and code must not branch on which adapter it is in.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "schemas" / "adapter-contract.yml"
PORTABILITY = ROOT / "docs" / "portability.md"
STATUSES = {"full", "partial", "none"}

# A check that names an adapter to exclude it: "!= claude-code",
# "-ne codex", "not in ('cursor',)". Code that needs a capability asks for the
# capability; branching on "not the other adapter" breaks every later one.
_ADAPTERS = r"(?:claude(?:-code)?|codex|cursor|gemini|kiro|windsurf)"
NEGATIVE_IDENTITY = re.compile(
    r"(?:!==?|\s-ne\s|\bis\s+not\b|\bnot\s+in\b)\s*[\(\[\{]?\s*[\"']?" + _ADAPTERS + r"\b",
    re.IGNORECASE)


def _portability_capabilities(text: str) -> list[str]:
    """The first column of the mapping table headed 'Compass capability'."""
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| Compass capability |"))
    names = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        names.append(line.strip().strip("|").split("|")[0].strip())
    return names


def contract_problems(root: Path) -> list[str]:
    """Every way the contract at `root` falls short; empty when it holds."""
    data = yaml.safe_load((root / "schemas" / "adapter-contract.yml").read_text(encoding="utf-8"))
    adapters = data.get("adapters") or []
    rows = data.get("capabilities") or []
    problems = []
    wanted = _portability_capabilities((root / "docs" / "portability.md").read_text(encoding="utf-8"))
    have = [r.get("capability") for r in rows]
    if have != wanted:
        problems.append(f"the rows {have} do not match docs/portability.md's table {wanted}")
    adapters_dir = root / "adapters"
    if adapters_dir.is_dir():
        for d in sorted(p.name for p in adapters_dir.iterdir() if p.is_dir()):
            if d not in adapters:
                problems.append(f"adapters/{d}/ has no column in the contract")
    if "claude-code" not in adapters:
        problems.append("the shipped adapter, claude-code, has no column")
    for row in rows:
        for adapter in adapters:
            cell = row.get(adapter)
            where = f"{row.get('capability')!r}, {adapter}"
            if not isinstance(cell, dict) or cell.get("status") not in STATUSES:
                problems.append(f"{where}: needs a status of full, partial or none")
                continue
            if cell["status"] == "none":
                if not str(cell.get("reason") or "").strip():
                    problems.append(f"{where}: none needs a reason")
                continue
            path = str(cell.get("path") or "").strip()
            if not path:
                problems.append(f"{where}: {cell['status']} needs a path")
            elif not (root / path).exists():
                problems.append(f"{where}: {path} does not exist")
    return problems


def negative_identity_lines(diff: str) -> list[str]:
    """Added lines in a unified diff that branch on not being an adapter."""
    hits, current = [], None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("+") and current and NEGATIVE_IDENTITY.search(line[1:]):
            hits.append(f"{current}: {line[1:].strip()}")
    return hits


def test_the_contract_holds():
    assert contract_problems(ROOT) == []


def test_the_doc_points_at_the_contract():
    assert "schemas/adapter-contract.yml" in PORTABILITY.read_text(encoding="utf-8")


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel in ("schemas/adapter-contract.yml", "docs/portability.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    data = yaml.safe_load((root / "schemas/adapter-contract.yml").read_text(encoding="utf-8"))
    for row in data["capabilities"]:
        path = row["claude-code"].get("path")
        if path and path.endswith("/"):
            (root / path).mkdir(parents=True, exist_ok=True)
        elif path:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).touch()
    return root


def test_an_adapter_directory_without_a_column_fails(tmp_path):
    root = _copy(tmp_path)
    assert contract_problems(root) == []
    (root / "adapters" / "codex").mkdir(parents=True)
    assert any("adapters/codex/ has no column" in p for p in contract_problems(root))


@pytest.mark.parametrize("cell, says", [
    (None, "needs a status"),
    ({"status": "mostly"}, "needs a status"),
    ({"status": "full"}, "needs a path"),
    ({"status": "partial", "path": "nowhere/at/all.md"}, "does not exist"),
    ({"status": "none"}, "needs a reason"),
])
def test_an_empty_or_bad_cell_fails(tmp_path, cell, says):
    root = _copy(tmp_path)
    path = root / "schemas" / "adapter-contract.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["capabilities"][0]["claude-code"] = cell
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert any(says in p for p in contract_problems(root))


def test_a_capability_missing_from_the_contract_fails(tmp_path):
    root = _copy(tmp_path)
    doc = root / "docs" / "portability.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace(
        "| CI integration |", "| CI integration |  |  |\n| A new capability |"), encoding="utf-8")
    assert any("do not match" in p for p in contract_problems(root))


@pytest.mark.parametrize("line", [
    'if adapter != "claude-code":',
    "if [ \"$ADAPTER\" != 'codex' ]; then",
    '[ "$RUNTIME" -ne cursor ] && exit 0',
    'if runtime not in ("claude",):',
    "if (adapter !== 'cursor') {",
])
def test_a_new_negative_identity_check_is_found(line):
    diff = f"+++ b/cli/compass_pkg/x.py\n@@ -1 +1,2 @@\n+{line}\n"
    assert negative_identity_lines(diff), line


@pytest.mark.parametrize("line", [
    'if adapter == "claude-code":',
    'if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then',
    '# not the claude-code adapter',
])
def test_other_lines_are_not_found(line):
    diff = f"+++ b/hooks/x.sh\n@@ -1 +1,2 @@\n+{line}\n"
    assert not negative_identity_lines(diff), line


def test_this_branch_adds_no_negative_identity_check():
    """The scan over this branch's own added lines in cli/ and hooks/."""
    base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=ROOT,
                          capture_output=True, text=True)
    if base.returncode != 0:
        pytest.skip("origin/main is not available, so there is no base to diff against")
    diff = subprocess.run(["git", "diff", "-U0", base.stdout.strip(), "--", "cli", "hooks"],
                          cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert negative_identity_lines(diff) == []
