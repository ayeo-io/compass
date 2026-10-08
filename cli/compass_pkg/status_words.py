# compass_pkg.status_words - what an issue's stored status says
"""The one place that knows which words the stored `status` can hold.

A manifest stores `backlog` (a hold a person set) or `done` (closed, with a
`close_reason`). It stores no word for work in flight: that state comes from
the records (`lifecycle.state_of`). Manifests written before 6.0.0 hold five
other words, and this module reads them until 7.0.0, so a reader that asks
`is_closed(manifest)` is right for old and new files alike. No other module
compares a status word.
"""
# DEPENDENCY: standard library only. `core` and `lifecycle` import this
# module; it imports nothing from the package.
from __future__ import annotations

STATES = ("backlog", "ready", "in-progress", "in-review", "done")
STORED_STATES = ("backlog", "done")
CLOSE_REASONS = ("completed", "not-planned", "duplicate")

# Words stored before 6.0.0, read until 7.0.0: the close reason each closing
# word stood for, and the words that meant a hold.
_RETIRED_CLOSE_REASON = {"landed": "completed", "abandoned": "not-planned"}
_RETIRED_HOLDS = ("queued", "parked")


def _word(manifest, key="status"):
    value = manifest.get(key) if isinstance(manifest, dict) else None
    return value.strip() if isinstance(value, str) else ""


# Words an in-flight issue could carry before 6.0.0, or that a hand edit
# could add. They are accepted and ignored: the records decide the state.
_IN_FLIGHT_WORDS = ("active", "ready", "in-progress", "in-review")


def stored(manifest):
    """The status text as stored, with `active` for none: the word the board
    counted work in flight under. It is for display and counts, not for
    comparing; ask a predicate instead."""
    value = manifest.get("status") if isinstance(manifest, dict) else None
    return value or _IN_FLIGHT_WORDS[0]


def is_in_flight(manifest):
    """True when no status says the issue is held or closed: the stored
    status is absent or one of the accepted in-flight words."""
    status = _word(manifest)
    return not status or status in _IN_FLIGHT_WORDS


def is_closed(manifest):
    """True for an issue that is done, whatever its close reason."""
    status = _word(manifest)
    return status == STORED_STATES[1] or status in _RETIRED_CLOSE_REASON


def close_reason(manifest):
    """Why a closed issue closed, or None for an open issue and for `done`
    with no reason. A `close_reason` the manifest names wins over the reason
    an old closing word stood for."""
    if not is_closed(manifest):
        return None
    named = _word(manifest, "close_reason")
    if named in CLOSE_REASONS:
        return named
    return _RETIRED_CLOSE_REASON.get(_word(manifest))


def is_completed(manifest):
    """True when the work was delivered: closed with reason `completed`.
    `done` with no reason is not read as completed."""
    return close_reason(manifest) == CLOSE_REASONS[0]


def is_held(manifest):
    """True for an issue a person set aside."""
    status = _word(manifest)
    return status == STORED_STATES[0] or status in _RETIRED_HOLDS


def is_parked(manifest):
    """True for a hold with a reason recorded: the old `parked`, or a
    `backlog` hold that carries `parked_reason` or `parked_at`."""
    if not is_held(manifest):
        return False
    if _word(manifest) == _RETIRED_HOLDS[1]:
        return True
    return _word(manifest) == STORED_STATES[0] and bool(
        manifest.get("parked_reason") or manifest.get("parked_at"))


def is_queued(manifest):
    """True for a hold that is waiting its turn, not parked with a reason."""
    return is_held(manifest) and not is_parked(manifest)
