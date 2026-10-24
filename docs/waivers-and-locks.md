# Waivers and locks

This page shows how to write a waiver, a lock, an unlock, an approver list and a layer in `compass.yml`. It is for the owner of a project that departs from the shipped default. The settings keys (adoption, autonomy and the rest) are in [configuration.md](configuration.md). This page covers the governance edits.

A waiver is a recorded departure from the shipped default, with a reason and a named approver. The decision behind it is `ADR-039`, the architecture decision record that says who may approve a departure from the shipped default and what a lock protects. The finding codes that lint prints are in `docs/policy-lint.md`.

## A first waiver

This `compass.yml` waives one readiness signal. The signal is not locked, so the waiver stands.

```yaml
schema: 1
extends: compass:default@7
owner: ada
readiness:
  tests-declared-and-under-two-minutes:
    set: {required_for_autonomous: false}
    waiver:
      reason: our suite runs in a merge queue, not before each change
      approved_by: ada
      approved_on: 2026-10-13
```

Check a file like this with `compass policy lint --file compass.yml`. Exit 0 means it passes.

## Layers

Compass reads the configuration as layers. Each layer sits on the layer above it.

| Layer | Where it is written |
|---|---|
| default | The shipped default. It is the root. |
| parent | An optional git parent, named in `extends`. |
| project | `compass.yml` in the project root. |
| issue | The `config:` key of one issue's `manifest.yml`. |

The layer keys of `compass.yml` are:

| Key | Meaning |
|---|---|
| `extends` | The layer above. `compass:default@7` names the shipped default, major 7. |
| `owner` | The person who owns the project. The owner approves waivers and unlocks. |
| `approvers` | Lists of names, by kind of approval: `issue-waiver` in the project file and `project-waiver` in a parent. |

The `issue-waiver` list in the project file names who may approve an issue waiver. A parent's `project-waiver` list names who may approve a project waiver. The owner approves a project waiver on the shipped default, which has no such list, so `approved_by: ada` in the example above is the owner. A name that is only in `issue-waiver` cannot approve a project waiver: lint refuses it with `W-APPROVER-NOT-ALLOWED`. When a list is absent, the `owner` approves. A waiver with no `owner` anywhere fails lint.

## Operations

An entry in a catalogue (a check, a gate, a stage, a readiness signal) changes the layer above it with one operation:

| Operation | Effect |
|---|---|
| `set` | Changes named fields of the entry and keeps the rest. |
| `replace` | Writes the whole entry again. |
| `remove` | Deletes the entry. A locked entry, or one that another entry uses, cannot be removed. |

An entry holds one operation. A change that loosens what the layer above set needs a waiver.

## Project waivers

A waiver sits inside the entry it excuses, under the `waiver` key. A project waiver has three fields:

- `reason` - why the project departs.
- `approved_by` - a name from the list that may approve, or the `owner`.
- `approved_on` - the date of the approval. It must not be later than today.

Compass works out which fields the waiver covers. There is no `covers` field to write. A waiver stays valid until the parent value of a waived field changes. Then `compass policy update` asks for a new approval.

## Issue waivers

An issue waiver sits in the issue's `config:` and has two fields, `reason` and `approved_by`. Here `approved_by` is the id of a human approval record in the issue's evidence. It has no `approved_on`, because the record holds a timestamp. The waiver ends when the issue lands. Use `compass issue configure` to propose a change to one issue's configuration and to see what it would do.

## Locks

The key `locked` on an entry protects it. Its value is `true`, or `hard` for a lock that no unlock lifts. A change that makes the entry stricter is allowed. A change that loosens it, or that cannot be compared, is refused. A waiver does not excuse a lock refusal. Lint reports the refusal as `K-LOCK-REFUSED`.

The shipped default locks:

- the stages `assess`, `verify` and `ship`, and their order;
- the gates `verify.correctness`, `verify.governance` and `verify.traceability`;
- the guardrails `G1` to `G4` (the shipped rules that every change must meet) and the checks in their sets, such as `suite-passed`;
- the spike gate and the spike guardrails.

The guardrail `G5` (a human signs off on the irreversible) and the check `human-approval-present` are locked hard. No unlock lifts a hard lock.

For example, a waiver on `suite-passed` fails lint with `K-LOCK-REFUSED`, because the shipped default locks that check. To depart from a locked entry the owner must unlock it.

## Unlocks

Only the project layer can write `unlock`. The project `owner` must approve it, and it needs a waiver. Write `unlock: true`, one operation (`set`, `replace` or `remove`) and the `waiver` together in the same entry. If the operation and the waiver are not in the entry with the `unlock`, lint reports `W-NO-OPERATION`. A parent, a preset or an issue that carries `unlock` fails lint. Compass reports a project that unlocks a shipped entry as not conforming, on every `compass check` run. This page gives no unlock example on purpose: an unlock leaves conformance, so decide it with the owner and read `ADR-039` first.

## Commands

| Command | Use it to |
|---|---|
| `compass policy lint` | Check the layers, the locks and the waivers. Add `--file PATH` to check one file. |
| `compass policy show` | Print every resolved field, the layer that wrote it and the waiver that excuses it. |
| `compass policy update` | Move the project to a newer shipped major, and re-approve each waiver the move affects. |
| `compass issue configure` | Propose a change to one issue's own configuration and preview its effect. |

## Limit of the approval check

Compass checks that an approver's name is in the list and that the date is not in the future. It does not prove who wrote the name. Anyone who can edit `compass.yml` can write any name. Review a change to a waiver in a pull request. See [security.md](security.md) for what Compass does and does not guard. For the 7.0.0 changes to configuration, see [upgrade-7-0-0.md](upgrade-7-0-0.md).
