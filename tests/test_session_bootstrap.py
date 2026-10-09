"""The operating contract reaches a session without the model choosing it.

The SessionStart hook injects compass-contract.md, so the contract reaches
every session, including an adopter's. The contract exists once: `CLAUDE.md`
and `skills/compass-runtime/SKILL.md` shared 46 sentences verbatim - 39% of
`CLAUDE.md` - before this, and they had already drifted, with
`compass-runtime` naming nine agents and omitting `architect`.

`AGENTS.md` is deliberately not part of this. It shares no sentence with
either, because it is the runtime-neutral expression for Codex, Amp and
Cursor. Other runtimes are out of scope for this contract.

Scenario ids: SB-A1..A3, SB-B1..B4, SB-C1, SB-C2, SB-D1, SB-D2 in
session-bootstrap/acceptance-criteria.md
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Named so it cannot collide: a bare `contract.md` is a substring of
# `docs/safety-contract.md` and `templates/ui-contract.md`, and a test that
# greps for it passes on either.
CONTRACT = ROOT / "compass-contract.md"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SESSION_HOOK = ROOT / "hooks" / "session-start.sh"
CLAUDE_MD = ROOT / "CLAUDE.md"
RUNTIME_SKILL = ROOT / "skills" / "compass-runtime" / "SKILL.md"
AGENTS_MD = ROOT / "AGENTS.md"

MAX_CONTRACT_WORDS = 400


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sentences(text):
    """Splits prose into sentences for the overlap check.

    Code blocks and frontmatter out; split on sentence ends and blank lines;
    keep fragments over 40 characters, which is what makes this about prose
    rather than about headings and file paths.
    """
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^---.*?^---", " ", text, flags=re.S | re.M)
    out = []
    for part in re.split(r"(?<=[.!?])\s+|\n\s*\n", text):
        part = " ".join(part.split())
        part = re.sub(r"^[-*#>\d.]+\s*", "", part)
        if len(part) > 40:
            out.append(part)
    return out


def _normalised(text):
    return {re.sub(r"[^a-z0-9 ]", "", s.lower()): s for s in _sentences(text)}


def _session_payload(cwd, source="startup"):
    return {"hook_event_name": "SessionStart", "source": source, "cwd": str(cwd)}


def _run_session_hook(cwd, source="startup", project_dir=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["bash", str(SESSION_HOOK)], input=json.dumps(_session_payload(cwd, source)),
        capture_output=True, text=True, env=env, cwd=str(cwd), timeout=60)


def _project(tmp_path, name="proj", compass=True):
    root = (tmp_path / name).resolve()
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    if compass:
        (root / ".compass" / "work").mkdir(parents=True)
        (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    return root


# ---------------------------------------------------------------------------
# SB-A1..A3 - the hook
# ---------------------------------------------------------------------------

def test_sb_a1_the_hook_is_registered_for_every_start(tmp_path):
    spec = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    starts = spec.get("hooks", {}).get("SessionStart")
    assert starts, (
        "hooks/hooks.json declares no SessionStart hook, so nothing loads the "
        "operating contract into a session")

    matchers = " ".join(str(entry.get("matcher", "")) for entry in starts)
    for source in ("startup", "clear", "compact"):
        assert source in matchers, (
            f"the SessionStart hook does not run on '{source}', so the "
            f"contract is lost the first time the session is {source}ed:\n"
            f"{matchers}")


@pytest.mark.parametrize("source", ["startup", "clear", "compact"])
def test_sb_a1b_the_hook_injects_the_contract_in_a_project(tmp_path, source):
    root = _project(tmp_path)
    r = _run_session_hook(root, source, project_dir=root)

    assert r.returncode == 0, (r.stdout + r.stderr)
    payload = json.loads(r.stdout)
    context = json.dumps(payload)
    assert "additionalContext" in context, (
        f"the hook returned no additionalContext:\n{r.stdout}")
    assert "Compass" in context, (
        f"the injected context does not mention Compass:\n{r.stdout[:400]}")


def test_sb_a2_the_contract_is_short_enough_to_always_carry():
    """The hook injects the contract at every session start, clear and
    compact, so it must stay short."""
    assert CONTRACT.exists(), (
        "there is no single contract file - the contract still exists only as "
        "prose inside CLAUDE.md and the compass-runtime skill")
    words = len(CONTRACT.read_text(encoding="utf-8").split())
    assert words <= MAX_CONTRACT_WORDS, (
        f"the contract is {words} words against a {MAX_CONTRACT_WORDS} ceiling. "
        "It is injected on every session start, clear and compact, so a "
        "contract nobody can afford to carry is the same as no contract.")


def test_sb_a3_the_hook_is_silent_outside_a_compass_project(tmp_path):
    """Same boundary as tests/test_hook_as_guest.py, minus the half that
    cannot apply.

    A SessionStart hook has nothing to refuse - it injects or it does not -
    so there is no fail-closed case here, only the guest case.
    """
    root = _project(tmp_path, compass=False)
    r = _run_session_hook(root)
    out = (r.stdout + r.stderr).strip()

    assert r.returncode == 0, out
    assert not out, (
        "the hook spoke at the start of a session in a repository that never "
        f"opted into Compass:\n{out}")


# ---------------------------------------------------------------------------
# SB-B1..B4 - the contract exists once
# ---------------------------------------------------------------------------

def test_sb_b1_both_claude_code_documents_point_at_the_contract():
    for path in (CLAUDE_MD, RUNTIME_SKILL):
        text = path.read_text(encoding="utf-8")
        assert re.search(rf"\b{re.escape(CONTRACT.name)}\b", text), (
            f"{path.relative_to(ROOT)} does not point at {CONTRACT.name}, so "
            "the contract is still being restated rather than referenced")


def test_sb_b2_the_two_claude_code_documents_share_no_sentence():
    """The mechanical form of "the contract exists once".

    The check reads the text, because nothing else keeps two copies the
    same.
    """
    a = _normalised(CLAUDE_MD.read_text(encoding="utf-8"))
    b = _normalised(RUNTIME_SKILL.read_text(encoding="utf-8"))
    shared = sorted(set(a) & set(b))

    assert not shared, (
        f"{len(shared)} sentence(s) appear verbatim in both CLAUDE.md and "
        "skills/compass-runtime/SKILL.md. One of them should carry the "
        "sentence and the other should point at it:\n  "
        + "\n  ".join(a[k][:100] for k in shared[:5]))


def test_sb_b3_the_runtime_neutral_document_is_untouched():
    """AGENTS.md is not a third copy and is not this cycle's work.

    It shares no sentence with either Claude Code document, because it is the
    portable expression for Codex, Amp and Cursor. Other runtimes are out of
    scope for this contract.
    """
    text = AGENTS_MD.read_text(encoding="utf-8")
    assert "Runtime-Neutral" in text, (
        "AGENTS.md no longer says it is the runtime-neutral expression - it "
        "has been rewritten as part of a Claude Code change")
    assert CONTRACT.name not in text, (
        f"AGENTS.md now points at {CONTRACT.name}, a Claude Code artefact. "
        "The portable document must not depend on the adapter's files.")


def test_sb_b4_the_contract_does_not_carry_a_stale_agent_roster():
    """The contract names every shipped agent or none: a roster kept by
    hand goes out of date.

    A roster maintained in prose drifts again. Either the contract names every
    shipped agent, or it names none and points at where they are listed.
    """
    shipped = {p.stem for p in (ROOT / "agents").glob("*.md")}
    assert shipped, "no agents ship, so this check would pass over nothing"

    text = CONTRACT.read_text(encoding="utf-8")
    named = {name for name in shipped if re.search(rf"\b{re.escape(name)}\b", text)}

    if named:
        missing = sorted(shipped - named)
        assert not missing, (
            "the contract names some agents but not all, which is the drift "
            f"this issue exists to remove: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# SB-C1 / SB-C2 - paths
# ---------------------------------------------------------------------------

def _bare_refs(directory, prefix):
    """Files naming `prefix` without ${CLAUDE_PLUGIN_ROOT} in front of it."""
    hits = []
    for path in sorted((ROOT / directory).glob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(rf"`({re.escape(prefix)}[^`]*)`", line):
                before = line[max(0, m.start() - 22):m.start()]
                if "CLAUDE_PLUGIN_ROOT" not in before and "CLAUDE_PLUGIN_ROOT" not in m.group(1):
                    hits.append(f"{path.relative_to(ROOT)}:{n}: {m.group(1)}")
    return hits


def test_sb_c1_plugin_shipped_paths_resolve_from_any_directory():
    """`templates/` and `approaches/` are never copied into a project.

    They ship with the plugin, so a bare relative path resolves inside the
    Compass repository and nowhere else - which is every adopter.
    """
    bare = _bare_refs("commands", "templates/") + _bare_refs("agents", "templates/")
    bare += _bare_refs("commands", "approaches/") + _bare_refs("agents", "approaches/")
    assert not bare, (
        "these references resolve only inside the Compass repository, because "
        "templates/ and approaches/ are never copied into a project:\n  "
        + "\n  ".join(bare))


def test_sb_c2_a_pin_to_the_plugin_root_says_where_a_project_changes_it():
    """The shipped governance prose is read from the plugin root.

    From 6.0.0 `/compass:init` copies no `governance/`: a project changes the
    rules in its `compass.yml`, and `compass policy show` prints what is in
    force. So an instruction can read the shipped prose from
    `${CLAUDE_PLUGIN_ROOT}/governance/`. The trap is a file that pins the
    prose and says nothing else, which ignores both the project's
    `compass.yml` and a 5.x project's own copy of `governance/` (which
    `find_governance()` still resolves project-local first, and `compass
    policy show` does not read that copy). Within eight lines of each pin the
    text must say that an unmigrated 5.x project runs on its own copy.
    """
    unexplained = []
    for directory in ("commands", "agents"):
        for path in sorted((ROOT / directory).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for n in _unexplained_pins(text):
                unexplained.append(f"{path.relative_to(ROOT)}:{n}")
    assert not unexplained, (
        "these pin governance/ to the plugin root without saying, nearby, that "
        "an unmigrated 5.x project runs on its own copy, so that copy would be "
        "ignored:\n  " + "\n  ".join(unexplained))


def _unexplained_pins(text):
    """Line numbers of plugin-root governance pins with no 'unmigrated 5.x
    project' wording within eight lines either side."""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        if re.search(r"CLAUDE_PLUGIN_ROOT[^`\n]*governance/", line):
            near = " ".join(lines[max(0, i - 8):i + 9])
            if not re.search(r"unmigrated\s+5\.x\s+project", near):
                found.append(i + 1)
    return found


def test_sb_c2_the_pin_check_reports_a_pin_without_the_copy_wording():
    """A pin that names `compass policy show` but not the 5.x copy is flagged,
    as is one whose explanation sits far away in the same file."""
    pin = "Read `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` and run `compass policy show`.\n"
    assert _unexplained_pins(pin) == [1]
    near = pin + "An unmigrated 5.x project runs on its own copied `governance/`.\n"
    assert _unexplained_pins(near) == []
    far = pin + "\n" * 20 + "An unmigrated 5.x project runs on its own copy.\n"
    assert _unexplained_pins(far) == [1]


# ---------------------------------------------------------------------------
# SB-D1 / SB-D2 - the other install path, and the portable story
# ---------------------------------------------------------------------------

def test_sb_d1_a_source_install_registers_the_same_hook():
    text = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "SessionStart" in text, (
        "scripts/install.sh does not register the SessionStart hook, so a "
        "source install has no operating contract while the plugin does")


def test_sb_d2_the_portability_mapping_names_the_hook():
    text = (ROOT / "docs" / "portability.md").read_text(encoding="utf-8")
    assert "SessionStart" in text, (
        "docs/portability.md does not name the SessionStart hook, so its "
        "mapping of what each runtime gets is now wrong for Claude Code")


def test_sb_d3_a_source_install_enforces_what_the_plugin_enforces():
    """install.sh and hooks.json must register the same matchers. Otherwise
    a source install does not check shell writes (`sed -i`, redirects,
    heredocs)."""
    spec = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    plugin = {ev: entries[0].get("matcher", "")
              for ev, entries in spec["hooks"].items()}
    installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")

    # install.sh writes its matchers as jq object literals: matcher: "Edit|Write|Bash"
    written = set(re.findall(r'matcher:\s*"([^"]+)"', installer))

    for event, matcher in plugin.items():
        if not matcher:
            continue
        assert matcher in written, (
            f"hooks/hooks.json enforces {event} on `{matcher}`, and "
            f"scripts/install.sh registers {sorted(written)}. A source "
            f"install is weaker than a plugin one.")

    # Registrations, not prose: the comment above register_hooks() explains
    # why MultiEdit was removed, and naming it there is not a registration.
    assert not [m for m in written if "MultiEdit" in m], (
        f"install.sh still registers MultiEdit, which is no longer a Claude "
        f"Code tool: {sorted(written)}")
    assert not [m for m in plugin.values() if "MultiEdit" in m], (
        f"hooks/hooks.json still registers MultiEdit: {plugin}")


def test_sb_d3b_uninstalling_removes_every_hook_installing_added():
    """A hook left behind points at a script that is no longer there."""
    installer = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    register = installer[installer.index("register_hooks()"):installer.index("unregister_hooks()")]
    unregister = installer[installer.index("unregister_hooks()"):]

    # Matched as `.hooks.<event>` with a word boundary, not as a bare
    # substring: "SessionStart" is a substring of "SessionStartX", so a
    # plain `in` check passes against a typo'd key and proves nothing.
    for event in ("PreToolUse", "PostToolUse", "Stop", "SessionStart"):
        pattern = rf"\.hooks\.{event}\b"
        assert re.search(pattern, register), (
            f"install.sh does not register {event}")
        assert re.search(pattern, unregister), (
            f"install.sh registers {event} but never removes it, so an "
            f"uninstall leaves a hook pointing at a deleted script")
