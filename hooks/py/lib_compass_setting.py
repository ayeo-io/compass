# Run by scripts/lib/compass-python.sh: compass_setting, print one project setting.
# The script passes its arguments on the command line; standard input is closed.

import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import project_settings

try:
    print(project_settings.scalar(sys.argv[1], sys.argv[2]))
except project_settings.CompassError as exc:
    print("compass: %s" % exc, file=sys.stderr)
    sys.exit(4)
