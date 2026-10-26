# Run by hooks/pre-tool.sh: emit_refusal, render one refusal from the registry.
# The hook passes its arguments on the command line; standard input is closed.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.refusals import render

code = sys.argv[1]
params = dict(arg.split("=", 1) for arg in sys.argv[2:])
print(render(code, **params))
