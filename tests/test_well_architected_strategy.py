"""A register of the cloud providers' well-architected frameworks, and an
advisory strategy that asks a design to name the pillars it touches.

Compass's strategies had nothing architectural, and nothing tied the judgement
of a design and its review to the frameworks the three large cloud providers publish.
`governance/architecture-sources.yml` lists them with their sources, their
pillars in provider-neutral words and the date each was last reviewed, and
`compass policy lint` checks it. The well-architected alignment strategy
(`S15`) asks a feature or initiative design to name the pillars it touches;
it advises and never gates (ADR-003). Issue `well-architected-strategy`.

Scenario id: WA-1.
"""
from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
REGISTER = ROOT / "governance" / "architecture-sources.yml"
PILLARS = {"reliability", "security", "cost", "operational excellence",
           "performance efficiency", "sustainability"}


def test_wa_1_the_register_lists_three_frameworks_with_their_sources():
    data = yaml.safe_load(REGISTER.read_text(encoding="utf-8"))
    frameworks = data["frameworks"]
    assert {f["provider"] for f in frameworks} == {"AWS", "Microsoft Azure", "Google Cloud"}
    for f in frameworks:
        assert f["name"] and f["digest"], f
        assert f["sources"] and all(u.startswith("https://") for u in f["sources"]), f
        assert f["pillars"] and set(f["pillars"]) <= PILLARS, f
        datetime.date.fromisoformat(str(f["last_reviewed"]))


def test_wa_1_lint_refuses_an_entry_with_no_review_date(tmp_path):
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    path = tmp_path / "governance" / "architecture-sources.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["frameworks"][0]["last_reviewed"]
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    (tmp_path / ".compass").mkdir()
    r = subprocess.run([sys.executable, str(CLI), "policy", "lint"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "last_reviewed" in r.stdout + r.stderr


def test_wa_1_the_strategy_advises_and_cites_adr_003():
    text = (ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    section = text.split("(`S15`)", 1)[1].split("\n---", 1)[0]
    assert "pillar" in section and "ADR-003" in section, section
    assert "architecture-sources.yml" in section, section
    rationale = (ROOT / "governance" / "strategies-rationale.md").read_text(encoding="utf-8")
    assert "(`S15`)" in rationale


def test_wa_1_the_planning_texts_point_to_it():
    for rel in ("agents/architect.md", "skills/plan-authoring/SKILL.md",
                "templates/technical-design.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "S15" in text, rel
