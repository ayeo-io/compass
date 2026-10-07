#!/usr/bin/env python3
# =============================================================================
# compass_pkg.core - shared helpers: governance discovery, manifest loading
# and key mapping, and the document resolver
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml

import fnmatch
import re as _re


SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))  # realpath: resolve symlinks
FRAMEWORK_ROOT = os.path.dirname(SCRIPT_DIR)  # cli/.. == the compass repo root

COMPASS_VERSION = "5.6.0"    # the CLI's own version
COMPASS_SCHEMA_VERSION = "2.0"    # the manifest.yml schema this CLI writes
COMPASS_SCHEMA_VERSION_11 = "1.1"  # schema version that introduced manifest.yml.status

from compass_pkg import project_settings  # noqa: E402  (defines CompassError)
from compass_pkg.project_settings import CompassError  # noqa: E402,F401


# --- small helpers -----------------------------------------------------------

def load_yaml(path):
    if not os.path.isfile(path):
        raise CompassError(f"not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return yaml.safe_load(fh) or {}
        except yaml.YAMLError as exc:
            raise CompassError(f"invalid YAML in {path}: {exc}")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def find_upwards(start, rel):
    """Walk up from `start` looking for a path `rel`; return its dir or None."""
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, rel)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


#: The files that make a `governance/` directory a declaration rather than a
#: directory that happens to share the name. Both must be present for the
#: directory to be usable; either one alone means the project declared
#: governance Compass cannot apply.
GOVERNANCE_FILES = ("routing-policy.yml", "guardrails.yml")

#: Markers of the project's own boundary. The upward walk does not go above the
#: first directory holding one of these, so a stray `governance/` in an outer
#: repository or a home directory cannot stop work inside a project.
BOUNDARY_MARKERS = (".compass", ".git")


def _governance_refusal(gov_dir, present, missing):
    """The message an incomplete project governance directory earns.

    This is also the migration path. A project in this state works today -
    its guardrails are quietly ignored - and fails on its first command after
    upgrading, so the message has to be actionable without reading the source.
    Two ways out, each one step.
    """
    shipped = os.path.join(FRAMEWORK_ROOT, "governance")
    return CompassError(
        "this project declares governance that Compass cannot apply.\n\n"
        f"  found   : {os.path.join(gov_dir, present)}\n"
        f"  missing : {os.path.join(gov_dir, missing)}\n\n"
        "Compass will not use its own defaults in place of yours without "
        "telling you, so nothing here is being applied.\n\n"
        "To keep your governance, add the missing file and edit it from there:\n"
        f"  cp {os.path.join(shipped, missing)} {gov_dir}/\n\n"
        "To use the shipped defaults instead, remove:\n"
        f"  {os.path.join(gov_dir, present)}"
    )


def find_governance():
    """The governance directory in force: the project's own, or the shipped one.

    Walks up from the working directory looking for a `governance/` holding at
    least one recognised file, and stops at the project boundary. What it finds
    decides the answer:

    - both files      -> that directory
    - one file only   -> refuse, and say which is missing and how to fix it
    - neither file    -> keep walking; the directory declared nothing
    - nothing at all  -> the framework's shipped defaults, silently

    The refusal is the point. Refuse, because otherwise a project that ships
    `guardrails.yml` without a policy gets the framework's governance with
    no warning, and a declared guardrail must not quietly become advisory.
    """
    cur = os.path.abspath(os.getcwd())
    while True:
        gov_dir = os.path.join(cur, "governance")
        if os.path.isdir(gov_dir):
            present = [f for f in GOVERNANCE_FILES
                       if os.path.isfile(os.path.join(gov_dir, f))]
            if len(present) == len(GOVERNANCE_FILES):
                return gov_dir
            if present:
                missing = next(f for f in GOVERNANCE_FILES if f not in present)
                raise _governance_refusal(gov_dir, present[0], missing)
            # Neither file: a directory that shares the name has declared
            # nothing. Walk past it.

        # Stop at the project's own boundary, inclusive of the directory that
        # marks it. Without this a project that declares no governance would
        # inherit - and could be refused by - a directory its author may not
        # know exists. When no marker is found the walk reaches the
        # filesystem root; that is deliberate.
        if any(os.path.exists(os.path.join(cur, m)) for m in BOUNDARY_MARKERS):
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    shipped = os.path.join(FRAMEWORK_ROOT, "governance")
    if os.path.isfile(os.path.join(shipped, "routing-policy.yml")):
        return shipped
    raise CompassError(
        "could not find governance/ - neither a project-local one nor the "
        "framework's shipped defaults. Run from inside a Compass project or repo."
    )


def find_compass_dir():
    """The project's .compass/ directory (walking up from cwd)."""
    proj = find_upwards(os.getcwd(), ".compass")
    if not proj:
        raise CompassError(
            "no .compass/ directory found - run from inside a Compass project."
        )
    return os.path.join(proj, ".compass")


def load_mode():
    """Read the adoption mode from the project's settings: 'enforced' (default)
    or 'advisory'. In advisory mode every failure is still reported, but the
    CLI exits 0 - useful for piloting Compass without blocking delivery."""
    try:
        root = os.path.dirname(find_compass_dir())
    except CompassError:
        return "enforced"
    # `lenient` lets a conflict through: the mode cannot be read, so the
    # command must not carry on as if it were enforced or advisory.
    mode = str(project_settings.lenient(root).get("adoption") or "").strip().lower()
    return mode if mode == "advisory" else "enforced"


# The stage hand-offs that can wait for a person, and the `autonomy:`
# values that choose among them. Here, not in policy.py, because core reads
# the setting and policy.py already imports core.
CHECKPOINT_STAGES = ("assess", "define", "refine", "plan")
AUTONOMY_VALUES = ("controlled", "balanced", "autonomous")


def load_autonomy():
    """Read `autonomy:` from the project's settings: how often a session stops
    to wait for a person. Missing means `balanced`. Any other value is
    refused, not read as balanced: a typo that silently changed how often
    a session stops would give no sign."""
    try:
        root = os.path.dirname(find_compass_dir())
    except CompassError:
        return "balanced"
    value = project_settings.settings(root).get("autonomy")
    if value is None:
        return "balanced"
    value = str(value).strip().lower()
    if value not in AUTONOMY_VALUES:
        named = os.path.relpath(project_settings.settings_source(root), root)
        raise CompassError(
            f"`autonomy: {value}` in {named} is not a setting; "
            f"use {', '.join(AUTONOMY_VALUES)} (balanced if left out).")
    return value


def mode_banner(mode):
    """The visible banner so an advisory run is never mistaken for enforced."""
    if mode != "advisory":
        return "[mode: enforced]"
    try:
        root = os.path.dirname(find_compass_dir())
    except CompassError:
        root = os.getcwd()
    return ("[mode: advisory] - every failure below is reported but NOT blocking; exit "
            "code will be 0. Set %s when the team is ready."
            % project_settings.named(root, "adoption", "enforced"))


def exit_for_mode(failures, mode):
    """0 in advisory; 1 in enforced when there are failures; 0 otherwise."""
    if failures and mode == "advisory":
        return 0
    return 1 if failures else 0


def session_issue():
    """The issue `COMPASS_ISSUE` names for this session, or None when it is
    unset or empty. Not stripped: the hooks read the value as it is, and a
    value with spaces must be refused by both, not accepted by one."""
    value = os.environ.get("COMPASS_ISSUE", "")
    return value or None


def _one_segment(slug, where):
    """Refuse a slug that is not one path segment.

    A slug is joined onto `.compass/work/`. `../side` or `a/b` would resolve
    outside it or below another issue, and every reader - the pre-tool hook
    included - would then judge the edit by another directory's state.
    """
    if slug in (".", "..") or "/" in slug or "\\" in slug:
        raise CompassError(
            f"{where} names '{slug}', which is not one path segment. An issue "
            f"slug names a directory directly under .compass/work/.")
    return slug


def resolve_issue_dir(slug=None):
    """Resolve an issue's working directory.

    Priority: explicit slug > COMPASS_ISSUE > .compass/current-task pointer >
    most recently changed dir under .compass/work/ (with a warning -
    ambiguous). COMPASS_ISSUE names one session's issue: `compass run` sets
    it, so an unattended session never works on the person's issue. A bad
    value is refused, not passed over for the pointer.
    """
    compass_dir = find_compass_dir()
    work = os.path.join(compass_dir, "work")
    if slug:
        d = os.path.join(work, _one_segment(slug, "--issue"))
        if not os.path.isdir(d):
            raise CompassError(f"no issue directory for slug '{slug}' under {work}")
        return d
    session = session_issue()
    if session is not None:
        d = os.path.join(work, _one_segment(session, "COMPASS_ISSUE"))
        if not os.path.isdir(d):
            raise CompassError(
                f"COMPASS_ISSUE names '{session}', which is not an issue "
                f"under {work}. Set it to a real issue slug, or unset it to "
                f"use .compass/current-task.")
        return d
    pointer = os.path.join(compass_dir, "current-task")
    if os.path.isfile(pointer):
        with open(pointer, "r", encoding="utf-8") as fh:
            s = fh.read().strip()
        if s:
            d = os.path.join(work, _one_segment(s, ".compass/current-task"))
            if os.path.isdir(d):
                return d
            sys.stderr.write(
                f"compass: .compass/current-task points at '{s}' but that "
                f"issue directory does not exist - ignoring.\n"
            )
    # fallback: most recently changed - warn, because this is the fragile path
    if not os.path.isdir(work):
        raise CompassError(f"no issues found: {work} does not exist")
    candidates = [
        os.path.join(work, d) for d in os.listdir(work)
        if os.path.isdir(os.path.join(work, d))
    ]
    if not candidates:
        raise CompassError(f"no issue directories under {work}")
    if len(candidates) > 1:
        sys.stderr.write(
            "compass: no --issue slug and no .compass/current-task pointer - "
            "falling back to the most recently modified issue directory. This "
            "is ambiguous; run `compass issue use <slug>` to be sure.\n"
        )
    return max(candidates, key=os.path.getmtime)


# The manifest's filenames, current first and retired second. A FALLBACK the
# lookup tries second, never a substitution for the current name.
#
# The retired value is here rather than inline because a blanket rename over
# the tree has already collapsed a compatibility map to an identity once - on
# 2026-08-25, taking the fallback with it - and did it again to this very
# function during the manifest sweep, rewriting the pair to
# ("manifest.yml", "manifest.yml"). `test_nir_d3` asserts the two differ, so
# the same edit fails instead of passing silently.
MANIFEST_NAMES = ("manifest.yml", "task" + ".yml")


def manifest_path(task_dir):
    """The issue's manifest, by whichever name it carries on disk.

    Current name first, retired name second - the same order every other
    renamed artifact resolves in. A project that has not run `compass migrate`
    still reads, which ADR-006 needs and which matters more here than
    anywhere else: `.compass/work/` is gitignored in this repository, so its
    records have no git history to restore from.
    """
    for name in MANIFEST_NAMES:
        candidate = os.path.join(task_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(task_dir, "manifest.yml")


def load_manifest(task_dir):
    path = manifest_path(task_dir)
    if not os.path.isfile(path):
        raise CompassError(
            f"no manifest.yml in {task_dir} - has the issue been assessed? "
            f"The manifest is what every command reads."
        )
    task = load_yaml(path)
    # schema_version compatibility: a major mismatch is unsafe to silently run
    # against - the shape may have changed. Same major is OK (additive); absent
    # is OK in 1.0 for back-compat with pre-versioned files.
    sv = task.get("schema_version")
    if sv:
        try:
            major = str(sv).split(".")[0]
        except Exception:
            major = None
        if major is not None and major not in ("1", "2"):
            raise CompassError(
                f"{path}: schema_version is '{sv}', but this CLI handles "
                f"'{COMPASS_SCHEMA_VERSION}' (and reads 1.x by key "
                f"normalisation). Update Compass, or migrate the manifest.yml."
            )
    return normalize_spine(task), path


# The 1.x -> 2.0 manifest key map. Read-side only: every loader normalises to
# the v2 canonical keys, so the rest of the CLI speaks one vocabulary and an
# un-migrated 1.x manifest (an adopter tree mid-upgrade, or the migration tool
# reading its own input) keeps working. Writers always emit 2.0.
SPINE_KEY_MAP = {
    # The root key naming the issue is `issue`. Files written with the
    # retired `task` key still load through this row.
    "task": "issue",
    "readings": "assessment",
    "route": "delivery_approach",
    "phases": "stages",
    "fired_guardrails": "policy_rules_fired",
    "backfills": "follow_ups",
    "reframes": "reassessments",
    # ADR-023. Anthropic's platform docs split single-agent work from
    # multiagent work, and fan out "independent subtasks"; `topology` and
    # `stream` were Compass-only words for both. Manifests written before the
    # rename keep loading through these two rows (ADR-006).
    "topology": "orchestration",
    "stream_ceiling": "subtask_ceiling",
}
ASSESSMENT_KEY_MAP = {
    "blast_radius": "risk",
    "terrain": "familiarity",
    "magnitude": "size",
    "intent": "goal",
    "touches": "labels",
}


def migrate_map_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.pardir, "migrate-map.yml")


# The parsed migrate map, keyed by path, modification time and size: every
# manifest read goes through `normalize_spine`, which asks for several of its
# sections, and parsing the file each time was most of the cost of reading
# many manifests. A changed or swapped file has a new key and is read again.
_MIGRATE_MAP_CACHE = {}


def _migrate_map_data(path):
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    if key not in _MIGRATE_MAP_CACHE:
        with open(path, encoding="utf-8") as fh:
            _MIGRATE_MAP_CACHE[key] = yaml.safe_load(fh) or {}
    return _MIGRATE_MAP_CACHE[key]


def migrate_map_section(name, fallback):
    """One section of `cli/migrate-map.yml`, or the in-module copy of it.

    THE READER LIVES HERE, not in the migration module, because `core` must not
    import `migrate` - that is the import cycle `test_cli_module_split` exists
    to prevent. `migrate` imports `core` already, so the dependency runs one
    way.

    The mapping itself stays in the data file: this module is a scanned
    surface, and the map has to name six retired words. The fallback is for a
    bare checkout with no framework install, and a test proves it equal to the
    file with the file made unreadable - a guard that reads the file both times
    is comparing it with itself.
    """
    try:
        data = _migrate_map_data(migrate_map_path())
    except OSError:
        # No framework install beside this module - use the in-module copy.
        return dict(fallback)
    except yaml.YAMLError as exc:
        # A corrupt map is not a missing map. Falling back here would migrate
        # some manifests and not others, with nothing said; every reader of
        # every manifest goes through this path, so it fails loudly instead.
        raise CompassError(
            f"{migrate_map_path()} is not valid YAML, so retired names cannot "
            f"be migrated: {exc}")
    if not isinstance(data, dict):
        raise CompassError(
            f"{migrate_map_path()} must be a mapping of section name to "
            f"rename table; found {type(data).__name__}")
    section = data.get(name)
    if isinstance(section, dict) and section:
        return section
    return dict(fallback)


# The fallback copy. Retired spellings in a scanned surface would normally be a
# violation; this is the one place they are unavoidable, and the scan exemption
# for it is recorded in governance/terminology.yml.
_V1_STAGE_KEYS = {
    "frame": "assess", "specify": "define", "clarify": "refine",
    "distribute": "breakdown", "build": "implement", "land": "ship",
}


def _stage_key_renames():
    return migrate_map_section("stage_keys", _V1_STAGE_KEYS)


def normalize_spine(task):
    """Return the manifest with v2 canonical keys, whatever generation it was
    written in. A v2 key present alongside its v1 twin wins; the v1 key is
    dropped either way. Idempotent on a v2 manifest."""
    if not isinstance(task, dict):
        return task
    out = {}
    for k, v in task.items():
        k2 = SPINE_KEY_MAP.get(k, k)
        if k2 in out and k in SPINE_KEY_MAP:
            continue
        out[k2] = v
    # Stage keys. `frame` was banned as a stage name at the v2 freeze and
    # survived as a live machine key, because governance/*.yml is not a scanned
    # surface. Archived issues carry the retired spellings, so they
    # are mapped forward on load and rewritten on disk by `compass migrate`
    # (ADR-006: accept both, remove the old at the major version).
    st = out.get("stages")
    if isinstance(st, dict):
        renames = _stage_key_renames()
        mapped = {}
        for k, v in st.items():
            k2 = renames.get(k, k)
            if k2 in mapped and k in renames:
                continue
            mapped[k2] = v
        out["stages"] = mapped

    a = out.get("assessment")
    if isinstance(a, dict):
        a2 = {}
        for k, v in a.items():
            k2 = ASSESSMENT_KEY_MAP.get(k, k)
            if k2 in a2 and k in ASSESSMENT_KEY_MAP:
                continue
            a2[k2] = v
        out["assessment"] = a2
    # 1.x manifests carry owed/paid; readers see outstanding/resolved, and
    # `compass migrate` rewrites them on disk. Value map, mirroring the key
    # map above.
    if out.get("delivery_approach") in SHAPE_VALUE_MAP:
        out["delivery_approach"] = SHAPE_VALUE_MAP[out["delivery_approach"]]
    fups = out.get("follow_ups")
    if isinstance(fups, list):
        for f in fups:
            if isinstance(f, dict) and f.get("status") in FOLLOW_UP_STATUS_MAP:
                f["status"] = FOLLOW_UP_STATUS_MAP[f["status"]]
    # A friction entry's `phase` names a stage, so it maps like a stage key.
    for f in (out.get("friction") if isinstance(out.get("friction"), list) else []):
        if isinstance(f, dict) and f.get("phase") in _stage_key_renames():
            f["phase"] = _stage_key_renames()[f["phase"]]
    # Gate ids. ADR-023 renamed `verify.fitness` to `verify.architecture`.
    # This is not cosmetic: `compass check` looks a gate's accepted evidence
    # types up BY ID, and an id that no longer resolves yields None, which
    # skips the type requirement instead of failing it. An archived gate would
    # then clear with a written note - the one thing a mechanical gate refuses.
    gates = out.get("gates")
    if isinstance(gates, list):
        gate_renames = migrate_map_section("gate_ids", GATE_ID_MAP)
        for g in gates:
            if isinstance(g, dict) and g.get("id") in gate_renames:
                g["id"] = gate_renames[g["id"]]
    # Evidence types. ADR-023 renamed `coherence-check` to `consistency-check`;
    # a manifest written before that keeps clearing its gate (ADR-006).
    ev = out.get("evidence")
    if isinstance(ev, list):
        ev_renames = migrate_map_section("values", {}).get(
            "evidence_type", EVIDENCE_TYPE_MAP)
        for entry in ev:
            if isinstance(entry, dict) and entry.get("type") in ev_renames:
                entry["type"] = ev_renames[entry["type"]]
    # Friction categories. ADR-023 retired `ceremony`, and the enum holds
    # single tokens, so the pair became over-weight / under-weight. A manifest
    # written before that keeps loading (ADR-006).
    friction = out.get("friction")
    if isinstance(friction, list):
        renames = migrate_map_section("values", {}).get(
            "friction_category", FRICTION_CATEGORY_MAP)
        for entry in friction:
            if isinstance(entry, dict) and entry.get("category") in renames:
                entry["category"] = renames[entry["category"]]
    # Assess records a `subtask_ceiling:` number, because it cannot know the
    # shape before the distribution map exists. A manifest written before
    # that carries an orchestration word and no ceiling, so the word is read
    # as the ceiling it implied. The recorded word is KEPT: an archived
    # manifest says what it said, and breakdown legitimately writes an
    # orchestration of its own.
    if out.get("subtask_ceiling") is None:
        word = out.get("orchestration")
        if isinstance(word, str) and word:
            # A capped 1.x manifest recorded the sentence
            # "solo (capped to 1 worktree)"; its first word is the one to read.
            out["subtask_ceiling"] = RETIRED_ORCHESTRATION_CEILING.get(
                word.split(" ")[0], None)
    # The on-disk schema_version is preserved: readers must be able to say
    # honestly what generation a manifest was written in (the receipt reports
    # legacy manifests). Writers stamp the current version when they save.
    return out


# The orchestration words a pre-ceiling manifest could carry, and the ceiling
# each always implied. `multiagent` is None - unbounded - for the same reason the
# evaluator's table said so: no number for it exists anywhere in the policy.
#
# The table stays here because archived manifests still carry the words and
# have to keep reading.
RETIRED_ORCHESTRATION_CEILING = {"solo": 1, "solo-or-pair": 2, "swarm": None}  # vocabulary-scan: allow - names the retired words archived manifests carry (ADR-006)


# 1.x follow-up states -> their v2 spellings, applied read-side by
# normalize_spine above.
FOLLOW_UP_STATUS_MAP = {"owed": "outstanding", "paid": "resolved"}

# The in-module fallback for the friction rename, used when no framework
# install is present to read cli/migrate-map.yml from.
FRICTION_CATEGORY_MAP = {"over-ceremony": "over-weight",
                         "under-ceremony": "under-weight"}

# The in-module fallback for the evidence-type rename, same contract.
EVIDENCE_TYPE_MAP = {"coherence-check": "consistency-check"}

# The in-module fallback for the gate-id rename, same contract.
GATE_ID_MAP = {"verify.fitness": "verify.architecture"}

# The in-module fallback for the guardrail check rename. A project that ran
# /compass:init before ADR-023 names the retired spelling in its own
# guardrails.yml; the check still ships, so resolve the name rather than
# reporting it as unimplemented.
CHECK_NAME_MAP = {"coherence-check-passes": "consistency-check-passes"}

# 1.x shape values -> the v2 change-type values (machine spelling,
# hyphenated). Read-side via normalize_spine; the evaluator
# canonicalises its own writes through the same map; the migrator
# persists it.
SHAPE_VALUE_MAP = {
    "express": "quick-fix",
    "standard": "regular",
    "expedition": "full",
    "feature": "regular",       # renamed 5 Oct 2026: now an issue type
    "initiative": "full",       # renamed 5 Oct 2026: now a level of work
}
#: The route names in weight order; a test keeps them equal to route_shapes.
ROUTE_NAMES = ("spike", "quick-fix", "regular", "hotfix", "full")


def canonical_shape(value):
    # The v2 machine spelling for a delivery-approach value.
    return SHAPE_VALUE_MAP.get(str(value or ""), value)

# Machine delivery-approach values -> the v2 change-type names the display
# layer prints. The manifest keeps the machine value; the terminal never
# shows it (the receipt is the most shareable screen Compass produces).
SHAPE_DISPLAY = {
    "express": "quick fix",
    "standard": "regular",
    "expedition": "full",
    "feature": "regular",
    "initiative": "full",
    # the v2 machine spelling renders without the hyphen
    "quick-fix": "quick fix",
}


def display_shape(value):
    """The v2 change-type name for a machine delivery-approach value."""
    return SHAPE_DISPLAY.get(str(value or ""), str(value or ""))


# The stage-name half of the same boundary: nothing retired is printed,
# whatever the key underneath is called.
#
# THIS MAP IS KEYED ON THE CURRENT KEYS, not the retired ones. `normalize_spine`
# maps a retired key forward on load, so by the time anything is displayed the
# key is already `assess`, `define` and so on - a map still keyed on `frame`
# would silently stop matching and print the raw key.
#
# The map is keyed on the current keys, because `normalize_spine` maps
# retired keys forward before display. It is an identity map. It stays so
# the display layer is the one place a stage name is chosen; the next
# rename edits this table, not the print sites.
STAGE_DISPLAY = {
    "assess": "assess",
    "define": "define",
    "refine": "refine",
    "plan": "plan",
    "breakdown": "breakdown",
    "implement": "implement",
    "verify": "verify",
    "ship": "ship",
}


def display_stage(value):
    """The v2 pipeline-stage name for a machine stage key."""
    return STAGE_DISPLAY.get(str(value or ""), str(value or ""))


def save_manifest(task, path):
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(task, fh, sort_keys=False, default_flow_style=False)


# --- architecture loading (assess) --------------------------------------------
# `Inv-1`: the assessment stays judgement only. The load record goes to
# architecture-loaded.yml (a separate file), never into the manifest's
# `assessment`.
# `Inv-7`: deterministic - same inputs produce same output; sha256 per artifact
#         lets later agents see that a file changed during the issue.
# `Inv-8`: backward compat - absence of architecture/ is silent (empty record).

#: Narrative files assess looks for under architecture/ (in order).
_NARRATIVE_FILES = [
    "architecture/system-context.md",
    "architecture/relations.md",
    "architecture/ownership.md",
]

#: The optional structured file.
_INVARIANTS_FILE = "architecture/invariants.yml"


def _file_sha256(path: str) -> str:
    """Return the hex SHA-256 digest of the file at *path*."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _scan_adrs(arch_dir: str) -> list:
    """Return a list of ADR summary dicts from architecture/decisions/ADR-*.md.

    Each dict: {id, path, title, status}
    Frontmatter is parsed as YAML between the first pair of '---' lines.
    Raises ValueError on malformed YAML frontmatter (TRC-X1 - fail loudly on
    bad structured input, naming the file path and the parse error).
    Files with no frontmatter delimiters have their id/title/status inferred
    from the filename (missing frontmatter is not an error; bad YAML is).
    """
    decisions_dir = os.path.join(arch_dir, "decisions")
    if not os.path.isdir(decisions_dir):
        return []
    adrs = []
    for name in sorted(os.listdir(decisions_dir)):
        if not (name.startswith("ADR-") and name.endswith(".md")):
            continue
        # Derive id from filename as the reliable fallback.
        stem = name[:-3]  # strip .md
        parts = stem.split("-", 2)       # ADR-NNN-slug
        adr_id = "-".join(parts[:2]) if len(parts) >= 2 else stem
        rel_path = f"architecture/decisions/{name}"
        title, status = stem, "proposed"
        full = os.path.join(decisions_dir, name)
        text = open(full, encoding="utf-8").read()  # noqa: WPS515
        # Extract YAML frontmatter between first two '---' lines
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                fm_text = text[3:end].strip()
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except yaml.YAMLError as exc:
                    raise ValueError(
                        f"ADR parse error in {full}: {exc}"
                    ) from exc
                title = fm.get("title", title)
                status = fm.get("status", status)
                if fm.get("id"):
                    adr_id = fm["id"]
        adrs.append({"id": adr_id, "path": rel_path,
                     "title": title, "status": status})
    return adrs


def frame_load_architecture(project_root: str, task_dir: str) -> dict:
    """Load the project's architecture/ artifacts into a structured record.

    Writes ``.compass/work/<task>/architecture-loaded.yml`` and returns the
    same dict.  Never raises on absent files (Inv-8).  Does raise on malformed
    invariants.yml (TRC-X1 - fail loudly on bad structured input).

    Schema (schema_version 1.0):
        schema_version: "1.0"
        loaded_at: <ISO timestamp>
        artifacts:
          - path: <relative to project_root>
            sha256: <hex>
            type: narrative | structured
            parsed: <inline content>   # structured only
        adrs:
          - id: "ADR-001"
            path: <relative path>
            title: <string>
            status: proposed | accepted | superseded
    """
    arch_dir = os.path.join(project_root, "architecture")
    artifacts: list = []

    if os.path.isdir(arch_dir):
        # 1. Narrative files
        for rel in _NARRATIVE_FILES:
            full = os.path.join(project_root, rel)
            if os.path.isfile(full):
                artifacts.append({
                    "path": rel,
                    "sha256": _file_sha256(full),
                    "type": "narrative",
                })

        # 2. Optional structured file - fail loudly on bad YAML (TRC-X1)
        inv_rel = _INVARIANTS_FILE
        inv_full = os.path.join(project_root, inv_rel)
        if os.path.isfile(inv_full):
            raw = open(inv_full, encoding="utf-8").read()
            try:
                parsed = yaml.safe_load(raw)
            except yaml.YAMLError as exc:
                raise CompassError(
                    f"invariants.yml parse error in {inv_full}: {exc}"
                )
            artifacts.append({
                "path": inv_rel,
                "sha256": _file_sha256(inv_full),
                "type": "structured",
                "parsed": parsed,
            })

        # 3. Discover ADRs
        adrs = _scan_adrs(arch_dir)
    else:
        # architecture/ absent - backward compat: produce an empty record
        adrs = []

    record = {
        "schema_version": "1.0",
        "loaded_at": now_iso(),
        "artifacts": artifacts,
        "adrs": adrs,
    }

    # Write to the issue directory (never to the manifest's `assessment` - `Inv-1`)
    os.makedirs(task_dir, exist_ok=True)
    out_path = os.path.join(task_dir, "architecture-loaded.yml")
    with open(out_path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(record, fh, sort_keys=False, default_flow_style=False,
                       allow_unicode=True)

    return record


# --- the delivery-approach evaluator (the deterministic core) ---------------

# when-condition dimension keys: a project policy written against the v1
# names keeps matching until it migrates.
def shape_stages(shape):
    """A route shape's per-stage weights, tolerating the retired key name.

    The policy-side analogue of SPINE_KEY_MAP: a project routing policy
    written before the v2 freeze says `phases:` where the current one says
    `stages:`. Living here rather than at the call site keeps every retired
    spelling in the one module that is allowed to name them, so the
    vocabulary scan can enforce that rule everywhere else.
    """
    raw = dict(shape.get("stages") or shape.get("phases") or {})
    # And the KEYS inside it, not only the block's own name. A policy written
    # before this rename says `frame:` where the current one says `assess:`,
    # and the evaluator prints these straight - so without this the tool that
    # computes the approach is the loudest place a retired name still appears.
    renames = _stage_key_renames()
    out = {}
    for k, v in raw.items():
        k2 = renames.get(k, k)
        if k2 in out and k in renames:
            continue
        out[k2] = v
    return out


_WHEN_KEY_MAP = {
    "blast_radius": "risk", "terrain": "familiarity",
    "magnitude": "size", "intent": "goal", "touches": "labels",
    "touches_any": "labels_any", "touches_common": "labels_common",
}


def reading_matches(when, assessment, orders=None):
    """Does a `when:` condition match the assessment? List value == any-of.
    Special key `labels_any`: intersect against the assessment's `labels`.
    Special key `any_of`: a list of sub-conditions, matching if ANY matches.
    `{at_least: v}` on an ordered dimension: see `catalogue_check.at_least`.

    Keys are otherwise ANDed, so `any_of` alongside another key means "that
    key AND one of these". `any_of` exists because a rule sometimes has to
    fire on genuinely alternative conditions - the human-sign-off guardrail
    applies to the four irreversible domains OR to critical risk, and
    expressing that as separate rules would split one rule into two that can
    come to disagree.
    """
    for key, val in (when or {}).items():
        key = _WHEN_KEY_MAP.get(key, key)
        if key == "any_of":
            clauses = val if isinstance(val, list) else [val]
            if not any(reading_matches(c, assessment, orders) for c in clauses):
                return False
        elif isinstance(val, dict) and "at_least" in val:
            from compass_pkg.catalogue_check import at_least
            if not at_least(key, val["at_least"], assessment.get(key), orders):
                return False
        elif key == "labels_any":
            wanted = val if isinstance(val, list) else [val]
            have = assessment.get("labels") or []
            if not any(t in have for t in wanted):
                return False
        else:
            allowed = val if isinstance(val, list) else [val]
            if assessment.get(key) not in allowed:
                return False
    return True


# --- per-issue artifact names ------------------------------------------------
# The archive uses the v2 filenames. The old-name map lives in
# compass_pkg.migrate, which reads un-migrated trees.
# The five answers a lookup can give. OMITTED and UNRESOLVABLE both mean "no
# document here" and they mean opposite things - one is a decision, the other is
# a broken record. Collapsing them is how a document stops being read while the
# review page reports it as deliberately left out.
FOUND = "found"
OMITTED = "omitted"
UNRESOLVABLE = "unresolvable"
ABSENT = "absent"
#: A registered path resolved to somewhere outside the project. A manifest is
#: a file a contributor can write; paths are measured from the project root,
#: so the string can point anywhere. Reading is all a caller does with the
#: answer, so the worst case is narrow - but refusing costs one comparison.
#: REFUSED never falls back to the flat filename: a rescue would mean the
#: refusal fires only when it changes nothing, which is a check that cannot
#: fail.
REFUSED = "refused"


def _registered_path(task_dir, rel):
    """Resolve a registry `path` against the project root.

    A path in the `artifacts:` registry is measured from the PROJECT ROOT, so
    an entry can name `docs/compass/<date>-<slug>/technical-design.md` while the
    manifest stays under `.compass/work/<slug>/`. That is the whole reason human
    documents can live where a reviewer expects them.

    Returns (path, refused). `refused` is True when the result is not inside the
    project, and the caller must not fall back.

    THE ANCHOR IS NOT THE CALLER. The project root is derived from `task_dir`,
    which is `<project>/.compass/work/<slug>`, and NOT from the working
    directory: `compass` runs from anywhere inside a project, and a document's
    location is a property of the issue rather than of where someone happened to
    type the command.

    THE `evidence:` REGISTRY IS NOT THIS. Evidence stays under the issue
    directory and its paths stay relative to it. The two registries are
    different keys read by different code; reading evidence paths from the
    project root would break every gate in a repository at once.
    """
    if os.path.isabs(rel):
        # An absolute path is not project-relative by definition. Treat it the
        # same as an escape rather than honouring it: there is no legitimate
        # reason for an issue's document to be addressed absolutely, and
        # honouring it is the widest possible version of the hole below.
        return rel, True
    # Found the same way `find_compass_dir` finds it, but walking up from the
    # ISSUE rather than from the working directory. Counting three levels up
    # from task_dir would give the same answer for the usual
    # `<project>/.compass/work/<slug>` and the wrong one everywhere else - a
    # git worktree, a test fixture, or a project that nests its work root
    # differently. A wrong project root does not raise; it silently resolves
    # every registered path against the wrong tree.
    task_dir = os.path.abspath(task_dir)
    project = find_upwards(task_dir, ".compass")
    if project is None:
        # No `.compass/` above this directory. Nothing to anchor to, so treat
        # the issue directory as the root rather than inventing one further up:
        # answering against an arbitrary ancestor is how a resolver reaches
        # into a tree it was never pointed at.
        project = task_dir
    resolved = os.path.normpath(os.path.join(project, rel))
    inside = (resolved == project
              or resolved.startswith(project + os.sep))
    return resolved, not inside


# Where an issue's documents live is a naming rule rather than a reader, so
# it has its own module. Re-exported here because every existing caller
# imports these from core.
from compass_pkg.issue_layout import (  # noqa: E402
    DOCS_ROOT, docs_dir_for, is_issue_document)


def docs_dir(task_dir):
    """The project-relative directory this issue's human documents live in.

    The reader half: looks up the slug and the manifest's `created:` date, then
    asks `issue_layout` for the name. The rule itself holds no reader, which is
    what keeps the two modules from importing each other.
    """
    slug = os.path.basename(os.path.normpath(task_dir))
    created = ""
    path = manifest_path(task_dir)
    if os.path.isfile(path):
        try:
            created = str((load_yaml(path) or {}).get("created") or "").strip()
        except Exception:                            # noqa: BLE001
            created = ""
    return docs_dir_for(created, slug)


def artifact_location(task_dir, name):
    """Where a document is, or where it was looked for - project-relative.

    For a check line to say WHICH file it read. "Nothing to evidence" and
    "everything is typed" are the same green line to a reader, and the first of
    them is what a check that never found the document says, so the path is the
    only thing that tells the two apart.

    Project-relative because an absolute path in a check line is noise, and
    differs between machines for the same issue.
    """
    path = artifact_path(task_dir, name)
    project = os.path.dirname(find_compass_dir() or "") or os.getcwd()
    try:
        rel = os.path.relpath(path, project)
    except ValueError:                               # a different drive on Windows
        rel = path
    rel = rel.replace(os.sep, "/")
    return rel if os.path.isfile(path) else "%s - not there" % rel


def _registry(task_dir):
    """The issue's artifact registry, or [] when it has none.

    Older issue directories predate the registry. A missing one is the
    ordinary case, never a fault.
    """
    path = manifest_path(task_dir)
    if not os.path.isfile(path):
        return []
    try:
        task = load_yaml(path)
    except CompassError:
        return []
    arts = (task or {}).get("artifacts") if isinstance(task, dict) else None
    return arts if isinstance(arts, list) else []


def _entry_for(task_dir, kind):
    for e in _registry(task_dir):
        if isinstance(e, dict) and e.get("kind") == kind:
            return e
    return None


# Kinds this framework renamed, and the filename a landed issue still holds.
# Read-side only: the resolver finds the old file, and `compass migrate`
# rewrites it on disk (ADR-006).
_RENAMED_KIND_FILES = {
    # kind -> the filename a LANDED issue still holds. The values are the
    # RETIRED names on purpose: this map is the only reason an issue that
    # shipped before the rename still resolves. It is a FALLBACK the lookup
    # tries SECOND, never a substitution for the current name.
    #
    # `test_trc_b2` asserts each value differs from its key, so a blanket
    # rename that turns this map into an identity fails.
    "technical-design": "design.md",
    "intent": "prd.md",
}


def _flat_names(kind):
    """Every filename to try for a kind, in preference order.

    The name this framework writes TODAY always comes first; a renamed kind
    appends the retired filename, so an issue that landed before the rename
    still resolves.

    The order matters both ways, and a wrong order fails silently. Returning
    the retired name alone would hide every document written after the
    rename. Preferring the retired name where both exist would make every
    reader take the out-of-date copy.
    """
    current = kind if kind.endswith(".md") else kind + ".md"
    retired = _RENAMED_KIND_FILES.get(kind)
    if retired and retired != current:
        return [current, retired]
    return [current]


def _flat_name(kind):
    """The filename a kind is written under today.

    Only the current name. For the retired one a landed issue may still hold,
    ask `_flat_names`.
    """
    return _flat_names(kind)[0]


def _first_flat_on_disk(task_dir, kind):
    """The first of a kind's candidate filenames that is actually there."""
    for candidate in _flat_names(kind):
        path = os.path.join(task_dir, candidate)
        if os.path.isfile(path):
            return path
    return None


def artifact_path(task_dir, name):
    """The on-disk path of a per-issue artifact, by its v2 filename.

    A registered path wins; the flat filename is the fallback, so an issue
    with no registry entry for this document still resolves.

    Callers that need to know WHY that is the answer want resolve_artifact().
    """
    kind = name[:-3] if name.endswith(".md") else name
    entry = _entry_for(task_dir, kind)
    if entry and entry.get("path"):
        registered, refused = _registered_path(task_dir, entry["path"])
        if refused:
            # No fallback. This function owes its callers a path, and the only
            # honest path for a refused entry is the one the framework would
            # write - not a file that happens to sit beside the manifest, which
            # would let a refused entry read as a clean hit.
            return os.path.join(task_dir, name)
        if os.path.isfile(registered):
            return registered
    # Current name first, then the retired one - the same order, through the
    # same helper, as `resolve_artifact`. Two functions that both find an
    # artifact must not disagree about which file they found.
    flat = _first_flat_on_disk(task_dir, kind)
    if flat is not None:
        return flat
    return os.path.join(task_dir, name)


def unregistered_document(task_dir, name):
    """The path of a document in the issue's documents folder that the
    registry does not name, or None when there is no such file.

    A route that does not earn a document cannot register it: refine on a
    feature writes `requirements-review.md` and leaves it unregistered. This
    is how a reader finds that file without building the path itself. The
    project root comes from the issue's folder, not the current directory,
    because the status line runs from wherever Claude Code is.
    """
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))
    path = os.path.join(root, docs_dir(task_dir), name)
    return path if os.path.isfile(path) else None


def resolve_artifact(task_dir, kind):
    """Where a document is, and why that is the answer.

    Returns (state, path, reason):

      FOUND        path is real; reason says which route found it.
      OMITTED      the registry records a deliberate omission, with its reason.
      UNRESOLVABLE an entry names a path that is not there, and the flat
                   filename is not there either. The reason names both paths
                   tried, because the entry is wrong and someone has to fix it.
      ABSENT       no entry and no file. Ordinary for an issue that predates the
                   registry; not a fault on its own.
    """
    entry = _entry_for(task_dir, kind)
    flat = _first_flat_on_disk(task_dir, kind)
    # Both names, so a reader chasing an absence is not sent looking for a file
    # the framework does not write any more.
    tried = " or ".join(_flat_names(kind))

    if entry is not None and entry.get("status") == "omitted":
        return (OMITTED, None,
                entry.get("reason") or "omitted, with no reason recorded")

    if entry is not None and entry.get("path"):
        registered, refused = _registered_path(task_dir, entry["path"])
        if refused:
            # Deliberately before the flat-filename fallback. Rescuing a
            # refused entry with the file beside the manifest would mean the
            # refusal only ever fires when there is nothing to find, so it
            # could never fail on the case it exists for.
            return (REFUSED, None,
                    "%s names %s, which resolves outside the project. A "
                    "registered path is measured from the project root and may "
                    "not leave it."
                    % (entry.get("id", "the entry"), entry["path"]))
        if os.path.isfile(registered):
            if flat is not None:
                # Both copies exist. The registry decides, and the reason names
                # the other one so somebody deletes it - a second copy of a
                # document nobody knows about is the one that gets read next.
                return FOUND, registered, (
                    "the registered path - note there is also a stale %s beside "
                    "the manifest" % os.path.basename(flat))
            return FOUND, registered, "the registered path"
        if flat is not None:
            return FOUND, flat, (
                "the flat filename - the registered path %s is not there"
                % entry["path"])
        return (UNRESOLVABLE, None,
                "%s names %s, which does not exist, and there is no %s either"
                % (entry.get("id", "the entry"), entry["path"], tried))

    if flat is not None:
        return FOUND, flat, "the flat filename"
    return ABSENT, None, "no registry entry and no %s" % tried


def issue_arg(p):
    """The `--issue SLUG` argument, which many verbs take identically.

    One helper instead of the same line in every verb, which also keeps
    `cli/compass` under its line cap.
    """
    p.add_argument("--issue", dest="task", metavar="SLUG",
                   help="issue slug (default: COMPASS_ISSUE, then the "
                        "current-task pointer)")
    return p


def assessment_key_errors(assessment):
    """One error per `assessment:` key the manifest schema does not allow.

    `issue lint` refused such keys only through jsonschema, which a release
    runs, while `approach evaluate --write` and `compass check` passed them
    to landing (#399). All three call this, and it reads the allowed keys
    from the schema with the standard library, so it runs with or without
    jsonschema installed."""
    if not isinstance(assessment, dict):
        return []
    path = os.path.join(FRAMEWORK_ROOT, "schemas", "manifest.schema.json")
    with open(path, encoding="utf-8") as fh:
        allowed = list(json.load(fh)["properties"]["assessment"]["properties"])
    return [f"assessment has a key the manifest schema does not allow: "
            f"'{key}'; the allowed keys are {', '.join(allowed)}"
            for key in assessment if key not in allowed]
