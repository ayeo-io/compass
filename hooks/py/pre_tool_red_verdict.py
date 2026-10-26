# Run by hooks/pre-tool.sh: the red-before-green verdict.
# The hook passes its arguments on the command line; standard input is closed.

# One verdict, shared with `suite-passed`, so the hook and the check cannot
# disagree about what counts as a red. red_first.py documents each word.
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.red_first import verdict_line

print(verdict_line(sys.argv[1], sys.argv[2]))
