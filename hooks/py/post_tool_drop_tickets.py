# Run by hooks/post-tool.sh: delete the call tickets of a finished Bash call.
# The hook pipes the tool call's JSON to standard input.

import json, sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import delegation_tickets

try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
if isinstance(event, dict):
    delegation_tickets.drop_call(event)
