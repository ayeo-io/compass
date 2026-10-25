<!--
TEMPLATE: requirements-review.md
Role in the pipeline: the ambiguity ledger. The review QAs the criteria
against themselves and against governance; every ambiguity found, every
question asked, and every resolution is recorded here. Collapsed on a
quick fix when the criteria are a single scenario certified unambiguous
at assess (and no policy rule needs the review), and on a hotfix where
the reproduction is the clarification. Skipped entirely on a spike - the
behavior is the unknown, so there is nothing to QA. On the regular approach
or anything heavier this file always exists.

Fill every {{PLACEHOLDER}}. Each entry is a closed loop: question →
resolution → who decided → what it changed.
-->
<!-- absorbed: "clarification." -->
<!-- absorbed: "# Clarifications - {{ISSUE_SLUG}}" -->

# Requirements review - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

---

## Self-QA of the spec

<!-- Did the spec contradict itself? Are there scenarios with no observable
     Then? Untestable language? Record what the QA pass of acceptance-criteria.md
     against itself turned up. -->

- {{finding - or "spec is internally consistent; no self-contradictions found"}}

## Governance QA of the spec

<!-- Does any scenario cross a guardrail (the shipped guardrails) or run
     against a strategy (the shipped strategies, or your project's strategies
     file, if it has one), or push a non-goal from
     intent.md? Cite the guardrail or strategy. -->

- {{finding with governance reference - or "no governance conflict found"}}

---

## Ambiguity ledger

<!-- One entry per ambiguity. An open entry blocks the plan stage - refine
     does not hand a question downstream. -->

### Q1 - {{SHORT TITLE}}

- **Question:** {{the ambiguity, stated precisely}}
- **Resolution:** {{the decision made}}
- **Decided by:** {{NAME / role}}
- **Governance reference:** {{e.g. "product strategy: depth for existing users" - or "n/a"}}
- **Spec change:** {{which scenario id in acceptance-criteria.md was added/edited/removed - or "no spec change, clarification only"}}
- **Status:** {{resolved \| open (blocks Plan)}}

### Q2 - {{SHORT TITLE}}

- **Question:** {{…}}
- **Resolution:** {{…}}
- **Decided by:** {{…}}
- **Governance reference:** {{…}}
- **Spec change:** {{…}}
- **Status:** {{resolved \| open}}

<!-- Add Q3, Q4, … as needed. -->

---

## Worked example
<!-- compass:optional -->

A decision recorded in the target register, not as a label stack - see
`skills/compass-runtime/writing-voice-worked-example.md` for a full
requirements review rewritten this way. One entry, in the same continuous
prose every entry above should aim for:

> The receipt's line cap was unclear - a defensible default, or something a
> project should be able to configure? jed72 kept it fixed at fifty lines, a
> hundred columns wide: a standard terminal shows that much without
> scrolling, and a receipt that cannot fit needs a less verbose renderer, not
> a setting.
<!-- absorbed: "> a knob." -->

That one paragraph carries what was unclear, the decision, who made it,
and what it rests on - the same four things each `{{PLACEHOLDER}}`
entry above owes, said as a colleague would say them rather than filled into
a form.

---

## Gate

### Definition of Ready

<!-- The crisp check that the spec is ready to LEAVE refine and enter Plan.
     This is the entry gate; the Definition of Done in verification-report.md is the
     exit gate. It is written by `compass issue render` from the manifest: an item is
     met by evidence recorded with `--meets`, by a person's `compass evidence approve
     --check`, or carried by `compass follow-up add --defers`. A tick on this page
     counts for nothing. The items are the plan entry list of the issue's
     configuration (`compass issue template show requirements-review`). -->

<!-- compass:render dor -->
<!-- /compass:render -->

Next stage: **plan** (`/compass:plan`).
