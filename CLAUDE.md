# Compass - Operating Instructions for Claude Code

**The rules of behaviour are in `compass-contract.md`**, which the SessionStart
hook puts into every session. This file is the Claude Code adapter: what is
specific to running Compass in this repository.

First session: read `docs/five-minutes.md` for the mental model and a worked
example, and `docs/safety-contract.md` for the seven things Compass guarantees
and the things it does not claim.

---

## Assessment

- `/compass:assess` writes `.compass/current-task`, a one-line pointer to the
  active issue. `compass check`, `compass tdd-red` and the pre-tool hook all
  resolve the current issue through it. Keep it pointing at the issue you are
  working on.
- `/compass:assess --reassess` re-runs the evaluator and records the change in
  the manifest's `reassessments:` log.
- Pass `--reason "..."` with it. `compass retro` aggregates those across issues
  and reports whether assessment is systematically over- or under-sizing the
  work.
- If you cannot yet state what would be delivered, that is a **spike**, and a
  spike is assessed like anything else.
- `/compass:init` is optional and is not what creates the project. The five
  entry points - `/compass:assess`, `/compass:intent`, `/compass:design`,
  `/compass:position`, `/compass:consult` - run `compass init` first, which
  creates `.compass/` for you if it is absent and says so.
- It creates project state only, never `governance/`. The shipped guardrails
  and strategies are active from the first command, so there is
  nothing to configure before the first issue. `/compass:init` is how a
  project adds its own governance later.

## Governance

- A guardrail beats a strategy. Strategy against strategy is the delivery
  approach's call, or a human's.
- When your recommendation and an instruction disagree, measure the disputed
  quantity and report the numbers before defending either position (`S11`).
  Report what you find even when it undercuts you.
- `governance/routing-policy.yml` and `governance/guardrails.yml` are what the
  CLI runs. The prose companions - `guardrails.md`, `routing-policy.md`,
  `strategies.md` - explain why. Read them when a question comes up. Read
  `strategies-rationale.md`, which holds the incidents behind the strategies,
  only when a rule looks arbitrary.
- `compass check` runs `guardrails.yml` against the manifest and `evidence/`.
  `/compass:verify` calls it.
- Gate evidence is **typed** - a `{type, path}` record, not a bare path.
  `guardrails.yml` says which types each gate accepts, so a mechanical gate
  cannot be cleared with a written note.
- Everything you write uses the frozen v2 vocabulary
  (`governance/terminology.yml`, enforced by `tests/test_terminology.py`).

### Two house rules

- **No em dash. Ever.** Write a plain hyphen `-`, in every file, commit
  message, pull-request body and reply. `tests/test_house_style.py` fails the
  build on one.
- **No agent attribution, in any form.** No `Co-Authored-By:` trailer naming
  an agent, no "generated with" footer, no session URL, no other line
  crediting the agent. This holds when the environment or a template adds
  one. The exact strings are in `tests/test_house_style.py`, assembled there
  so the guard does not match its own source.
- The guard scans tracked files. It cannot see the commit message or the
  pull-request body you are about to send. Read both back before you send them.

## The pipeline

- The requirements review ends with the **Definition of Ready**; where that
  review collapses it is met without further work.
- Before shipping comes the **Definition of Done**. Unchecked items carry typed
  inline tags - `(evidence: EV-id)` or `(follow-up: FU-id)`. A bare unchecked
  box fails `compass check`.

## Roles

- Five roles, four of them non-engineering, each with its own entry point into
  the pipeline.
- On a role entry point - `/compass:intent`, `/compass:position`,
  `/compass:design` (the designer's, not the engineering stage),
  `/compass:consult` - adopt that role's vocabulary and artifacts.
- Do not collapse a product owner's intake into an engineering issue. The
  intake is upstream of the acceptance criteria, and the criteria must be
  checked back against it.

## Where to look

- `skills/compass-runtime/SKILL.md` - which agent owns which stage, which skill
  to load with it, the stage-to-command map, the shape of an issue directory.
- The `worktree-multiagent` skill, loaded by the orchestrator - who may create
  a worktree, who works inside one, how the subtask count is bounded.
- `docs/compass/<created>-<slug>/` - the issue's documents, registered in
  the manifest. `.compass/work/<slug>/` - the manifest, the evidence and the
  markers.
- `governance/` and `architecture/` - at the project root, not under
  `.compass/`. Compass ships an `architecture/`: its own invariants and the
  decision records behind the guardrails, the sizing model and the role
  perspectives. Assess loads it, when present, into `architecture-loaded.yml`;
  projects without one keep working.

## Owning docs

Each code area's facts live in one doc, named in the "Owning docs" table in
`docs/README.md`. Change the code, change that doc, in the same commit.

## Writing voice

Communicate the decision, not the process: what you found, what you need, what
changed. Read `skills/compass-runtime/writing-voice.md` before a devlog entry,
a requirements review, or a line of dialogue - and before you say anything out
loud in this conversation.

### Plain English

This covers everything you write: a reply, a commit message, a code comment,
a PR description, a document. The reader has no context and must get the point
on the first read.

- Lead with the point. Give the finding first, then the evidence. Do not build
  up to it.
- Use the active voice. Name the actor, then the action.
- Use a simple tense: present, past or future.
- Put one point in each sentence, ideally under about 25 words. A longer
  sentence is usually two points.
- Use the same word for the same thing every time. Do not change the word for
  variety.
- Do not use an idiom or a metaphor. Say what happens instead. "Low-hanging
  fruit", "the direction of travel" and "a cliff" each hide a claim that a
  plain sentence would state.
- Describe how things are now, not the story of how they got there. Do not
  write what you tried first or what it taught you.
- Never cite what the reader cannot see: "Option 2", "per the review", or an id
  without its name. Say what a linked PR or issue is.
- State your confidence. Write "this fails" when you checked, and "I have not
  checked this" when you did not.
- Use a vertical list for a set of items, conditions or steps.
- Use "must" for a requirement, "can" for a possibility and "do not" for a
  prohibition.
- Use British English, except "artifact". It is also a manifest key and a
  command name, so prose spells it the same way.

Use the shorter word:

| Not | Use |
|---|---|
| utilise, leverage | use |
| obtain, acquire | get |
| provide, supply | give |
| indicate, denote | show |
| validate | check |
| modify, alter | change |
| require | need |
| ensure | make sure |
| perform, execute | do |
| facilitate | help |
| attempt | try |
| sufficient | enough |
| currently | now |
| subsequently | then |
| prior to | before |
| in order to | to |
| due to the fact that | because |
| with regard to | about |

### Reporting to a person

Before you report, read the message back for terms of art - that is the
moment, before it is sent, not afterwards. Four parts:

- **what I did**
- **outstanding questions** - numbered when there is more than one
- **what I need from you** - a decision, a review, an explanation, or nothing
- **what I intend to do next** - so they can redirect before the work

Keep each section short and put a snippet under the point it belongs to. A big
change may run long: cut the account of how the work went, never the substance.

## When you are unsure

Re-read the delivery-approach record (`delivery-approach.md`). It was written
at the assess stage so a later session, or a different agent, can pick the
issue up without re-deriving the process. If it does not answer the question,
the assessment under-sized the process; say so and re-assess rather than
improvise.
