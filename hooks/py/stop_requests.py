# Run by hooks/stop.sh: show unseen approval requests and drop unused call tickets.
# The hook pipes its input JSON to standard input.

import json
import os
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import approval_requests, delegation_tickets

try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
session = str(event.get("session_id") or "") if isinstance(event, dict) else ""
seen, texts = set(), []
for folder in sys.argv[1:]:
    if not folder or not os.path.isdir(folder):
        continue
    real = os.path.realpath(folder)
    if real in seen:
        continue
    seen.add(real)
    delegation_tickets.drop_session(os.path.dirname(folder), session)
    text = approval_requests.stop_message(folder, os.environ)
    if text:
        texts.append(text)
if texts:
    print(json.dumps({"systemMessage": "\n\n".join(texts)}))
