---
id: ADR-028
title: The Compass CLI ships as a directory, not as a single-file archive
status: accepted
date: 2026-10-02
supersedes: ''
superseded_by: ''
---

## Context

Compass's CLI and the pre-tool hook's checks need Python 3.10 or later. A
person on a machine without it learns this late: macOS no longer ships
`python3`. Issue #271 asked whether shipping the CLI as one file, a
Python zipapp, would make the dependency easier to live with, and asked for a
measured go or no-go.

The CLI was built as a zipapp from `cli/compass_pkg` and `cli/vendor` with
`python3 -m zipapp`, on one Mac with Python 3.11.9. Sizes are file bytes;
the directory's figure counts tracked files only, not bytecode caches. Each
startup time is the median of ten warm runs of `--help`, after one run to
warm the caches:

| Form | Size | `--help` startup |
|---|---|---|
| `cli/` directory | 1.0 MB (1,018,964 bytes) | 0.06 s |
| zipapp, compressed | 307 KB | 0.18 s |
| zipapp, uncompressed | 1.0 MB | 0.18 s |

## Decision

The CLI ships as a directory, as now. Compass does not ship a zipapp.
Instead, it says early when Python 3.10 or later is missing: the
session-start hook and `scripts/install.sh` check for it, and
`docs/safety-contract.md` states what each hook does without it.

## Alternatives considered

- **A zipapp.** Rejected:
  - It still needs `python3`, so it does not remove the dependency the
    issue is about.
  - It saved no space against the directory's tracked files when
    uncompressed, and about 0.7 MB compressed.
  - It tripled startup, from 0.06 s to 0.18 s. Every CLI call, and every
    hook check that imports the CLI's package, would pay that.
  - It needed a code change to find its bundled PyYAML, which the CLI
    checks for as a directory.
  - Outside a project with its own `governance/`, it could not find the
    shipped governance, so the defaults would also have to be bundled and
    read from inside the archive.
  - The plugin install already delivers every file in one step, so a single
    file saves the person nothing.
- **A frozen binary that bundles Python,** such as PyInstaller. It would
  remove the dependency, at the cost of one build per platform, code
  signing on macOS, and a much larger download. Not measured here; it is a
  separate decision if the dependency proves to block adoption.

## Consequences

- Python 3.10 or later stays a requirement, and is now said at install and
  at session start.
- The CLI keeps its current startup. The session-start hook gains one
  `python3` launch for the version check, about 0.02 s.
- A frozen binary stays open as a later decision, with this record as its
  starting point.

## References

- Issue #271, the Python dependency said early.
- `scripts/lib/python-check.sh`, the shared check.
- `docs/safety-contract.md`, "Compass needs Python 3.10 or later".
