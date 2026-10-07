# checked-binaries-are-pinned-in-the-rival-name-gate

## Decided by

The architect agent (compass:architect), on the maintainer's behalf while they were away on 7 October 2026. The maintainer can reverse it.

## Date

2026-10-07

## Supersedes

Nothing. It adds to `2026-10-04-rival-names-never-committed.md`, which still holds.

## Decision

The rival-name gate scans every tracked file. A UTF-8 file is scanned as text. Any other file is scanned as its printable runs of four or more characters, so a name in image metadata is found. Compressed bytes can spell a short alias in such a run by chance.

A person who has checked a binary file can pin it in `scripts/rival-name-binary-pins.txt`. Each line is a git blob hash, one space and the file's path. The file holds hashes and paths only, never a name.

- A pin exempts only the content scan of a non-UTF-8 file, and only while both the path and the current blob hash match. Any change to the file gives a new hash, and the file is scanned again.
- A pin never exempts the path scan, a UTF-8 file, or the input of `--text` and `--github-event`.
- A pin whose hash no longer matches, or whose path is no longer tracked, is reported as stale and exempts nothing.
- The gate refuses a pin file with any other content.
- Record sync scans the files it writes with the same reader, and applies the same pins, matched on the path inside the record.
- Before pinning a file, check that its hits lie in compressed data and not in metadata or archive members. When the names key grows, regenerate `scripts/rival-name-hashes.txt` and review the pins.

Pinned on 7 October 2026: `assets/compass-icon.png` and `tests/fixtures/archive-sample.tar.gz`. Scanning decompressed archive members and PNG text chunks is a separate gap, tracked as its own issue.

## Why

A gate that fails on compressed noise gets bypassed. Skipping binary files altogether would drop the check on real image metadata. Pinning each checked file by its exact bytes keeps the check and removes the noise, and any change to the file brings the check back.

## Evidence

When the names key gained an entry on 7 October 2026, the gate reported six matches inside the two pinned files. All six lay inside compressed data: four in the PNG's IDAT chunks, two in the archive's compressed deflate data. The PNG's metadata chunks and the archive's 352 members held no name.
