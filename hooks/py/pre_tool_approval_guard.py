# Run by hooks/pre-tool.sh: the approval and delegation guard.
# The hook pipes the tool call's JSON to standard input.

import json, sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.approval_guard import check

try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
found = check(event if isinstance(event, dict) else {})
if found:
    code, params = found
    print(code)
    for key, value in params.items():
        print("%s=%s" % (key, " ".join(str(value).split())))
elif isinstance(event, dict):
    # The call is allowed. A delegated approval it carries gets a ticket in
    # the common store, which tells the CLI the session and caller Claude
    # Code reported. A ticket that cannot be written blocks nothing: the CLI
    # finds no ticket and refuses, so the approval is not recorded. issue()
    # never raises.
    from compass_pkg import delegation_tickets
    delegation_tickets.issue(event)
