<!--
TEMPLATE: verification-report.md
Role in the pipeline: the Verify output. Proves the work with EVIDENCE -
recorded command output and artifacts a reader can open, never assertion. "It works" is not a
gate-passing statement on any delivery approach. The delivery approach's gate set and review
dimensions come from delivery-approach.md; the `immovable_gates` from
governance/routing-policy.md are added regardless.

Fill every {{PLACEHOLDER}}. Every pass needs evidence attached - an empty
evidence block is an automatic fail.
-->

# Verification Report - {{ISSUE_SLUG}}

> **Date:** {{DATE}}
> **Agents:** `verifier`, `reviewer`{{, `product-marketer` if the claims dimension applies}}
> **Approach (from delivery-approach.md):** {{reference shape}} · **Gate count:** {{1 \| 2 \| all}}
> **Orchestration:** {{solo \| pair \| multiagent orchestration - verifies per subtask, then combined}}

---

## 1. Scenario acceptance results

<!-- Written by `compass issue render` from the scenarios and the red, green and acceptance
     records in the manifest, with the failure modes de-scoped at define. Do not edit between
     the markers: the next render replaces it. -->

<!-- compass:render coverage -->
<!-- /compass:render -->

## 2. Test suite evidence

<!-- LINKED, NOT REPRODUCED. The run itself lives in an evidence record that
     `compass tdd-green` wrote; this section gives the command, the headline
     numbers, and the record to open. A report that pastes its evidence grows
     past two screens and stops being read. The reader who wants the raw run
     can open the file, and a file can be re-run where a paste cannot.

     On multiagent orchestration, list each subtask's record, then the combined one. -->
<!-- absorbed: "the raw run can open the file - which is more than a paste gives them," -->
<!-- absorbed: "because a paste cannot be re-run." -->

**Command run:** `{{e.g. npm test}}`

<!-- The records below are listed by `compass issue render` from the manifest's evidence. -->

<!-- compass:render evidence -->
<!-- /compass:render -->

**Coverage (against the "Tested before it lands" guardrail's floor, `G1`):**
{{e.g. 87.4% lines, floor 80% - record: `evidence/{{coverage.json}}`}}

## 3. Review dimensions

<!-- Apply each dimension delivery-approach.md lists. correctness, governance,
     traceability are ALWAYS on for delivery work - they are the default
     guardrails in review form. Others as the approach needs: regression,
     security (scaled or full), clarity, claims. Each gets pass/fail AND
     evidence.

     "Assessed by" records WHO reached the judgement: the `reviewer` agent, a
     named person, or "author" where the person who did the work also graded
     it. Be accurate rather than flattering. An author-assessed dimension is
     weaker evidence than an independently assessed one - the author cannot
     see what they did not think of, and clarity in particular has no
     mechanical backstop. This is a record, not a gate: nothing fails because
     a dimension was self-assessed, but a reader can weigh it, and
     `compass retro` can spot a project where one dimension is never
     independently reviewed. The mechanical checks (`compass check`, the test
     suite) are unaffected either way - they do not care who ran them. -->

| Dimension | Applies on this delivery approach? | Result | Assessed by | Evidence |
|---|---|---|---|---|
| correctness | always | {{PASS \| FAIL}} | {{reviewer \| name \| author}} | {{every scenario in §1 passes}} |
| governance | always | {{PASS \| FAIL}} | {{…}} | {{honours governance/ - guardrails clear with evidence, strategy deviations recorded; cite checks}} |
| traceability | always | {{PASS \| FAIL}} | {{…}} | {{code→scenario→intent and claim→scenario chains intact}} |
| regression | {{yes / no}} | {{PASS \| FAIL \| n/a}} | {{…}} | {{nothing that was passing before now fails - link the record}} |
| security | {{full / scaled / no}} | {{PASS \| FAIL \| n/a}} | {{…}} | {{OWASP-style pass, scaled to the assessed risk}} |
| clarity | {{yes / no}} | {{PASS \| FAIL \| n/a}} | {{…}} | {{a future reader can follow it}} |
| claims | {{if role / yes}} | {{PASS \| FAIL \| n/a}} | {{…}} | {{see launch-readiness.md - every claim traces to a passing scenario}} |

## 4. Gate decision

<!-- A gate passes only with evidence. The block lists every gate the issue runs, from the
     manifest, written by `compass issue render`. -->

<!-- compass:render gates -->
<!-- /compass:render -->

**Overall:** {{PASS - advance to ship \| FAIL - the issue does not advance}}

<!-- If FAIL: the issue does not advance. Fix it, or QA sends it back to
     the define stage if the scenarios are uncoverable. -->

**If FAIL - disposition:** {{"fix and re-check" \| "sent back to the define stage: scenarios TRC-… are uncoverable because …"}}

## 5. Failure modes de-scoped at define

<!-- Each entry in the manifest's `failure_modes_descoped`, recorded with
     `compass scenario descope`, is listed under the coverage block in section 1:
     the mode and why no scenario covers it. -->

## 6. Decisions taken for the user

<!-- Written by `compass issue render` from the decisions an agent took for the person
     (`compass issue decision add`) and the reassessments in the manifest. -->

<!-- compass:render decisions-taken -->
<!-- /compass:render -->

---

## Gate

### Definition of Done

<!-- The crisp exit check. The Definition of Ready (requirements-review.md) was the entry
     gate into plan; this is the exit gate out of verify. It is written by
     `compass issue render` from the manifest. An item is met by a record, never by a
     tick on this page:

       - evidence: `compass gate pass ... --meets <item>` or `compass evidence add ... --meets <item>`
       - a person: `compass evidence approve --check <item>`
       - a deferral to ship: `compass follow-up add FU-<id> --defers <item> --summary "..."`

     An item with no record is open and fails `dod-evidence-typed`. Cross-issue: if another
     issue's follow-up has target_task pointing at the issue being shipped and is still
     outstanding, `compass check` fails at ship time until it is settled. The items are the
     `verify` exit list of the issue's configuration. -->

<!-- compass:render dod -->
<!-- /compass:render -->

Next stage: **ship** (`/compass:ship`) - only on overall PASS.
