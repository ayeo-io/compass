# Run by hooks/pre-tool.sh: match one path against the code globs.
# The hook passes its arguments on the command line; standard input is closed.

import fnmatch, json, sys
path = sys.argv[1]
for g in json.loads(sys.argv[2]):
    if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.rstrip("/") + "/*") \
            or fnmatch.fnmatch("/" + path, "*/" + g.lstrip("/")):
        print(g)
        break
