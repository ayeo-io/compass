# Approaches

A delivery issue runs one path of four stages: assess, specify, build and
ship (ADR-092). Assess does not pick a process. It scores the three scored
dimensions, reads the two switches and the domain labels (`rubric.md`), and
`compass approach evaluate` selects the evidence the change owes before it
ships. The path is the same for every size. A small change owes less
evidence; a change that touches `auth` owes more.

There are two approaches:

| Approach | One-line character | Gates | Read |
|---|---|---|---|
| **delivery** | Any change that ships: the four-stage path, with the evidence assess selects. | 3 or more, from the evidence | `path.md` |
| **spike** | You do not understand the problem well enough to state it. Explore, then graduate or discard. Nothing ships. | 1 | `spike.md` |

The hotfix is a setting of the assessment, `urgency: live-defect`, not an
approach. `path.md` says what it adds.

`compass approach evaluate --verbose` prints the evidence and the gates for
any assessment, and it is the authority: this table is a summary of it.

Every issue, however light or exploratory, obeys the default guardrails in
`governance/guardrails.md`. A spike suspends the red-before-green strategy,
but not the tested-before-ship guardrail, because nothing lands from a spike
until it graduates to the path. If a file here seems to permit crossing a
guardrail, that is a bug in the file: `docs/methodology.md` and
`governance/guardrails.md` are the authority.

## The files

- `path.md` - the four stages, what each produces, the evidence rows, the
  hotfix setting and the spike.
- `spike.md` - the spike: when assess selects it, what it suspends, and how
  it graduates or is discarded.
- `rubric.md` - the three scored dimensions, the two switches and the domain
  labels, with the test for each value.
- `assess-procedure.md` - the full assess procedure, read by `/compass:assess`
  for `--reassess` and when the change needs more than the light path.
- `composition-reference.md` - how `compass approach evaluate` computes the
  evidence, for a person who tunes the configuration or explains a result.
