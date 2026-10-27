# Run by hooks/pre-tool.sh: read the project's enforcement.code_globs.
# The hook passes its arguments on the command line; standard input is closed.

import json, re, sys
import compass_pkg
from compass_pkg import project_settings
try:
    cfg = project_settings.settings(sys.argv[1])
    globs = ((cfg.get("enforcement") or {}).get("code_globs")) or []
    # A string would be walked one character at a time, and `*` alone
    # guards every path. Any other shape is a config this cannot read.
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        raise ValueError("enforcement.code_globs must be a list of strings, "
                         "not %r" % (globs,))
except Exception as exc:            # unreadable config -> cannot answer
    # The refusal already says which file could not be read, so this is the
    # reason alone. A conflict is not a read failure and has its own status
    # and refusal; its stderr line is the keys, and the registry words the rest.
    print(getattr(exc, "file", None) or project_settings.settings_file(sys.argv[1]))
    conflict = isinstance(exc, project_settings.SettingsConflict)
    print(exc.shown if conflict else exc, file=sys.stderr)
    sys.exit(5 if conflict else 4)
print(project_settings.settings_file(sys.argv[1]))
# A safe glob is matched by the shell case statement exactly as
# fnmatch.fnmatch(path, g) matches it (the three tests are in the matcher
# below, for an unsafe glob). No apostrophe here: bash 3.2 miscounts quotes in
# a heredoc inside a command substitution.
safe = all(re.fullmatch(r"[A-Za-z0-9_./*?+=,:@%-]+", g) for g in globs)
print("safe" if safe else "unsafe")
print(json.dumps(globs))
if safe:
    for g in globs:
        print(g)
