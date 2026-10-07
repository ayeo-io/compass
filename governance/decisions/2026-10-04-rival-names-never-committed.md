# rival-names-never-committed

## Decided by

jed72

## Date

2026-10-04

## Supersedes

Nothing recorded. The rule replaces an earlier, narrower one that forbade quoting another product's text in committed files; that rule had no entry here.

## Decision

No rival product's name, alias, organisation, repository slug, URL or domain is committed to GitHub: not in tracked files or paths, branch names, commit messages, pull request titles or bodies, or the delivery record. Committed text uses the codes R1 to R9. The key that maps codes to names is held by the maintainer and is never committed. Comparison runs committed to Compass stay in codes; named public evidence waits for a separate comparison repository, and until it exists no public claim names a rival.

## Why

Not recorded.

## Evidence

The maintainer's rule of 4 October 2026 and its confirmation the same day, in the project's planning notes; issue #366 and the pull request that adds `scripts/rival-name-gate.py`.

## Amendment: pinned binary files (2026-10-07)

The gate scans every tracked file. A UTF-8 file is scanned as text. Any other file is scanned as its printable runs of four or more characters, so a name in image metadata is found. Compressed bytes can spell a short alias in such a run by chance.

A person who has checked a binary file can pin it in `scripts/rival-name-binary-pins.txt`. Each line is a git blob hash, one space and the file's path. The file holds hashes and paths only, never a name.

- A pin exempts only the content scan of a non-UTF-8 file, and only while both the path and the current blob hash match. Any change to the file gives a new hash, and the file is scanned again.
- A pin never exempts the path scan, a UTF-8 file, or the input of `--text` and `--github-event`.
- A pin whose hash no longer matches, or whose path is no longer tracked, is reported as stale and exempts nothing.
- The gate refuses a pin file with any other content.
- Record sync scans the files it writes with the same reader. It applies the same pins, matched on the path inside the record.
- Before pinning a file, check that its hits lie in compressed data and not in metadata or archive members. The key growing means regenerating `scripts/rival-name-hashes.txt` and reviewing the pins.

Pinned now: `assets/compass-icon.png` and `tests/fixtures/archive-sample.tar.gz`. Scanning decompressed archive members and PNG text chunks is a separate gap.
