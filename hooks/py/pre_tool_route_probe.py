# Run by hooks/pre-tool.sh: read whether the issue's delivery approach is decided.
# The hook passes its arguments on the command line; standard input is closed.
#
# The manifest's `delivery_approach` key alone decides. 9.0.0 writes no
# delivery-approach.md (ADR-091), and a document an 8.x issue registered no
# longer counts, because an issue assessed on 8.x holds the key too.

import os
import sys
import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.core import load_yaml
try:
    task = load_yaml(os.path.join(sys.argv[1], "manifest.yml"))
except Exception:                       # noqa: BLE001 - a missing or unreadable manifest decides nothing
    task = None
decided = isinstance(task, dict) and bool(task.get("delivery_approach"))
print("found" if decided else "absent")
