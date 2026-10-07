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

The hooks and the CLI judge work against the current issue:
`.compass/current-task`, or `COMPASS_ISSUE` when a session's environment
sets it. `COMPASS_ISSUE` comes first, so two sessions in one project can work
on two issues; `compass run` sets it for each unattended session. A value
that names no issue is refused (`bad-session-issue`), never passed over for
the pointer.

Two interactive sessions share the pointer, so the pre-tool hook records the
issue each Claude Code session last worked on, by its session id, in a
`sessions.json` file under `.compass/`. When another session has moved the pointer since,
the session's next code edit is refused (`pointer-moved`) until it runs
`compass issue use <slug>` to say which issue it means. A record older than
12 hours is ignored and dropped the next time the table is written, and a
session with `COMPASS_ISSUE` set, or a runtime that gives no session id, is
not tracked. Writes are locked, so two sessions at once keep both records,
and a `.gitignore` in `.compass/` keeps the table out of every project's
commits.

## Deliberate limits

### Compass does not prove correctness

Compass checks that acceptance, traceability and evidence are present and
coherent. It does not establish that the requirements are right, the tests are
enough or the implementation is defect-free.

### A green test record has limited meaning

A test-run record holds **one exit code for one command**. That is all it
proves. It does not prove:

- which tests were collected or ran - a command that runs no test, such as
  `true`, records a green;
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

Tracing a file into the issue between two runs of the same command
changes `changes_id`, because the traced file joins `changed_files`; it
changes `tree_id` too only when the file was untracked. Tracing an
already-tracked file changes only `changes_id`. So a green recorded after
that trace is a new assertion, not a rerun of the one before it: the same
command on the same code is not flagged as a rerun, and the traced file
shows in `changed_files`.

Two kinds of traced file are not checked. An untracked file git ignores
changes neither id and is not checked: git will not stage it, so an edit
after the green is not reported, and a second run is flagged as a rerun.
If it is forced in with `git add -f` after the green, `ship-commit`
refuses until the green is run again.
A traced symlink is not checked either: neither side of the comparison
counts it, so a link pointed elsewhere after the green is not reported.

`compass ship-commit` judges the staged files right before each commit.
A git hook can still stage a file during the commit itself; when the new
commit then differs from what the green tested, the commit stands but
the issue is not marked landed, and `ship-commit` names the files and
exits non-zero.

Teams must keep their normal CI controls.

### `quick-fix finish` judges what to commit by when a file changed

`compass quick-fix start` records which files were already changed or
untracked, and which directories held no tracked file. It keeps that
record inside the git directory, where nothing is committed. `compass
quick-fix finish` refuses any of those files the agent did not trace, and
lists the files it commits. It does not guard three cases:

- a file created after `start` is taken as the change's, whoever made it;
- the start record is not checked for tampering: an edited record changes
  what `finish` refuses;
- an issue with no start record, such as one begun before `start` wrote
  one, commits a tracked file changed before the fix began.

Two more cases follow from how `finish` decides. A test the scenario
declares is committed even if it changed before `start`, because the
scenario names it. And an issue started before the record moved into the
git directory kept a digest record beside its manifest, which is
committed with the issue's records.

Read the file list `finish` prints before you push.

### Compass enforces nothing in a project that has not opted in

The hooks are installed at user scope and run in every repository on the
machine. A repository with no `.compass/` directory has never opted into
Compass, so `pre-tool.sh` and `post-tool.sh` pass through silently there: no
refusal, no output, nothing. `compass init` creates `.compass/`, which the
five entry-point commands run, so a project opts in the moment someone runs
a Compass command in it. One write happens everywhere: the session-start hook
keeps the status line launcher in the plugin's own data folder, so the
status line keeps working after an upgrade. It writes nothing in the
repository and prints nothing.

The boundary is the directory, not the state of the work. A project that has
opted in and has not been assessed is still refused, and a project the hook
cannot read is still refused - Compass answering "allow" to a question it
could not ask would be a guardrail switched off silently.

The same rule covers a project with both `compass.yml` and
`.compass/config.yml`. When `compass.yml` is Compass's file (it has a
top-level `schema:` key) and the old file still holds a setting such as
`enforcement`, that setting would stop guarding without a word, so the hook
refuses with `settings-conflict` and the CLI commands that read settings stop
with the same text. A `compass.yml` with no `schema:` is not taken for
Compass's file: the old file keeps guarding and a warning says so. A
`compass.yml` that is the only settings file is read as it is.

### Compass needs Python 3.10 or later

The CLI and the pre-tool hook's checks are Python. Without a working
`python3` 3.10 or later on the PATH, an opted-in project refuses code edits
rather than permitting them, and says so at install and at session start,
before the first refusal. Edits to files the hook does not guard as code,
such as documentation, go through as usual.

| Part | No `python3`, or one that does not run | `python3` older than 3.10 |
|---|---|---|
| `scripts/install.sh` | Says none was found, or that it did not run, warns, and installs anyway. | Names the version, warns, and installs anyway. |
| `hooks/session-start.sh` | Tells the person and the model, in place of the operating contract. Never blocks. | The same, naming the version. |
| `hooks/pre-tool.sh` | Refuses each code edit, and each edit to a path that is neither built-in code nor exempt in a project that has a settings file (it cannot read `enforcement.code_globs`): `python-missing` when there is no `python3`, `reader-failed` when it does not run. | Its checks run, but the CLI cannot record the assessment and failing test they look for, so a code edit in an issue without them is refused as usual. |
| `hooks/post-tool.sh` | No change: it does not use Python. | No change. |
| `hooks/stop.sh` | Says the end-of-session check did not run, and exits 0. | Runs its check as usual. |
| `compass` | Does not run. | Does not run. |

These rows were checked by running each hook with no `python3`, with one
that exits without running, and with Python 3.9.6. A repository that never
opted in sees none of this. Shipping the CLI as a single file would not
remove the dependency; ADR-028 records why Compass ships as a directory.

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

- the project declares no `records_signed_since` date in its state file
  (the one `compass init` writes in `.compass/`, or `.compass/config.yml` for
  a project created before that file existed)
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

### A check's compatibility within a major version is shown on its corpus only

Each built-in check implementation carries a version, and a fixture corpus of
cases with known verdicts. A build rule fails when a corpus verdict changes
and the major version does not. Across majors, Compass is designed to refuse
rather than reinterpret. Within a major, compatibility is shown on the corpus
cases and nowhere else. A change of behaviour that no case exercises is not
detected, and the corpus is small (two cases for each check at first).

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
