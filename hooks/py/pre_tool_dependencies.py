# Run by hooks/pre-tool.sh: the issues this issue waits for.
# The hook passes its arguments on the command line; standard input is closed.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import lifecycle

for line in lifecycle.hook_lines(sys.argv[1]):
    print(line)
