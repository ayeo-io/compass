# compass_pkg.candidate_client - the candidate and the client of an outer-loop green
"""The fields `candidate`, `candidate_kind` and `client` of an outer-loop green
record (ADR-085).

A unit-test green and an acceptance green look the same unless the record says
what was tested and through which interface. `compass tdd-green --loop outer`
takes `--candidate <build id>|local` and `--client api|web|cli`. A build id is a
deployed candidate. `local` is a build started from the working tree, named by
the tree id the record already holds, as the product owner decided.

On an issue the four-layer acceptance strategy (`S17`) applies to, an outer-loop
green that lacks either field is refused where it is written (`compass
tdd-green`, `compass quick-fix finish`) and where it is registered (`compass
evidence add`), and `outer-loop-recorded` fails one that reached the registry
another way. The caller decides whether the strategy applies, so this module
needs no scope rule of its own (ADR-079).

`compass retro --acceptance` reads `summary` for the clients per issue and the
deployed and local candidates.
"""
# DEPENDENCY: standard library (os); compass_pkg.core and red_first. It imports
# no command module and no check module, so the check and command modules and
# `acceptance_strategy` can all import it.
from __future__ import annotations

import os

from compass_pkg.core import CompassError
from compass_pkg.red_first import load_record

#: The client interfaces an outer-loop green can name. The list is fixed: a
#: project cannot add a client (ADR-085).
CLIENTS = ("api", "web", "cli")
KINDS = ("local", "deployed")
LOCAL = "local"


def green_records(task, task_dir):
    """`[(path, record)]` of each registered test-run record that holds a passing
    run, in registry order. A path outside the issue folder is not read."""
    root = os.path.realpath(task_dir)
    out = []
    for entry in (task or {}).get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        path = entry.get("path") or ""
        full = os.path.realpath(os.path.join(task_dir, path))
        if os.path.commonpath([root, full]) != root:
            continue
        record = load_record(full)
        if record.get("exit_code") == 0 and record.get("passed") is True:
            out.append((path, record))
    return out


def _missing_text(missing):
    return " and ".join(missing)


def missing(record):
    """The names of `candidate` and `client` the record lacks, in that order."""
    return [f for f in ("candidate", "client")
            if not (isinstance(record.get(f), str) and record[f].strip())]


def named(verb, loop, candidate, client, applies, tree_ids):
    """The fields to write on a green: `{candidate, candidate_kind, client}`, or
    `{}` when neither is given. Raises `CompassError`, before the command runs,
    when the client is not one of `CLIENTS`, when either is given on the inner
    loop, when the strategy `applies` and either is missing on the outer loop,
    and when a local candidate has no tree id to be named by."""
    candidate = candidate.strip() if isinstance(candidate, str) else None
    client = client.strip() if isinstance(client, str) else None
    if client and client not in CLIENTS:
        raise CompassError(
            f"compass {verb}: --client {client!r} is not a client interface; use one of: "
            f"{', '.join(CLIENTS)}. Nothing was run or recorded.")
    if (candidate or client) and loop != "outer":
        raise CompassError(
            f"compass {verb}: --candidate and --client name what an acceptance green ran "
            f"against and through; a unit-test green names neither. Add --loop outer, or "
            f"leave them out.")
    if loop == "outer" and applies:
        lacks = [n for n, v in (("candidate", candidate), ("client", client)) if not v]
        if lacks:
            raise CompassError(
                f"compass {verb}: the outer-loop green names no {_missing_text(lacks)}. "
                f"The four-layer acceptance strategy applies to this issue, so an "
                f"outer-loop green must say what it ran against and through: add "
                f"--candidate <build id>|local and --client {'|'.join(CLIENTS)}. "
                f"Nothing was run or recorded.")
    if not candidate and not client:
        return {}
    out = {}
    if candidate == LOCAL:
        tree = (tree_ids or {}).get("tree_id")
        if not tree:
            raise CompassError(
                f"compass {verb}: --candidate local is named by the tree id of the "
                f"working tree, and git cannot name the tree here. Name the build id "
                f"instead. Nothing was run or recorded.")
        out.update(candidate=tree, candidate_kind=LOCAL)
    elif candidate:
        out.update(candidate=candidate, candidate_kind="deployed")
    if client:
        out["client"] = client
    return out


def fault(path, record):
    """Why an in-scope outer-loop green's candidate or client does not hold, or None."""
    lacks = missing(record)
    if lacks:
        return (f"{path} names no {_missing_text(lacks)}; record the green again with "
                f"`compass tdd-green --loop outer --candidate <build id>|local "
                f"--client {'|'.join(CLIENTS)}`")
    if record.get("client") not in CLIENTS:
        return (f"{path} names client {record.get('client')!r}, which is not one of "
                f"{', '.join(CLIENTS)}")
    if record.get("candidate_kind") not in KINDS:
        return (f"{path} names candidate kind {record.get('candidate_kind')!r}, which is "
                f"not local or deployed")
    return None


def registration_refusal(path, record, applies):
    """The refusal `compass evidence add` gives an outer-loop green with no candidate
    or no client on an issue the strategy `applies` to, or None."""
    if not applies or not isinstance(record, dict) or record.get("loop") != "outer":
        return None
    if record.get("passed") is not True:
        return None
    lacks = missing(record)
    if not lacks:
        return None
    return (f"compass evidence add: {path} is an outer-loop green that names no "
            f"{_missing_text(lacks)}. The four-layer acceptance strategy applies to this "
            f"issue, so the record is not registered. Record the green with `compass "
            f"tdd-green --loop outer --candidate <build id>|local --client "
            f"{'|'.join(CLIENTS)}`, which registers it.")


def summary(task, task_dir):
    """`(clients, kind)` of an issue's registered outer-loop greens: the sorted
    clients they name, and `deployed` when any names a deployed candidate, `local`
    when the rest name a local one, else `none`."""
    outer = [r for _, r in green_records(task, task_dir) if r.get("loop") == "outer"]
    clients = sorted({r["client"] for r in outer if r.get("client") in CLIENTS})
    kinds = {r.get("candidate_kind") for r in outer if r.get("candidate")}
    kind = "deployed" if "deployed" in kinds else (LOCAL if LOCAL in kinds else "none")
    return clients, kind
