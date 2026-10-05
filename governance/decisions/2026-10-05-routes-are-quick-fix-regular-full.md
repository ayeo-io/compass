# routes-are-quick-fix-regular-full

## Decided by

jed72

## Date

2026-10-05

## Supersedes

Nothing.

## Decision

The delivery approaches are named `quick-fix`, `regular`, `full`, `hotfix` and `spike`, everywhere: the routing policy's keys, every manifest written from now on, the approach documents and the CLI. The old names - `express`, `standard` and `expedition` as policy keys, `feature` and `initiative` as approach names - are read through `cli/migrate-map.yml` and warned about, and are removed at the next major version.

## Why

Chosen from the recommendation of 5 October. Three delivery approaches had two names, which already caused the retro to weigh every approach as 0. `feature` is about to be an issue type and `initiative` a level of work, so keeping them as approach names would force a second rename; `standard` is a size value and the old key behind that defect. Naming the approaches by weight removes those three collisions. `full` is also a stage weight, as in `assess: full`; the two live in different fields, so the machine never confuses them, and prose always says "the full approach", never a bare "full".

## Evidence

The maintainer's answer to the routing-model questions on 5 October 2026, applied in the change that renames the routes (the one-name-per-route issue).
