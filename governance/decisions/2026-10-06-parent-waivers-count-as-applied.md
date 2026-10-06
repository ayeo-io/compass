# parent-waivers-count-as-applied

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

When a project extends a published configuration, the waivers in that configuration count as already applied. `compass policy effective` shows each as "parent waiver, not approved by this project". The adopter's approval is the approval of the `extends:` itself when the parent loosens the default.

## Why

The adopter's decision is whether to take the parent as a whole, and the approval of a loosening `extends:` records it. Re-approving each parent waiver would repeat that decision once per waiver, and the parent's maintainers already approved each one in their own file.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-27 of the configurable-framework technical specification.
