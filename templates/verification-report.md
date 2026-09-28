<!--
TEMPLATE: verification-report.md
Produced by: the verify stage (`/compass:verify`); owning role QA, agents
             `verifier` (runs the suites) and `reviewer` (applies the
             review dimensions).
Lives at:    docs/compass/<created>-<issue-slug>/verification-report.md
Role in the pipeline: the Verify output. Proves the work with EVIDENCE -
recorded command output and artifacts a reader can open, never assertion. "It works" is not a
gate-passing statement on any delivery approach. The delivery approach's gate set and review
dimensions come from delivery-approach.md; the `immovable_gates` from
governance/routing-policy.md are added regardless.

Fill every {{PLACEHOLDER}}. Every pass needs evidence attached - an empty
evidence block is an automatic fail.
-->

# Verification Report - {{ISSUE_SLUG}}

> **Stage:** verify · **Date:** {{DATE}} · **Owning role:** QA
> **Agents:** `verifier`, `reviewer`{{, `product-marketer` if the claims dimension applies}}
> **Approach (from delivery-approach.md):** {{reference shape}} · **Gate count:** {{1 \| 2 \| all}}
> **Orchestration:** {{solo \| pair \| multiagent orchestration - verifies per subtask, then combined}}

---

## 1. Scenario acceptance results

<!-- Every scenario in acceptance-criteria.md run as an acceptance check - the same
     artifact the spec was, read now at verification time. -->

| Scenario id | Title | Result | Evidence (the record id - §2 links it) |
|---|---|---|---|
| `TRC-A1` | {{…}} | {{PASS \| FAIL}} | {{EV-id}} |
| `TRC-A2` | {{…}} | {{PASS \| FAIL}} | {{EV-id}} |
| `TRC-B1` | {{…}} | {{PASS \| FAIL}} | {{EV-id}} |
| `TRC-F1` | {{…}} | {{PASS \| FAIL}} | {{EV-id}} |

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

| Record | What it covers | Result |
|---|---|---|
| `evidence/{{green-TRC-x.json}}` | {{which scenarios}} | {{e.g. 214 passed, 0 failed}} |

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

<!-- A gate passes only with evidence. List every gate in delivery-approach.md's set
     PLUS every immovable gate from governance/routing-policy.md. -->

| Gate | Required by | Status |
|---|---|---|
| verify.correctness | immovable + approach | {{GREEN \| RED}} |
| verify.governance | immovable + approach | {{GREEN \| RED}} |
| verify.traceability | immovable + approach | {{GREEN \| RED}} |
| verify.regression | approach | {{GREEN \| RED}} |
| verify.claims | role rule (marketer in play) | {{GREEN \| RED \| n/a}} |
| {{verify.security / verify.clarity …}} | approach | {{GREEN \| RED}} |

**Overall:** {{PASS - advance to ship \| FAIL - the issue does not advance}}

<!-- If FAIL: the issue does not advance. Fix it, or QA sends it back to
     the define stage if the scenarios are uncoverable. -->

**If FAIL - disposition:** {{"fix and re-check" \| "sent back to the define stage: scenarios TRC-… are uncoverable because …"}}

## 5. Decisions taken for the user

<!-- Every choice an agent made that the user would otherwise have made: a
     scope cut, a design fork, a finding judged out of scope, a re-sequenced
     subtask. One line each, with where it is recorded. "None" is an answer;
     an empty section is not. -->

{{decision - where it is recorded}}

---

## Gate

- [ ] Every required review dimension passed with evidence attached.
- [ ] Every gate in `delivery-approach.md` and every immovable gate is GREEN.
- [ ] This report is complete - no empty evidence blocks.

### Definition of Done

<!-- The crisp exit check. The Definition of Ready (requirements-review.md)
     was the entry gate into plan; this is the exit gate out of verify.
     Items 1-5 are proven here, with evidence above. Items 6-7 are
     carried into shipping - listed so the close-out is one continuous
     checklist, not two.

TYPED DOD - REQUIRED INLINE-TAG SYNTAX (evidence, not assertion - the
guardrail applies to the checklist itself):
  Every unchecked box must carry exactly ONE of these inline tags, or be
  ticked. The tag spellings are machine syntax the checker parses - they
  rename with the schema, not before:

    - [ ] (evidence: EV-<id>) <description>
        Passes when EV-<id> is in the manifest's evidence registry with an
        accepted type (test-run, command-output, manual-review,
        human-approval, artifact, security-review, migration-plan,
        rollback-plan, claim-review).

    - [ ] (follow-up: FU-<id>) <description>
        Passes (defers) when FU-<id> is in the manifest's follow-up ledger
        (the follow_ups: list) with status: outstanding. Add target_task: <slug>
        on the entry to block that issue's shipping until this one is
        settled (compass follow-up resolve --issue <source-slug> FU-<id>).

    - [x] <description>
        A human-ticked box passes unconditionally - the human took
        responsibility.

    - [ ] <bare description>   ← FAILS compass check (bare unchecked box)
        Narrative notes in devlog.md do NOT clear a DoD item. Evidence,
        not assertion.

  Cross-issue: if another issue's follow-up ledger has target_task pointing
  at the issue being shipped, and that entry is still outstanding, compass
  check fails at ship time until it is settled.
-->

- [ ] (evidence: {{EV-id}}) **Every scenario passes** - §1 is all PASS; the
      spec, read as the acceptance suite, is green.
- [ ] (evidence: {{EV-id}}) **TDD suite green** - §2 links the record of the
      full suite passing.
- [ ] (evidence: {{EV-id}}) **Coverage meets the "Tested before it lands"
      guardrail's floor (`G1`)** - evidence in §2.
- [ ] (evidence: {{EV-id}}) **No lint / format / type errors** - clean, with
      the record linked.
- [ ] (evidence: {{EV-id}}) **Traceability intact** - code → scenario → intent
      holds; claim → scenario holds where the marketer is in play.
- [ ] (follow-up: {{FU-id}}) *(carried to ship)* Living docs updated to match
      reality.
- [ ] (follow-up: {{FU-id}}) *(carried to ship)* Every outstanding follow-up
      settled - no unsettled hotfix follow-up, no unbacked marketing claim.

Next stage: **ship** (`/compass:ship`) - only on overall PASS.
