# Composing and constraining, and the spike case

This file describes what `compass approach evaluate` does; a session does not
do it by hand. `approaches/composition-reference.md`
covers the same ground from the policy's side; this is the reading that goes
with the skill.

## Composing the candidate approach

Go stage by stage, not approach by approach:

- **Define** - scenario count and discovery depth; behaviour mapping if brownfield.
- **Refine** - thorough / lightweight / collapsed. Collapsed is permitted *only* when the
  spec is a single unambiguous scenario *and* no routing guardrail needs the requirements review.
- **Plan** - one-liner / real `technical-design.md` / plan + distribution map.
- **Breakdown** - solo / pair / multiagent, subtask count from the distribution map.
- **Implement** - test-surface target, scaled to risk.
- **Verify** - which review dimensions, how many gates (see "Review
  dimensions by delivery approach" in `approaches/composition-reference.md`).
- **Ship** - trivial integration vs. coordinated merge; which follow-ups are owed.

Name the nearest reference shape for shared vocabulary, then list deviations
explicitly. "Regular, but the verify stage also runs `security` because risk
is cross-cutting" is a correct, expected output - not an exception.

The composition step is where the **routing strategies** apply. They *bias* the
candidate - `default_shapes` says which reference shape an assessment leans towards,
and the tie-breaking `biases` settle the close calls ("when size is
unclear, estimate up"; "prefer the lightest approach that still clears the routing
guardrails"). A routing strategy is a starting point, not a verdict: depart from
one when the issue warrants, and record the departure in `delivery-approach.md`.

## Composing a spike

When goal reads `exploration`, the composition leans towards **Spike** - the
approach for work you cannot yet state as delivery. Compose towards Spike
when *all three* hold: the goal is genuinely exploration not delivery, the work is
a question rather than a known change, and nothing irreversible is in scope.

What is different about a Spike composition:

- **The TDD strategy (red-before-green) is suspended.** Red-before-green is the wrong
  discipline for code written precisely to learn something and likely thrown
  away. The approach-aware pre-tool hook does not block on a Spike - it reads a
  `.compass/work/<task>/.spike` marker file. **The Router writes that marker
  when it composes a spike**; without it the hook will still block.
- **The define stage collapses to the question, the requirements review is skipped, the plan stage collapses to a
  timebox.** A spike has no acceptance criteria - its output is knowledge.
- **Nothing lands from a Spike.** The only exit that keeps code is *graduating*
  - re-assessing into a real delivery approach where the tested-before-ship, acceptance-before-code, and traceability guardrails apply in full.
  This is what makes suspending the TDD strategy safe: a spike cannot put
  untested code on `main`, because it has no path to `main` at all.
- A question that can only be answered by touching irreversible surface
  (`auth`, `payments`, `personal-data`, `migrations`) is **not** a Spike - the
  routing guardrail floors force those to the full approach regardless of intent.

## Constraining with the routing guardrails

After composing - the candidate already biased by the routing strategies - run
it through the **routing guardrails** in `governance/routing-policy.md` in this
order: **floors** raise it, **caps** limit it, **immovable_gates** are added,
blocking **role_rules** add artifacts and stage blocks. Record every routing
guardrail that fires *and quote its rationale* in `delivery-approach.md`. Never apply a
constraint silently - a reader of `delivery-approach.md` must see which bounds were active.

The split is the whole point: routing strategies *bias* what the assess stage
chooses, routing guardrails *bound* what it is allowed to do. A human can override an
assessment value or a strategy-biased choice per-issue; a human cannot override a routing
guardrail per-issue - changing one means amending
`governance/routing-policy.md`.

