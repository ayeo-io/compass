"""Documentation gaps reported after 6.0.0 stay closed.

Covers the site pages, the waiver and lock syntax page, the templates and the
releasing guide (issue `docs-gaps-after-6-0-0`).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CLI = ROOT / "cli" / "compass"
PAGE = DOCS / "waivers-and-locks.md"
THREE = ("github-labels.md", "github-labels-walkthrough.md",
         "upgrade-7-0-0.md")


def _config():
    return yaml.safe_load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"))


def _nav_pages(nav):
    for item in nav:
        for value in (item.values() if isinstance(item, dict) else [item]):
            if isinstance(value, list):
                yield from _nav_pages(value)
            else:
                yield value


def _allowed():
    lines = _config()["exclude_docs"].splitlines()
    return {line.strip()[2:] for line in lines if line.strip().startswith("!/")}


def _relative_links(path):
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    for target in re.findall(r"\]\(([^)]+)\)", text):
        target = target.split("#")[0]
        if target and "://" not in target and not target.startswith("mailto:"):
            yield target


def _run(args, **kw):
    return subprocess.run([sys.executable, str(CLI), *args],
                          capture_output=True, text=True, cwd=ROOT, **kw)


def test_trc_001_site_publishes_the_three_missing_pages():
    nav = set(_nav_pages(_config()["nav"]))
    allowed = _allowed()
    for page in THREE:
        assert (DOCS / page).exists(), page
        assert page in nav, f"{page} is not in the nav"
        assert page in allowed, f"{page} has no allow line in exclude_docs"


def test_trc_002_links_on_the_three_pages_stay_inside_the_site():
    nav = set(_nav_pages(_config()["nav"]))
    for page in THREE:
        for target in _relative_links(DOCS / page):
            assert target in nav, f"{page} links to {target}, not in the nav"


def test_trc_003_syntax_page_is_published_and_linked_from_configuration():
    assert PAGE.exists()
    assert "waivers-and-locks.md" in set(_nav_pages(_config()["nav"]))
    assert "waivers-and-locks.md" in _allowed()
    config_page = (DOCS / "configuration.md").read_text(encoding="utf-8")
    assert "](waivers-and-locks.md" in config_page


def test_trc_004_syntax_page_names_every_key():
    text = PAGE.read_text(encoding="utf-8")
    for key in ("waiver", "reason", "approved_by", "approved_on", "locked",
                "unlock", "owner", "approvers", "extends", "set", "replace",
                "remove"):
        assert re.search(rf"`{key}`", text), f"page does not name {key}"


def _page_commands():
    text = PAGE.read_text(encoding="utf-8")
    found = set()
    for span in re.findall(r"`(compass [^`]+)`", text):
        words = []
        for word in span.split()[1:]:
            if word.startswith(("-", "<", "[")) or not re.fullmatch(
                    r"[a-z][a-z-]*", word):
                break
            words.append(word)
        if words:
            found.add(tuple(words))
    return found


def test_trc_005_every_command_on_the_syntax_page_exists():
    commands = _page_commands()
    for needed in (("policy", "lint"), ("policy", "show"),
                   ("policy", "update"), ("issue", "configure")):
        assert needed in commands, f"page does not name compass {needed}"
    for words in sorted(commands):
        result = _run([*words, "--help"])
        assert result.returncode == 0, (words, result.stderr[-300:])


def test_trc_006_syntax_page_names_no_policy_effective():
    assert "policy effective" not in PAGE.read_text(encoding="utf-8")


def test_trc_007_syntax_page_example_passes_policy_lint(tmp_path):
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r"```yaml\n(.*?)```", text, flags=re.S)
    assert match, "page holds no yaml block"
    example = tmp_path / "compass.yml"
    example.write_text(match.group(1), encoding="utf-8")
    result = _run(["policy", "lint", "--file", str(example)])
    assert result.returncode == 0, result.stdout[-500:] + result.stderr[-300:]


def test_trc_008_syntax_page_says_a_waiver_does_not_excuse_a_lock():
    text = PAGE.read_text(encoding="utf-8")
    assert "K-LOCK-REFUSED" in text
    assert re.search(r"waiver does not excuse a lock", text)


def test_trc_009_no_template_cites_the_strategies_file_as_a_project_path():
    pattern = re.compile(
        r"(?<!\$\{CLAUDE_PLUGIN_ROOT\}/)governance/strategies\.md")
    hits = []
    for path in sorted((ROOT / "templates").rglob("*")):
        if path.is_file():
            for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.name}:{number}")
    assert hits == []


def _orchestration_line():
    for line in (ROOT / "templates" / "manifest.yml").read_text(
            encoding="utf-8").splitlines():
        if line.startswith("orchestration:"):
            return line
    raise AssertionError("no orchestration line")


def test_trc_010_manifest_template_names_breakdown_as_orchestration_recorder():
    line = _orchestration_line()
    assert "#" in line
    comment = line.split("#", 1)[1].lower()
    assert "breakdown" in comment
    assert "evaluator" not in comment


def test_trc_011_manifest_template_parses_with_null_orchestration():
    data = yaml.safe_load(
        (ROOT / "templates" / "manifest.yml").read_text(encoding="utf-8"))
    assert "orchestration" in data
    assert data["orchestration"] is None


def test_trc_012_releasing_guide_names_artifact_freshness_and_links_its_page():
    assert (DOCS / "artifact-freshness.md").exists()
    text = (DOCS / "releasing.md").read_text(encoding="utf-8")
    assert "artifact freshness" in " ".join(text.lower().split())
    assert "](artifact-freshness.md" in text


def test_trc_013_releasing_guide_says_freshness_refusals_are_opt_in():
    text = (DOCS / "releasing.md").read_text(encoding="utf-8")
    assert "`artifact-freshness`" in text
    assert re.search(r"only\s+when\s+the\s+`artifact-freshness`\s+capability"
                     r"\s+is\s+on", text)
