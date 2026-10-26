# Run by hooks/pre-tool.sh: read or take the session lease on the issue.
# The hook passes its arguments on the command line; standard input is closed.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.session_lease import check

print(check(*sys.argv[1:]))
