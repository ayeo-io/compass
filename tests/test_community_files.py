"""An outside contributor can find the security policy, the code of conduct
and the issue templates.

#99 found the repository had a CONTRIBUTING.md but no security policy, no
code of conduct and no issue templates. The maintainer chose GitHub private
vulnerability reporting for security reports and conduct@ayeo.io for
conduct reports (2026-10-05).

Scenario id: CF-1 (issue `security-policy-and-templates`).
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPORTING = "https://github.com/ayeo-io/compass/security/advisories/new"


def test_cf_1_security_policy_routes_reports_privately():
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert REPORTING in text
    assert "public issue" in text.lower()
    assert "latest" in text.lower()


def test_cf_1_code_of_conduct_names_the_covenant_and_the_contact():
    text = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "Contributor Covenant" in text and "2.1" in text
    assert "conduct@ayeo.io" in text


def test_cf_1_issue_templates_ask_for_the_version():
    folder = ROOT / ".github" / "ISSUE_TEMPLATE"
    for name in ("bug-report.yml", "feature-request.yml"):
        form = yaml.safe_load((folder / name).read_text(encoding="utf-8"))
        assert form["name"] and form["description"] and form["body"], name
        ids = {item.get("id") for item in form["body"]}
        assert "version" in ids, name
    config = yaml.safe_load((folder / "config.yml").read_text(encoding="utf-8"))
    urls = [c["url"] for c in config.get("contact_links", [])]
    assert REPORTING in urls


def test_cf_1_contributing_points_at_both():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "SECURITY.md" in text and "CODE_OF_CONDUCT.md" in text
