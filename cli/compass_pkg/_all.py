"""Aggregates every public name in the package.

The entry point re-exports through this so that anything loading
`cli/compass` by file path - as the test suite does - still finds every
public name in the package.
"""
from compass_pkg.analyze import *  # noqa: F401,F403
from compass_pkg.bdd import *  # noqa: F401,F403
from compass_pkg.calibration import *  # noqa: F401,F403
from compass_pkg.check_cmd import *  # noqa: F401,F403
from compass_pkg.checks import *  # noqa: F401,F403
from compass_pkg.core import *  # noqa: F401,F403
from compass_pkg.borrowed_docs import *  # noqa: F401,F403
from compass_pkg.dashboard import *  # noqa: F401,F403
from compass_pkg.terminal import *  # noqa: F401,F403
from compass_pkg.flow import *  # noqa: F401,F403
from compass_pkg.governance import *  # noqa: F401,F403
from compass_pkg.ingest import *  # noqa: F401,F403
from compass_pkg.landed_by import *  # noqa: F401,F403
from compass_pkg.verb_help import *  # noqa: F401,F403
from compass_pkg.next_cmd import *  # noqa: F401,F403
from compass_pkg.policy import *  # noqa: F401,F403
from compass_pkg.quick_fix_cmd import *  # noqa: F401,F403
from compass_pkg.receipt import *  # noqa: F401,F403
from compass_pkg.refusals import *  # noqa: F401,F403
from compass_pkg.rework import *  # noqa: F401,F403
from compass_pkg.routing import *  # noqa: F401,F403
from compass_pkg.manifest import *  # noqa: F401,F403
from compass_pkg.tdd import *  # noqa: F401,F403
from compass_pkg.init_cmd import *  # noqa: F401,F403
from compass_pkg.terminology_cmd import *  # noqa: F401,F403
from compass_pkg.migrate import *  # noqa: F401,F403
