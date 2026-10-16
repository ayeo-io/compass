# compass_pkg.migrate_kinds - which kind each document in an archived issue becomes
"""The mapping table and the per-issue plan of `compass issue migrate`.

Before 7.0.0 the migrate registered every document under its own filename
stem, so the archive holds kind names no catalogue declares (`verify-security`,
`integrated-review-3`, `design`, `prd`). This module says what each name
becomes:

  * a name on the not-an-artifact list stays where it is and is not registered;
  * a name the catalogue declares is that kind;
  * `design` and `prd` are the kinds `technical-design` and `intent`;
  * every review file is a round of the `review` kind;
  * any other name is unmapped: it is reported and left where it is.

`plan_issue` reads one issue and returns what the migrate would do. It writes
nothing, so the dry run and the apply read the same plan, and a plan that
cannot be made (`RoundCollision`) stops the issue before anything changes.
`migrate.py` carries the plan out, one numbered step at a time.
"""
# DEPENDENCY: standard library; compass_pkg.artifact_kinds, compass_pkg.core,
# compass_pkg.stable_ids. It imports no command module.
from __future__ import annotations

import copy
import datetime
import fnmatch
import os
import re
from dataclasses import dataclass, field

import yaml

from compass_pkg import artifact_kinds, word_map
from compass_pkg.core import docs_dir, find_upwards, manifest_path
from compass_pkg.stable_ids import (APPROACH_HOTFIX, APPROACH_QUICK_FIX, APPROACH_SPIKE,
                                    DEPTH_LIGHTWEIGHT, DEPTH_THOROUGH, NOT_AN_ARTIFACT,
                                    STAGE_ASSESS)

#: The migrate runs this after each numbered step of an issue, with the issue's
#: slug and the step's name: "repoint", "register", "move", "rewrite", "pointer"
#: or "stub". It does nothing. A test replaces it with a function that raises, to
#: stop the migrate at that step and look at the issue.
STEP_HOOK = lambda slug, step: None            # noqa: E731

#: The kind a registered, undeclared kind becomes.
ALIAS_KINDS = {"design": "technical-design", "prd": "intent"}

#: The kinds the registry loses; their files stay where they are.
DROPPED_KINDS = ("recommendation",)

REVIEW = "review"

#: How a name is read.
SKIP, KIND, ALIAS, PLAIN, FAMILY, UNMAPPED = (
    "not-an-artifact", "kind", "alias", "plain-round", "family-round", "unmapped")

#: The review families that take the next free round (rule 5).
_FAMILIES = (
    re.compile(r"^review-claims(?:-(\d+))?$"),
    re.compile(r"^security-review(?:-(\d+))?$"),
    re.compile(r"^integrated-review-(\d+)$"),
    re.compile(r"^verify-[a-z]+(?:-(\d+))?$"),
)


class RoundCollision(Exception):
    """Two plain review files claim one round. `files` are `(where, name)`."""

    def __init__(self, slug, round_number, files):
        self.slug, self.round, self.files = slug, round_number, list(files)
        super().__init__(
            "%s: %s both claim review round %d. Resolve the named files "
            "(keep one as review-%d.md and rename or remove the other) and re-run."
            % (slug, " and ".join("%s (%s)" % (n, w) for w, n in self.files),
               round_number, round_number))


@dataclass(frozen=True)
class Target:
    how: str
    kind: str | None = None
    number: int | None = None        # plain: its round; family: the number in the old name


@dataclass(frozen=True)
class Rule:
    """One row of the table: its order, its label and the match."""
    order: int
    label: str
    match: object                    # callable(name, catalogue) -> Target | None


def _rule_skip(name, _catalogue):
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in NOT_AN_ARTIFACT):
        return Target(SKIP)


def _rule_declared(name, catalogue):
    for kind, body in catalogue.items():
        if not isinstance(body, dict):
            continue
        if artifact_kinds.repeats(body):
            number = artifact_kinds.round_of(body, name)
            if number is not None:
                return Target(PLAIN, kind, number)
        elif body.get("file") == name:
            return Target(KIND, kind)


def _rule_alias(name, catalogue):
    stem = name[:-3] if name.endswith(".md") else name
    if stem in ALIAS_KINDS and ALIAS_KINDS[stem] in catalogue:
        return Target(ALIAS, ALIAS_KINDS[stem])


def _rule_plain_review(name, catalogue):
    if name == "review.md" and REVIEW in catalogue:
        return Target(PLAIN, REVIEW, 1)


def _rule_family(name, catalogue):
    stem = name[:-3] if name.endswith(".md") else name
    if REVIEW not in catalogue:
        return None
    for pattern in _FAMILIES:
        found = pattern.match(stem)
        if found:
            return Target(FAMILY, REVIEW, int(found.group(1)) if found.group(1) else 1)


def _rule_unmapped(_name, _catalogue):
    return Target(UNMAPPED)


#: The mapping table. The first row that matches a name decides its target.
KIND_RULES = (
    Rule(1, "a name on the not-an-artifact list", _rule_skip),
    Rule(2, "a name the catalogue declares", _rule_declared),
    Rule(3, "design and prd, the old names of two kinds", _rule_alias),
    Rule(4, "review.md, round 1 of review", _rule_plain_review),
    Rule(5, "review-claims, security-review, integrated-review-<n>, verify-<word>", _rule_family),
    Rule(6, "anything else: reported, left in place", _rule_unmapped),
)


def lookup(name, catalogue, rules=KIND_RULES):
    """The target of one filename (with `.md`) under `rules`. A table with a row
    removed reads the names that row covered as unmapped, or as what a later row
    makes of them."""
    for rule in rules:
        found = rule.match(name, catalogue)
        if found is not None:
            return found
    return Target(UNMAPPED)


def shipped_catalogue():
    """The kinds the shipped default declares, as `{kind: entry}`."""
    return artifact_kinds.catalogue(None)


# --- the plan ---------------------------------------------------------------------


@dataclass
class Move:
    """One document to register, and to move or rename when its path differs."""
    kind: str
    round: int | None
    name: str                        # the filename it has now
    where: str                       # "beside" (the work folder) or "docs"
    old_rel: str                     # project-relative
    new_rel: str
    reason: str = ""                 # for a new registry entry

    @property
    def moves(self):
        return self.old_rel != self.new_rel

    @property
    def renamed(self):
        return self.name != os.path.basename(self.new_rel)


@dataclass
class Plan:
    slug: str
    moves: list = field(default_factory=list)
    both_places: list = field(default_factory=list)   # (Move, note): the new path exists; keep the copy
    repoints: list = field(default_factory=list)      # (entry id, old kind, new kind)
    dropped: list = field(default_factory=list)       # (entry id, kind)
    both_stay: list = field(default_factory=list)     # (old kind, new kind)
    kept_elsewhere: list = field(default_factory=list)  # (name, kind, registered path)
    left: list = field(default_factory=list)          # names on the not-an-artifact list
    unmapped: list = field(default_factory=list)      # (where, name)
    pointer: str | None = None                        # project-relative path to remove
    pointer_kept: str | None = None                   # a file that is not the pointer, left in place
    stub: dict | None = None                          # {"entry": id, "from": rel, "to": rel}
    adopted_map: str | None = None                    # a small map adopted with no depth, kept
    rekinds: list = field(default_factory=list)       # Rekind: a stem-named entry and its target
    rekind_problems: list = field(default_factory=list)  # what a person must do, one line each
    registry_after: list | None = None                # the registry once the rekinds are made
    # Every move the plan made before any was held back. Step 3 reads these, so a
    # stem entry still finds the file it maps to.
    rekind_moves: list = field(default_factory=list)
    held_pairs: list = field(default_factory=list)    # HeldPair: two entries for a person to settle


def load_manifest(task_dir):
    path = manifest_path(task_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _markdown(folder):
    if not os.path.isdir(folder):
        return []
    return [n for n in sorted(os.listdir(folder))
            if n.endswith(".md") and not n.startswith(".")
            and os.path.isfile(os.path.join(folder, n))]


def is_pointer(path, marker):
    try:
        with open(path, encoding="utf-8") as fh:
            return marker in fh.read(400)
    except (OSError, UnicodeDecodeError):
        return False


def _current_word(section, value):
    """`value` in today's words: an archived manifest may still hold a retired one."""
    value = str(value or "")
    return word_map.tables().get(section, {}).get(value) or value


def depth_of(data):
    """The depth the delivery-approach record is registered at: the approach's
    assess stage when that mode is an artifact depth, else lightweight. The short
    forms of a quick fix, a hotfix and a spike are lightweight."""
    if str(data.get("delivery_approach") or "") in (APPROACH_QUICK_FIX, APPROACH_SPIKE, APPROACH_HOTFIX):
        return DEPTH_LIGHTWEIGHT
    mode = _current_word("stage_mode", (data.get("stages") or {}).get(STAGE_ASSESS))
    return DEPTH_THOROUGH if mode == DEPTH_THOROUGH else DEPTH_LIGHTWEIGHT


def plan_issue(task_dir, rename_v1=None, pointer_marker="<!-- compass: moved -->", stays=(),
               data=None):
    """What the migrate does for one issue. It reads and writes nothing.

    `rename_v1` is the v1-to-current filename map: a name it renames is read as its
    new name, because the migrate renames those files first. `data` is the manifest
    to plan against, when it is not the one on disk: the dry run passes the manifest
    it has edited in memory. Raises `RoundCollision` when two plain review files
    claim one round, before anything is written."""
    slug = os.path.basename(os.path.normpath(task_dir))
    plan = Plan(slug)
    data = load_manifest(task_dir) if data is None else data
    if data is None:
        return plan
    task_abs = os.path.abspath(task_dir)
    project = find_upwards(task_abs, ".compass") or task_abs
    work_rel = os.path.relpath(task_abs, project).replace(os.sep, "/")
    docs_rel = docs_dir(task_dir)
    catalogue = shipped_catalogue()
    registry = [e for e in (data.get("artifacts") or []) if isinstance(e, dict)]

    # The registry: kinds to re-point or drop.
    present = {e.get("kind") for e in registry}
    for entry in registry:
        kind = entry.get("kind")
        if kind in DROPPED_KINDS:
            plan.dropped.append((entry.get("id"), kind))
        elif kind in ALIAS_KINDS and kind not in catalogue:
            if ALIAS_KINDS[kind] in present:
                plan.both_stay.append((kind, ALIAS_KINDS[kind]))
            else:
                plan.repoints.append((entry.get("id"), kind, ALIAS_KINDS[kind]))

    # The files, in both folders.
    renames = rename_v1 or {}
    beside_names = set(_markdown(task_abs))
    files = []
    for name in sorted(beside_names):
        if name in stays:
            continue
        if name == "delivery-approach.md" and is_pointer(os.path.join(task_abs, name), pointer_marker):
            continue
        if name in renames and renames[name] not in beside_names:
            name = renames[name]
        files.append(("beside", name))
    docs_names = _markdown(os.path.join(project, docs_rel))
    files += [("docs", n) for n in docs_names]

    plain, family, kind_files = {}, [], []
    for where, name in files:
        target = lookup(name, catalogue)
        if target.how == SKIP:
            plan.left.append(name)
        elif target.how == UNMAPPED:
            plan.unmapped.append((where, name))
        elif target.how == PLAIN:
            plain.setdefault(target.number, []).append((where, name))
        elif target.how == FAMILY:
            family.append((target.number, name, where))
        else:
            kind_files.append((where, name, target))
    for number, claimed in sorted(plain.items()):
        if len(claimed) > 1:
            raise RoundCollision(slug, number, claimed)

    def rel(where, name):
        return "%s/%s" % (work_rel if where == "beside" else docs_rel, name)

    def place(move, dest_name):
        if move.where == "beside" and dest_name in docs_names:
            plan.both_places.append((move, "%s is in both places - %s is registered and the "
                                           "copy beside the manifest is left to compare"
                                     % (move.name, move.new_rel)))
        else:
            plan.moves.append(move)

    held = {n for _w, n in files}
    for where, name, target in kind_files:
        kind = target.kind
        dest_name = catalogue[kind].get("file")
        others = [e for e in registry if e.get("kind") == kind
                  and os.path.basename(str(e.get("path") or "")) != name]
        if target.how == ALIAS and (dest_name in held or others):
            plan.both_stay.append((name[:-3], kind))     # both stay (ACF-44)
            continue
        # A person registered the kind at another file that exists. Re-pointing the
        # entry at this one would discard that record, and a later step would edit
        # this file (ACF-66, DCJ-98). A path whose file is gone holds nothing back,
        # and neither does an old filename this run renames to this one.
        elsewhere = [str(e["path"]) for e in others if e.get("path")
                     and renames.get(os.path.basename(str(e["path"]))) != name
                     and os.path.isfile(os.path.join(project, str(e["path"])))]
        if target.how == KIND and elsewhere:
            plan.kept_elsewhere.append((name, kind, elsewhere[0]))
            continue
        place(Move(kind, None, name, where, rel(where, name), rel("docs", dest_name),
                   "migrated from %s" % name), dest_name)
    for number, claimed in sorted(plain.items()):
        where, name = claimed[0]
        dest_name = artifact_kinds.filename(catalogue[REVIEW], number)
        place(Move(REVIEW, number, name, where, rel(where, name), rel("docs", dest_name),
                   "migrated from %s" % name), dest_name)
    top = max(plain, default=0)
    for offset, (_number, name, where) in enumerate(sorted(family), start=1):
        dest_name = artifact_kinds.filename(catalogue[REVIEW], top + offset)
        place(Move(REVIEW, top + offset, name, where, rel(where, name), rel("docs", dest_name),
                   "migrated from %s" % name), dest_name)
    plan.moves.sort(key=lambda m: (m.kind != "delivery-approach", m.round or 0, m.kind, m.name))

    # The compatibility pointer of an earlier run.
    beside_record = os.path.join(task_abs, "delivery-approach.md")
    if os.path.isfile(beside_record):
        record = next((e for e in registry if e.get("kind") == "delivery-approach"), None)
        registered = str((record or {}).get("path") or "")
        if is_pointer(beside_record, pointer_marker):
            if registered and os.path.isfile(os.path.join(project, registered)):
                plan.pointer = rel("beside", "delivery-approach.md")
        elif registered and os.path.isfile(os.path.join(project, registered)) \
                and registered != rel("beside", "delivery-approach.md"):
            plan.pointer_kept = rel("beside", "delivery-approach.md")

    plan.stub = stub_map(task_dir, data, project, plan)
    plan.adopted_map = adopted_map(data, project, plan)
    after = copy.deepcopy(registry)
    plan.rekind_moves = plan.moves + [m for m, _note in plan.both_places]
    plan.rekinds, plan.rekind_problems, plan.held_pairs = rekind_entries(
        after, plan.rekind_moves, project, catalogue)
    plan.registry_after = after
    # A pair reported for a person stays as it is, entries and files. A move with the
    # pair's kind and round would point the held entry at the stem entry's file, and
    # the next run would merge the two; a move of either file would change it.
    for pair in plan.held_pairs:
        def held(move, pair=pair):
            return (move.kind, move.round) == (pair.kind, pair.round) \
                or {move.old_rel, move.new_rel} & {pair.stem_path, pair.held_path}
        plan.moves = [m for m in plan.moves if not held(m)]
        plan.both_places = [(m, note) for m, note in plan.both_places if not held(m)]
    # A document in both places is registered once, by its both-places entry, so the
    # run that registers it says it is in both places. The copy in the documents
    # folder would otherwise register first, and the both-places line would never be
    # true on an apply.
    both = {(m.kind, m.round, m.new_rel) for m, _note in plan.both_places}
    plan.moves = [m for m in plan.moves
                  if m.moves or (m.kind, m.round, m.new_rel) not in both]
    return plan


# --- the entries the 6.x migrate registered under a filename stem --------------------

#: The fields that say whether a document is approved. They move with the entry's id.
STATUS_FIELDS = ("status", "approved_by", "approved_at", "digest")


@dataclass(frozen=True)
class Rekind:
    """One stem-named entry and the kind (and round) its document becomes. `merged`
    is True when another entry already held that kind and round: one entry stays,
    with the id and approval `_stem_wins` chose. `kept` and `dropped` say, for the
    report, which id and approval or status stayed and which went."""
    entry_id: object
    old_kind: str
    kind: str
    round: int | None
    merged: bool
    held_id: object = None
    kept: str = ""
    dropped: str = ""

    @property
    def label(self):
        return "%s round %d" % (self.kind, self.round) if self.round else self.kind


def is_stem_entry(entry, catalogue):
    """Was this entry registered under a filename stem the table maps elsewhere?
    The 6.x migrate wrote `kind: review` with no round, `kind: review-2` and
    `kind: integrated-review-3`. `design`, `prd` and `recommendation` have their own
    step, and a name no row of the table maps is left as it is."""
    kind = entry.get("kind") if isinstance(entry, dict) else None
    if not isinstance(kind, str) or kind in DROPPED_KINDS or kind in ALIAS_KINDS:
        return False
    body = catalogue.get(kind)
    if isinstance(body, dict):
        return artifact_kinds.repeats(body) and entry.get("round") is None
    return lookup(kind + ".md", catalogue).how in (PLAIN, FAMILY, KIND)


def _target_of(stem, entries, moves, project, catalogue):
    """(kind, round) the stem entry's document becomes, or None when nothing says.

    The file decides, not the stem: `integrated-review-3` takes the next free round,
    which only the plan's move knows. A file an earlier 7.0.0 migrate already renamed
    is found through the entry that run wrote, whose reason names the old file."""
    path = str(stem.get("path") or "")
    if not path:
        return None
    base = os.path.basename(path)
    found = next((m for m in moves if path in (m.old_rel, m.new_rel)), None) \
        or next((m for m in moves if m.name == base), None)
    if found is not None:
        return found.kind, found.round
    if os.path.isfile(os.path.join(project, path)):
        return None
    heir = next((e for e in entries if e is not stem and isinstance(e, dict)
                 and (e.get("path") == path or e.get("reason") == "migrated from %s" % base)
                 and not is_stem_entry(e, catalogue)), None)
    if heir is not None and isinstance(heir.get("kind"), str):
        return heir["kind"], heir.get("round")
    return None


def _may_merge(stem, held, project):
    """May the stem entry's record replace what `held` holds? Yes when they name one
    file, when either file is gone, or when `held` is a draft an earlier migrate
    wrote. With only the stem's file present, the rename gives `held`'s path to that
    file, so the two entries name one document. Two entries that name two files that
    both exist are a person's to settle."""
    stem_path, held_path = stem.get("path"), held.get("path")
    if stem_path == held_path:
        return True
    if not all(os.path.isfile(os.path.join(project, str(path)))
               for path in (stem_path, held_path)):
        return True
    return str(held.get("reason") or "").startswith("migrated from ") \
        and not held.get("approved_by")


@dataclass(frozen=True)
class HeldPair:
    """Two entries the merge step reports for a person: the stem entry and the entry
    already at its kind and round name two files that both exist. The plan holds back
    both entries and both files. Paths are project-relative, as the entries hold them."""
    stem_id: object
    held_id: object
    kind: str
    round: int | None
    stem_path: str
    held_path: str


def rekind_entries(entries, moves, project, catalogue):
    """Move each stem-named entry in `entries` onto the kind and round its document
    becomes, in place. Returns ([Rekind], [problem line], [HeldPair]).

    With no entry at that kind and round, the stem entry is re-pointed: its kind and
    round change and it keeps everything else. With one, the stem entry's id, status
    and approval move onto it and the stem entry is removed, so each file keeps one
    entry. The register step then points the entry at the file's new path. Two
    entries whose files both exist are left as they are and returned as a HeldPair."""
    done, problems, pairs = [], [], []
    for stem in [e for e in entries if is_stem_entry(e, catalogue)]:
        target = _target_of(stem, entries, moves, project, catalogue)
        if target is None:
            problems.append(
                "the registry entry %s (kind %s) names %s, and no document maps to it - "
                "remove the entry, or register its file with `compass issue artifact set` "
                "and then remove it" % (stem.get("id"), stem.get("kind"),
                                        stem.get("path") or "no file"))
            continue
        kind, number = target
        number = number if artifact_kinds.repeats(catalogue.get(kind) or {}) else None
        old_kind = stem.get("kind")
        held = next((e for e in entries if e is not stem and isinstance(e, dict)
                     and e.get("kind") == kind and e.get("round") == number), None)
        if held is None:
            stem["kind"] = kind
            if number:
                stem["round"] = number
            done.append(Rekind(stem.get("id"), old_kind, kind, number, False))
            continue
        if not _may_merge(stem, held, project):
            problems.append(
                "the registry entries %s (kind %s, at %s) and %s (%s, at %s) name two "
                "files that both exist - keep one entry, remove the other, and re-run"
                % (stem.get("id"), old_kind, stem.get("path"), held.get("id"),
                   Rekind(None, old_kind, kind, number, True).label, held.get("path")))
            pairs.append(HeldPair(stem.get("id"), held.get("id"), kind, number,
                                  str(stem.get("path")), str(held.get("path"))))
            continue
        held_id = held.get("id")
        stem_said = _record_of("the stem entry's", stem)
        held_said = _record_of("the round entry's", held)
        if _stem_wins(stem, held):
            held["id"] = stem.get("id")
            for key in STATUS_FIELDS:
                if key in stem:
                    held[key] = stem[key]
                elif key != "status":
                    held.pop(key, None)
            kept, dropped = stem_said, held_said
        else:
            kept, dropped = held_said, stem_said
        entries.remove(stem)
        done.append(Rekind(stem.get("id"), old_kind, kind, number, True,
                           held_id, kept, dropped))
    return done, problems, pairs


def _approved(entry):
    return bool(entry.get("approved_by")) or entry.get("status") == "approved"


def _approval_time(entry):
    """`approved_at` as an aware time, for comparing two approvals. YAML reads an
    unquoted time as a datetime and a quoted one as a string; both are accepted. A
    time that cannot be read sorts before any that can."""
    value = entry.get("approved_at")
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            value = None
    elif isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        value = datetime.datetime(value.year, value.month, value.day)
    if not isinstance(value, datetime.datetime):
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value


def _stem_wins(stem, held):
    """Does the merged entry keep the stem entry's id and approval, or the round's?

    The later approval wins, and the id goes with it, so the entry that survives is
    the one a person approved last. When only one is approved, that one wins. When
    neither is, the round entry's id and status are kept: stage exits write status,
    so the round entry, the one a stage reads now, holds the more current status. A
    tie between two approvals keeps the stem entry."""
    if _approved(stem) != _approved(held):
        return _approved(stem)
    if not _approved(stem):
        return False
    return _approval_time(stem) >= _approval_time(held)


def _record_of(whose, entry):
    """`whose` id and approval, or id and status, in the words the report uses."""
    if _approved(entry):
        said = "its approval by %s at %s" % (entry.get("approved_by") or "no one named",
                                             entry.get("approved_at") or "no recorded time")
    else:
        said = "its status %s, not approved" % (entry.get("status") or "none")
    return "%s id %s and %s" % (whose, entry.get("id"), said)


def adopted_map(data, project, plan):
    """The new path of a distribution map the migrate adopts, unregistered before, on an
    issue with fewer than two subtasks, or None. It is registered with no depth, so the
    stub rule, which reads the lightweight depth, does not judge it: it is kept as a
    person's map and the report lists it (architect ruling on the archive measures)."""
    if any(isinstance(e, dict) and e.get("kind") == "distribution-map"
           for e in data.get("artifacts") or []):
        return None
    move = next((m for m in plan.moves if m.kind == "distribution-map"), None)
    if move is None:
        return None
    subtasks = data.get("subtasks")
    count = len(subtasks) if isinstance(subtasks, list) \
        else _map_rows(os.path.join(project, move.old_rel))
    return move.new_rel if count < 2 else None


def stub_map(task_dir, data, project, plan=None):
    """The rename of a lightweight distribution map on an issue with fewer than two
    subtasks, or None. The map is renamed, never deleted, so a person can still read it."""
    entry = next((e for e in (data.get("artifacts") or [])
                  if isinstance(e, dict) and e.get("kind") == "distribution-map"), None)
    home = "%s/distribution-map.md" % docs_dir(task_dir)
    moving = {m.kind: m.new_rel for m in (plan.moves if plan else [])}
    if entry is None or _current_word("artifact_depth", entry.get("depth")) != DEPTH_LIGHTWEIGHT \
            or entry.get("status") in ("superseded", "omitted"):
        return None
    rel = moving.get("distribution-map") or entry.get("path") or home
    # A map that is beside the manifest is moved first, so it is read where it will be.
    source = os.path.join(project, rel)
    if not os.path.isfile(source):
        if "distribution-map" not in moving:
            return None
        source = os.path.join(project, next(m.old_rel for m in plan.moves
                                            if m.kind == "distribution-map"))
    subtasks = data.get("subtasks")
    count = len(subtasks) if isinstance(subtasks, list) else _map_rows(source)
    if count >= 2:
        return None
    return {"entry": entry.get("id"), "from": rel, "to": rel + ".v6.bak"}


def _map_rows(path):
    """How many subtask ids a distribution map names: the rows of its `Subtask` table."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return 0
    rows, in_table = 0, False
    for line in lines:
        text = line.strip()
        if not text.startswith("|"):
            in_table = False
            continue
        cells = [c.strip().strip("`*").strip() for c in text.strip("|").split("|")]
        first = cells[0] if cells else ""
        if first.lower() == "subtask":
            in_table = True
        elif in_table and re.fullmatch(r"subtask-\d+", first.lower()):
            rows += 1
    return rows
