---
id: ADR-040
title: Stable ids live in one registered constants module
status: proposed
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

The configurable-framework design moves the stages, delivery approaches, checks, gates and dimensions into catalogues that a project extends as data. The catalogues become the one source of truth for what each of them declares. The CLI still needs to name some of them: a built-in check implementation asks whether an issue is a spike, and the migration map turns a retired name into its current one.

Today those names are scattered as string literals through `cli/compass_pkg/`. The five delivery approach ids are `spike`, `quick-fix`, `regular`, `hotfix` and `full`. They appear in two separate tuples of all five, `ROUTE_NAMES` (`cli/compass_pkg/core.py:607`) and `CHECKPOINT_ROUTES` (`cli/compass_pkg/policy.py:76`), and in comparisons such as `task.get("delivery_approach") == "spike"` (`cli/compass_pkg/check_cmd.py:449`).

The approach-name literals were counted with this command, run in `cli/compass_pkg/` on 6 October 2026:

```sh
grep -o -E "[\"'](spike|quick-fix|regular|hotfix|full)[\"']" *.py | wc -l
```

It finds 44 quoted matches on 33 lines in 9 files. Reading each line gives:

- 34 name a delivery approach in code, in `core.py` (15), `routing.py` (6), `policy.py` (5), `quick_fix_cmd.py` (3), `calibration.py` (2), `check_cmd.py` (1), `diagnose.py` (1) and `next_cmd.py` (1).
- 4 are inside comments (`routing.py:342` twice, `analyze.py:78` and `analyze.py:324`).
- 4 are `"full"` used for a stage weight or document depth, not an approach (`analyze.py:80`, `routing.py:304`, `routing.py:345`, `routing.py:360`).
- 2 are `"quick-fix"` as a command name (`next_cmd.py:280`, `quick_fix_cmd.py:84`).

So 10 of the 44 matches are not ids. A test that bans the bare words would fail on ordinary code.

## Decision

**One source of truth for declarations.** What a stage, approach, check, gate or dimension is and does is declared only in the catalogues. Code never restates a declaration.

**One module for ids.** Built-in check implementations, the default loader and the migration map may refer to a stable id only through a new module, `stable_ids.py` in `cli/compass_pkg/`. A stable id is a stage id, an approach id, a gate id or a dimension id. The module:

- holds named constants and nothing else, with no prose;
- imports nothing, so every other module can import it;
- holds only ids that a shipped catalogue defines.

**A test enforces both directions.** It must check that:

- every id in `stable_ids.py` exists in the shipped catalogues;
- no other module in `cli/compass_pkg/` holds a stable id as a string literal.

**The test states its scope in its header.** It scans string literals in three positions: dictionary keys, comparison operands (including `in` against a tuple or set) and tuple or set elements. Each module has an explicit allow list for a literal that matches an id but means something else, such as `"full"` as a document depth or `"quick-fix"` as a command name. An allow-list entry names the line's purpose. The test must prove it can fail: a planted approach id in a comparison in a scanned module must turn it red.

## Alternatives considered

- **No literals at all in the CLI.** Rejected: every id would have to come from loaded configuration, so a built-in implementation could not name the stage or approach it was written for. A rename in a project's data would change what the code checks, with no test to catch it. The registered module keeps the ids fixed in code and checked against the catalogues.
- **Ban the id words anywhere in `cli/compass_pkg/`.** Rejected: 10 of today's 44 matches are not ids, and words such as `plan`, `full` and `regular` are also ordinary strings and verb names.
- **Leave the literals where they are.** Rejected: the same five names already sit in two tuples that must be kept equal by hand, and a rename in the catalogues would leave the code naming an id that no longer exists.

## Consequences

- An id rename in a shipped catalogue fails the test until `stable_ids.py` changes with it, so the rename and the code move in one change.
- Moving today's 34 approach literals into the module touches eight modules, before the stage and gate literals are counted. The design does this in one increment.
- The allow lists are a maintained exception list. Each entry must say why the literal is not an id, so a reviewer can reject a convenient one.
- The scan does not see an id built at run time, for example by string formatting. The scope says so rather than claiming full coverage.

## References

- ADR-012: the v2 vocabulary is frozen; the approach ids in `stable_ids.py` are words under that freeze.
- ADR-033: projects add checks, gates and dimension values as data.
- ADR-038: check implementations carry versions; the implementations that refer to these ids.
- `cli/compass_pkg/core.py:607` (`ROUTE_NAMES`), `cli/compass_pkg/policy.py:76` (`CHECKPOINT_ROUTES`), `cli/compass_pkg/check_cmd.py:449`.
- `governance/routing-policy.yml:324-368` (the five approach shapes today).
- Ledger: `governance/decisions/2026-10-06-old-route-names-readable-until-7-0-0.md` (the approach names, and the old ones readable until 7.0.0).
