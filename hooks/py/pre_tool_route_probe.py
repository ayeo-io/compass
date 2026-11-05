# Run by hooks/pre-tool.sh: read whether the issue's delivery approach is decided.
# The hook passes its arguments on the command line; standard input is closed.
#
# The manifest's `delivery_approach` key is the record: 9.0.0 writes no
# delivery-approach.md (ADR-091). A document an older issue registered still
# counts, so an archive that holds one reads as it did.

import os
import sys
import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.core import FOUND, load_yaml, resolve_artifact
try:
    task = load_yaml(os.path.join(sys.argv[1], "manifest.yml"))
except Exception:                       # noqa: BLE001 - a missing or unreadable manifest decides nothing
    task = None
decided = isinstance(task, dict) and bool(task.get("delivery_approach"))
if not decided:
    decided = resolve_artifact(sys.argv[1], "delivery-approach")[0] == FOUND
print("found" if decided else "absent")
