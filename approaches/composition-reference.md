# How an approach is composed and constrained

Assess does not load this file.

This describes what `compass approach evaluate` does: how a candidate shape
is composed from the four dimensions, and how floors, caps, immovable gates
and role rules then constrain it. A session does not do any of it by hand -
that is the determinism boundary. The CLI computes; you read the dimensions
and run the command.

Read this when tuning `governance/routing-policy.yml`, or when you need to
understand why the CLI returned the approach it did. `compass approach
evaluate --verbose` prints which rules fired for any assessment, and that is
usually the faster answer.

## Composing the candidate delivery approach (Step 1 is in `rubric.md`)

The candidate delivery approach is a composition, not a lookup. Assess
assembles it from per-dimension contributions:

| The delivery approach is heavier when… | The delivery approach is lighter when… |
|---|---|
| risk is `cross-cutting`/`critical` | risk is `trivial` |
| familiarity is `brownfield-unmapped` | familiarity is `greenfield` or `brownfield-mapped` |
| size is `large`/`product` | size is `atomic`/`small` |
| a non-engineering role is involved (more artifacts, more gates) | only `engineer` is involved |

Concretely, `compass approach evaluate` decides, per stage:

- **Define** - how many scenarios, discovery vs. behaviour mapping, how deep.
- **Refine** - full pass, light pass, or collapsed (only collapsible when the
  spec is a single unambiguous scenario *and* no routing rule needs it).
- **Plan** - "edit this file" one-liner, a real technical plan, or a plan plus
  a distribution map.
- **Breakdown** - skipped (solo), pair, or multiagent. Subtask count comes from the
  distribution map; orchestration thresholds come from `.compass/config.yml`.
- **Implement** - test surface target, scaled to risk.
- **Verify** - which review dimensions apply (see below), how many gates.
- **Ship** - trivial integration vs. coordinated multi-worktree merge; which
  follow-ups are owed.

Most compositions land near one of the five reference shapes
(quick fix, feature, initiative, hotfix, spike). Assess names the
nearest reference shape in `delivery-approach.md` for shared vocabulary, then lists any
stage-level deviations from it. A delivery approach that is "Feature, but Verify also runs
the security dimension because risk is cross-cutting" is a normal output.

### Review dimensions by delivery approach (the default; routing rules can add but not remove)

| Dimension | quick fix | Feature | initiative | Hotfix | Spike |
|---|---|---|---|---|---|
| correctness | ✓ | ✓ | ✓ | ✓ | - |
| governance | ✓ | ✓ | ✓ | ✓ | - |
| traceability | ✓ | ✓ | ✓ | ✓ | - |
| regression | - | ✓ | ✓ | ✓ | - |
| security | - | scaled | ✓ | ✓ | - |
| clarity | - | ✓ | ✓ | - | - |
| claims | if role | if role | ✓ | if role | - |

"scaled" = applied in proportion to risk. "if role" = applied when the
product-marketer role is in play. `correctness`, `governance`, `traceability`
are on for every delivery approach because they *are* the default guardrails in
review form. **Spike** runs none of these - it ships nothing, so it has only
its own Conclude gate ("was the question answered?"); see `approaches/spike.md`.

---

## Constraining with the routing rules

The candidate delivery approach - already biased by the routing strategies
above - is now bounded by the **routing rules** in `governance/routing-policy.md`:

1. **floors** raise the delivery approach or force stages back to full weight.
2. **caps** limit scale-up (e.g. the worktree ceiling on critical risk).
3. **immovable_gates** are added whatever the delivery approach.
4. **blocking role_rules** add required artifacts and stage blocks.

Every routing rule that fires is recorded. Assess never applies a
constraint silently - if quick fix became initiative, `delivery-approach.md` says which floor
did it and quotes the floor's rationale.
