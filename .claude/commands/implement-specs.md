---
description: Work through the 24 Sep 2026 feature specs in priority order, autonomously, raising new specs for anything found along the way
---

# /implement-specs

Implement the feature specs in `docs/analysis/2026-09-24-spec-*.md`, in the
order below, one at a time, through Compass's own pipeline. Do not wait for
permission between specs. $ARGUMENTS names a spec id to start from; without
it, start at the first spec not yet landed.

## Order

Work the list top to bottom. Skip a spec whose issue is already landed.

1. D1 contract-facts - blocks the 5.0.0 tag
2. D2 validate-scan-vs-archive - blocks the 5.0.0 tag
3. D3 unbound-green-requires-red
4. D4 red-record-identity-cutoff
5. D5 hook-failure-matrix
6. D6 reach-counts-move-with-every-test - found while landing D1
7. D7 validate-help-prints-headings-only - found while landing D2
8. D8 created-date-can-be-backdated - found while landing D3
9. D9 acceptance-declared-after-the-work - found while landing D3
10. D10 coverage-flag-with-autoload-off - found while landing D3
11. D11 current-task-path-traversal - found while landing D4
12. D12 code-globs-as-a-string - found while landing D5
13. D13 claims-called-immovable-elsewhere - found while landing B1; run after B1, which was in flight
14. D14 red-for-a-module-not-yet-written - found in B1's rehearsal; run after B1
15. D15 changes-id-misses-unlisted-files - found in B1's rehearsal; run after B1
16. D16 retro-weighs-only-retired-route-names - found at the retro after B1
17. D17 red-through-a-shell-wrapper - found in D14's security review; after D14
18. D18 devlog-logs-edits-outside-the-project - found while landing D14
19. A1 facts-drift-guard - do this before the rest so the drift class cannot
    return while they land
20. A6 evidence-binding - tranche 2; closes the gap the external review
    ranks first, and D4 prepares it
21. B1 orchestrator-loop-hardening - re-read its Amendment before assessing
22. B2 dispatch-protocol - use B1's result; the three recorded runs can be
    later specs on this list
23. D19 changed-file-keeps-one-scenario - found by B2's subtask-3 builder; a defect, so directly after B2
24. D25 rerun-check-misses-script-changes - found while landing D21, which it blocked; so before D21
25. D21 map-cells-reach-git-unchecked - found in B2's security review
26. D22 merge-overwrites-an-ignored-record - found in B2's security review
27. D26 tree-id-misses-a-same-second-edit - found while landing D23, whose suite it failed at random; so before D23
28. D23 check-does-not-compare-record-with-map - found in B2's security and claims reviews
29. D24 multiagent-scripts-still-say-ship - found in B2's third clarity review
30. D27 tr-range-fails-on-linux - found by CI on B2's PR, which it fails; a defect, so before B4
31. B4 skill-prose-pressure-tests - re-read its Amendment before assessing - carries B2's run 2 under the dispatch protocol
32. D28 source-hash-skips-nested-records - found by B4's subtask-2 builder; a defect, so directly after B4
33. D29 red-without-a-test-unlocks-edits - found in B4's eighth integrated review; a defect, so with D28 after B4
34. D30 eval-judge-gaps - left open by B4's passing review; a defect, and B6 reuses the judge, so before B6
35. D31 subtask-cost-keeps-last-try-only - found writing B4's run record; a defect, so before B6, which records run 3
36. D32 feature-route-omits-the-map - found assessing D30; a defect, so before B6
37. D33 eval-gaps-after-d30 - left open by D30's passing review; a defect, and B6 reuses the judge, so before B6
38. B6 comparison-suite - tranche 2; reuses B4's harness - carries B2's run 3 and the README claim
39. D34 eval-gaps-after-d33 - a defect placed after B6 on purpose: each gap spec has left a smaller one and none changed a recorded result, so chasing them first would keep B6 waiting
40. B3 resident-footprint-diet
41. B11 quick-fix-overhead - behind: B6 found Compass costs about seven times the tokens of no framework for the same result; after B3, which it depends on
42. D36 quick-fix-finish-gaps - defect: B11's second review left a second `finish` call with no way forward; directly after B11, whose code it fixes
43. D37 ship-commit-judges-the-staged-files - defect: D36's review found ship-commit compares disk files but commits staged ones; directly after D36
44. D38 refusal-template - defect (tranche 3, PRD 03): one registry and shape for refusals; the raw `land` block-phase key is still printed
45. B10 comparison-scenarios-that-discriminate - behind: B6's scenarios could not tell the frameworks apart
46. D35 eval-gaps-after-d34 - a defect placed after B10 on purpose, like D34: none changes a published result, and B10 will rework the same files
47. A2 system-spec-split
48. A3 retire-the-last-v1-leak
49. B9 single-entry-point - tranche 2
50. B5 install-without-python-anxiety
51. B7 codex-adapter - tranche 2; gated on B6's published results
52. B8 session-diagnosis - tranche 2
53. A4 review-focus-in-define
54. A5 backlog-ageing-signal
55. A7 status-line - ahead (tranche 3, PRD 01): the human sees route, stage, gates and evidence at no token cost
56. A8 progress-rail - ahead (tranche 3, PRD 02): the route as a rail on `next`; shares a renderer with A7
57. A9 clickable-paths - ahead (tranche 3, PRD 04): after A8, whose renderer it uses
58. A10 issue-overview - ahead (tranche 3, PRD 05): a generated overview drawing the traceability chain
59. B12 demo-recording - behind (tranche 3, PRD 06): last, because it records D38, A7 and A8; ask before it lands, as a published asset

## Per spec

1. Read the spec file. It carries problem, evidence, change and acceptance.
2. Run `/compass:assess` for it. The spec's "Suggested route" line is a
   suggestion; the assessment decides. If they disagree, record why in
   delivery-approach.md and follow the assessment.
3. Follow the route the evaluator returns, stage by stage. The spec's
   acceptance section seeds the scenarios at define.
4. Land it: `compass check` green, gates passed, ship. Update the matching
   GitHub issue if one exists and `gh` is available; otherwise note the issue
   number in the devlog as still open.
5. Move to the next spec without stopping.

## Autonomy rules

- Do not pause between specs and do not ask which spec is next - the list
  answers that.
- Stop and ask only when: a change is irreversible or destructive beyond the
  repository; a change touches auth, secrets or published release artifacts;
  or a spec's acceptance cannot be met honestly and re-assessment does not
  resolve it. Say plainly which case applies.
- Never route around the hook, the checks or the vocabulary scan to keep
  moving. A blocked path is information; record it and re-assess.
- Follow CLAUDE.md's house rules in every file, commit message and reply: no
  em dash, no agent attribution, plain English, British spelling.

## Self-improvement

- Capture friction at every ship. After every third landed spec, run
  `compass retro` and read what it says about sizing before assessing the
  next one.
- If this command's order proves wrong - a dependency the list missed, a spec
  overtaken by events - correct this file in the same commit as the work that
  proved it wrong, and say in one line what changed and why.
- If a spec is wrong in substance, do not implement it as written. Amend the
  spec file first, record the amendment reason at the top of the file, then
  implement the amended version.

## Raising what you find

When you meet a defect, a gap or an improvement that is not on this list:

1. Do not widen the current issue. Record it as a follow-up in the manifest
   if it belongs to the current spec, otherwise:
2. Write a new spec at `docs/analysis/<date>-spec-<n>-<slug>.md` in the same
   shape: tier, suggested route, problem, evidence with paths, change,
   acceptance.
3. Give it a tier: defect if something is wrong now, behind if a rival does
   it better, ahead if Compass leads and can stretch.
4. Insert it into the order above by tier (defects before behind, behind
   before ahead) and say in the reply where it went.
5. Raise a matching GitHub issue when `gh` works; otherwise append a line to
   `docs/analysis/2026-09-24-file-issues.sh` so the next run creates it.

## Reporting

At each spec's land, report in the repository's four-part shape: what landed,
outstanding questions, what you need (normally nothing), and which spec is
next. Keep it short; the manifests carry the detail.
