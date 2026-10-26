# Run by hooks/prompt-approval.sh: record the approval or rejection the person typed.
# The hook passes its input on file descriptor 3; standard input is closed.

import json
import os
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import prompt_approval

with os.fdopen(3) as fh:
    event = prompt_approval.load_event(fh.read())
result = prompt_approval.handle(event, dict(os.environ), plugin_root=sys.argv[1])
if result is not None:
    print(json.dumps(result.output()))