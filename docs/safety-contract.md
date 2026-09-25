# Compass safety contract

This contract states what Compass itself will enforce when its adapter and CLI
are used for an issue. It does not transfer responsibility for software quality
or operational safety away from the team.

The contract applies from Compass 1.0.0. Weakening a guarantee needs a
major-version change and a documented migration path.

## Guarantees

Where a guarantee has changed since 1.0.0, the version it changed in is named
beside it rather than left for a reader to infer from the git history. A
guarantee with no version beside it has held since the contract began.


### 1. Routing is deterministic after assessment

Risk, familiarity, size, goal and role need judgement. Once those values
are recorded, `compass approach evaluate` applies the routing policy as a pure
function.

The same assessment plus the same policy produces the same approach, every
time.

### 2. A declared guardrail cannot silently become advice

Every declared guardrail must map to an implemented CLI check. Policy linting
and issue checking fail closed when an implementation is missing.

If project configuration disables an executable check, Compass reports it as
not checked, names it and explains how to restore it. It does not count the
check as passing.

### 3. Required gates need typed evidence

Compass will not clear a required mechanical gate with narrative assurance.
Evidence is registered by id and type, and each gate declares which evidence
types it accepts.

Follow-ups are recorded explicitly and must be resolved before Compass
completes the shipping workflow.

### 4. A spike cannot silently become delivery

A spike can explore without the normal TDD strategy, but it cannot produce
production-landable changed files. It must conclude with one of three
decisions: discard, defer or graduate.

Graduation creates a new assessment and delivery approach before anyone turns
findings into production work.

### 5. Irreversible work needs recorded human approval

Human approvals are needed for:

- auth and access-control changes;
- payments or movement of money;
- personal data and privacy;
- migrations; and
- any critical-risk change that can lose data, lose money, breach auth or
  privacy, or resist clean rollback.

The evidence records the approver, role, decision, time, scope and conditions.

### 6. Compass CI checks process integrity

`compass ci` checks routing, issue schemas, evidence, approvals, traceability
and follow-ups across Compass issues.

Its failures are structured: every failure message names what failed, why it
matters and what to do next, so a red run is actionable without reading the
source.

It does not run the project's tests, linting, security scanning, builds or
deployment checks. Project CI and Compass CI are complementary lanes.

### 7. Issue state survives the conversation

Compass writes the assessment, approach, artifacts, evidence, decisions and
status beneath `.compass/`. Another person, session or compatible runtime can
resume by reading the files rather than reconstructing chat history.

## Deliberate limits

### Compass does not prove correctness

Compass checks that acceptance, traceability and evidence are present and
coherent. It does not establish that the requirements are right, the tests are
enough or the implementation is defect-free.

### A green test record has limited meaning

A test-run record holds **one exit code for one command**. That is all it
proves. It does not prove:

- which tests were collected or ran;
- that the run exercised every declared scenario; or
- that a trusted runner made the record.

Each record does name the tree it ran on, with two git tree ids: `tree_id`,
the tracked files on disk plus the issue's own new files, and `changes_id`,
the issue's changed files and the test files its scenarios declare.
`compass check` judges the issue's newest record:

- in flight, once every gate has passed, it fails if the tree has changed
  since the record was made
- landed, it fails if the issue's changed files and declared tests in the
  commit that landed it are not the files that were tested

The ids show which tree a record claims; they do not prove that a trusted
runner produced the record, and an older record is not judged. A record
written outside a git repository, or before records carried a tree id, is
not judged either.

Teams must keep their normal CI controls.

### Compass enforces nothing in a project that has not opted in

The hooks are installed at user scope and run in every repository on the
machine. A repository with no `.compass/` directory has never opted into
Compass, so `pre-tool.sh` and `post-tool.sh` pass through silently there: no
refusal, no output, nothing. `compass init` creates `.compass/`, which the
five entry-point commands run, so a project opts in the moment someone runs
a Compass command in it.

The boundary is the directory, not the state of the work. A project that has
opted in and has not been assessed is still refused, and a project the hook
cannot read is still refused - Compass answering "allow" to a question it
could not ask would be a guardrail switched off silently.

### The red marker is checked against its record, and a record can still be written by hand

The pre-tool hook refuses a code edit unless a failing test is on record for
the issue. The hook reads the red record beside the marker -
`evidence/red*.json` - and checks its `content_digest`; an empty marker
unlocks nothing.

**What that does not buy.** The digest is a plain `sha256` over the record's
own fields, with no secret, so anyone who can write the file can compute a
matching one. It is tamper evidence, not forgery resistance: it catches a
record edited after it was written, and it does not catch one written from
scratch by someone who knows the format. Forging a red record needs
valid JSON with a correct digest, not an empty file. It is still possible.

A record with no identity - written before records carried one, or written
by hand - unlocks an edit only in one of two cases:

- the project declares no `records_signed_since` date in
  `.compass/config.yml`
- the record's own timestamp is earlier than that date

`compass init` writes the date as the day the project was set up, so a new
project refuses unstamped records from the start. A project set up earlier
keeps the older allowance until it adds the line. Two limits remain. The
timestamp can be written by hand too, so the cutoff raises the cost of a
forged record from one line of JSON to a dated one, and no further. And
`.compass/` is not a guarded path, so the line can be deleted like any other
project setting.

### Shell-write detection is best-effort

The Claude Code pre-tool hook completely covers supported file-editing tools.
For shell commands it recognises these write shapes, and only these:

- `>` and `>>` redirects, including the `cat > file <<EOF` heredoc form
- `sed -i`, `perl -i`
- `tee`, and the destination argument of `cp` and `mv`
- `patch -p<n>` and `git apply` - writers with unknowable targets
- an inline interpreter script (`python3 -c`, `node -e`, a heredoc) that opens
  a file for writing

Anything else runs unchecked: a write through a script, a build step, or an
interpreter reached via a wrapper is not detected. Unknown commands are allowed
rather than blocking ordinary development indiscriminately.

Shell scripts, makefiles and extensionless scripts are not classified
as production-code file types for red-before-green enforcement.

Inside a worktree, Edit and Write are checked against that worktree's own red
state, because they name their file and the hook resolves the project from
it. A shell write is not. Its targets are found against the session's
project, with two results:

- a relative path is checked against the session's issue, not the worktree's
- an absolute path into a worktree outside the project - the default place
  for worktrees - is not checked at all

See [Security](security.md) for the exact trust boundaries and hardening
guidance.

### Compass governs its own workflow, not every agent action

Compass cannot prevent a person, automation or agent from changing the
repository outside its adapter and commands. Repository permissions, branch
protection, review policy and CI remain essential.

### Compass is adaptable, not universal

The shipped policies are a starting point. Teams can add strategies and
project guardrails, provided they preserve this contract.

## Mechanical enforcement

| Guarantee | Primary mechanism |
|---|---|
| 1 (deterministic routing) | `compass approach evaluate` over assessment and policy |
| 2 (implemented guardrails) | `compass policy lint` and `compass check` |
| 3 (typed evidence) | Gate type declarations plus the issue evidence registry |
| 4 (spike containment) | Routing conflict checks and spike invariants |
| 5 (human approval) | Structured `human-approval` evidence checked before ship |
| 6 (process-integrity CI) | `compass ci` |
| 7 (resumable state) | the manifest (`templates/manifest.yml`), its artifacts and evidence under `.compass/` |

## What adopters still own

- Make an honest assessment and review the computed approach.
- Review generated specifications, designs and evidence.
- Run normal engineering and operational controls.
- Protect the repository and CI environment.
- Keep secrets out of committed Compass artifacts.
- Reassess when the work changes shape.
