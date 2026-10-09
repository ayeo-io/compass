---
id: ADR-048
title: Reading issue state across worktrees
status: accepted
date: 2026-10-09
supersedes: ''
superseded_by: ''
---

## Context

An issue records its state in `.compass/work/<slug>/` in the tree where it is worked on. A repository with several git worktrees has several such folders, and one slug can exist in many of them. A reader of one checkout cannot see an issue under way in another.

On the maintainer's machine on 9 October 2026 there were 79 trees and 34,953 issue folders. Most folders in other trees are copies of issues that are already done in the checkout being read.

## Decision

**`--worktrees` on `compass board render` and `compass board refresh` reads the other trees. Without it, only this checkout is read.** The option exists on those two commands only.

- **Which trees.** `git -C <project root> worktree list --porcelain`, run with a fixed argument list and no shell. An entry marked prunable or bare, or whose folder is missing, is skipped and counted. If git fails (not a repository, git missing), the board reads this checkout and says why in the page header.
- **This checkout first.** It is parsed before the other trees are listed, because it is read in any case.
- **Skip what is done here.** A folder in another tree whose slug is done in this checkout, whatever its close reason, is not statted. The checkout's own record decides. A slug that is open or unreadable here is still compared with the copies elsewhere, and a slug done in another tree but open here is still read.
- **One copy per slug.** The copy shown is the one whose `manifest.yml` has the newest modification time. On a tie, this checkout wins, then the tree whose path sorts first. A copy with no manifest ranks below every copy that has one. The newest copy decides even when it cannot be parsed, so the issue goes in the note that lists what the page cannot place. The card names its tree and says how many other trees hold the slug.
- **No parse to choose.** Choosing the copy opens no manifest. It lists folders and reads modification times only. Each chosen manifest is parsed once.
- **Each issue is judged by its own tree.** Its gates and stage depths come from its manifest, its recommendation from its tree's documents, and its evidence is checked against its tree's files. The policy that labels the routing signal is this checkout's.
- **Links.** A folder in another tree that is a link leading out of that tree is not followed. It is listed in the note with its tree and the reason.
- **Nothing is written to any tree's issue state.**

**Measured on that machine** (79 trees, 9 October 2026), before and after the skip:

| Measure | Without the skip | With the skip |
|---|---|---|
| Folders checked | 34,953 | 6,122 |
| Manifests parsed | 489 | 108 |
| Total time | 5.8 s | 2.17 s |

The target for a read of ten worktrees that each hold the archive sample is under 5.0 seconds.

**What `--worktrees` writes to git's object store.** The evidence check for an in-progress issue computes the hash of the tree the issue's test record was made on. For an issue in another worktree it runs git there with a copy of that worktree's index. `git add` and `git write-tree` can write loose objects (file contents and trees not already stored) to the repository's shared object store. Nothing else changes: each tree's files, its real index, `HEAD`, refs and reflogs stay as they were, and the copy of the index is deleted. `compass flow` already does this for this checkout's in-progress issues. `git gc` removes unreferenced loose objects after its prune period. A version that writes nothing would run git against a temporary object directory with the real store as an alternate; it is a follow-up.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| No skip of slugs done here | Simpler rule. | 5.8 s on the measured machine, over the 5.0 s target. |
| Skip slugs done in any tree | Faster still. | It would hide an issue done on another branch but reopened here. |
| Scan the file system for `.compass/` folders | Needs no git. | Slow and unbounded. |
| A tree list in `compass.yml` | Explicit. | Setup, and the list goes out of date. |
| A shared issue store outside any tree | One place to read. | State belongs in the project (ADR-005). |
| Parse every copy and pick by a recorded time | Exact. | About 160 s estimated, and no such field exists. |
| One board per tree | No new rule. | No cross-tree view. |
| Skip the evidence check in other trees | Writes nothing to the object store. | The stale-evidence flag is lost for the very issues the worktree view exists to show. |

## Consequences

**Positive:**
- A reader sees issues under way in other worktrees, named by tree.
- An unreadable manifest in one tree hides no other issue in any tree.

**Negative:**
- A copied archive without preserved modification times can make a stale copy the newest. The card's tree name and "also in" count are the mitigation.
- A slug done here is never shown from another tree, even when another tree holds a newer open copy.
- An open slug whose newest copy is in another tree is parsed twice: once here and once there.
- The evidence check writes loose objects to the shared object store, as described above.

**Neutral / follow-on:**
- `also_in` counts only the trees that were checked for the slug, so it is 0 for a slug done here.

## References

- ADR-005: state is reconstructible from disk and belongs to the project.
- ADR-036: an issue runs against its own stored configuration, never this checkout's policy.
- ADR-046: the delivery board is one data set with one renderer per output.
