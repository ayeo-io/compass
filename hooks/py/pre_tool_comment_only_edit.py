# Run by hooks/pre-tool.sh: whether an Edit changes only comments.
# The hook pipes the tool call's JSON to standard input.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import comment_only_edit

sys.exit(comment_only_edit.main(sys.argv[1:], sys.stdin))
