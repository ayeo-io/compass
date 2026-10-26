# Run by hooks/pre-tool.sh: read the issue's delivery approach.
# The hook passes its arguments on the command line; standard input is closed.

import sys
import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.core import FOUND, resolve_artifact
state, _path, _reason = resolve_artifact(sys.argv[1], "delivery-approach")
print("found" if state == FOUND else "absent")
