# Run by hooks/pre-tool.sh: compass_record_session, record the session on the issue.
# The hook passes its arguments on the command line; standard input is closed.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.session_record import record

record(*sys.argv[1:])
