---
id: ADR-097
title: Resident text stays under 600 words and each refusal names its fix
status: proposed
date: 2026-11-07
supersedes: ''
superseded_by: ''
---

## Context

Compass 9.0.0 is an ATDD framework with a proof trail (ayeo-io/compass-delivery#358 [Cut resident text under 600 words and name the fix in each refusal], under #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail]). The issue asks:

> Cut what every session reads to the minimum, and make each refusal name its fix.
> - The operating contract and the resident skill text stay under 600 words, and the contract fits on one screen.
> - Each refusal names the exact command that clears it.
> - Remove guarded paths that only protected the deleted documents.
>
> Why: resident text is 63-72% of what a quick-fix session reads. A Compass run has 9-29 refused calls, and each is a request with the full context.

The resident text is what every request of a session carries:

- `compass-contract.md`, which the SessionStart hook puts into the context;
- the `description:` of each skill and command a model can invoke, which Claude Code keeps in the context.

No skill body loads on every session. The project's lessons block and language line also load, but a project writes them.

What is in place before this change, measured on `v9` at `688794be` with the word count of `tests/test_instruction_volume.py`:

| Part | Words |
|---|---|
| `compass-contract.md` | 415 (2,691 characters, 64 lines, longest line 78 columns) |
| 13 skill descriptions | 214 |
| 8 command descriptions a model can invoke | 74 |
| **Total** | **703**, about 949 tokens at 1.35 tokens per word |

Four commands set `disable-model-invocation: true` (`approve`, `delegate`, `reject` and `revoke`) and cost nothing. The `behavior-mapping` skill has an alias folder under its old British spelling whose only description is "Renamed to behavior-mapping".

The refusals:

- `cli/compass_pkg/refusals.py` holds 30 codes. Each renders as "Blocked:", "Why:" and "Fix:" lines.
- Some fix lines do not name a command a session can run. The `no-scenario` fix names `compass scenario add <slug> --id TRC-001`, which the CLI refuses with exit 2 ("unrecognized arguments: --id TRC-001"). `checkpoint-no-outcome` and `definition-of-done-open` tell the agent to run `compass evidence approve`, which the contract allows only under a delegation. `bad-current-task` tells the agent to edit `.compass/current-task` by hand.

The refused calls of a heavy run, from the base sdd-bench runs at `1776a1dc`, per run:

| Refusal | Per run |
|---|---|
| Chained commands ("contains multiple operations") | 6.0 |
| `requires approval` | 3.4 |
| A variable that cannot be checked | 2.5 |
| Bash denied | 1.5 |
| Pre-tool hook refusal | 1.2 |
| Other parsing refusals | 2.2 |

Most refused calls come from the permission check of Claude Code, not from Compass. Chains and variables are 8.5 of about 16 a run. Compass's own hook refusals are 1.2 a run.

ADR-091 removed every required document except the acceptance criteria, and with them the two landing refusals that read documents. A few guarded paths still name a document that 9.0.0 no longer writes.

`docs/releasing.md`, "Before changing the words sessions act on", says a change to `compass-contract.md` or to a hook refusal message is measured with sdd-bench before it merges.

## Decision

1. **The resident text stays under 600 words, and the build fails at 600.** The count is:
   - the words of `compass-contract.md`;
   - the words of the `description:` of each skill and each command a model can invoke;
   - one word for the name of each of those skills and commands.

   The lessons block (at most 150 words) and the language line are not counted, because the project writes them. A new test, `test_resident_text`, fails at 600 words or more and prints the count of each part with a token estimate at 1.35 tokens per word. It replaces the resident target of `tests/test_instruction_volume.py`. The target is 553 words: a contract of 342 words, descriptions of 191 words and 20 names.

2. **The contract fits on one screen: at most 40 lines of at most 80 columns.** The build fails when either is over. 80 columns is the width a terminal opens at, and the width the tests already render `--help` at. 40 lines is what a laptop shows in an editor or a full-height terminal. The new contract is 40 lines and 2,191 characters, and no line is over 80 columns. The older size targets (`CONTRACT_TARGET` and `CONTRACT_WORD_TARGET`) stay targets that warn, lowered to 2,200 characters and 350 words.

3. **The contract keeps every pinned phrase and gains one rule.** Every phrase that `tests/test_context_budget.py`, `tests/test_approval_docs.py`, `tests/test_contract_claude_md_drift.py`, `tests/test_contract_facts.py` and `tests/test_ste100_writing_rule.py` pin stays. The sentence "Explicitly typing any Compass command always works." goes, with the one test that pins it, because it describes Claude Code and is not a rule. The new rule is: "Run one `compass` command per Bash call, with no `&&`, `;`, loop or `$VAR` around it." It is 17 words. It aims at the chains and variables that are about half of a heavy run's refused calls. No run has measured its effect yet.

4. **The descriptions get shorter, and the alias skill goes.** Each skill description keeps its "Load at" stage, so a session still knows when to load it. The alias folder of `behavior-mapping` is deleted. Its row in `cli/compass_pkg/old_names.py` stays for #359 [Add compass migrate and the 9.0.0 upgrade guide].

5. **Each fix line names a command that clears the refusal, or is listed with the reason it cannot.** Ten codes change:

   | Code | New fix |
   |---|---|
   | `bad-current-task` | `compass issue use <slug>`, with `compass flow` to list the issues |
   | `checkpoint-no-outcome` | `compass evidence request --checkpoint {stage} --issue {slug}`, then stop; the person answers with `/compass:approve` |
   | `definition-of-done-open` | `compass follow-up add` with `--defers`, or `compass evidence add` with `--meets`, for each open item |
   | `no-acceptance-criteria`, `no-scenario` | `compass scenario add TRC-001 --issue {slug} --intent "<one sentence>"` |
   | `release-line-heading` | the verb that refused, run again with `--release-note "<plain text>"` |
   | `release-line-missing` | the verb that refused, run again with `--release-note`; a landing names `compass ship-commit` or `compass quick-fix finish` |
   | `approval-request-protected`, `delegation-caller-mismatch` | `compass evidence request` with its subject flag and `--issue` |
   | `no-red-on-record` | `compass acceptance start` with the `--kind` it needs |

   Twelve codes have no single command that clears them, for example `python-missing` (install Python) and `pr-review-protected` (another person approves the pull request). Each of them names what clears it instead. `config-invalid` is one of them: its Why line names the fault, and `compass policy lint` passes a `compass.yml` whose `enforcement.code_globs` is a string, which the hook refuses.

   A new test, `test_refusal_fix_commands`, holds the rule:
   - It fills the placeholders of each fix line with fixed samples and parses each `compass <verb>` command it names with the CLI's own parser. The parse must succeed. This test would have found `--id`.
   - Each slash command a fix line names must be a command a model can invoke, unless the line says the person types it.
   - A code that names no command must be in a `NO_COMMAND` table in the test, with the reason. A code in neither fails.
   - A fix line must not name `compass evidence approve` without `--delegated`.

   Each rendered refusal stays under the 60-word cap of `tests/test_refusal_registry.py`.

6. **The guarded paths that only protected a deleted document are removed.** Nothing in 9.0.0 writes these files:
   - the issue index (`README.md` in the `docs/compass/` folder) leaves `manifest.FRAMEWORK_OWNED_PATHS`, so a ship commit that stages it is refused as out of scope;
   - the living spec (`docs/system-spec.md`, `docs/system-spec-archive.md`) and the index leave the files that `compass quick-fix finish` does not trace (`start_state.py`);
   - the stop hook no longer warns about a failing gate decision in `verification-report.md` (`hooks/py/stop_scan.py`).

   The readers that judge archived landings and verdicts stay: `tip_scope.py`, `release_notes.py`, `checks.py` and the `no-acceptance-criteria` refusal.

7. **The hook's fallback to `delivery-approach.md` stays.** `hooks/py/pre_tool_route_probe.py` accepts a registered `delivery-approach.md` when the manifest has no `delivery_approach` key. The contract 5 corpus builds each issue without that key and writes `delivery-approach.md` for every state except `no-approach`. Without the fallback, each of those entries would refuse with `no-delivery-approach`, against its recorded exit code. #359 can remove the fallback with the other readers of old records.

8. **The #361 bench run is the measured run for this change.** #361 [Run the pre-registered sdd-bench measurement on the 9.0.0 release candidate] measures the release candidate against the published baseline. The release candidate holds the new contract and the new fix lines, and the pre-registered counts include refused calls. Nothing merges to `main` before the release candidate is measured, so no change to the contract or a refusal ships without a measurement. No separate sdd-bench run is made for this change.

## The size of the saving

The cut is small in tokens, and this record says so:

- By the count of `tests/test_instruction_volume.py`, which has no names, the resident text goes from 703 to 533 words. That cuts 170 words, about 230 tokens on each request. With one word for each name, the new text is 553 words.
- A quick fix in the base runs made 11 requests and read 0.31M tokens. The saving is about 2,500 tokens, about 0.8% of a quick fix.
- A heavy run made 101 to 137 requests and read 13 to 18M tokens. The saving is about 23,000 to 31,000 tokens, about 0.2%.
- Running unchanged Compass again moved the total by 8.9%, so a bench run of this change alone cannot show a 1% saving.

Most of the 63-72% in the issue is the system prompt and tools of Claude Code, which Compass cannot cut. The larger possible effect is on refused calls: the one-command rule and the fix lines. Only a bench run can show it, and #361 is that run.

## As built

Measured on the `358-paths` branch by `tests/test_resident_text.py` (run with `-s` to print the numbers) and by rendering each code of `tests/test_refusal_registry.py` at its longest fixture:

| Measure | Before | After |
|---|---|---|
| Resident words, with no names | 703 | 533 |
| Resident words, as `test_resident_text` counts them | - | 553: contract 342, skill descriptions 134, command descriptions 57, names 20 |
| Token estimate at 1.35 tokens per word | 949 | 747 |
| `compass-contract.md` | 64 lines, longest 78 columns, 2,691 characters | 40 lines, longest 79 columns, 2,191 characters |
| Rendered refusal words, 30 codes | - | 23 to 59, mean 42.7; the cap is under 60 |

The longest refusals are `no-red-on-record` and `delegation-caller-mismatch` at 59 words and `definition-of-done-open` at 58.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| One screen is 24 lines | The height of macOS Terminal and of the VT100 | It holds about 200 words, too few for the approval and staging rules or the guardrail list |
| Count the lessons cap in the 600 words | A project's lessons load on every session too | The project writes them, and it would leave 450 words for Compass |
| Keep the two limits as targets that warn | Other size targets warn (`size-caps-as-targets`) | The issue says "stay under", and a target that warns does not stop a change that goes over |
| A separate sdd-bench run for this change | `docs/releasing.md` asks for a run before the contract or a refusal changes | The saving is below the run-to-run noise, and #361 measures the release candidate before anything merges |
| Remove the `delivery-approach.md` fallback now | It reads a document 9.0.0 does not write | It changes contract 5, which needs a new corpus |
| Leave the one-command rule out | It is not measured, and it adds 17 words | Chains and variables are the largest group of refused calls |
| Keep the alias skill until #359 | `old_names.py` keeps the old names until 9.0.0 | A model never loads it, and its 14 words are paid on every request |
| Reword every CLI error, not only the 30 refusal codes | The base runs had 19 to 32 tool errors a run | It is a far larger change; it is left to a follow-up issue |

## Consequences

What changes for a user:

- Every request of a session carries about 230 fewer tokens.
- The contract asks for one `compass` command per Bash call.
- Each refusal names a command that clears it and that the CLI accepts, or says what clears it when no command can.
- A ship commit that stages the issue index (`README.md` in the `docs/compass/` folder) is refused, and a hand edit of the living spec during a quick fix is traced. Each is a visible refusal or trace that names the file. A branch made before 9.0.0 that changed those files and merges after the upgrade meets one of them.

What stays:

- Contracts 1 to 5. The hook keeps every refusal code and the two phrases the contract 5 corpus pins. No file in `tests/fixtures/frozen-digests.yml` changes.
- Every archived `compass check` verdict.
- `CLAUDE.md`. The three phrases `tests/test_contract_claude_md_drift.py` pins stay in the contract word for word. Making the `CLAUDE.md` approval bullet match the contract word for word is the owner's choice.

## Open questions

Each question has the decision this change builds. The owner confirms questions 1, 2, 3, 4 and 7 when accepting this record, because each changes what the issue accepts or what a user sees.

1. **What is one screen?** Decided: 40 lines of at most 80 columns (decision 2).
2. **What counts in the 600 words?** Decided: the contract, the description of each skill and command a model can invoke, and one word for each name. The lessons block and the language line are not counted (decision 1).
3. **Does the #361 run meet the releasing rule for this change?** Decided: yes (decision 8).
4. **Are the two limits hard?** Decided: yes. The 600-word and 40-line limits fail the build. The other size targets stay warnings.
5. **Does the alias skill go?** Decided: yes, in 9.0.0. The `old_names` row stays for #359.
6. **Do the start-state and land-scope exemptions go?** Decided: yes (decision 6).
7. **Does the hook's fallback to `delivery-approach.md` stay?** Decided: yes (decision 7).
8. **Is the one-command rule in the contract?** Decided: yes. It is not measured; #361 shows its effect.
9. **Which refusals are in scope?** Decided: the 30 registry codes and the hook's own lines. The other CLI errors go to a follow-up issue.
10. **Does `CLAUDE.md` change?** Decided: no.
11. **Is there an ADR?** Decided: yes, this record.

## References

- ayeo-io/compass-delivery#358 [Cut resident text under 600 words and name the fix in each refusal] and its parent, #345 [Reposition Compass 9.0.0 as an ATDD framework with a proof trail].
- Related issues: #359 [Add compass migrate and the 9.0.0 upgrade guide], #361 [Run the pre-registered sdd-bench measurement on the 9.0.0 release candidate].
- ADR-091 (the deleted documents), ADR-093 (sdd-bench is the only measurement Compass accepts), ADR-094 (the fixed check set).
- `compass-contract.md`, `cli/compass_pkg/refusals.py`, `cli/compass_pkg/manifest.py`, `cli/compass_pkg/start_state.py`, `hooks/py/stop_scan.py`, `hooks/py/pre_tool_route_probe.py`, `tests/test_instruction_volume.py`, `tests/test_refusal_registry.py`, `docs/releasing.md`.
- New tests named above: `test_resident_text` and `test_refusal_fix_commands`.
