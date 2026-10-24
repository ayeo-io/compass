"""The documents say what the delegation change ships (issue `delegation-everywhere`,
group H).

These cases read tracked text. They check the command files, the safety contract, the
README, the guardrails, the owning document of the delegation code, the decision
record that amends ADR-069 and its index, the upgrade notes, and that no current
document still states a limit that no longer holds.

Scenario ids: `TRC-081` to `TRC-083` and `TRC-100` to `TRC-105`. Each test name starts
with its scenario id.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FLAG_HINT = ("[--agent <name>] [--until <time>] [--on <issues>] [--for <forms>] "
             "[--max <n>]")


def _text(path):
    return (ROOT / path).read_text(encoding="utf-8")


def _front(path):
    match = re.match(r"---\n(.*?)\n---\n", _text(path), re.S)
    return yaml.safe_load(match.group(1))


def _flat(text):
    return " ".join(text.split())


def _section(text, start, end):
    """The text from the heading that holds `start` to the next heading that holds
    `end`, or to the end."""
    first = text.index(start)
    last = text.find(end, first + len(start))
    return text[first:last if last != -1 else len(text)]


def test_TRC_081_the_command_file_shows_the_flag_form():
    front = _front("commands/delegate.md")
    assert front["argument-hint"] == FLAG_HINT
    assert front["disable-model-invocation"] is True
    assert "named agent" not in front["description"], front["description"]


def test_commands_approve_and_reject_show_the_issue_form():
    assert "--issue <slug>" in _front("commands/approve.md")["argument-hint"]
    assert "--issue <slug>" in _front("commands/reject.md")["argument-hint"]
    for name in ("approve", "reject"):
        assert "--issue" in _text(f"commands/{name}.md").split("---", 2)[2]


def test_TRC_082_the_safety_contract_states_the_limits_that_hold_now():
    text = _flat(_text("docs/safety-contract.md"))
    for banned in ("at most 24 hours", "one named agent", "a stated scope",
                   "at most five delegations"):
        assert banned not in text, banned
    for needle in ("until `/compass:revoke`", "the session it was typed in",
                   "its subagents", "every issue in the repository's worktrees",
                   "common store", "main checkout", "ticket"):
        assert needle in text, needle


def _adr_077():
    found = sorted((ROOT / "architecture" / "decisions").glob("ADR-077-*.md"))
    assert len(found) == 1, found
    return found[0]


def test_TRC_083_a_decision_record_amends_adr_069():
    text = _flat(_adr_077().read_text(encoding="utf-8"))
    for needle in ("ADR-069 decisions 1, 2, 3 and 5", "`--agent`", "`--until`", "`--on`",
                   "limit of five", "24-hour limit", "No end time",
                   "A forgotten delegation would outlive the run it was meant for",
                   "session-start list"):
        assert needle in text, needle
    # ADR-069 is accepted and frozen, so the relation is recorded the way every
    # decision record states an amendment: in ADR-077's text and in both rows
    # of the decision index. ADR-069 itself is not edited.
    assert "This record amends ADR-069 decisions 1, 2, 3 and 5" in text
    index = _text("architecture/decisions/README.md")
    row_077 = next(line for line in index.splitlines() if "[ADR-077]" in line)
    row_069 = next(line for line in index.splitlines() if "[ADR-069]" in line)
    assert "amends ADR-069 decisions 1, 2, 3 and 5" in row_077, row_077
    assert "amended by ADR-077" in row_069, row_069


def test_TRC_100_the_readme_s_delegation_bullet_says_the_person_sets_the_bounds():
    text = _text("README.md")
    bullet = _flat(_section(text, "- **You set the bounds", "- **Autonomy"))
    assert "at most 24 hours" not in bullet
    assert "the person sets the bounds" in bullet or "bounded" not in bullet, bullet
    assert "until `/compass:revoke`" in bullet and "session start" in bullet, bullet


def test_TRC_101_governance_guardrails_md_states_what_a_guardrail_5_delegation_covers_now():
    text = _flat(_text("governance/guardrails.md"))
    assert "at most 24 hours" not in text
    assert "--for g5" in text and not re.search(r"(?<!--)\bfor g5\b", text), text
    assert "no end time and cover every issue" in text, text
    assert "each irreversible change gets" not in text


def test_TRC_102_docs_entry_exit_evaluation_md_describes_the_delegation_and_review_behavior_that():
    text = _flat(_text("docs/entry-exit-evaluation.md"))
    assert f"/compass:delegate {FLAG_HINT}" in text
    for banned in ("at most 24 hours", "at most five delegations",
                   "marks every one reviewed"):
        assert banned not in text, banned
    assert "only the approvals the session was shown" in text


def test_TRC_103_the_decision_index_names_the_record_that_amends_adr_069():
    rows = [line for line in _text("architecture/decisions/README.md").splitlines()
            if line.startswith("| [ADR-")]
    own = [r for r in rows if r.startswith("| [ADR-077]")]
    assert len(own) == 1, own
    assert "ADR-077" in next(r for r in rows if r.startswith("| [ADR-069]"))


def test_TRC_104_the_upgrade_guide_of_the_release_that_ships_this_change_says_what():
    text = _flat(_text("docs/upgrade-next.md"))
    for needle in ("positional form of `/compass:delegate` is refused",
                   "`--labels` is refused",
                   "own `.compass/delegations/` gives no approval",
                   "`--issue <slug>`", "plain command"):
        assert needle in text, needle


def test_TRC_105_no_current_document_states_a_delegation_limit_that_no_longer_holds():
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    skip = ("tests/", "cli/", ".compass/", "docs/compass/", "CHANGELOG.md",
            "docs/upgrade-7-0-0.md", "docs/releasing.md")
    stale = ("at most 24 hours", "at most five delegations", "/compass:delegate <agent> until")
    found = []
    for name in listed.splitlines():
        if name.startswith(skip) or "/ADR-069-" in name:
            continue
        path = ROOT / name
        try:
            text = _flat(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        found += [(name, phrase) for phrase in stale if phrase in text]
    assert not found, found


def test_TRC_118_the_evidence_type_texts_name_the_issue_form():
    guardrails = yaml.safe_load(_text("governance/guardrails.yml"))
    preset = yaml.safe_load(_text("governance/presets/default/evidence-types.yml"))

    def find(node):
        if isinstance(node, dict):
            if "human-approval" in node and isinstance(node["human-approval"], dict):
                return node["human-approval"].get("description", "")
            for value in node.values():
                found = find(value)
                if found:
                    return found
        return ""

    for label, doc in (("governance/guardrails.yml", guardrails),
                       ("governance/presets/default/evidence-types.yml", preset)):
        text = _flat(find(doc))
        assert "--issue <slug> --delegated --as <agent>" in text, (label, text)
