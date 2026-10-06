---
description: Integrate, run regression, update living docs, settle follow-ups
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# /compass:ship

Ship closes the issue: integrate the work, prove the combination, update the
living docs, and settle every follow-up the approach deferred. An issue with an
unsettled follow-up is an open issue - ship refuses to close it.

## Setup

- Read `delivery-approach.md` for the orchestration and the list of owed
  follow-ups.
- Read `verification-report.md` - shipping does not run on unverified work.

## Spike note

On a spike, ship is **graduate or discard** - never "merge to main". Nothing
ships from a spike. Either the findings feed a fresh `/compass:assess` for
real delivery work (graduation - see `${CLAUDE_PLUGIN_ROOT}/approaches/spike.md`), or the spike is
discarded with its learnings recorded in `devlog.md`. The procedure below is
for delivery work; on a spike, follow the graduate-or-discard step in
`${CLAUDE_PLUGIN_ROOT}/approaches/spike.md` instead.

## Procedure

1. **Integrate.**
   - **Solo orchestration:** commit on the current branch with
     `compass ship-commit -m "<message>"` - it is robust to auto-fixing
     pre-commit hooks (which otherwise silently no-op the commit and leave
     HEAD unmoved), retries once after re-staging the hooks' fixes, and
     **errors if HEAD did not advance** so a commit that did not happen
     cannot count as shipped. Pass `--issue <slug>` to mark the issue
     shipped only on a checked commit. For a long message, `-F <file>`
     reads it from a file; never fall back to `git commit` around it.
   - **Message rules:** the message follows the cold-reader strategy: say
     what changed and why, for someone who was not in the conversation; no
     `Co-Authored-By:` trailer for any agent and no "Generated with"
     footer. The same applies to a pull-request body.
   - **Pair or multiagent:** the `orchestrator` (or lead builder on a pair)
     runs `scripts/integrate.sh` - an orchestrated merge of all worktrees.
     The orchestrator is the only agent allowed to resolve cross-subtask
     conflicts.
2. **Combined regression.** Run regression across the *combined* result. On
   a multiagent this is non-negotiable - per-subtask green does not imply
   integrated green. Record the run and link the record.
3. **Update living docs.** Bring READMEs, architecture notes, and any docs
   the change touched in line with reality. If the change is launch-visible
   (the product-marketer role is in play), draft the release notes here
   too - pulled from `positioning.md`, so every line in the notes is already
   a scenario-backed claim. `product-marketer` owns their wording.
4. **Settle owed follow-ups.** Check `delivery-approach.md`'s de-scope
   ledger, `manifest.yml`'s `follow_ups:` and `claims:` lists, and the
   approach's standing obligations:
   - **Hotfix follow-up** (mandatory): `delivery-approach.md` completed
     properly (not the urgent stub); the reproduction test promoted into a
     real Given/When/Then scenario in `acceptance-criteria.md` *and*
     `manifest.yml`'s `scenarios:`, traceable to the defect; a root-cause line
     in the `devlog.md`. Mark the matching `follow_ups:` entry `paid` -
     `compass check` fails at ship while any is owed.
   - **Marketer claims gate** (when the product-marketer role is in play):
     every claim in `manifest.yml`'s `claims:` traces to a passing scenario id.
     Invoke `product-marketer` to confirm; `compass check`'s
     `claim-traces-to-scenario` check is the mechanical backing. This gate
     blocks shipping per the routing policy's `role_rules`.
   - Any other de-scoped artifact the ledger marked as owed.
5. **Run `compass check` as the final mechanical gate.** It runs every
   `guardrails.yml` check against `manifest.yml` and `evidence/` - suite
   passed, traceability holds, every `pass` gate has evidence, no owed
   follow-up unpaid, and (where a human sign-off applies) the approval is
   on record. It exits non-zero on any failure; record its output and link
   the record. This is
   the mechanical check before shipping.

   **Typed Definition of Done (evidence, not assertion):** `compass check`
   also parses the `### Definition of Done` section of
   `verification-report.md` and enforces the inline-tag rule. Every
   unchecked DoD box must carry one of:

   - `- [ ] (evidence: EV-<id>) <description>` - passes if `EV-<id>` is in
     `manifest.yml`'s evidence registry with an accepted type (`test-run`,
     `command-output`, `manual-review`, `human-approval`, `artifact`, etc.).
   - `- [ ] (follow-up: FU-<id>) <description>` - passes if `FU-<id>` is in
     `manifest.yml`'s `follow_ups:` with `status: outstanding`. The follow-up
     can carry an optional `target_task: <slug>` field; when set, the named
     issue's ship check fails until this entry is paid
     (`compass follow-up resolve --issue <slug> <FU-id>`).
   - `- [x] <description>` - a human-ticked box passes unconditionally.
   - `- [ ] <bare description>` - **fails**. Narrative notes in `devlog.md`
     (e.g. "USER TO APPLY") never clear a DoD item - evidence, not
     assertion.

   Cross-issue blocking: if another issue's `follow_ups:` has `target_task`
   pointing at the issue being shipped, and that follow-up is still
   `status: outstanding`, `compass check` fails at ship even if this issue's
   own DoD section is clean. Pay the upstream follow-up first.
6. **Capture process friction (advisory - never a gate).** With the gate
   already cleared in step 5, record where Compass's *own* process weight cost
   more than it returned between assess and ship.
   - Run `compass _friction-capture --internal` - it assembles a draft
     `friction:` list from signals the CLI already computed (recorded
     re-assessments, absorbed assessment-debt) and writes it into
     `manifest.yml`.
   - Then offer the author **one optional line**: *"anything the framework
     made harder than it should have been?"* - pass it with `--note "..."
     --note-category <over-weight|tooling|...> --note-phase <stage>`.
     **Recording nothing is a valid, common outcome.**
   - Notes the agent recorded during the run with `compass issue friction`
     are kept. Each cites evidence and a fix; `compass retro --friction`
     counts them in their own column, and they never make a lesson alone.
   - This step never blocks shipping: it runs after the gate, writes only
     the `friction:` section (no follow-up, no gate), and
     `compass retro --friction` later aggregates it across issues as
     advice, never as a gate (Flow advises but never gates).
   - If the person corrected something during the issue and said they had
     to say it before, offer to keep it as a project lesson: run
     `compass lesson propose "<their words>"`, quoting them,
     and never `compass lesson add`. It takes effect only when someone runs
     `compass lesson accept`.
7. **Final devlog entry.** One entry: what shipped, what checked it,
   what follow-ups were settled.
8. **After a review fix.** If review of the pull request changes the
   issue's own files after `ship-commit` landed it, commit the fix, re-run
   `compass tdd-green`, then run `compass ship-commit --issue <slug> -m
   <message>` with nothing staged. It moves `land_commit` to HEAD, and
   refuses while the newest green does not name HEAD's files.

## Gate - ship refuses to close the issue unless

- integration is complete and combined regression is green (evidence recorded
  and linked);
- living docs are updated;
- `compass check` passes (its output recorded and linked);
- **every owed follow-up is settled** - no unsettled hotfix follow-up, no
  unbacked marketing claim, no de-scoped artifact left owed.

If a follow-up cannot be completed now, the issue stays open and
`/compass:status` keeps flagging it. A deferred follow-up must be settled
before the issue closes.
