# The example-first refinement chain

A worked walk-through, read once to learn the method.

Good BDD scenarios do not appear fully formed. They emerge through a
disciplined refinement chain: **vague idea → concrete examples → acceptance
criteria → at least one executable specification each**.

1. **Start with the vague idea.** "Users should be able to reset their
   password." This is a wish, not a spec. It is the right starting point -
   not the ending point.

2. **Generate concrete examples.** Ask: *what does that look like in the
   real world?* A user with a valid email who asks for a reset link, gets a
   link. A user whose token has expired, cannot use the old link. A user who
   has already reset once today, hits a rate limit. Concrete examples ground
   abstract wishes in observable events.

3. **Map into acceptance criteria.** Each example suggests a criterion:
   "Given a valid, unexpired reset token, the user can set a new password."
   At this step you are also applying the ubiquitous language - the shared
   vocabulary of the domain that every role (engineer, product owner, QA,
   marketer) uses consistently. Terms that are vague in conversation become
   precise in criteria. "Expired" gets a definition; "rate limit" gets a
   number.

4. **Write at least one executable specification per criterion.** The
   criterion becomes a Given/When/Then scenario. A criterion with no
   runnable scenario is a wish that never became a check - and the acceptance-before-code guardrail
   refuses that: acceptance must be *stated and checkable*. One runnable
   scenario per criterion is the minimum; multiple scenarios cover the edges.

### Naming discipline

Scenario names carry the refinement: they state an **outcome**, not a step.
"should" as a prefix disciplines this well - "should reject an expired
token" names a required outcome, not a call-path.

- *Prefer:* `Scenario: expired token should be rejected`
- *Avoid:* `Scenario: test token expiry check`

The ubiquitous language is not optional. When "user," "subscriber," and
"account" are used interchangeably in scenarios, they carry different
implications to different readers. Pick the domain term and use it
consistently - the spec is the contract between all five roles.

### What stays refused

**User stories** ("As a [role], I want [feature], so that [outcome]") are
refused as a per-role spec format in Compass - see
`architecture/decisions/ADR-004-one-spec-many-lenses.md`. <!-- vocabulary-scan: allow - the record's own filename; ADR-004 keeps the word its decision was about, so a citation must name the real file -->The rationale: a
user story format embeds a single role's
perspective into the spec, which means one role's spec and another role's
spec diverge. Compass uses one `acceptance-criteria.md` that all five roles read
through their own perspective (see `skills/intent-interview/role-translation.md`), not five separate
role-scoped artifacts. The BDD scenario *is* the shared artifact; the
role-translation perspective is how each role reads it. User stories as a format
are fine upstream of Compass (in a brief or a Jira ticket) - they
are not the spec, and they do not replace the scenario.

