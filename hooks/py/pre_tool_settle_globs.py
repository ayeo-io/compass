# Run by hooks/pre-tool.sh: settle_deferred_globs, match the deferred write targets.
# The hook passes its arguments on the command line; standard input is closed.

import fnmatch, json, os, sys
globs = json.loads(sys.argv[1])
with open(sys.argv[2], "rb") as handle:
    paths = [os.fsdecode(line) for line in handle.read().split(b"\n")[:-1]]
for number, path in enumerate(paths, 1):
    for g in globs:
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.rstrip("/") + "/*") \
                or fnmatch.fnmatch("/" + path, "*/" + g.lstrip("/")):
            print(number)
            print(g)
            sys.exit(0)
