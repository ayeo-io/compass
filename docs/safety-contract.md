# Compass safety contract

This contract states what Compass itself will enforce when its adapter and CLI
are used for an issue, and what it does not claim. It does not transfer
responsibility for software quality or operational safety away from the team.

The contract applies from Compass 1.0.0. Weakening a guarantee needs a
major-version change and a documented migration path. Where a guarantee has
changed since 1.0.0, the version it changed in is named beside it.

## Guarantees

### 1. Routing is deterministic after assessment

- Risk, familiarity and size need judgment, as do the goal and urgency
  switches. Once those values are recorded, `compass approach evaluate`
  applies the routing policy as a pure function.
- Its inputs are the recorded assessment and the project's resolved
  configuration (the fixed check set with the tighten-only settings of
  `compass.yml`). The same inputs produce the same approach, every time.
- From 9.0.0 the issue's own `config:` is not an input ([ADR-094]), and the
  documents an issue has on disk are not an input ([ADR-091]).
- Without `--write` it reads the configuration stored at the last evaluation;
  with `--write`, the current one.
- From 9.0.0 every delivery issue owes the same evidence ([ADR-099]). Risk,
  size, familiarity and urgency add no review and no record.
- A label of guarantee 5, a label in the project's `signoff_labels` and
  critical risk add a person's approval. A project's `require_evidence`
  setting adds the evidence it names.

### 2. A declared guardrail cannot silently become advice

- Every declared guardrail must map to an implemented CLI check. Policy
  linting and issue checking fail closed when an implementation is missing.
- If project configuration disables an executable check, Compass reports it as
  not checked, names it and explains how to restore it. It does not count the
  check as passing.

### 3. Required gates need typed evidence

- Compass will not clear a required mechanical gate with narrative assurance.
  Evidence is registered by id and type, and each gate declares which
  evidence types it accepts.
- From 9.0.0 Compass writes the evidence of a delivery issue itself
  ([ADR-099]). The session writes no evidence by hand.
- `compass quick-fix finish` reads the scenarios from the acceptance criteria
  and the changed files from git, runs the tests and writes the red and green
  records. It passes the three gates every issue has (`verify.correctness`,
  `verify.governance` and `verify.traceability`) from those records and the
  output of `compass check`.
- In a record that `finish` made, red before green means that the tests fail
  without the change. The test command must fail on a copy of the commit the
  issue started from, with the test files of the change laid over it, and
  pass on the working tree ([base-copy.md][base-copy]).
- The red record says `proved_on: base-copy` and names the base commit. The
  limits are under "What the record of a 9.0.0 issue does not claim" below.
- Follow-ups are recorded explicitly. On a path issue each one links to the
  GitHub issue that tracks the work. An open Definition of Done item, where a
  project's settings make the issue owe the Definition of Done, is met only
  by such a follow-up.
- On an issue assessed before 9.0.0 each follow-up must be resolved before
  Compass completes the shipping workflow.

### 4. A spike cannot silently become delivery

- A spike can explore without the normal TDD strategy, but it cannot produce
  production-landable changed files.
- It must conclude with one of three decisions: discard, defer or graduate.
- Graduation creates a new assessment and delivery approach before anyone
  turns findings into production work.

### 5. Irreversible work needs recorded human approval

Human approvals are needed for an issue labeled:

- `auth` - auth and access-control changes;
- `payments` - payments or movement of money;
- `personal-data` - personal data and privacy; or
- `migrations` - migrations, which can lose data that cannot be restored.

The evidence records the approver, role, decision, time, scope and conditions.

#### The trigger

- From 7.0.0, critical risk on its own does not need this sign-off. CI,
  review and the other guardrails still gate critical-risk code.
- A project adds labels to the trigger with the tighten-only setting
  `signoff_labels` in its `compass.yml`. No setting can loosen the trigger
  ([ADR-094]).
- An issue assessed before 7.0.0 keeps the trigger stored with it.

#### Approval of the scenarios before code

From 9.0.0 a person also approves the scenarios before any code edit
([ADR-099]). This holds for an issue with one of the four labels, with a label
in `signoff_labels`, or with critical risk.

- The session writes the scenarios in the acceptance criteria, asks with
  `compass evidence request --checkpoint specify` and stops.
- Until a person has answered, the pre-tool hook refuses a code edit with the
  code `code-before-approval`, and `compass quick-fix finish` refuses to
  write the record.

#### An approval covers the change the person saw

- `compass quick-fix finish` writes a digest of the code and test files of
  the change in the manifest (`change_sha256`). The request for the sign-off
  or the ship approval holds that digest, and so does the approval record.
- When the code or the tests change afterwards, the next `finish` writes a
  new request. `compass check` fails `human-approval-present` and
  `ship-approval-present` until a person approves the new state. The earlier
  record stays on record and no longer counts.
- The ship approval can also be read from the approving review of the merged
  pull request, which is given after the change stopped moving.
- An approval record with no digest, and an issue whose record was not
  written by `finish`, are not compared with the change.

#### Which record counts

- Only a `human-approval` record given for guardrail `G5` meets this
  approval. A record that names another subject - a `check`, `waiver`,
  `checkpoint`, `artifact`, `decisions` or `ship` key, or a `guardrail` other
  than exactly `G5` - was given for that subject and is set aside.
- A record with no subject key, the form earlier sign-offs use, still counts.
  A landed issue that the earlier rule passed is reported, never failed.
- A `G5` sign-off is given before code and is not the ship approval
  ([ADR-095]). A ship approval is a `human-approval` record with
  `ship: <slug>`, or a review of the merged pull request.
- A person gives the ship approval with `compass evidence request --ship`,
  then `/compass:approve`; or with `compass evidence approve --ship` at a
  terminal; or through an agent under a delegation typed `--for ship` and
  confirmed with its code.
- A person's answer to a checkpoint hand-off (`compass evidence approve
  --checkpoint`) is a `checkpoint-approval` record, not a `human-approval`,
  so it never meets this approval.
- How each record was made shows, and is never judged. A record holds `via`:
  `terminal`, `prompt` or `delegation`. The detail of
  `human-approval-present` says "via a terminal", "via a typed prompt", "via
  <agent> under <delegation>", or "written without a Compass command" for a
  record with no `via`, which still counts.

#### How a person approves

- In Claude Code a person records the sign-off by typing `/compass:approve`:
  the agent asks with `compass evidence request`, the Stop hook shows the
  request in Compass's words, and a `UserPromptExpansion` hook records the
  typed command ([ADR-068]).
- At a terminal a person runs `compass evidence approve --guardrail` and the
  value `G5`, giving `--approver`, `--role` and `--scope`. On a host whose
  adapter has no person-only approval event, that is the only path.
- The agent's words in a request, its scope and a waiver's reason, are shown
  with every control, format and line-separator character removed, so an
  escape sequence cannot move the cursor over, and a direction override
  cannot reorder, the line that names the subject.

#### Delegation

A person can delegate approvals with `/compass:delegate [--agent <name>]
[--until <time>] [--on <issues>] [--for <forms>] [--max <n>]` ([ADR-069],
amended by [ADR-077]). The person sets the bounds. Compass puts no upper
limit on how long a delegation lasts or on how many are in force.

- With no `--until`, a delegation lasts until `/compass:revoke`. Compass lists
  each delegation with no end time when a session starts, after `/clear` and
  after the conversation is compacted. It shows no list for a session resumed
  with `--resume` or `--continue`, which keeps its session id and so its
  delegations.
- With no `--agent`, a delegation covers the session it was typed in: its main
  agent and its subagents, including built-in ones such as general-purpose, in
  any worktree. With `--agent <name>`, it covers that agent in any session.
  `any` is refused.
- With no `--on`, a delegation covers every issue in the repository's
  worktrees, at any generation. With `--on <issues>`, it covers those issues,
  each at the generation it had when the delegation was made.
- Every worktree reads one common store: `.compass/delegations/` in the main
  checkout. A delegation file in a linked worktree's own folder gives no
  approval.
- The guardrail 5 sign-off is covered only with `--for g5`, and only after the
  person types back a code the hook showed them. After that code, the
  delegation can have no end time and cover every issue, so one typed-back
  code can cover several irreversible changes. `--labels` is not a flag.
- The record names the person, the agent and the delegation. The manifest
  keeps a copy of each delegation used (`delegations_used:`), with no nonce
  and no session id.
- The person sees a summary of delegated approvals, from any worktree, until
  they mark them reviewed. `/compass:approve` with nothing pending marks
  reviewed only the approvals that the session's last summary showed.
- `/compass:reject <record id>` overrules one. For the sign-off it writes an
  `approval-withdrawal` record, which never reverses an action already taken
  and never fails a landed issue.

**The call ticket.** The agent runs `compass evidence approve --issue <slug>
--delegated --as <agent>` as a plain command in its Bash tool, with `compass`
in command position.

- The pre-tool hook reads the command and writes a call ticket into the
  store: the session and the caller that Claude Code reported, and a digest
  of the command's words. The CLI takes the matching ticket and tests the
  session from it. It never reads the session from the environment.
- A call the hook never read, such as one inside a script, has no ticket of
  its own, so the CLI refuses it.
- Compass deletes the ticket when the call finishes or fails, when Claude
  Code reports the call's permission denied, when the turn ends, and when the
  person submits the next prompt. An unused ticket expires after 10 minutes.

Three windows stay open. In each, the ticket names only the session and the
agent that made the call.

1. The person denies a permission prompt. Claude Code runs no hook until the
   next prompt, so a process the agent had already started in the background
   can take the ticket before then.
2. Auto mode's check denies a call and Claude Code sends no hook for it. The
   agent can take the ticket from a script in the same turn.
3. The shell skips a `compass` command in command position, as after `true
   ||` or `false &&` or on a heredoc line. A program that the same call
   starts can take its ticket before the call ends.

Two limits come from running as the person's operating system user. Neither
limit is closed: a process that can do either can already act as the person.

- A process running as that user can write a ticket into the store.
- A process that can start Claude Code as that user can resume a session by
  its id, as `claude --resume <session id>` does, and so use a delegation
  typed in that session without `--agent`. Session ids appear in the issue's
  records.

#### What holds the boundary, and what does not

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
- The code is 64 bits, so its salted hash cannot be searched within the
  10-minute window. That protects the stored hash only. The transcript shows
  the code in clear, so for the transcript the person's Enter is the barrier.
- Each typed command is recorded once. The hook refuses `/compass:approve`,
  `/compass:reject` and `/compass:delegate` when the input has no
  `prompt_id`, and refuses a `prompt_id` that a record, a closed request or a
  delegation already holds. `/compass:revoke` needs no `prompt_id`: it only
  ends delegations.
- The guarantee is as strong as the terminal check, and no stronger: a
  process running as the same operating system user can still write a
  record, a request, a delegation file or `manifest.yml`, pipe forged input
  into the hook, or drive a session through a pseudo-terminal.
- The prompt path needs the plugin install: the hook acts only on a command
  whose `command_source` is `plugin`. A source install
  (`scripts/install.sh`) registers the hook, but its commands are not plugin
  commands, so a person there approves at a terminal.

#### The approval guard

The pre-tool hook refuses the agent's tool calls on approval state
(`cli/compass_pkg/approval_guard.py`). The guard is defense in depth against
an accidental or injected read of the session transcript or of an approval
request. It is not a hard boundary. The stored hash, the 64-bit code and the
person's typed approval are what keep a delegation from being confirmed
without a person. The exact reading rules are in the
[hook reference](hook-reference.md#the-approval-guard), and the reasons are
in the decision record
[the approval guard judges words, not text][guard-decision].

The guard refuses these calls. Each path check ignores letter case.

| Call | Refusal code |
|---|---|
| Edit or Write on an issue's `approval-requests/` files, and a Bash word that names that folder or `hooks/prompt-approval.sh` | `approval-request-protected` |
| Edit, Write, Read or Grep under `.compass/delegations/`, a Grep whose glob names `delegations`, and a Bash word that names that folder | `delegation-protected` |
| A Grep glob, or a Bash word with `*`, `?` or `[`, that matches a delegation path and not an ordinary path of the same shape | `delegation-protected` |
| A delegated approval whose `--as` is not exactly the agent Claude Code reports | `delegation-caller-mismatch` |
| Read or Grep on the session transcript's folder, inside it or on any folder above it, such as the configuration folder or the home folder | `transcript-protected` |
| An approving review of a pull request, with `gh pr review` or `gh api` | `pr-review-protected` |

How the guard reads a call:

- The guard reads a simple command as words and judges any other command by
  its whole text. A simple command is made only of plain `git`, `gh`, `ls`,
  `wc`, `stat` and `cat` commands. The gate fails closed: a shape it does not
  name is not simple.
- In a simple command, the message text of a commit, an issue, a pull request
  or a release is not judged. In any other command, any text that names a
  protected thing is refused.
- `ls`, `wc` and `stat` may name a request path, and `cat` may name
  `hooks/prompt-approval.sh`, as the one bare operand of a command that
  stands alone. The delegation folder has no exemption.
- Read, Grep, Edit and Write may name a file inside the auto-memory folder
  (`<configuration folder>/projects/<one folder>/memory/`), after `..`,
  letter case and each symbolic link are resolved. A Bash command that names
  the folder stays refused.
- A project's own `.claude` folder is not refused.

Limits and known costs:

- A Grep over the whole project still reaches the delegation folder.
- The glob check is a heuristic. It passes a glob that picks a delegation
  file together with other files, such as `**/*l*.yml`.
- The glob check refuses some ordinary Grep globs, such as `**/*-*.yml`.
- The guard refuses some ordinary words in a `compass evidence` command, such
  as `--reason 'fix --assets'` and a compact JSON value with a comma. The
  refusal names the word.
- In a command that is not simple, a quoted word that holds a refused form,
  such as `grep 'gh pr review -a' docs`, is refused.
- `ls ~` and `cd ~` are refused, because the home folder is above the
  transcript.
- Claude Code writes a hook's block message to the transcript (measured on
  2.1.301), and the block message is where the person sees the code that
  confirms a g5 delegation.
- A review approval by another person on the merged pull request is the ship
  approval, and the agent runs `gh` with the person's login. That is why the
  guard refuses an approving review.

#### What the approval guard does not stop

The Bash checks match words, so they stop the agent's ordinary use and not a
deliberate workaround. A text-matching guard cannot follow anything that the
shell, a spelling or an interpreter builds at run time. The stored
confirmation hash and the 64-bit code (ayeo-io/compass#599) are the control
that holds then. These are not detected:

- words built at run time: a variable, command substitution, a value read
  from a file or the environment, arguments built by `xargs` or `printf`, an
  encoding, `python3 -c`, or a list passed to Python's `subprocess`;
- a glob that expands against a file the agent wrote, such as `appro?e` or
  `--a?`;
- a glob in the name of a protected folder, which the guard can only test
  against sample paths;
- brace expansion in a glob, in Bash or in a Grep glob, such as
  `{d,x}eleg*/*` and `**/{DL-*,x}.yml`;
- patterns that only zsh reads, such as `.compass/(deleg\|x)ations/*` and
  `.compass/deleg*/DL-<->.yml`;
- a case-sensitive glob, such as `.compass/*/[A-Z]*`: the guard lower-cases
  the glob, so it passes;
- a Bash command that reads the folder without naming it, such as `grep -r x
  .compass` or `find .compass -type f -exec cat {} +`;
- a tool option that takes its own glob, such as `rg -g`, `find -name` and
  `--include`, and extended globs after `shopt -s extglob`;
- a Bash glob rooted in a folder other than the call's working folder, such
  as `$PWD/.compass/deleg*/*`;
- a Bash glob that spells neither .compass nor deleg, such as `cat .c*/d*/*`;
- a relative path after `cd`, such as `cd .compass && cat d*/*`, or `cd` into
  the memory folder and then a read of a file one folder up;
- a relative Bash path, such as `grep -r x ../..`;
- the root folder alone, such as `grep -r x /`, or a glob in the first
  folder of a path, such as `/U*/...`;
- a symbolic link inside the memory folder that a Grep over the folder
  follows;
- a command, function or alias that an earlier Bash call defined, and a git
  alias, git hook or git config that runs a command;
- a script written by one command and run by another, also when the Write
  tool wrote it;
- an approving review of a pull request sent in a way that names no review:
  a path or a field held in a variable or a file, a `gh` alias or extension,
  and another HTTP client such as `curl` with the person's token. GitHub
  records such a review under the person's account, and Compass cannot tell
  it from the person's own review.

What holds when a script reads protected state:

- A delegated approval from a script the hook never read has no call ticket
  of its own, so the CLI refuses it, apart from the three windows above.
- For the delegation files, the stored hash and the 64-bit code hold. The
  hash is stored and the code is not, so a script cannot read the code from
  the files.
- For the transcript, which shows the confirmation code in clear, only a
  person's typed command confirms a delegation, and the agent cannot type
  it. An agent that reads the code can still word a prompt suggestion that
  holds it, so the person's Enter is the only barrier.

### 6. Compass CI checks process integrity

- `compass ci` checks routing, issue schemas, evidence, approvals,
  traceability and follow-ups across Compass issues.
- Its failures are structured: every failure message names what failed, why
  it matters and what to do next.
- It does not run the project's tests, linting, security scanning, builds or
  deployment checks. Project CI and Compass CI are complementary lanes.

### 7. Issue state survives the conversation

Compass writes the assessment, approach, artifacts, evidence, decisions and
status beneath `.compass/`. Another person, session or compatible runtime can
resume by reading the files rather than reconstructing chat history.

**The current issue.** The hooks and the CLI judge work against the current
issue: `.compass/current-task`, or `COMPASS_ISSUE` when a session's
environment sets it.

- `COMPASS_ISSUE` comes first, so two sessions in one project can work on two
  issues. A value that names no issue is refused
  (`bad-session-issue-restart`), never passed over for the pointer.
- In a worktree the order reverses: the worktree's own pointer comes first
  (see "Worktrees" under "Shell-write detection is best-effort").

**Two sessions on one pointer.** The pre-tool hook records the issue each
Claude Code session last worked on, by its session id, in a `sessions.json`
file under `.compass/`.

- When another session has moved the pointer in the session's own project,
  the session's next code edit is refused (`pointer-moved`) until it runs
  `compass issue use <slug>`.
- A record older than 12 hours is ignored.
- A session with `COMPASS_ISSUE` set, or a runtime that gives no session id,
  is not tracked.
- A `.gitignore` in `.compass/` keeps the table out of every project's
  commits.

**Saving the manifest.** `compass` commands save an issue's `manifest.yml`
through `core.save_manifest`, which `manifest_store.py` implements. The merge
rules are in the [hook reference](hook-reference.md#a-manifest-save).

- A reader sees the old manifest or the new one, never an empty or partial
  file.
- Reading a manifest takes no lock, so the pre-tool hook never waits for a
  writer.
- When another save changed the file after this command's load, the save
  merges this command's changes into the file as it is now.
- When both changed the same value to different values, the save stops with
  an error that names the key, and writes nothing. Run the command again.
- A save merges only a manifest that `load_manifest` or
  `manifest_store.load_file` returned, or a copy of one. A save of a mapping
  built any other way, such as the new manifest `compass quick-fix start`
  writes, overwrites the file.

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

Teams must keep their normal CI controls.

**What a record names.** A record names the tree it tested by `tree_id` and
by the SHA-256 of each changed file and declared test file. The fields are
in the [hook reference](hook-reference.md#a-test-run-record).

**What `compass check` judges.** It judges the issue's newest record:

- in flight, once every gate has passed, it fails if the tree has changed
  since the record was made
- landed, it fails if the issue's changed files and declared tests in the
  commit that landed it are not the files that were tested

An older record is not judged. A record written outside a git repository, or
before records carried a tree id, is not judged either.

**`SHA256SUMS`.** The CLI writes `evidence/SHA256SUMS` in the issue folder.
Run `sha256sum -c .compass/work/<slug>/evidence/SHA256SUMS` from the project
root to check the files without Compass. It shows the files are the bytes the
CLI recorded, not their modes. It does not prove a trusted runner wrote them,
because anyone who can write the record can write this file.

**A file traced between two runs.**

- Tracing a file into the issue between two runs of the same command adds it
  to `changed_files`, so the second green is a new assertion and is not
  flagged as a rerun. Tracing an already-tracked file changes only
  `file_sha256`, not `tree_id`.
- An untracked file git ignores changes neither id and is not checked: an
  edit after the green is not reported. If it is forced in with `git add -f`
  after the green, `ship-commit` refuses until the green is run again.
- A traced symlink is not checked: a link pointed elsewhere after the green
  is not reported.

**`compass ship-commit`.**

- It judges the staged files right before each commit. A git hook can still
  stage a file during the commit itself. When the new commit then differs
  from what the green tested, the commit stands but the issue is not marked
  done, and `ship-commit` names the files and exits non-zero.
- In the committed record mode ([delivery-record.md][delivery-record]) the
  commit holds a record that says the issue landed. When a check after the
  commit fails, the working copy is put back to not landed and the output
  says the commit still holds the landed record. `git reset --soft HEAD^`
  removes an unpushed commit.
- `trail.md` is generated, but nothing stops a hand edit of its prose. A
  changed statement with unchanged sum lines passes `sha256sum -c`. `compass
  trail --check` reports the edit.
- A formatter or git hook that rewrites a record file during the commit
  makes a sum line fail at that commit. `ship-commit` names each such file
  and does not change its exit code.
- In a shallow clone that does not hold the land commit, `compass check`
  reports the landed comparison as not in this clone.

**Landing at HEAD with nothing staged.** `compass ship-commit --issue <slug>`
lands at HEAD only when the issue's own commits at the tip stay inside its
declared scope. It walks the first parent from HEAD, and the
[hook reference](hook-reference.md#compass-ship-commit) gives the rules of
the walk. When the base branch is not found, every merge is judged in full.

### `quick-fix finish` judges what to commit by when a file changed

`compass quick-fix start` records which files were already changed or
untracked, and which directories held no tracked file. It keeps that record
inside the git directory, where nothing is committed.

`compass quick-fix finish` takes as the change:

- each path the working tree holds that git has not committed, changed or
  untracked and not ignored;
- a committed path only when the manifest traces it already, from an earlier
  `finish` or from `compass changed-file add`, and it differs from the commit
  the issue started from. A commit that a pull, a rebase or another person
  adds after `start` does not enter the change;
- a tracked file under `.compass/` that is not issue state, such as the 8.x
  settings file `.compass/config.yml` (`compass.yml` since 8.0.0).

It leaves out or refuses:

- A path that was already changed or untracked at `start` is left out and
  named on a `left out :` line.
- The files a test run leaves, such as `.coverage`, are never part of the
  change.
- When the session committed the whole fix by hand, `finish` refuses and
  names `compass changed-file add`. When it committed only part of it,
  `finish` goes on and names each such file on an `untraced :` line.
- `finish` traces a change to the living spec like any other file.
  `ship-commit` refuses a staged project index, the `README.md` of the
  `docs/compass/` folder, as out of scope ([ADR-091]).

It does not guard three cases:

- a file created after `start` is taken as the change's, whoever made it;
- the start record is not checked for tampering: an edited record changes
  what `finish` refuses;
- an issue with no start record, such as one begun before `start` wrote
  one, commits a tracked file changed before the fix began. `finish` refuses
  an untracked file of such an issue until it is traced.

Three more cases follow from how `finish` decides:

- A path traced by hand with `compass changed-file add` is part of the change
  even if it changed before `start`.
- A test the scenario declares is committed even if it changed before
  `start`.
- An issue started before the record moved into the git directory kept a
  digest record beside its manifest, which is committed with the issue's
  records.

Read the `committed:` and `left out :` lines `finish` prints before you push.

### Compass enforces nothing in a project that has not opted in

- The hooks are installed at user scope and run in every repository on the
  machine. A repository with no `.compass/` directory has never opted into
  Compass, so `pre-tool.sh` and `post-tool.sh` pass through silently there:
  no refusal, no output.
- `compass init` creates `.compass/`, and the five entry-point commands run
  it, so a project opts in the moment someone runs a Compass command in it.
- One kind of write happens everywhere: the session-start hook keeps two
  launchers in the plugin's own data folder. It writes nothing in the
  repository and prints nothing.
- The boundary is the directory, not the state of the work. A project that
  has opted in and has not been assessed is still refused, and a project the
  hook cannot read is still refused.
- When `compass.yml` is Compass's file (it has a top-level `schema:` key) and
  `.compass/config.yml` still holds a setting such as `enforcement`, the hook
  refuses with `settings-conflict` and the CLI commands that read settings
  stop with the same text.
- A `compass.yml` with no `schema:` is not taken for Compass's file: the old
  file keeps guarding and a warning says so. A `compass.yml` that is the only
  settings file is read as it is.

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
| `hooks/pre-tool.sh` | Refuses each code edit, and each edit to a path that is neither built-in code nor exempt in a project that has a settings file (it cannot read `enforcement.code_globs`): `python-missing` when there is no `python3`, `reader-failed` when it does not run. | Its checks run, but the CLI cannot record the assessment and scenarios they look for, so a code edit in an issue without them is refused as usual. |
| `hooks/post-tool.sh` | No change: it does not use Python. | No change. |
| `hooks/stop.sh` | Says the end-of-session check did not run, and exits 0. | Runs its check as usual. |
| `compass` | Does not run. | Does not run. |

These rows were checked by running each hook with no `python3`, with one
that exits without running, and with Python 3.9.6. A repository that never
opted in sees none of this. [ADR-028] records why Compass ships as a
directory and not as a single file.

The parts of the hook:

- The hooks run each Python check from its own file in `hooks/py/`, never
  from text inside the script. `hooks/pre-tool.sh` sources the rest of its
  checks from parts in `hooks/lib/`.
- The hook checks every part before it runs any of them. A part that is
  missing from the install, or that cannot be read, refuses every call the
  hook sees, in any project, with `reader-failed` naming the part.
- A missing file for a check in `hooks/py/` refuses the same way the check
  does when its Python fails. A missing file for a step that only records or
  displays skips that step.

### The red marker is checked against its record, and a record can still be written by hand

- On an issue assessed before 9.0.0, the pre-tool hook refuses a code edit
  unless a failing test is on record for the issue. A 9.0.0 delivery issue
  needs no failing test before a code edit, because `compass quick-fix
  finish` proves the red itself ([ADR-099]).
- The hook reads the red record beside the marker - `evidence/red*.json` -
  and checks its `content_digest`; an empty marker unlocks nothing.

**What the digest does not protect against.** The digest is a plain `sha256`
over the record's own fields, with no secret, so anyone who can write the
file can compute a matching one. It is tamper evidence, not forgery
resistance: it catches a record edited after it was written, and it does not
catch a new record written by someone who knows the format.

A record with no identity - written before records carried one, or written
by hand - unlocks an edit only in one of two cases:

- the project declares no `records_signed_since` date in its state file
  (the one `compass init` writes in `.compass/`, or `.compass/config.yml` for
  a project created before that file existed)
- the record's own timestamp is earlier than that date

`compass init` writes the date as the day the project was set up, so a new
project refuses unstamped records from the start. A project set up earlier
keeps the older allowance until it adds the line. Two limits remain:

- The timestamp can be written by hand too.
- `.compass/` is not a guarded path, so the line can be deleted like any
  other project setting.

### A code edit needs a scenario on record, but the hook does not judge the scenario

Guardrail `G2` (acceptance defined before it is built) is enforced before the
code exists: the pre-tool hook refuses a code edit while the issue owes
scenarios and its manifest has none.

- On a path issue (one whose manifest records `evidence_required`,
  [ADR-092]) every issue owes scenarios, so the hook refuses the edit with
  `no-scenario`, which names `compass scenario add`. `compass quick-fix
  start` writes the first scenario, so an issue it opened has one.
- Where the scenarios owe a person's approval (guarantee 5), the hook refuses
  the edit with `code-before-approval` until a person has given it.
- On an issue assessed before 9.0.0 only `define: thorough` owes scenarios
  before code, and the refusal is `no-acceptance-criteria`. A hotfix and a
  spike are exempt by their modes. The red check that runs after it still
  applies.
- A spike is never a path issue, and its `.spike` marker suspends the check.

The hook counts the manifest's `scenarios:` entries and reads nothing else.

- It does not check that a scenario has an intent or a test, or that it
  describes the change; `compass check` judges those (`G2` and `G3`).
- This check does not refuse an edit when the manifest cannot be read.

### A dependency between issues is read from this checkout, and a fault never blocks

An issue can record the issues it waits for in its manifest's `depends_on`
(`compass issue depends add`). While the issue is at the implement stage, and
neither on hold nor done, the pre-tool hook refuses a production-code edit
with `waits-for-issue` when a dependency has not reached its `until`
([ADR-062], [issue-dependencies.md][issue-dependencies]).

- `.acceptance` does not clear the refusal. A spike is never refused for it.
- The hook reads each dependency's manifest from this checkout's
  `.compass/work/` and runs no git command. A dependency finished only in
  another worktree still refuses here.
- To clear the refusal, bring that issue's folder into this checkout, or run
  `compass issue depends remove <slug>`. No override flag exists.
- The hook refuses only on a positive read of an unmet dependency. A
  dependency on an issue with no manifest here, a manifest that does not
  parse, an unknown `until`, an entry of the wrong shape and a dependency
  that waits for this issue in turn each allow the edit with one warning line
  on standard error. `compass issue lint` reports the same fault and fails.
- A reader that cannot run at all, such as a broken install, still refuses.
- The hook reads one level. A hand-written cycle of three or more issues,
  each at implement, refuses all of them until one dependency is removed.
  `compass issue depends add` refuses to write a cycle, and lint reports one.

### The pre-tool hook refuses on a removed working directory, and three exits still let a call through

Claude Code blocks a tool call only when the pre-tool hook exits with 2. Any
other exit code is a non-blocking error, and the call runs. The hook therefore
turns each fault it can reach into exit 2 with a stated reason.

When the session's working directory has been removed, for example by a
clean-up step such as `cd d && rm -rf ../d`, the hook follows three rules:

1. It falls back to `CLAUDE_PROJECT_DIR` and gives the same verdict as it
   does from a directory that exists.
2. When `CLAUDE_PROJECT_DIR` is not set and an Edit or Write names a file
   inside a Compass project by its absolute path, it refuses with
   `working-directory-gone`. This covers any file, a document as well as
   code.
3. It allows the call when no project can be found: a shell command, a
   relative path with no known base, or a repository that has not opted in.

A Read or Grep is never refused for a removed directory. A shell write in a
removed directory with `CLAUDE_PROJECT_DIR` unset is not seen, because it
names no file path.

Three exits still let a call through, because the hook cannot turn them into
exit 2:

- The hook's own folder is gone. The shell cannot open the script and exits
  127.
- A helper script the hook calls is unreadable, or fails when it runs.
- A time-out of the hook. On Claude Code 2.1.295 or later the time-out is
  covered by the declared limit: `hooks/hooks.json` sets `"timeout": 15` and
  `"onFailure": "block"`, so a time-out blocks the call. On older versions a
  time-out lets the call run.

The hook has no catch-all exit rule, such as a trap that maps every exit other
than 0 and 2 to 2. On bash 3.2.57 an `EXIT` trap like that ends a direct
unbound-variable exit with status 0, so the call runs.

### An Edit that changes only comments of Python or YAML needs no failing test

On an issue assessed before 9.0.0, the pre-tool hook refuses an Edit of
production code unless a failing test is on record. An Edit of a `.py`, `.yml`
or `.yaml` file that changes only comments, docstrings or layout runs with no
failing test and no assessed issue. The hook proves this from the file on
disk and never from the text of the Edit
(`cli/compass_pkg/comment_only_edit.py`). The exact rules, the pragma list
and the cost of the check are in the
[hook reference](hook-reference.md#the-comment-only-check). The reasons are
in the decision record
[a comment-only edit of code needs no failing test][comment-decision].

What is not covered:

- Shell and every other language are not covered: each such Edit is judged
  as before.
- `NotebookEdit` and `MultiEdit` are not wired to the hook.
- A Write is never judged this way: a Write that replaces a file is judged
  as a code change.
- A comment that carries a pragma is code, such as `# type: ignore`,
  `# noqa`, `# nosec`, `# fmt: off`, a shebang line or an encoding line. So
  is an Edit that adds a hidden character. A prose comment that mentions a
  pragma word needs a failing test too.

**The check fails closed.** When the hook cannot prove that the Edit is
comment-only, the Edit is judged as before the check existed. That covers a
file over 1048576 bytes, a file that does not parse, a duplicate key in YAML,
an encoding other than UTF-8 or ASCII, a template file and a check that runs
out of time. A missing `python3` still refuses with `python-missing`.

**Stated limits.** Each lets an Edit through that a stricter check would
refuse:

- The hook reads the file once and cannot lock it, so a change to the file
  between the read and the Edit is not detected.
- The docstring rule is a word list. A docstring that a framework reads as
  grammar or help is not detected: a PLY grammar rule, the help text of click
  or typer, and a FastAPI description.
- The directive rule is a deny list of words. A scanner or formatter
  directive that is not on the list passes as a comment. So does an Edit that
  removes `#cloud-config` or `#include` from the first line of a YAML file.
- A YAML comment in a Helm template passes the YAML check, because the parser
  sees a comment. This matters only where `enforcement.code_globs` guards a
  template.
- A symbolic link under `evals/*/seed/` that points at production code is
  exempt, because a symbolic link is not followed. The same holds for
  `tests/` and `.compass/`.
- The hook uses awk. The hook was written and tested on the awk of macOS
  only. The continuous-integration runners use Linux awk, and this contract
  does not claim that the two give the same results.

**Known costs.**

- A large file keeps the old verdict: the check reads a Python file up to
  about 780 KiB and a YAML file up to about 230 KiB.
- A slower machine refuses a file that is close to the limit. The refusal is
  safe: the Edit keeps the old verdict.

**Two more rules apply with this one.**

- `evals/*/seed/` at the project root needs no failing test, because it holds
  input that an evaluation harness copies and never runs in place. Compass
  ships no harness ([ADR-093]). `examples/`, `cli/vendor/`,
  `.github/scripts/`, `evals/` outside `seed/`, `src/examples/` and
  `db/seed/` stay guarded. The setting `enforcement.code_globs` only ratchets
  up.
- A shell script, makefile or extensionless script is not a built-in
  production-code file type. A file that `enforcement.code_globs` declares is
  guarded.

### Shell-write detection is best-effort

The Claude Code pre-tool hook completely covers supported file-editing tools.
Where this section says a write needs a failing test on record, that is the
rule for an issue assessed before 9.0.0. A 9.0.0 delivery issue needs a
scenario and, where owed, the scenario approval ([ADR-099]).

For shell commands the hook recognizes a fixed list of write shapes, and only
those. The [hook reference](hook-reference.md#shell-write-detection) gives
each shape in full:

- `>`, `>>` and `>|` redirects, including a heredoc
- `sed -i`, and `perl` and `ruby` with `-i` in any flag group
- the arguments of `tee`, and the last argument of `cp` and `mv`
- `patch -p<n>` and `git apply` - writers with unknowable targets
- an inline interpreter script (`python3 -c`, `node -e`, a heredoc) whose
  write call, such as `open`, `os.replace` or `shutil.move`, names its target
  as a string, or as a name the same script assigns a string to

Anything else runs unchecked. Unknown commands are allowed rather than
blocking ordinary development indiscriminately. These are not detected:

- a write through a script file, a build step or an interpreter reached via a
  wrapper
- a write call in another form, such as `open(p, mode='w')` or
  `Path(p).open('w')`, or a call split over lines
- a path built at run time: joined from parts, returned by a function or read
  from the environment
- a destination that is itself a substitution, or ends in one:
  `cp a.ts $(echo src/app.ts)` and `cp a.ts src/app.ts$(true)`
- a destination given by an option: `cp -t src /tmp/a.ts`
- a `cp` or `mv` that another command runs:
  `find . -name a.ts -exec cp {} src/app.ts \;`
- a command inside a string that a nested shell runs:
  `sudo sh -c 'cp a.ts src/app.ts'`
- a quoted `;`, `&`, `|` or `(` before the destination: `cp "a;b" src/app.ts`
- a `case` pattern inside a substitution:
  `cp "$(case x in x) echo y;; esac)" src/app.ts`
- a write through a symbolic link: a symbolic link is not followed
- a command written to mislead the hook: it reads the command's text and
  does not run it

A path is judged where it points, not how it is spelled. A path with a part
the hook cannot know, such as a variable it cannot resolve, is judged as a
path inside the project.

**The limits that bound the hook's time.** Where Compass is in use, the hook
refuses a Bash command it cannot scan in time (`bash-command-too-long`,
`bash-command-too-complex`). In a repository that has not opted in, it skips
only the write scan, and the approval and transcript guards still read the
whole command. The limits, their values and the timed command shapes are in
the [hook reference](hook-reference.md#hook-time-limits).

- The hook never scans a part of a command. A command over 98304 bytes is
  refused.
- The work budget reads no clock, so it cannot see a machine slower than the
  one that was timed. An 8 second fuse covers that case.
- The fuse does not interrupt a process that is running or one write target.
- The hook declares a time limit of 15 seconds, and Claude Code blocks the
  call when the hook runs past it. This holds from Claude Code 2.1.295.
- The size limits work on every version of Claude Code. On an older version
  the length limit still refuses long commands, but a command that runs past
  the time limit can let the call run. Not every timeout fails closed.
- Not measured: only one version of Claude Code was available, so the
  behavior of older versions is from its documentation.
- A machine without `jq` has no time bound: a command of 20 KB took 33.9
  seconds. On Claude Code 2.1.295 or later the 15-second timeout is the only
  control there.
- `scripts/install.sh` does not set the timeout keys, so a source install
  keeps the default timeout of 600 seconds.

**Worktrees.** Inside a worktree, Edit and Write follow the worktree's own
issue and failing test. The full rules for a Bash call are in the
[hook reference](hook-reference.md#worktrees).

- The worktree's pointer names the issue. COMPASS_ISSUE applies in the
  session's own project, and in a worktree only when the worktree's pointer
  is empty.
- A pointer that names a missing issue, or no issue to name at all, refuses
  (`bad-session-issue`); the hook never guesses the most recently changed
  issue there.
- An edit in a worktree of a different repository is refused, and so is one
  in a tree git cannot read.
- `pointer-moved` applies in the session's own project only.
- A Bash call whose working folder is in a worktree of the session's
  repository is judged by that worktree's issue. The hook reads the working
  folder from the `cwd` field of the call. A subagent started with worktree
  isolation keeps the parent session's `CLAUDE_PROJECT_DIR`, and this is how
  its shell writes reach its own worktree's issue.
- A path that lands outside the worktree, a path with a part the hook cannot
  know, and every target of a command that can change its folder are judged
  against the session's project and issue.
- Otherwise a shell write still resolves from the session's project: when
  the call has no usable `cwd`, when no `.compass/` folder is found above it,
  and when the tree is not tied to the session's repository.

Three limits remain:

- a symbolic link is not followed: a link made inside the worktree that
  points into the main checkout makes a write through it look like a write
  in the worktree
- a `cd` inside the command is not followed: a relative write after
  `cd <worktree>` from the main checkout, or after `cd <scratch folder>`
  from a worktree, is judged by the session's issue
- an absolute path into a worktree is judged by the project of the call's
  working folder; from the main checkout, a path into a worktree outside the
  project - the default place for worktrees - is not checked at all

See [Security](security.md) for the exact trust boundaries and hardening
guidance.

### Compass governs its own workflow, not every agent action

Compass cannot prevent a person, automation or agent from changing the
repository outside its adapter and commands. Repository permissions, branch
protection, review policy and CI remain essential.

**A ship approval read from GitHub is a copy, read once.**

- `compass issue link set --pr <n>` copies each counting review approval of
  the merged pull request into a `pr-approval` record: the reviewer, the
  review id and URL, and the commits ([github-links.md](github-links.md)).
- It counts a review only when GitHub names a `User` account other than the
  pull request's author.
- An agent cannot add the record with `compass evidence add`, and the
  pre-tool hook refuses an agent's approving review.
- The same limits hold as for a delegation ([ADR-069]): a process that runs
  as the same operating system user can edit `manifest.yml`, or put another
  program named `gh` on `PATH` before Compass runs it.
- `compass check` does not read GitHub again, so a review dismissed after the
  read still counts. A reader checks a record against GitHub by its review
  id, with `gh api repos/<repo>/pulls/<n>/reviews/<review_id>`.

### A check's compatibility within a major version is shown on its corpus only

- Each built-in check implementation carries a version, and a fixture corpus
  of cases with known verdicts. A build rule fails when a corpus verdict
  changes and the major version does not.
- Across majors, Compass is designed to refuse rather than reinterpret.
- Within a major, compatibility is shown on the corpus cases and nowhere
  else. A change of behavior that no case exercises is not detected, and the
  corpus is small (two cases for each check at first).

**A waiver of one check on one issue is approved like any other subject.**

- From 9.0.0 a waiver in an issue's manifest (`compass waiver add`) excuses
  its one check on that issue only once a `human-approval` record names it,
  given at the issue's current generation.
- The record comes from a typed `/compass:approve`, a terminal, or an agent
  under a delegation the person typed with `--for waivers` and confirmed with
  its code. No default delegation covers a waiver.
- The check `human-approval-present` and the checks of guardrail `G5` are
  never waived.
- The same limits hold as for any approval: an approval is a name and a date
  in a record, and it is not authenticated. Compass checks the approver's
  name against `approvers.waiver`, or the owner, and anyone who can write
  `manifest.yml` can write a record. See [waivers.md](waivers.md).

**No project departs from the check set, so there is no conformance line.**
9.0.0 has no locks and no unlocks ([ADR-094]): a setting can only add to the
check set, so `compass check` and `compass approach show` print no
conformance line. A waiver is shown on its check's row.

### What the record of a 9.0.0 issue does not claim

**The order of the work.** A red that `compass quick-fix finish` proved shows
that the tests fail on the base commit and pass with the change. It does not
show that a test was written before the code. A red recorded earlier with
`compass tdd-red` still counts, and is the only proof of that order.

**A review, by default.** A 9.0.0 delivery issue owes no review gate but the
three every issue has. The regression, security, clarity and architecture
reviews, the Definition of Done, the reproduction of a live defect before
anything else, and the records of the four-layer acceptance strategy (`S17`)
are owed only where a project adds their tokens with `require_evidence`
([configuration.md](configuration.md)).

**A trace by scenario.** `finish` traces every changed file to every scenario
of the issue. A trace of one file to one scenario exists only where the
session recorded it with `compass changed-file add`.

**A true red, where the base copy has a limit.** A test that needs untracked
build output fails on the base copy for that reason, and `finish` records
the failure as the red ([base-copy.md][base-copy]).

### Compass is adaptable, not universal

The shipped policies are a starting point. Teams can add strategies and
project guardrails, provided they preserve this contract.

## Mechanical enforcement

| Guarantee | Primary mechanism |
|---|---|
| 1 (deterministic routing) | `compass approach evaluate` over assessment and policy |
| 2 (implemented guardrails) | `compass policy lint` and `compass check` |
| 3 (typed evidence) | Gate type declarations plus the issue evidence registry; `compass quick-fix finish` writes the records |
| 4 (spike containment) | Routing conflict checks and spike invariants |
| 5 (human approval) | Structured `human-approval` evidence given for guardrail `G5`, checked before ship; the `specify` approval before code; the digest of the change on each approval |
| 6 (process-integrity CI) | `compass ci` |
| 7 (resumable state) | the manifest (`templates/manifest.yml`), its artifacts and evidence under `.compass/` |

## What adopters still own

- Make an honest assessment and review the computed approach.
- Review generated specifications, designs and evidence.
- Run normal engineering and operational controls.
- Protect the repository and CI environment.
- Keep secrets out of committed Compass artifacts.
- Reassess when the work changes shape.

[ADR-028]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-028-cli-ships-as-a-directory.md
[ADR-062]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-062-a-dependency-is-a-manifest-field-and-the-block-is-derived.md
[ADR-068]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-068-a-person-approves-inside-claude-code-through-an-event-the-model-cannot-raise.md
[ADR-069]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-069-a-person-can-delegate-approvals-to-a-named-agent-for-a-stated-time-and-scope.md
[ADR-077]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-077-delegations-cover-the-typing-session-until-revoked.md
[ADR-091]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-091-compass-needs-only-the-acceptance-criteria.md
[ADR-092]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-092-compass-runs-one-path-of-four-stages.md
[ADR-093]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-093-compass-keeps-only-what-a-reviewer-of-one-change-needs.md
[ADR-094]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-094-compass-runs-one-fixed-check-set.md
[ADR-095]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-095-compass-reads-the-ship-approval-from-the-merged-pull-request.md
[ADR-099]: https://github.com/ayeo-io/compass/blob/main/architecture/decisions/ADR-099-compass-keeps-the-record-itself-and-a-change-takes-two-commands.md
[guard-decision]: https://github.com/ayeo-io/compass/blob/main/governance/decisions/2026-10-19-the-approval-guard-judges-words-not-text.md
[comment-decision]: https://github.com/ayeo-io/compass/blob/main/governance/decisions/2026-10-19-a-comment-only-edit-of-code-needs-no-failing-test.md
[delivery-record]: https://github.com/ayeo-io/compass/blob/main/docs/delivery-record.md
[issue-dependencies]: https://github.com/ayeo-io/compass/blob/main/docs/issue-dependencies.md
[base-copy]: https://github.com/ayeo-io/compass/blob/main/docs/base-copy.md
