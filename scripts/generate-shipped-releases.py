#!/usr/bin/env python3
"""Write, or check, the table of shipped governance releases.

Reads every `v*` git tag, takes `governance/routing-policy.yml` and
`governance/guardrails.yml` as that tag shipped them, and writes
`governance/shipped-releases.yml` (version and content digest per file) and
`governance/shipped-releases.tar.xz` (the files, one member per distinct
file). `compass policy migrate` reads those two at run time; it never reads a
tag. Run this after cutting a release tag. `--check` writes nothing and exits
1 when the table lacks a tag or holds an entry that no longer matches its tag.
"""
import argparse
import io
import os
import subprocess
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli", "vendor"))
sys.path.insert(0, os.path.join(ROOT, "cli"))

import yaml  # noqa: E402

from compass_pkg import shipped_releases as sr  # noqa: E402

HEADER = ("# The governance files each shipped release held, by version and content digest.\n"
          "# Written by scripts/generate-shipped-releases.py from the git tags; do not edit.\n"
          "# The files are in shipped-releases.tar.xz. compass policy migrate reads both.\n")


def _git(*argv):
    return subprocess.run(["git", *argv], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def _version_key(tag):
    return tuple(int(part) for part in tag[1:].split("."))


def collect():
    """`(releases, members)` from the tags: the table rows, oldest first, and
    `{member name: text}`."""
    releases, members = [], {}
    for tag in sorted(_git("tag", "--list", "v*").split(), key=_version_key):
        row = {"tag": tag}
        for name, kind, key in ((sr.POLICY, "routing-policy", "routing_policy"),
                                (sr.GUARDRAILS, "guardrails", "guardrails")):
            text = _git("show", f"{tag}:governance/{name}")
            version = str(yaml.safe_load(text).get("version"))
            digest = sr.content_hash(text)
            row[key] = {"version": version, "digest": digest}
            members.setdefault(sr.member_name(kind, version, digest), text)
        releases.append(row)
    return releases, members


def archive_bytes(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:xz", format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(members):
            data = members[name].encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(data), 0, 0o644
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="write nothing; exit 1 when the table is stale")
    args = parser.parse_args(argv)
    releases, members = collect()
    if args.check:
        stale = [t for t in sr.missing_tags(sr.table(ROOT), [r["tag"] for r in releases])]
        stale += [r["tag"] for r in releases
                  if r not in sr.table(ROOT) and r["tag"] not in stale]
        for tag in stale:
            print(f"stale: {tag}")
        return 1 if stale else 0
    table = os.path.join(ROOT, sr.TABLE_FILE)
    with open(table, "w", encoding="utf-8") as fh:
        fh.write(HEADER + yaml.safe_dump({"schema": 1, "releases": releases},
                                         sort_keys=False, default_flow_style=False))
    with open(os.path.join(ROOT, sr.ARCHIVE_FILE), "wb") as fh:
        fh.write(archive_bytes(members))
    print(f"wrote {len(releases)} releases, {len(members)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
