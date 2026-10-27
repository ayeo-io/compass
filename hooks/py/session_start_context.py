# Run by hooks/session-start.sh: build the session's context from the contract and the project.
# The hook passes its arguments on the command line; standard input is closed.

import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    contract = fh.read()

try:
    from compass_pkg.lessons import render_block
    lessons = render_block(sys.argv[2])
except BaseException:  # noqa: BLE001 - the contract must still reach the session
    lessons = ""
if lessons:
    contract = contract.rstrip("\n") + "\n\n" + lessons + "\n"

try:
    from compass_pkg import project_settings, readiness_record
    autonomy = str(project_settings.settings(sys.argv[3]).get("autonomy") or "balanced")
    readiness = readiness_record.hook_line(sys.argv[3], autonomy.strip().lower())
except BaseException:  # noqa: BLE001 - the contract must still reach the session
    readiness = ""
if readiness:
    contract = contract.rstrip("\n") + "\n\n" + readiness + "\n"

# One line when the project sets `language`. It is built from the canonical
# tag only (cli/compass_pkg/language.py), so a value in compass.yml cannot
# carry text into the session. Unset, malformed or unreadable adds nothing.
try:
    from compass_pkg import language
    tag_line = language.hook_line(sys.argv[3])
except BaseException:  # noqa: BLE001 - the contract must still reach the session
    tag_line = ""
if tag_line:
    contract = contract.rstrip("\n") + "\n\n" + tag_line + "\n"

# Approvals made under a delegation that the person has not reviewed are
# shown to the person, never recorded here (ADR-069 decision 5). A summary
# that cannot be built is left out.
#
# The whole message is built before anything is recorded, and each part is
# guarded on its own: a damaged delegation file can cost the list of open-ended
# delegations or the review summary, never the contract, and a row is recorded
# as shown only after the message that shows it is out.
try:
    event = json.loads(sys.argv[4])
except ValueError:
    event = {}
if not isinstance(event, dict):
    event = {}
session = str(event.get("session_id") or "")
try:
    from compass_pkg import delegations
except BaseException:  # noqa: BLE001 - the contract must still reach the session
    delegations = None
lines, review, state = "", "", None
if delegations is not None:
    # Each delegation with no end time is listed, whether or not anything
    # waits for review.
    try:
        lines = delegations.session_start_lines(sys.argv[3], session,
                                                str(event.get("source") or ""))
    except BaseException:  # noqa: BLE001
        lines = ""
    try:
        state = delegations.summary_state(sys.argv[3])
        review = delegations.summary_text(state)
    except BaseException:  # noqa: BLE001
        state, review = None, ""
message = "\n".join(part for part in (lines, review) if part)

out = {
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": contract,
    }
}
if message:
    out["systemMessage"] = message
print(json.dumps(out), flush=True)
if state is not None:
    try:
        # A session start has no prompt id, so the entry it records holds none.
        delegations.record_shown(state, session, "")
    except BaseException:  # noqa: BLE001
        pass
