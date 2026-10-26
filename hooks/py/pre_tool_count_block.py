# Run by hooks/pre-tool.sh: compass_count_block, count one block in the interruptions log.
# The hook passes its arguments on the command line; standard input is closed.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.interruptions import record

record(sys.argv[1], sys.argv[2], "hook_blocks")
