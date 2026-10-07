#!/usr/bin/env python3
"""Write, or check, the two generated legacy views.

`governance/routing-policy.yml` and `governance/guardrails.yml` are generated
from the default preset (`governance/presets/default/`) and the sidecar
`governance/legacy-views.yml`. With no option this writes both. `--check`
writes nothing and exits 1 when a committed view differs from what the
generator writes. `--pin` rewrites the pinned preset digests in
`tests/fixtures/preset-digests.yml`. `--pin-hashes` rewrites
`tests/fixtures/governance-content-hashes.json`, which pins each view's content
to its version.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))

from compass_pkg import legacy_views  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when a view is stale")
    parser.add_argument("--pin", action="store_true",
                        help="pin the current preset digests")
    parser.add_argument("--pin-hashes", action="store_true",
                        help="pin the content hashes of the two views to their versions")
    parser.add_argument("--root", default=ROOT, help="the directory holding governance/")
    args = parser.parse_args(argv)
    if args.pin:
        print(f"wrote {legacy_views.pin_digests(args.root)}")
        return 0
    if args.pin_hashes:
        print(f"wrote {legacy_views.pin_content_hashes(args.root)}")
        return 0
    if args.check:
        stale = legacy_views.stale_views(args.root)
        for line in stale:
            print(line)
        return 1 if stale else 0
    for path in legacy_views.write_views(args.root):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
