# Run by hooks/approval-summary.sh: show the delegation summary for a new prompt.
# Standard input is the hook's own input JSON, which the hook passes on.

import json
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import delegation_tickets, delegations

try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
if not isinstance(event, dict):
    event = {}
session = str(event.get("session_id") or "")
# A new prompt ends the turn before it, which may have ended as Interrupted
# with no Stop hook: a ticket that no command used must not outlive that turn.
delegation_tickets.drop_session(sys.argv[1], session)
state = delegations.summary_state(sys.argv[1])
text = delegations.summary_text(state)
if text:
    print(json.dumps({"systemMessage": text}), flush=True)
# The rows are recorded as shown only after the message is out.
delegations.record_shown(state, session, str(event.get("prompt_id") or ""))
