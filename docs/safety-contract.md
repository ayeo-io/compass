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

Only a `human-approval` record given for guardrail `G5` meets this approval. A
record that names another subject - a `check`, `waiver`, `checkpoint`,
`artifact` or `decisions` key, or a `guardrail` other than exactly `G5` - was
given for that subject and is set aside. In Claude Code a person records
the sign-off by typing `/compass:approve`: the agent asks with `compass
evidence request`, the Stop hook shows the request in Compass's words, and a
`UserPromptExpansion` hook records the typed command (ADR-068). At a
terminal a person runs `compass evidence approve --guardrail` and the value `G5`,
giving `--approver`, `--role` and `--scope`; on a host whose adapter
has no person-only approval event, such as Codex, that is the only path.

From 7.0.0 a person can also delegate approvals to one named agent with
`/compass:delegate`, for at most 24 hours and a stated scope (ADR-069). The
guardrail 5 sign-off is covered only when typed, and only after the person
types back a code the hook showed them. The record names the person, the
agent and the delegation. The person sees a summary of delegated approvals
until they mark them reviewed, and `/compass:reject <record id>` overrules
one; for the sign-off it writes an `approval-withdrawal` record, which never
reverses an action already taken and never fails a landed issue.

What holds the boundary, and what does not:

- Only a person's typed command records an approval in Claude Code. The
  command files set `disable-model-invocation: true`, so the Skill tool and
  a scheduled job cannot raise the event, and the hook refuses a command
  file without the flag. A command in another session's message or in a
  subagent's report never expands. This was measured on Claude Code 2.1.300.
- The hook refuses a nested `claude -p` session, which reports a
  `CLAUDE_CODE_ENTRYPOINT` starting with `sdk-`. Entrypoint values of IDE
  and desktop sessions were not measured, so only `sdk-` is refused.
- A prompt suggestion accepted with Tab can submit arguments the model
  worded. The approval binds to the request Compass showed, and a g5
  delegation needs the typed-back code.
- The guarantee is as strong as the terminal check, and no stronger: a
  process running as the same operating system user can still write a
  record, a request or a delegation file, pipe forged input into the hook,
  or drive a session through a pseudo-terminal.
- The prompt path needs the plugin install: the hook acts only on a command
  whose `command_source` is `plugin`. A source install
  (`scripts/install.sh`) registers the hook, but its commands are not plugin
  commands, so a person there approves at a terminal.

A record with no subject key, the form earlier sign-offs use, still counts. A
landed issue that the earlier rule passed is reported, never failed.

A person's answer to a checkpoint hand-off (`compass evidence approve
--checkpoint`) is a `checkpoint-approval` record, not a `human-approval`, so it
never meets this approval.

The pre-tool hook refuses the agent's tool calls on approval state
(`cli/compass_pkg/approval_guard.py`):

- Edit or Write on an issue's `approval-requests/` files, and a Bash command
  that names that folder or `hooks/prompt-approval.sh`
  (`approval-request-protected`);
- Edit or Write under `.compass/delegations/`, and a Bash command that names
  that folder (`delegation-protected`);
- a delegated approval whose `--as` is not exactly the agent Claude Code
  reports (`delegation-caller-mismatch`). The call is the main agent only
  when the hook input has neither `agent_type` nor `agent_id`, and the CLI
  takes no abbreviated flag, so `--deleg` cannot pass unseen;
- Read or Grep on the session transcript, and a Bash command that names it or
  a `.claude*/projects` folder (`transcript-protected`). Claude Code writes a
  hook's block message to the transcript (measured on 2.1.301), and the block
  message is where the person sees the code that confirms a g5 delegation.

The Bash checks match text, so they stop the agent's ordinary use and not a
deliberate workaround. A process running as the same operating system user
can still write these files, or `manifest.yml`.

How each record was made shows, and is never judged. A record holds `via`:
`terminal`, `prompt` or `delegation`. The detail of `human-approval-present`
and the receipt say "via a terminal", "via a typed prompt", "via <agent>
under <delegation>", or "written without a Compass command" for a record
with no `via`, which still counts.

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

With nothing staged, `compass ship-commit --issue <slug>` lands at HEAD
only when the issue's own commits at the tip stay inside its declared
scope. It walks the first parent from HEAD. A commit that changes only
the living spec is passed over. A merge whose merged-in commits are all
on the base branch, such as a merge of `origin/main`, counts only the
paths it changed against every parent, which is its conflict resolution.
Any other merge, such as a multiagent integration merge, is judged in
full and ends the walk, whatever commit the merged branch started from.
The walk stops at the issue's newest other commit, which is judged in
full.

The base branch is the remote's default branch (`origin/HEAD`), or
`origin/main`, the base `compass spec sync` merges. When neither
resolves, such as in a clone with no remote, every merge is judged in
full, and the refusal says that the base was not found.

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

### A dependency between issues is read from this checkout, and a fault never blocks

An issue can record the issues it waits for in its manifest's `depends_on`
(`compass issue depends add`). While the issue is at the implement stage, and
neither on hold nor done, the pre-tool hook refuses a production-code edit
with `waits-for-issue` when a dependency has not reached its `until`. The
refusal comes before the declared-acceptance exit, so `.acceptance` does not
clear it; a spike is never refused for it. ADR-062 records the decision.

The hook's read has these limits:

- It reads each dependency's manifest from this checkout's `.compass/work/`,
  through the manifest loader and never the parse cache, and runs no git
  command. A dependency finished only in another worktree still refuses here.
  The refusal names both ways out: bring that issue's folder into this
  checkout, or run `compass issue depends remove <slug>`. No override flag
  exists.
- It refuses only on a positive read of an unmet dependency. A dependency on
  an issue with no manifest here, a manifest that does not parse, an unknown
  `until`, an entry of the wrong shape and a dependency that waits for this
  issue in turn each allow the edit with one warning line on standard error.
  `compass issue lint` reports the same fault and fails. A reader that cannot
  run at all, such as a broken install, still refuses.
- It reads one level. A hand-written cycle of three or more issues, each at
  implement, refuses all of them until one dependency is removed;
  `compass issue depends add` refuses to write a cycle, and lint reports one.
- An issue with no `depends_on`, or an empty one, starts no extra process and
  opens no other manifest. With dependencies, the hook starts one more
  python3 process and opens each dependency's manifest once.

### The hook records each session on its issue, and a fault never blocks

On every Edit, Write or Bash call it judges, the pre-tool hook adds the
call's session id to the issue's `usage.sessions`, once, so `compass
ship-commit` can read that session's transcript when the issue lands. ADR-063
records the decision; this is the one place the hook writes an issue's
manifest.

- The issue comes from `COMPASS_ISSUE` or `.compass/current-task`, read in
  shell. With neither, nothing is recorded; the most recently changed issue
  is never guessed. A session whose fresh entry in the session table behind
  the `pointer-moved` refusal names another issue is not recorded on the
  pointer's issue.
- A session id that is not letters, digits, `-` and `_` is not recorded.
- An id already in the manifest costs one `grep` and no python3 process. A new
  id starts one python3 process, which opens only that issue's manifest.
- The write never waits. It tries the issue's `.manifest.lock` once, without
  blocking, and records nothing when another writer holds it; a later call
  records the id. `compass` commands hold the same lock while they write a
  manifest.
- It inserts the id into the file's text and checks that the parsed result
  changed only `usage.sessions`, so no other byte moves. It replaces the file
  atomically, after comparing the bytes on disk with those it read; a writer
  that changed the file in between is merged, not overwritten.
- Any fault - a read-only manifest or folder, a failed write, a recorder that
  cannot run - leaves the manifest as it was and no temporary file behind, and
  the hook judges the call as before. Recording never refuses a call. A broken
  install still refuses through the hook's other readers.
- A session that makes no tool call the hook sees is not recorded, and a
  command that loaded the manifest before the hook wrote can drop the id when
  it saves. The next call then records it again.

### Shell-write detection is best-effort

The Claude Code pre-tool hook completely covers supported file-editing tools.
For shell commands it recognises these write shapes, and only these:

- `>` and `>>` redirects, including the `cat > file <<EOF` heredoc form
- `sed -i`, `perl -i`
- the arguments of `tee`, and the last argument of `cp` and `mv`, found in
  the same simple command as the `tee`, `cp` or `mv` word, including behind
  a wrapper such as `sudo` or `timeout`; a file that another command in the
  same line only reads is not a target
- `patch -p<n>` and `git apply` - writers with unknowable targets
- an inline interpreter script (`python3 -c`, `node -e`, a heredoc) that opens
  a file for writing

Anything else runs unchecked: a write through a script, a build step, or an
interpreter reached via a wrapper is not detected. Unknown commands are allowed
rather than blocking ordinary development indiscriminately.

A target that starts with a variable, such as `$S/plant.ts`, is judged at the
variable's value only when the same command states that value for certain:

- the command assigns the variable once, to a plain absolute path with no
  `..` step, in a statement that always runs before the write;
- nothing after the assignment names the variable, other than to use it, or
  runs `eval`, `source`, `read`, `declare` or another command that can set a
  variable without naming it.

Any other variable, including one from the environment or from `$(...)`, is
judged as a path inside the project, so a write through it needs a failing
test on record. The hook reads the command's text and does not run it, so a
command written to mislead that reading is not detected, like any other
write through a script.

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

### The readiness floor reads a record a person can edit

From 7.0.0 an issue on `autonomy: autonomous` is refused at `compass approach
evaluate --write` while the repository is below the readiness floor or has no
fresh readiness record. The floor guards against an unready repository, not
against a person. The record, `.compass/readiness.yml`, is a plain file in the
checkout, and anyone who can edit it can mark a readiness signal present, as
anyone who can edit `compass.yml` can change the commands it runs.

- An untrusted CI contribution is refused before the record is read, so a
  record committed with the contribution cannot clear the floor.
- The session-start hook adds one readiness line for an autonomous project
  below the floor or not measured. It reads the record and runs nothing, and
  its readiness code has its own guard: a record or settings file it cannot
  read loses the line, never the contract, and the hook exits 0.
- The floor is not a guardrail. It decides whether work runs without a
  person, not whether work lands.

### A check's compatibility within a major version is shown on its corpus only

Each built-in check implementation carries a version, and a fixture corpus of
cases with known verdicts. A build rule fails when a corpus verdict changes
and the major version does not. Across majors, Compass is designed to refuse
rather than reinterpret. Within a major, compatibility is shown on the corpus
cases and nowhere else. A change of behaviour that no case exercises is not
detected, and the corpus is small (two cases for each check at first).

**An approval of a waiver is a name and a date, and is not authenticated.** A waiver that loosens the shipped default carries `approved_by` and, for a
project waiver, `approved_on`. Lint checks a project waiver's approver against the parent's
`approvers.project-waiver` list, or the owner when the parent sets no such list (an empty list lets nobody approve), and that an issue waiver's
approval is a record in the issue's evidence. It cannot check that the person
named gave the approval. Anyone who can edit `compass.yml` can write any name
and date. Repository permissions and review of the pull request that changes
`compass.yml` are the control.

**Conformance is a statement about the configuration, not about the work.** A project that unlocks a framework entry is reported non-conformant on every
`compass check`, `compass issue receipt` and `compass approach show`. The
line states that the configuration departs from the framework's locks. It does
not say that any work was done badly, and a project that unlocks nothing is not
shown to have done good work. A hard lock (guarantee 5) cannot be unlocked at
all.

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
| 5 (human approval) | Structured `human-approval` evidence given for guardrail `G5`, checked before ship |
| 6 (process-integrity CI) | `compass ci` |
| 7 (resumable state) | the manifest (`templates/manifest.yml`), its artifacts and evidence under `.compass/` |

## What adopters still own

- Make an honest assessment and review the computed approach.
- Review generated specifications, designs and evidence.
- Run normal engineering and operational controls.
- Protect the repository and CI environment.
- Keep secrets out of committed Compass artifacts.
- Reassess when the work changes shape.
