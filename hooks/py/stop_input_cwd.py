# Run by hooks/stop.sh: the cwd the hook input names.
# The hook pipes the tool call's JSON to standard input.

import json, sys
try:
    cwd = json.load(sys.stdin).get("cwd")
except Exception:
    cwd = None
if isinstance(cwd, str) and cwd.startswith("/") and "\n" not in cwd:
    print(cwd)
