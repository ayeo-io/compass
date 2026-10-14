---
id: ADR-063
title: Checkpoint outcomes and session usage are stored, and the autonomy and cost figures are derived
status: accepted
date: 2026-10-13
supersedes: ''
superseded_by: ''
---

Accepted by jed72 on 2026-10-14, through compass:architect under automation mode.

## Context

`compass retro --impact` reports lead time and change failure. It cannot report how much work ran without a person, or what a change cost, because no record holds either:

- The manifest's `checkpoints:` lists the stage hand-offs that wait for a person. Nothing records whether a person answered one, or that the autonomy setting passed it. The stage commands write a prose line to `devlog.md`, which no tool reads.
- A person's approval is typed evidence (`human-approval`, `artifact-approval`), but no type covers a checkpoint.
- The `usage` block, with tokens, requests and `cost_usd` per stage, is written only by `compass quick-fix finish`. No other approach records what it cost.

Six existing decisions bound the answer:

- ADR-006: a manifest without a new key reads exactly as before.
- ADR-026: `ship-commit` is the one step that lands an issue. A refusal there must leave nothing half done.
- ADR-031: the delivery record copies the configured paths file by file.
- ADR-036: an issue's stored generation does not change after it is written.
- ADR-045 and ADR-051: a fact derived from records is computed when read, never stored.
- The shipped check `human-approval-present`, which serves guardrail `G5`, is `locked: hard`. It accepts any approved `human-approval` record.

A transcript holds a person's prompts. `session_usage.stage_usage` already reads a transcript and keeps only numbers, model names and times.

## Decision

1. **What is stored and what is derived.**
   - Stored:
     - `checkpoint_outcomes`, one entry per checkpoint stage: `{stage, outcome, by, at}`, with `outcome` either `waited` or `skipped`, and `evidence` on a `waited` entry;
     - the `checkpoint-approval` records a `waited` entry cites;
     - `usage.sessions`, the session ids that worked on the issue;
     - the `usage` counts.
   - Derived when read, and stored nowhere: the human judgement, guardrailed and autonomous counts (the band split), the autonomy ratio, whether usage is complete, and every median.
   - The schema holds no key for a derived figure.
   - One outcome is kept per stage. A person's later answer replaces an agent's `skipped`, never the reverse. Outcomes belong to the issue, not to a generation, so an answer never changes a stored generation.

2. **A checkpoint answer is its own evidence type.**
   - `compass evidence approve --checkpoint <stage>` writes a `checkpoint-approval` record and the `waited` outcome that cites it. The command needs a terminal, refuses the approver `agent` and needs a role.
   - The record has no `check` key, and `compass evidence add` refuses the type.
   - `human-approval-present`, the human-check reader and the waiver check read only `human-approval` records, with `artifact-approval` also read for human checks. None of them reads this type, so a checkpoint answer never clears `G5`, a human check or a waiver, and no check changes.
   - An agent records a hand-off that autonomy passed with `compass issue checkpoint add <stage> --outcome skipped --by <agent>`, which writes no evidence record.

3. **Only issues assessed after this change are judged.**
   - An issue is judged when its manifest holds the `checkpoint_outcomes` key. The first assessment of a new issue writes it as an empty list.
   - A reassessment does not add it, and no migrate back-fills it. The two commands of decision 2 refuse an issue that is not judged, rather than add the key.
   - An older issue is therefore never refused, and the retro counts it as not measurable for autonomy, whatever its `checkpoints:` list holds.

4. **The landing refusal is an entry in an ordered list.**
   - `ship-commit` runs a list of landing refusals before it stages, renders, commits, derives or syncs anything. The first entry refuses a judged issue that lists a checkpoint with no outcome.
   - A refusal leaves every file as it was.
   - A later refusal is one more entry, not a branch in the command.
   - `quick-fix finish` runs the same list with its other preconditions.

5. **The pre-tool hook records each session once, and never stops an edit for it.**
   - On every tool call it judges, the hook resolves the issue from `COMPASS_ISSUE` or the pointer, in shell, and searches the manifest for the session id.
   - A recorded id costs no Python process. A new one starts one process, which:
     - tries a new per-issue manifest lock once, without waiting, and writes nothing if another writer holds it;
     - inserts the id into `usage.sessions` by text, and checks that the parsed result changed nothing else;
     - replaces the file atomically, after comparing the bytes on disk with those it read, and merges again if they changed.
   - `core.save_manifest` holds the same lock while it writes, so the hook never replaces a manifest a command is writing.
   - Any fault allows the edit and leaves the manifest as it was. This is the first time the hook writes an issue's manifest.

6. **Usage is read from every recorded session's full transcript, under a size bound, keeping numbers only.**
   - After a landing, `ship-commit` reads the transcripts of every session in `usage.sessions`, and of the session running it, line by line. Nothing is sampled.
   - Before reading, it sums the size of every file. Above 1 GiB it reads none and records `recorded: false` with the reason `too-large`.
   - A missing or unreadable transcript records its reason, and an unpriced model leaves its cost null. Usage never stops a landing.
   - An issue that is not judged (decision 3) gets no block, so it lands exactly as before.
   - Transcripts are only read. The block keeps numbers, booleans, model names, times, session ids and fixed reason words.
   - No transcript text or path is stored. Session ids reach the delivery record inside the manifest it already copies, as the quick fix's `usage.session` does.
   - Requests are divided into stage windows by each stage's ending record. Requests after the last such record are `unattributed`.
   - A window that another issue recording the same session overlaps is marked `shared`, and the retro counts that issue as unmeasured for cost.

7. **Unmeasured is not zero.**
   - An issue without complete usage, that is not judged, without an outcome for each listed checkpoint, or whose configuration cannot be read for its bands, is counted as not measured. It is never counted as zero.
   - Each figure prints the number of issues it rests on, and is withheld below the existing floors: 20 issues, and 3 per approach group.

## Alternatives considered

| Alternative | Why considered | Why rejected |
|---|---|---|
| Write a checkpoint answer as a `human-approval` record that `human-approval-present` ignores | One approval type | Changes a hard-locked check |
| Store each issue's band split and cost summary at ship | Cheaper retro | A stored copy goes out of date when a person answers a checkpoint later (ADR-045) |
| Back-fill `checkpoint_outcomes` on older issues with a migrate | Every issue judged | Nothing records what happened at their hand-offs, so a back-fill would invent outcomes |
| A branch for the new refusal inside `ship-commit` | Smaller change | Each later refusal would edit the same function |
| Record sessions in a separate file beside the manifest | No manifest write in the hook | A second record of the same fact, which can disagree with the manifest |
| A blocking lock in the hook | Simpler | A tool call would wait on another process |
| Rewrite the manifest through a YAML round trip in the hook | No text editing | It can change bytes the hook did not mean to change |
| Sample transcripts, or bound the read by time | Faster landing | Sampling understates cost; a time bound cannot be set exactly in a test |
| A separate record for the transcript read | One decision per record | The read exists only for this data flow, so it is decision 6 here |

## Consequences

**Positive:**

- The retro can report the autonomy ratio, the band split, the cost per change and the decisions confirmed, each with its sample size.
- A judged issue cannot land with an unanswered listed hand-off, and the refusal names the command that answers it.
- `G5` and every human check read exactly what they read before.

**Negative:**

- The pre-tool hook writes the manifest, once per session and issue, and runs one more `grep` on every call.
- Every issue folder gains an empty `.manifest.lock`.
- A session that makes no tool call the hook sees, and is not the session that ships, is not counted.
- `ship-commit` takes longer on an issue with long sessions.

**Neutral / follow-on:**

- A stage with no ending record has its requests counted in the next stage that has one.
- Older issues stay unmeasured. The figures grow as new issues land.

## References

- ADR-006: backward compatibility.
- ADR-026: `ship-commit` lands and derives.
- ADR-031: the delivery record.
- ADR-036: the stored generation and `atomic_io`.
- ADR-045 and ADR-051: derived state is not written.
- ADR-048: reading issue state across worktrees.
- ADR-050: the `artifact-approval` type, the precedent for a person's approval that never clears `G5`.
- `docs/autonomy-and-cost.md` owns the facts of the outcomes, the session record, the usage block and the derived figures.
