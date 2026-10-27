# Run by hooks/pre-tool.sh: compass_say_how_this_project_opted_in.
# The hook passes its arguments on the command line; standard input is closed.

import sys
import compass_pkg
from compass_pkg import project_settings
try:
    rec = project_settings.state(sys.argv[1]).get("initialized")
except Exception:
    sys.exit(0)
if isinstance(rec, dict) and rec.get("by"):
    print(" ".join(str(rec["by"]).split()))
    print(" ".join(str(rec.get("at") or "").split()))
