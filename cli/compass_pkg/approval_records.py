# compass_pkg.approval_records - the approvals of a human check and of guardrail `G5`
"""Say what an approval record was given for, and whether a `human` check that
lists `approvers:` has a current approval.

An approval names its subject (ADR-066). A `human-approval` record that holds
any key of `SUBJECT_KEYS` was given for that check, waiver, checkpoint,
document or set of decisions. A record that holds none of them, and whose
`guardrail` key is absent or exactly `G5`, was given for guardrail `G5`:
`gives_g5` says so, and `human-approval-present`, the check of `G5`, counts
only such a record. `compass evidence approve --guardrail` writes one, given
the value `G5`.

The rest of this module reads the approvals of a human check.

A tick does not clear such a check, and neither does a deferral tag. The check
also needs a `human-approval` entry in the issue's evidence registry (or an
`artifact-approval` entry, which `compass evidence approve --artifact` writes
and which needs no `scope`) that:

- names the check (`check: <id>`) and holds a decision, `approved` or
  `rejected`,
- holds `approver`, `role`, `scope` and `timestamp` (not `scope` for an
  `artifact-approval` entry),
- is by a listed approver,
- is written for this issue (`issue: <slug>`), and
- is written for the issue's current generation (`generation: <n>`, absent
  when the issue has none).

A record that fails any of these is set aside: it cannot clear the check and
it cannot block it. Of the records that remain, the newest decides, so a later
rejection withdraws an approval. An approver's name is not authenticated, the
same limit as every `human-approval` record. `compass evidence approve`
writes a record; anyone who can write `manifest.yml` can also add one.
"""
# DEPENDENCY: standard library (dataclasses, os);compass_pkg.layers (the project's owner);
# compass_pkg.stable_ids (the id of guardrail `G5`).
# It imports no command module, so the stage-list evaluator and the
# `compass evidence approve` command can both use it.
from __future__ import annotations

import dataclasses
import os
import unicodedata

from compass_pkg.stable_ids import GATE_G5

#: The longest part of a loader reason or a folder name that the approver message shows.
SHOWN_MAX = 120
#: The longest folder name the approver message shows (a path is longer than a reason).
SHOWN_FOLDER_MAX = 240
#: Control, format and line-separator characters: none reaches a person's screen.
HIDDEN = ("Cc", "Cf", "Zl", "Zp")

#: The fields every `human-approval` record holds (the same four
#: `human-approval-present` and a waiver's approval need).
REQUIRED = ("approver", "role", "scope", "timestamp")

#: The evidence type `compass evidence approve --artifact` and `--decisions`
#: write. It meets an artifact's human check here and is read nowhere else:
#: `human-approval-present`, the check of guardrail `G5`, reads only
#: `human-approval`, and a waiver's approval needs that type too.
ARTIFACT_APPROVAL = "artifact-approval"

#: What an `artifact-approval` record holds. It needs no `scope`: the document
#: is the scope.
ARTIFACT_REQUIRED = ("approver", "role", "timestamp")

#: The decisions a record can hold; `rejected` withdraws an earlier approval.
APPROVED, REJECTED = "approved", "rejected"
DECISIONS = (APPROVED, REJECTED)

#: The keys that name what an approval was given for. A `human-approval`
#: record that holds any of them, whatever the value, was given for that
#: subject, so it is not the sign-off of guardrail `G5`. A deny-list, because
#: earlier sign-offs hold extra keys such as `path` or `conditions`. A writer
#: that adds a subject key adds it here (ADR-066).
SUBJECT_KEYS = ("check", "waiver", "checkpoint", "artifact", "decisions")

#: The only guardrail with a sign-off, and the only value of `guardrail` read.
G5 = GATE_G5

#: What `approvers:` lists when it lists the project's owner.
OWNER = "owner"

#: The first words of the detail of a failure, by cause.
NO_RECORD = "no approval record"
NOT_LISTED = "approver not listed"
OTHER_ISSUE = "approval is for another issue"
OTHER_GENERATION = "approval is for another generation"
WITHDRAWN = "approval withdrawn"

#: What a person does to record an approval, for a failure detail.
HOW = ("the agent asks with `compass evidence request --check ID` and the person "
       "types `/compass:approve` in Claude Code, or the person runs `compass evidence "
       "approve --check ID --approver NAME --role ROLE --scope TEXT` at a terminal; a "
       "record holds check, decision, approver, role, scope, timestamp, issue and "
       "generation")

#: How a person records the sign-off of guardrail `G5`, for a failure detail.
G5_HOW = ("in Claude Code the person types `/compass:approve` for the request the agent "
          "made with `compass evidence request --guardrail G5`; or an agent they delegated "
          "g5 to runs it with `--delegated --as <agent>`; or the person runs `compass "
          "evidence approve --guardrail G5` with `--approver <name> --role <role> --scope "
          "<text>` in a terminal")

#: The record that withdraws an approval made under a delegation (ADR-069).
WITHDRAWAL = "approval-withdrawal"


def not_withdrawn(approved, registry):
    """`(standing, note)`: the approved records that no `approval-withdrawal`
    in the registry names, and a failure note naming the guardrail `G5`
    sign-offs that were withdrawn ('' when none was)."""
    withdrawn = {e.get("withdraws"): e.get("id") for e in registry
                 if isinstance(e, dict) and e.get("type") == WITHDRAWAL}
    standing = [a for a in approved if a.get("id") not in withdrawn]
    gone = [a.get("id") for a in approved if a.get("id") in withdrawn and gives_g5(a)]
    note = (f"{WITHDRAWN}: {', '.join(gone)} was withdrawn by "
            f"{', '.join(withdrawn[g] for g in gone)}" if gone else "")
    return standing, note


def provenance(record):
    """How a record was made, in words, from its `via` key (ADR-068
    decision 7). No verdict reads it: the detail of `human-approval-present`
    and the receipt show it. A record with no `via` still counts."""
    via = record.get("via")
    if via == "prompt":
        return "via a typed prompt"
    if via == "terminal":
        return "via a terminal"
    if via == "delegation":
        return (f"via {record.get('approved_by_agent') or 'an agent'} under "
                f"{record.get('delegation') or 'a delegation'}")
    if via is None:
        return "written without a Compass command"
    return f"via {shown(via)}"


#: Why no owner can be named, one value per cause (`OwnerLookup.cause`).
CAUSE_UNREADABLE = "unreadable"                    # the loader rejects compass.yml
CAUSE_NOT_TEXT = "owner-not-text"
CAUSE_CONFIG_ONLY = "owner-in-config-yml"
CAUSE_FILE_ABOVE = "compass-yml-above"
CAUSE_MISSING_IN_WORKTREE = "compass-yml-missing-in-worktree"
CAUSE_MISSING = "compass-yml-missing"
CAUSE_NO_OWNER = "no-owner"                        # reads fine, has no owner key


@dataclasses.dataclass(frozen=True)
class OwnerLookup:
    """The project's owner, or the one cause that no owner can be named."""
    owner: str | None        # the owner, stripped; None when none can be named
    cause: str | None        # None when owner is set; else one CAUSE_*
    detail: str = ""         # the loader's reason, or the kind of the owner value
    root: str = ""           # the folder that holds .compass, where the file is read
    found_in: str = ""       # the folder of the compass.yml found above root


def shown_text(text, limit=SHOWN_MAX):
    """`text` as a person reads it in a message: no control, format or line-separator
    character, white space folded, and at most `limit` characters, so a hostile file name or
    key cannot add a line, move the cursor or make the message long."""
    kept = "".join(c for c in str(text) if unicodedata.category(c) not in HIDDEN)
    return " ".join(kept.split())[:limit]


def _kind(value):
    """The owner value's type in words; `bool` first because it is an `int`."""
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, (int, float)):
        return "a number"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return f"a {type(value).__name__}"


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _owner_in_config(root):
    """Does the old settings file hold a text `owner`? An unreadable file says no.
    The shared settings reader (`project_settings`) is the only code that names the
    old file; this asks it, so the caller can tell a person whose owner sits there
    that `compass.yml` needs it."""
    from compass_pkg import project_settings
    return project_settings.old_file_text(root, "owner") is not None


def _file_above(root):
    """The nearest folder above `root` that holds a `compass.yml`, or ''."""
    node = os.path.dirname(root)
    while node != root:
        if os.path.isfile(os.path.join(node, "compass.yml")):
            return node
        root, node = node, os.path.dirname(node)
    return ""


def owner_and_cause(task_dir):
    """An `OwnerLookup` for the project file above the issue. The first match
    wins: the loader fails, the owner is text, the owner is not text, the owner
    is only in `.compass/config.yml`, the file is above the project folder, the
    file is missing, else the file names no owner."""
    from compass_pkg import layers
    root = layers.find_project_root(task_dir)
    path = os.path.join(root, "compass.yml")
    exists = os.path.isfile(path)
    loaded = None
    if exists:
        try:
            loaded = layers.load_project_layer(root)
        except Exception as exc:                       # noqa: BLE001
            detail = shown_text(str(exc).replace(path + ": ", "").replace(path, ""))
            return OwnerLookup(None, CAUSE_UNREADABLE, detail, root)
    value = loaded[0].doc.get("owner") if loaded else None
    if _text(value):
        return OwnerLookup(_text(value), None, root=root)
    if value is not None and not isinstance(value, str):
        return OwnerLookup(None, CAUSE_NOT_TEXT, _kind(value), root)
    if _owner_in_config(root):
        return OwnerLookup(None, CAUSE_CONFIG_ONLY, root=root)
    if not exists:
        above = _file_above(root)
        if above:
            return OwnerLookup(None, CAUSE_FILE_ABOVE, root=root, found_in=above)
        cause = (CAUSE_MISSING_IN_WORKTREE if os.path.isfile(os.path.join(root, ".git"))
                 else CAUSE_MISSING)
        return OwnerLookup(None, cause, root=root)
    return OwnerLookup(None, CAUSE_NO_OWNER, root=root)


def project_owner(task_dir):
    """The `owner:` of the project file above the issue, or None for every
    cause that no owner can be named. Waivers read the owner from the same
    file (`waivers.allowed_approvers`)."""
    return owner_and_cause(task_dir).owner


def approver_listed(listed, approver, owner=None):
    """Does an `approvers:` list name this approver? The entry `owner` names
    the project's owner (and nobody when the project has none). Any other
    entry names the person with that id, a role included, until roles are
    resolved. `agent` names no one: an approval is a person's. This is the
    person branch of the matching `reviewers:` uses."""
    name = str(approver)
    if name == "agent" or name.startswith("agent:"):
        return False
    names = [owner if str(one) == OWNER else str(one) for one in listed]
    return name in [one for one in names if one]


def shown(value):
    """A value as the detail shows it: `none` when absent, else its repr."""
    return "none" if value is None else repr(value)


def subject_of(record):
    """None when the record names no subject but guardrail `G5`; else the
    subject it names, as a failure detail shows it: "check 'dod-reviewed'",
    "waiver", "guardrail 'g5'". A map value is shown by its key alone."""
    for key in SUBJECT_KEYS:
        if key in record:
            value = record[key]
            return key if isinstance(value, dict) else f"{key} {shown(value)}"
    if "guardrail" in record and not (isinstance(record["guardrail"], str)
                                      and record["guardrail"] == G5):
        return f"guardrail {shown(record['guardrail'])}"
    return None


def gives_g5(record):
    """Was this record given for guardrail `G5`? True when it holds no key of
    `SUBJECT_KEYS` and its `guardrail` key is absent or exactly `G5`."""
    return subject_of(record) is None


def _claims(task, check_id):
    """The `human-approval` and `artifact-approval` entries of the registry that
    name the check and hold a decision, oldest first. An entry that is not a map
    is skipped."""
    return [e for e in task.get("evidence") or []
            if isinstance(e, dict) and e.get("type") in ("human-approval", ARTIFACT_APPROVAL)
            and e.get("check") == check_id and e.get("decision") in DECISIONS]


def listing(check_id, listed, owner):
    """The approvers a check lists, with `owner` shown as the person it
    names."""
    named = [(f"owner ({owner})" if owner else "owner (no project owner is declared)")
             if one == OWNER else one for one in listed]
    return f"{check_id} lists approvers {', '.join(named)}"


def judge(check_id, check, task, task_dir):
    """`(status, detail)` for the approval half of a human check: `pass`, or
    `fail` with the cause first and the approvers who may approve named."""
    listed = [str(one) for one in (check.get("approvers") or [])]
    owner = project_owner(task_dir)
    who = listing(check_id, listed, owner)
    claims = _claims(task, check_id)
    if not claims:
        return "fail", f"{NO_RECORD}: {who}; {HOW}"
    slug = os.path.basename(os.path.normpath(task_dir))
    generation = task.get("generation")
    first = None
    for entry in reversed(claims):
        name = entry.get("id")
        needed = ARTIFACT_REQUIRED if entry.get("type") == ARTIFACT_APPROVAL else REQUIRED
        missing = [k for k in needed if not entry.get(k)]
        if missing:
            first = first or (f"{NO_RECORD}: {name} is missing {', '.join(missing)}; "
                              f"{who}")
            continue
        if not approver_listed(listed, entry["approver"], owner):
            first = first or (f"{NOT_LISTED}: {name} was by {shown(entry['approver'])}; "
                              f"{who}")
            continue
        if entry.get("issue") != slug:
            first = first or (f"{OTHER_ISSUE}: {name} names issue "
                              f"{shown(entry.get('issue'))}, not {slug}; {who}")
            continue
        if entry.get("generation") != generation:
            first = first or (f"{OTHER_GENERATION}: {name} was given for generation "
                              f"{shown(entry.get('generation'))}, the issue is at "
                              f"generation {shown(generation)}; {who}")
            continue
        if entry["decision"] == REJECTED:
            return "fail", (f"{WITHDRAWN}: {name} by {shown(entry['approver'])} "
                            f"rejected {check_id}; {who}")
        return "pass", f"{name}: approved by {entry['approver']}"
    return "fail", first
