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

Risk, familiarity and size need judgment, as do the goal and urgency switches. Once those values
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

Human approvals are needed for an issue labeled:

- `auth` - auth and access-control changes;
- `payments` - payments or movement of money;
- `personal-data` - personal data and privacy; or
- `migrations` - migrations, which can lose data that cannot be restored.

The evidence records the approver, role, decision, time, scope and conditions.

From 7.0.0, critical risk on its own does not need an approval. Critical-risk
code that carries none of the four labels can be reverted at merge, and CI,
review and the other guardrails still gate it. Assess names the four labels
when risk is critical and none is set. A project that wants an approval for
every critical-risk change adds critical risk back to the trigger in its
`compass.yml` (`docs/upgrade-7-0-0.md`); the lock allows a stricter trigger.
An issue assessed before 7.0.0 keeps the trigger stored with it.

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

A person can also delegate approvals with `/compass:delegate [--agent <name>]
[--until <time>] [--on <issues>] [--for <forms>] [--max <n>]` (ADR-069,
amended by ADR-077). The person sets the bounds, and Compass puts no upper
limit on how long a delegation lasts or on how many are in force:

- With no `--until`, a delegation lasts until `/compass:revoke`. Compass lists
  each delegation with no end time when a session starts, after `/clear` and
  after the conversation is compacted, with its age, who it covers and how
  many approvals it has given. A session resumed with `--resume` or
  `--continue` keeps its session id, so a delegation typed in it still covers
  it, but Compass shows no list for a resumed session.
- With no `--agent`, a delegation covers the session it was typed in: its main
  agent and its subagents, including built-in ones such as general-purpose, in
  any worktree. With `--agent <name>`, it covers that agent in any session.
  `any` is refused.
- With no `--on`, a delegation covers every issue in the repository's
  worktrees, at any generation. With `--on <issues>`, it covers those issues, each
  at the generation it had when the delegation was made.
- Every worktree reads one common store: `.compass/delegations/` in the main
  checkout. A delegation file in a linked worktree's own folder gives no
  approval.
- The guardrail 5 sign-off is covered only with `--for g5`, and only after the
  person types back a code the hook showed them. After that code, the
  delegation can have no end time and cover every issue, so one typed-back code
  can cover several irreversible changes. `--labels` is not a flag.
- The agent runs `compass evidence approve --issue <slug> --delegated --as
  <agent>` as a plain command in its Bash tool, with `compass` in command
  position, not as an argument of `echo` or another command. The pre-tool
  hook reads the command and writes a call ticket into the store: the session
  and the caller that Claude Code reported, and a digest of the command's
  words. The CLI takes the matching ticket and tests the session from it. It
  never reads the session from the environment. A call the hook never read,
  such as one inside a script, has no ticket of its own, so the CLI refuses
  it.
- The hook writes the ticket before the call runs, so Compass deletes it as
  soon as it cannot be used for that call: when the call finishes or fails,
  when Claude Code reports the call's permission denied, when the turn ends,
  and when the person submits the next prompt. A ticket that is never taken
  also expires after 10 minutes. Three windows stay open. When the person
  denies a permission prompt, Claude Code runs no hook until the next prompt,
  so a process the agent had already started in the background can take the
  ticket before then. When auto mode's check denies a call and Claude Code
  sends no hook for it, the agent can take the ticket from a script in the
  same turn. When the shell skips a `compass` command in command position,
  as after `true ||` or `false &&` or on a heredoc line, a program that the
  same call starts can take its ticket before the call ends. In each case the
  ticket names only the session and the agent that made the call.
- Two limits come from running as the person's operating system user. A
  process running as that user can write a ticket into the store. A process
  that can start Claude Code as that user can resume a session by its id, as
  `claude --resume <session id>` does, and its hooks then report that
  session, so it can use a delegation typed in that session without
  `--agent`. Session ids appear in the issue's records. Neither limit is
  closed: a process that can do either can already act as the person.

The record names the person, the agent and the delegation. The person sees a
summary of delegated approvals, from any worktree, until they mark them
reviewed. `/compass:approve` with nothing pending marks reviewed only the
approvals that the session's last summary showed. `/compass:reject <record id>`
overrules one; for the sign-off it writes an `approval-withdrawal` record, which
never reverses an action already taken and never fails a landed issue.

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
  delegation needs the typed-back code. The code is 64 bits, 16 hex
  characters in groups of four, so its salted hash cannot be searched within
  the 10-minute window. That protects the stored hash only. The transcript
  shows the code in clear, so for the transcript the person's Enter is the
  barrier (see the limit on a script written by one command and run by
  another).
- Each typed command is recorded once. The hook refuses `/compass:approve`,
  `/compass:reject` and `/compass:delegate` when the input has no
  `prompt_id`, and refuses a `prompt_id` that a record, a closed request or a
  delegation already holds. `/compass:revoke` needs no `prompt_id`: it only
  ends delegations.
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
(`cli/compass_pkg/approval_guard.py`). Each path check ignores letter case,
because macOS opens a path in any case.

**What the guard is.** The guard is defense in depth against an accidental or
injected read of the session transcript or of an approval request. It is not a
hard boundary. A Write tool call that writes a script, followed by a Bash call
that runs it, was open before this guard changed, because the earlier hook
allowed both calls. The stored hash, the 64-bit code and the person's typed
approval are unchanged, and they are what keep a delegation from being
confirmed without a person.

**How the guard reads a Bash command.** The guard reads a simple command as
words (`cli/compass_pkg/approval_words.py`) and judges any other command by
its whole text. A command is simple when all of these hold:

- it is one command, or plain commands joined by `&&`, `;` or a new line;
- each command starts with `git`, `gh`, `ls`, `wc`, `stat` or `cat`, with no
  path, no `VAR=` word before it and no function or alias definition;
- it holds no pipe, `&`, `||`, parenthesis, backtick, comment, heredoc,
  here-string, process substitution, `eval`, `$'...'` or `$"..."`, and no
  unquoted brace, glob, tilde, `^` or `#` character (`{ } * ? [ ~ ^ #`),
  because the shell expands such a word before the command runs and the guard
  judges the word as typed. It holds no zsh number range such as `<1-3>`, no
  `>!`, no descriptor of two digits, no descriptor move (`>&2-`) and no quoted
  or escaped digit before a redirect. A command that is only a redirect is not
  simple, because zsh runs `cat` for it. A copy of a descriptor (`2>&1`,
  `>&2`) ends at a blank, a new line, `;` or `&`; any other white space
  character is part of a file name in the shell, so a copy followed by one is
  not simple;
- it holds no `$` outside message text, and no `$(`, `${` or backtick inside
  message text. A message value must be one quoted word, never joined to its
  option, and never start with `@`.

The gate fails closed: a shape it does not name is not simple. A `git commit`,
`tag`, `merge` or `revert` may hold only the options without a value that
`GIT_FLAGS` and `GIT_LETTERS` list in `approval_words.py` (such as `-a`,
`--amend`, `--no-edit` and `--allow-empty`) and a message option, because any
other option may take the next word as its value (`--author -m <path>`) or
read a file or a commit (`-F`, `-c`, `-C`, `-t`, `--template`). A `gh issue`,
`pr` or `release` `create`, `edit` or `comment` (and `pr review` and `pr
merge`) may hold only a message option. A global option before the verb (`git
-C dir`, `git -c`, `gh -R`) makes the command not simple.

**What the guard judges in a simple command.** It judges each command name,
each redirect target and each argument by its text, with quotes removed as the
shell removes them. It does not judge message text, so a commit message that
mentions a protected folder is allowed. Message text is a fixed list, one row
for each, and a widening is a visible change that needs a test row:

- the quoted value of `-m`, `-am` and `--message` of `git commit`, `tag`,
  `merge` and `revert`. A command with `-F`, `--file`, `-c` or `--exec` is
  not simple;
- the quoted value of `--title`, `--body`, `--notes`, `-t` and `-b` of `gh
  issue`, `gh pr` and `gh release`, only for the subcommands above.
  `--body-file` makes the command not simple. `gh api`, `gh alias`, `gh
  extension` and `gh pr checkout` have no message text, and the guard judges
  every word of them.

**What the guard judges by the whole text.** Every command that is not simple
is judged as it was before this change: any text that names a protected thing
is refused, and text that names none is allowed. That covers a pipe, a
heredoc, an `echo` or `printf` that names a request, a search pattern, a
message built with `$(...)`, a script written and run in one call, and a
command that the gate does not list. For example `git commit -m "$(cat
<<'EOF' ... EOF)"` is refused when its text names a protected thing and
allowed when it names none. A broader reading of text moved to a later
release (ayeo-io/compass-delivery-record#247).

**The exemptions.** An exemption removes one thing from one word. It holds
only when the command stands alone, has no redirect to a file (a copy of a
descriptor such as `2>&1` names no file), has one operand, and carries only the
plain options `ls -lah1` and `wc -lcwm` allow (`stat` and `cat` carry none; `--`
and any other option void the exemption). It does not hold for a path with a
`..` segment, so `ls <request folder>/../../../delegations` is refused. The
exemptions are:

- `ls`, `wc` and `stat` may name a request path as a bare path argument, with
  no glob, brace or tilde. The path can be a request folder or a request file,
  so `wc -l <request>` and `stat <request>` pass: they show a count or the
  file's metadata, not its content. `ls .compass/delegations` is refused: the
  delegation folder has no exemption;
- `cat` may name `hooks/prompt-approval.sh` as a bare path argument. Every
  other command that names the script is refused, including `chmod`, `git add`,
  `cp`, a runner and a listing, and a `cat` in a pipe or beside another
  command;
- a `VAR=` word, an option such as `--output=<path>`, and the word after `-f`,
  `--file`, `--files0-from`, `--output`, `--pre` or `--exec` are never bare
  arguments.

**The auto-memory folder.** Read, Grep, Edit and Write may name a file inside
`<configuration folder>/projects/<one folder>/memory/`, in any `.claude*`
configuration folder. The guard joins the path to the call's `cwd`, collapses
`..`, folds letter case and resolves each symbolic link, and the result must
still be inside that folder. Edit and Write need a file inside the folder; Read
and Grep may name the folder itself. A path with a glob or brace character, a
Grep glob with a `..` segment or a brace expansion that holds `..` (such as
`{..,x}/*.jsonl`), a path that leaves the folder and a symbolic link that
points out of it are refused. A Bash command that names the folder
stays refused, because the guard cannot follow `cd` out of it.

The guard refuses these calls:

- Edit or Write on an issue's `approval-requests/` files, and a Bash word that
  names that folder or `hooks/prompt-approval.sh`
  (`approval-request-protected`);
- Edit, Write, Read or Grep under `.compass/delegations/`, a Grep whose glob
  names `delegations`, and a Bash word that names that folder
  (`delegation-protected`). A Grep over the whole project still reaches the
  folder; the stored hash and the 64-bit code are what keep the confirmation
  code of a delegation out of reach. For both folders, a Bash command is
  read with each backslash and newline removed where the shell removes
  them, outside quotes and inside double quotes, so a name split across two
  lines, such as `.compass/deleg\<newline>ations`, counts as the whole name.
  In a simple command, the shell keeps the two characters inside single
  quotes, and so does the guard. A command that is not simple, such as one
  with a comment, a heredoc or a command substitution, is also read with
  every backslash and newline removed, because an apostrophe there may not
  be a quote to the shell; a split name inside single quotes is refused
  there too;
- a Grep glob, or a Bash word with `*`, `?` or `[`, that can match the
  delegation folder or a file in it, such as `d*/*`, `deleg*/*`,
  `deleg?tions`, `**/confirm-*` or `cat .compass/deleg*/*`
  (`delegation-protected`). The hook tests the glob with `fnmatch` against
  the folder `.compass/delegations` and two sample files in it, one named
  like a delegation record and `confirm-s.yml`, and against an ordinary path of the same shape: a
  folder `zz` and a file `file.yml` in it, both under `.compass`. It refuses
  the glob when it matches a delegation path and not the ordinary one. This is a
  heuristic: it can refuse a rare glob such as `**/*-*.yml`, and it passes a
  glob that picks a delegation file together with other files, such as
  `**/*l*.yml`. A Grep glob counts only when the search path is the
  delegation folder or a folder above it, so `src` and `.compass/work` pass.
  A Bash word is read after the shell's quotes are removed, in any letter
  case, and also inside `bash -c`, `sh -c` and `eval`. A backslash and
  newline inside a word are removed first, as the shell removes them. The
  glob is read as the shell reads it: `[^y]` counts as `[!y]`, and a POSIX
  class such as `[[:lower:]]` counts as one character. A quoted regular
  expression is read as a glob too, so `'.*delegat*'` is refused, while
  `'.*delegat.*'` is accepted because it picks an ordinary path as well. A
  Grep glob is also split on commas, so `*.yml,deleg*/*` is refused. Known
  cost: the rule also refuses `**/*-*.yml`, `**/D*`, `d*` and `**/*s.yml` as
  Grep globs;
- these globs are accepted, because they match an ordinary path as well: `*`,
  `**/*`, `**/*.md`, `*.yml`, `**/*.yml`, `src/**/*.py` and `.compass/*` in a
  Grep, and `ls .compass/*`, `ls .compass/work/*`, `cat
  .compass/work/*/manifest.yml`, `ls .compass/**`, `ls src/*.py` and `cat
  docs/*.md` in Bash;
- a delegated approval whose `--as` is not exactly the agent Claude Code
  reports (`delegation-caller-mismatch`). A Bash command counts as one when
  a word is `approve` and a word is `--delegated`, a prefix of it of five
  characters or more, or `--delegated=...`; the earlier rule, `evidence
  approve` beside any word that starts `--del`, also counts. The words of
  `bash -c`, `sh -c`, `eval` or a quoted command piped into a shell are read
  too. Every `--as` must name the caller, since the CLI keeps the last one.
  The hook also refuses any word that holds `--as` and is neither exactly
  `--as` nor `--as=...`, such as `--as${IFS}compass:architect`, `--as$IFS`,
  `--as$X`, `x--as`, `--asmain`, `--as-main` and `--assume-yes`, because the shell can
  turn it into a second `--as` that the hook cannot read. Quotes are removed
  first, so `"--as"` and `--a''s` count as `--as`. A word with white space is
  read again as its parts, so a quoted value is read word by word and a word
  that holds `--as` inside it, such as `--reason 'fix--assets'` or
  `--reason 'fix --assets'`, is refused too. That is the cost of refusing
  any word that holds `--as`; the refusal names the word, so a person can
  rephrase it. A backslash and newline inside a word are removed first, so
  `--a\<newline>s` counts as `--as`. The hook also refuses a word without
  white space that holds a brace expansion (a `{` with a `,` or `..` before
  the closing `}`), such as `--a{s=main,s=compass:architect}`, because the
  shell expands it into two `--as=` words. A quoted value with a space, such
  as `--reason '{"a": 1}'`, or with no comma or `..`, passes; a compact JSON
  value with a comma and no space, such as `'{"a":1,"b":2}'`, is refused
  as a known cost, in any `compass evidence` command (`--note`, `--reason`
  and the rest), and the refusal says the word may be built by the shell. A
  command with the word `compass` (or an escape-spelled `compass` in command
  position) and a word of ANSI-C quoting with an escape, such as
  `compass $'\x65vidence' $'appro\x76e'`, is refused even when `evidence`
  is spelled with escapes too. A command that names `evidence` (a word `evidence`, or a
  quoted word that holds `compass evidence`, or a `--delegated` flag) and
  holds ANSI-C quoting with an escape, such as `$'--a\x73'` or
  `$'appro\x76e'`, or a brace expansion in any word, such as
  `--{delegated,x}` or `appr{ove,x}`, is refused with the word named,
  whether or not `--delegated` shows, because the hook does not decode
  either spelling. A command that is not a
  delegated approval, such as `git update-index --assume-unchanged`, is not
  checked. The call is the main agent only when the hook input has neither
  `agent_type` nor `agent_id`, and the CLI takes no abbreviated flag, so
  `--deleg` cannot pass unseen. The message of a simple `git commit` or `gh pr`
  that names `--delegated` or `evidence approve` is text and is not judged. A
  real `compass evidence approve --delegated` is not a simple command, and any
  command that names it, in a message or not, is judged by its whole text and
  needs a matching `--as`;
- Read or Grep on the session transcript's folder, inside it or on any
  folder above it, such as the configuration folder or the home folder
  (`transcript-protected`). A relative path is read from the call's `cwd`,
  and a Grep with no path searches its `cwd`. A Bash word is refused when
  it names the transcript, a `.claude*/projects` folder, a configuration
  folder directly under the home folder (such as `~/.claude-ayeo`), or a
  folder above the transcript, such as `~`, `~<name>` or `$HOME`, once the
  shell's quotes are removed. A word with a glob or a brace counts by the
  folder before it, so a `cat` of a glob under `~/.claude-ayeo` is refused.
  A command on a folder above the transcript, such as `ls ~`, `cd ~` and
  `grep -r x ~`, is refused. A
  project's own `.claude` folder is not refused. Claude Code writes a hook's
  block message to the transcript (measured on 2.1.301), and the block
  message is where the person sees the code that confirms a g5 delegation.
  The hook reads a Grep's path with or without `jq`.

The Bash checks match words, so they stop the agent's ordinary use and not a
deliberate workaround. These limits remain. Most of them let a call reach the
transcript or run a delegated approval as another agent, and one (the memory
folder link) states where the guard is exact:

- words built at run time: a variable, the output of a command substitution
  that a shell does not run in the same call, and arguments built by `xargs`
  or `printf`. The guard sees the word as written, not as the shell builds it;
- a glob in the name of a protected folder, which the guard can only test
  against sample paths (the rules above), and a glob that expands against a
  file the agent wrote;
- a command, function or alias that an earlier Bash call defined, which a
  later simple `git commit` or `gh pr` then runs in place of the real command,
  and a git alias, git hook or git config that runs a command;
- a script written by one command and run by another. One call writes, another
  call runs: not detected, and a script written with the Write tool and run by
  a later Bash call is the same. This is an accepted limit, because the
  earlier hook allowed a Write tool call followed by a shell command that runs
  the file. A command that is not simple and names a protected thing in the
  same call is refused. A delegated approval is the exception: a script the
  hook never read has no call ticket of its own, so the CLI refuses it, apart
  from the three windows the delegation section above names. What holds
  depends on what the script reads:
  - for the delegation files, the stored hash and the 64-bit code. The hash is
    stored and the code is not, so a script cannot read the code from the
    files;
  - for the transcript, which shows the confirmation code in clear, only a
    person's typed command confirms a delegation. The prompt hook
    (`hooks/prompt-approval.sh`) runs only on the host's `UserPromptExpansion`
    event, it acts only on a command whose `command_source` is `plugin`, and a
    delegation is confirmed only from that event. The agent cannot type the
    command. An agent
    that reads the code in the transcript can still word a prompt suggestion
    that holds it, so the person's Enter is the only barrier, and the code adds
    nothing once the transcript is read;
- a relative path after `cd`: the guard sees only the `cwd` of the call, so
  `cd .compass && cat d*/*` is not stopped, and neither is `cd` into the
  memory folder and then a read of a file one folder up. This is also why a
  Bash command on the memory folder stays refused;
- a symbolic link inside the memory folder that a Grep over the folder follows
  is not detected, because the guard resolves the Grep path and not what
  `rg` finds inside it;
- the root folder alone, such as `grep -r x /`, or a glob in the first
  folder of a path, such as `/U*/...`, because `/` is also an argument of
  `tr`, `cut` and `expr`;
- a relative Bash path, such as `grep -r x ../..`, or a bare `cd` followed
  by a relative path: the check does not know the shell's working folder;
- a command assembled at run time: a variable, a script written with Write
  and then run, or a list passed to Python's `subprocess`;
- a delegated approval or a delegation glob that the hook reads as text and
  cannot follow: a flag built from a variable, command substitution, a value
  read from a file or the environment, and arguments built by `xargs` or
  `printf`;
- a word that a glob expands against a file the agent wrote, such as
  `appro?e` or `--a?`. A text-matching guard cannot follow anything that the
  shell, a spelling or an interpreter builds at run time: variables, command
  substitution, a glob that expands against a file the agent wrote,
  encodings and `python3 -c`. The stored confirmation hash and the 64-bit
  code (ayeo-io/compass#599) are the control that holds then;
- brace expansion in a glob, in Bash or in a Grep glob, such as
  `{d,x}eleg*/*`, `deleg{ations,x}/*` and `**/{DL-*,x}.yml`;
- patterns that only zsh reads, such as `.compass/(deleg\|x)ations/*` and
  `.compass/deleg*/DL-<->.yml`;
- a case-sensitive glob, such as `.compass/*/[A-Z]*` or the Grep glob
  `**/[A-Z]*.yml`: the guard lower-cases the glob, so it counts as a glob
  that picks the delegation files together with others, and passes;
- a Bash command that reads the folder without naming it, such as `grep -r x
  .compass` or `find .compass -type f -exec cat {} +`;
- a tool option that takes its own glob, such as `rg -g`, `find -name` and
  `--include`, and extended globs after `shopt -s extglob`, such as
  `.compass/@(deleg)ations/*`;
- a Bash glob rooted in a folder other than the call's working folder, such
  as `$PWD/.compass/deleg*/*`, a relative path after `cd`, such as `cd
  .compass && cat d*/*`, and a project root above the working folder;
- a Bash glob that spells neither .compass nor deleg, such as `cat .c*/d*/*`.
  The hook starts the guard only when a glob character follows `.compass/` or
  `deleg`, so this glob does not start it. A glob before `deleg` does start
  it when the command has a glob character after `deleg` in its second copy:
  the hook tests the command twice, so `cat .c*/delegations` starts the guard
  and is refused (`delegation-protected`). A glob character in a later word
  of the same command also starts the guard, which costs one python3 start
  and refuses nothing more.

A process running as the same operating system user can still write these
files, or `manifest.yml`.

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
that names no issue is refused (`bad-session-issue-restart`), never passed over
for the pointer. That order holds in the session's own project. In a worktree
the order reverses for Edit and Write: the worktree's own pointer names the
issue, and `COMPASS_ISSUE` applies only when that pointer is empty (see the
worktree paragraph below).

Two interactive sessions share the pointer, so the pre-tool hook records the
issue each Claude Code session last worked on, by its session id, in a
`sessions.json` file under `.compass/`. When another session has moved the
pointer in the session's own project since,
the session's next code edit is refused (`pointer-moved`) until it runs
`compass issue use <slug>` to say which issue it means. A record older than
12 hours is ignored and dropped the next time the table is written, and a
session with `COMPASS_ISSUE` set, or a runtime that gives no session id, is
not tracked. Writes are locked, so two sessions at once keep both records,
and a `.gitignore` in `.compass/` keeps the table out of every project's
commits.

`compass` commands save an issue's `manifest.yml` through
`core.save_manifest`, which `manifest_store.py` implements. The two writes
that do not are named in the last item below.

- The save writes a temporary file in the same folder and renames it over the
  manifest. A reader sees the old manifest or the new one, never an empty or
  partial file.
- Reading a manifest takes no lock, so the pre-tool hook, which reads a
  manifest on every tool call, never waits for a writer. A load records the
  bytes it read. The record goes when nothing holds the manifest any more.
- Under `.manifest.lock`, the save reads the file again. When another save
  changed it after this command's load, the save merges this command's
  changes into the file as it is now. The command's manifest then holds the
  merged result, so its next save keeps both commands' changes. The merge
  updates the command's own nested records rather than replacing them, so a
  record the command still holds stays part of the manifest.
- When both changed the same value to different values, the save stops with
  an error that names the key, and writes nothing. Run the command again. A
  value of another type, such as `true` for `1`, counts as a different value.
- A list of records that each carry a distinct `id`, such as `gates` or
  `evidence`, merges record by record, matched by `id`. A record one command
  removed stays removed when the other left it alone. When the other command
  changed it, the save stops with an error, as for any value both changed.
  The result keeps this command's order of records. A record only the other
  command added goes after the record it follows in the other's list.
- Any other list merges position by position. A position both commands changed
  differently is a conflict. Items each added at the end are all kept, and an
  item both added is kept once. A list one command shortened while the other
  changed it is a conflict.
- A save merges only a manifest that `load_manifest` or
  `manifest_store.load_file` returned, or a copy of one. A test fails when a
  function in the CLI assigns the result of `load_yaml` to the name it then
  passes to `save_manifest`; it does not follow a mapping through other
  functions. A save of a mapping built any other way, such as the new
  manifest `compass quick-fix start` writes, overwrites the file.
- The hook's session record and the release-line write do not go through
  `save_manifest`. Each holds the same lock, reads the file again inside it and
  replaces the file atomically.

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
the issue is not marked done, and `ship-commit` names the files and
exits non-zero.

When `git commit` leaves HEAD where it was, `ship-commit` stops with the
lines git printed, in git's own words, then says HEAD did not advance and
the land did not happen. It adds that a pre-commit hook may be the cause
only when git can run one here: the hook file exists, at the path git
reports for `hooks/pre-commit` (so `core.hooksPath` counts), and is marked
as runnable. A missing author identity therefore reports "Author identity
unknown" and does not point at a hook.

With nothing staged, `compass ship-commit --issue <slug>` lands at HEAD
only when the issue's own commits at the tip stay inside its declared
scope. It walks the first parent from HEAD. A commit that changes only
the living spec is passed over. A commit judged in full keeps the living
spec among its paths, so a hand edit of it is refused unless the issue
owns it. A merge whose merged-in commits are all on the base branch, such
as a merge of `origin/main`, counts only the paths it changed against
every parent, which is its conflict resolution, without the living spec.
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
- For an Edit or Write in a worktree of the session's repository, the
  worktree's pointer comes first, `COMPASS_ISSUE` stands in only for an empty
  pointer, and the session is recorded on that issue without reading the
  session table.
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
- A session that makes no tool call the hook sees is not recorded. A command
  that loaded the manifest before the hook wrote keeps the id when it saves:
  the save merges the hook's change.

### The pre-tool hook refuses on a removed working directory, and three exits still let a call through

Claude Code blocks a tool call only when the pre-tool hook exits with 2. Any
other exit code is a non-blocking error, and the call runs. The hook therefore
turns each fault it can reach into exit 2 with a stated reason.

When the session's working directory has been removed, for example by a
clean-up step such as `cd d && rm -rf ../d`, the hook follows three rules.
First, it falls back to `CLAUDE_PROJECT_DIR` and gives the same verdict as it
does from a directory that exists. Second, when `CLAUDE_PROJECT_DIR` is not set
and an Edit or Write names a file inside a Compass project by its absolute
path, it refuses with `working-directory-gone`. Third, it allows the call when
no project can be found: a shell command, a relative path with no known base,
or a repository that has not opted in. A Read or Grep is never refused for a
removed directory. A shell write in a removed directory with
`CLAUDE_PROJECT_DIR` unset is therefore not seen, because it names no file
path. An Edit or Write of any file inside a Compass project, a document as well
as code, is refused in that state: the earlier exit 1 let it through.

Three exits still let a call through, because the hook cannot turn them into
exit 2:

- The hook's own folder is gone. The shell cannot open the script and exits
  127.
- A helper script the hook calls is unreadable, or fails when it runs.
- A time-out of the hook. On Claude Code 2.1.295 or later the time-out is
  covered by the declared limit: `hooks/hooks.json` sets `"timeout": 15` and
  `"onFailure": "block"`, so a time-out blocks the call. On older versions a
  time-out lets the call run, and the limits of the hook, described above, keep
  it under the time-out.

The hook has no catch-all exit rule, such as a trap that maps every exit other
than 0 and 2 to 2. Measured on bash 3.2.57 on 2026-10-19, an `EXIT` trap like
that ends a direct unbound-variable exit with status 0, so the call runs: worse
than the exit 1 it replaces. An `ERR` trap does not fire inside functions
unless `set -E` is on, and that setting changes how every function in the hook
behaves. The fix therefore covers the one path that was reproduced, and the
other exits are stated here.

### An Edit that changes only comments of Python or YAML needs no failing test

The pre-tool hook refuses an Edit of production code unless a failing test is
on record. A comment cannot change what code does, so an Edit of a `.py`,
`.yml` or `.yaml` file that changes only comments, docstrings or layout runs
with no failing test and no assessed issue. The hook proves this from the file
on disk and never from the text of the Edit: it reads the file once, applies
the Edit in memory and compares the file before and after
(`cli/compass_pkg/comment_only_edit.py`). It prints nothing on an allow.

| Language | Files | The Edit is comment-only when | Code, so refused |
|---|---|---|---|
| Python | `*.py` | the syntax trees are the same; a docstring's text may change only when it stays the first statement of its module, class or function, is not an f-string, and the file mentions none of `__doc__`, `getdoc`, `help`, `doctest`, `exec` and `eval` | a string that is not a docstring, a second string statement, an f-string first statement, a `#` inside a string, a line joined to code by a backslash |
| YAML | `*.yml`, `*.yaml` | the parser's events are the same: data, key order, anchors, aliases, tags and merge keys; quote style and layout do not count | a duplicate key, aliases that expand to more than 100000 nodes, a `#` inside a block scalar or a quoted string |
| Shell | files that `enforcement.code_globs` declares | never | every edit keeps its verdict |
| Any other language | JavaScript, Go, SQL, Terraform, Dockerfile and the rest | never | every edit keeps its verdict |

Shell and every other language are not covered. A line that starts with `#` is
data inside a heredoc, a multi-line string or a command substitution, and every
shell file that `enforcement.code_globs` declares in this repository (12 files)
uses one of those. A reader that is wrong in the open direction would let a
data line change with no failing test. `NotebookEdit` and `MultiEdit` are not
wired to the hook and are unchanged.

A comment that carries a pragma is code. The hook refuses an Edit that adds,
changes or removes one: `# type: ignore`, `# noqa`, `# nosec`, `# fmt: off` and
`# fmt: on`, `# pragma: no cover`, `# pylint:`, `# mypy:`, `# pyright:`,
`# ruff:`, `# flake8`, `# isort:`, `# yamllint`, `# shellcheck`, a shebang
line and an encoding line (`# -*- coding` or `# coding:`). It also refuses the
directives of scanners and formatters that the list names: `# nosemgrep`,
`# gitleaks`, `# checkov`, `# lgtm`, `# NOSONAR`, `# codeql`, `# yapf`,
`# trivy` and `# tfsec`. The test is a superset of this list, so a prose
comment that mentions one of these words needs a failing test. An Edit that
adds a hidden character is refused too: a control character, a NUL byte, a
bidirectional control or a zero-width character.

The encoding cookie of the file is read for every Python Edit (PEP 263: a
comment on line 1, or on line 2 when line 1 is blank or a comment, that holds
`coding:` or `coding=` and a name). Python decodes the source with that name
before it parses a line. A cookie such as `utf-7` or `unicode_escape` turns text
inside a comment into a line break, and the hook reads UTF-8, so the Edit is
code when the cookie before or after the Edit is not `utf-8`, `utf8` or
`ascii`, and when the Edit adds, removes, changes or moves the cookie (two
comment lines put above a cookie on line 2 move it out of the first two
lines). When the cookie is `ascii`, an Edit that leaves a non-ASCII character in
the file is code too, because Python cannot load such a file. A file whose first
line starts with `#` and `template:` (cloud-init's
`## template: jinja`) is rendered as a template before a YAML parser reads it,
so an Edit of it is code too.

The check fails closed. In each of these cases the Edit is judged as before the
check existed, so it is refused unless a failing test is on record:

- the file is over 1048576 bytes, is not a regular file, is a symbolic link or
  is not UTF-8
- the old text is not in the file, or is in it more than once without
  `replace_all`
- the file before or after the Edit does not parse
- the Edit changes a pragma or adds a hidden character
- the encoding cookie is not `utf-8`, `utf8` or `ascii`, or the Edit changes it
- the file starts as a template
- the check runs out of budget, runs past its alarm or fails for any reason

The check runs in `python3`, with its standard library and the vendored YAML
reader. A check that is over budget or fails returns "no", and the hook then
judges the Edit as before. A missing `python3` still refuses with
`python-missing`, as for every reader of the hook. A Write is never judged this
way: a Write that replaces a file is judged as a code change.

The hook reads the file once and cannot lock it, so a change to the file
between the read and the Edit is not detected.

These are stated limits of the comment-only check. They are not fixed in this
version, and each lets an Edit through that a stricter check would refuse:

- The docstring rule is a word list. A docstring may change its text unless the
  file mentions `__doc__`, `getdoc`, `help`, `doctest`, `exec` or `eval`. A
  docstring that a framework reads without the file naming it is editable: a
  PLY grammar rule (`"""expr : expr PLUS term"""`), the help text of click or
  typer, and a FastAPI description. A docstring that a framework reads as
  grammar or help is not detected.
- The directive rule is a deny list of words. A scanner or formatter directive
  that is not on the list passes as a comment. The list now holds the common
  ones; a tool that is not on it is not seen. The same holds for a first line
  that a tool reads as a file type: an Edit that removes `#cloud-config` or
  `#include` from the first line of a YAML file passes as a comment edit.
- A template engine that reads comment text is relevant only where
  `enforcement.code_globs` guards a template. A YAML comment such as
  `# {{ "\nevil: true" }}` in a Helm template passes the YAML check, because
  the parser sees a comment.
- A symbolic link under `evals/*/seed/` that points at production code is
  exempt, because a path is judged by its text and a symbolic link is not
  followed. The same holds for `tests/` and `.compass/`.
- The hook uses awk, for example to count the length of a write target in the C
  locale. The hook was written and tested on the awk of macOS only. The
  continuous-integration runners use Linux awk, and this contract does not claim
  that the two give the same results.

Reading a shell command by its grammar, so that prose in a message or a
document is not taken for a write, is separate work (GitHub issue #247).

The check is charged to the work budget (see the Shell-write section below) by
the size of the larger of the two texts, before any parse. These constants are
in the hook's cost table, in microseconds, and the hook explains each of them
in a comment:

- COST_EDIT_START 40000: python3 with the package and the YAML reader loaded
- COST_EDIT_PARSE_PY 5000 and COST_EDIT_PARSE_YAML 5000: one parse and
  comparison of a text of three lines, charged twice
- COST_EDIT_KB_PY 3000 and COST_EDIT_KB_YAML 10000: for each KiB of both texts
- EDIT_ALARM_SECONDS 3: the longest the check may run

The charge is the start, plus twice the parse, plus the KiB of the larger text
times the rate. An Edit whose charge is past what is left of the budget is not
parsed. At these values a Python file is read up to about 780 KiB and a YAML
file up to about 230 KiB, and a larger file keeps the old verdict. The rates are
those of the slowest shape that was measured, so a file of comments is charged
at the rate of dense code.

The budget is a table and a hostile file breaks it: PyYAML takes about 90
seconds for 100000 `[` characters, a file of 100 KiB. The bound that holds is
`signal.alarm`. Its default action ends the process even inside C code, and the
hook then gives the old verdict and charges the whole alarm. The alarm is the
smaller of EDIT_ALARM_SECONDS and what is left before the 8 second fuse, less
one second; with less than one second left no check starts. A YAML file whose
aliases expand to more than 100000 nodes is refused without expanding it,
because each anchor is counted once with a table.

Worst cases, measured on 19 October 2026 on macOS with bash 3.2.57, Python
3.11.9 and the bundled PyYAML 6.0.2 (no libyaml), in the whole hook:

| Shape | Size | Seconds | Charge in microseconds |
|---|---|---|---|
| Python, statements of two bytes (`a`) | 700 KiB | 1.9 | 2153000 |
| Python, calls (`f(a, b)`) | 700 KiB | 1.4 | 2153000 |
| Python, 5000 lines of definitions and comments | 81 KiB | 0.1 | 293000 |
| Python, comment lines | 512 KiB | 0.1 | 1586000 |
| Python, comment lines | 1 MiB | 0.3 | none: not parsed |
| YAML, flow sequences of one-digit numbers | 200 KiB | 2.0 | 2060000 |
| YAML, list of mappings | 200 KiB | 1.4 | 2050000 |
| 100000 nested parentheses | 100 KiB | 0.3 | parse error |
| 30 anchors that each hold ten aliases of the last | 2 KiB | 0.3 | refused at 100000 nodes |
| 100000 `[` characters | 100 KiB | 3.3 | alarm |

For one file, per KiB of the two texts together, the slowest Python shape took
2.7 ms (statements of two bytes), against 2.0 ms for calls and 0.03 ms for
comment lines. The slowest YAML shape took 9.5 ms (flow sequences of one-digit
numbers), against 6.6 ms for a list of mappings and 0.7 ms for comment lines.
`tests/test_pre_tool_hook_comment_only_edit.py` holds each bound: the time of
the hook is between 0.2 and 3 times the work it charged, and every hostile
shape ends within 6 seconds.

A slower machine refuses a file that is close to the limit. The check ends at
the 3 second alarm and is charged the whole alarm, and the Edit keeps the old
verdict. A file of statements of two bytes and 700 KiB is charged 2.15 seconds
and takes 1.9 here, so a machine that is 1.6 times slower ends it at the alarm.
A GitHub-hosted Linux runner did so on 19 October 2026 (the check ran past
3 seconds). The refusal is safe, and the limit is for hostile files; a file that
people write is far from it (81 KiB of definitions and comments takes 0.1
seconds, in the table above). The model
test therefore uses files of about 40% of the limit (300 KiB of Python, 90 KiB
of YAML), which take 0.65 to 0.9 seconds here and leave a margin of 3.3 times
before the alarm. A second test uses files at the limit (780 KiB of Python,
230 KiB of YAML) and asserts only that the result is safe: a comment edit is
allowed or refused as before, an edit of code is always refused, and the hook
ends within 6 seconds.

Three more rules sit beside this one:

- Path classes. `evals/*/seed/` holds input that the eval harness copies into a
  sandbox and never runs in place, so it is not production code and needs no
  failing test. The pattern starts at the project root, and a `..` step cannot
  borrow it. These stay guarded: `examples/`, `cli/vendor/` (every Compass
  process runs it), `.github/scripts/` (CI runs it), `evals/` outside `seed/`,
  `src/examples/` and `db/seed/`. The setting `enforcement.code_globs` only
  ratchets up: no built-in exemption is wider than the code Compass can show is
  not production code. The same classification serves a shell redirect.
- Shell files. A file that `enforcement.code_globs` declares is guarded. A
  shell script, makefile or extensionless script is not a built-in
  production-code file type, so a project declares the ones it wants guarded.
- Messages. The refusal for a missing failing test (`no-red-on-record`) names
  `compass tdd-red` and `compass acceptance start`, for a change that has no
  natural test. A `.compass/current-task` that names an issue with no folder
  under `.compass/work/` is not a missing pointer: the hook says so, names the
  issue it falls back to (the issue that changed most recently) and judges the
  Edit by that issue, as before. `bad-session-issue` is for a
  worktree and says to run `compass issue use <slug>` there.
  `bad-session-issue-restart` is for the session's own project, where
  `COMPASS_ISSUE` outranks the pointer, so `compass issue use` changes nothing
  and a running session cannot change its environment: the person restarts
  the session with `COMPASS_ISSUE` naming an existing issue, or without it.

The rules and the reasons are in
`governance/decisions/2026-10-19-a-comment-only-edit-of-code-needs-no-failing-test.md`.

### Shell-write detection is best-effort

The Claude Code pre-tool hook completely covers supported file-editing tools.
For shell commands it recognizes these write shapes, and only these:

- `>`, `>>` and `>|` redirects, including the `cat > file <<EOF` heredoc
  form and a quoted target such as `> "src/app.ts"`
- `sed -i`, and `perl` and `ruby` with `-i` in any flag group, such as
  `-pi`, `-lpi` or `-i.bak`
- the arguments of `tee`, and the last argument of `cp` and `mv`, found in
  the same simple command as the `tee`, `cp` or `mv` word, including behind
  a wrapper such as `sudo` or `timeout`; a file that another command in the
  same line only reads is not a target, a `$(...)`, `<(...)`, backtick span
  or line continuation inside the command does not split it, a quoted
  bracket inside a span does not hide the words after it, and a write
  inside such a span is found
- `patch -p<n>` and `git apply` - writers with unknowable targets
- an inline interpreter script (`python3 -c`, `node -e`, a heredoc) whose
  write call (`open` with a write mode, `write_text`, `write_bytes`,
  `os.replace`, `shutil.copy` or `move`, `writeFileSync`, `File.write`)
  names its target as a string, or as a name the same script assigns a
  string to; a name assigned to and only read is not a target, and a path
  assigned to a name in the same script counts only when a write call uses
  that name

Anything else runs unchecked: a write through a script file, a build step,
an interpreter reached via a wrapper, or a path built at run time (joined
from parts, returned by a function or read from the environment) is not
detected. Unknown commands are allowed
rather than blocking ordinary development indiscriminately. These writes to
production code, for example, are not detected:

- a destination that is itself a substitution, or ends in one:
  `cp a.ts $(echo src/app.ts)` and `cp a.ts src/app.ts$(true)`
- a destination given by an option rather than as the last argument:
  `cp -t src /tmp/a.ts`
- a `cp` or `mv` that another command runs, where a word follows the
  destination: `find . -name a.ts -exec cp {} src/app.ts \;`
- a command inside a string that a nested shell runs:
  `sudo sh -c 'cp a.ts src/app.ts'`
- a quoted `;`, `&`, `|` or `(` outside a substitution, before the
  destination, which the hook reads as the end of the command:
  `cp "a;b" src/app.ts`
- a `case` pattern inside a substitution, whose `)` the hook reads as the
  end of the substitution: `cp "$(case x in x) echo y;; esac)" src/app.ts`

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

A path is judged where it points, not how it is spelled. Before the hook
decides whether a path is inside the project, it resolves `.`, `..` and
repeated slashes as text, and a path that differs from the project only in
letter case counts as inside it. A `..` after a part the hook cannot know,
such as an unexpanded variable or `~`, leaves the real location unknown, so
that path is judged inside the project, and the directories named before
the `..` do not exempt it: `$X/../tests/../src/app.ts` is judged as
production code, not as a test. A symbolic link is not followed.

The hook has to finish before Claude Code stops it, so it refuses a Bash
command it cannot scan in time where Compass is in use, and skips only the
write scan elsewhere. Five limits do this, all set from timings on a UTF-8
machine with bash 3.2: a command over 98304 bytes (`bash-command-too-long`),
and a command with more than 400 different write targets, a write target of
more than 2048 bytes, more than 20 different variable names at the start of a
write target, or more than 700 `$(` openers (`bash-command-too-complex`). The
length of a write target is counted in bytes, by awk in the C locale, before
any bash string operation runs on it. A glob in `enforcement.code_globs` that
bash cannot match itself is matched by Python once for all the write targets
of a command.

Those limits each bound one shape, and a command can hold several. So the
scans that grow with the command also share one work budget, counted in
microseconds of time measured on one machine. The flattening of
substitutions (which also stops by itself after a million steps), the walk
over the leading statements (which runs once for all the variable names), the
reading of the command for each variable name and the judging of each write
target all add their steps to it. A command that passes the budget is refused
with the same code, `bash-command-too-complex`, where Compass is in use, and
only has its write scan skipped elsewhere. The budget is 2400000, which is
2.4 seconds of work. The walk keeps its findings only for the variable names
that the write targets start with. Bash slows every later variable operation
as the number of shell variables grows, and the walk used to keep five
variables for every name a statement assigned: a command of 8000 assignments,
20 names, 20 targets and 1000 globs took 17.3 seconds although its work was
charged at 2.4 seconds. The steps of the flattening reach the hook in a file
that the hook makes and the flattening alone writes, as two numbers that the
hook checks (nine digits at most). The text of a command is never read as
that count: a write target named `compass-scan-work=5000000000000000000` once
made the counter negative, so that the budget never tripped, and now it is a
target like any other.

The budget is an estimate from a table and reads no clock. It cannot see an
interaction that the table does not charge, or a machine slower than the one
that was timed. A wall-clock fuse is the backstop for those. The hook reads
bash's own count of seconds (`$SECONDS`, which starts no process) when the
script starts, and checks it at each write target, at each variable name and
at each pass of the walk. When 8 seconds have gone it stops as it does for the
budget: it refuses with `bash-command-too-complex` where Compass is in use,
and exits 0 with the write scan skipped elsewhere. The count has a
granularity of one second, so the fuse trips between 7 and 8 seconds after
the script starts. No setting in the environment changes it. On a slower
machine the fuse refuses a command at 8 seconds; the budget alone would pass
the same command, and it would take longer.

The fuse is checked between write targets and between steps of the walk, so
it does not interrupt a process that is running, such as the settings reader,
or one write target. The quote strip and the path normalizer on one target
take time that grows with the square of its length (a target of 10 KB ran for
about 20 seconds, and one of 90 KB for 25 seconds), which is why a target over
2048 bytes is refused and not left to the fuse. The worst accepted single
target, 2048 bytes of quote pairs, `a/` segments, `x/./` segments, `a/../`
segments or a `${V}/` prefix, took 0.2 seconds in the whole hook, and 45 such
targets of segments, the most that fit in the length limit, took 1.3 seconds.
Quote pairs are taken out by awk, in linear time, before bash sees the target.

These are the largest accepted commands in the latest timings, on a machine
with 14 cores and a load average of 2 to 4, in seconds: 1.9 for 260 write
targets under a project whose settings hold 300 globs, 1.9 for 19900 leading
`:` lines and 1 name, 1.8 for 18200 such lines and 20 names, 1.6 for 9000
leading `cd` lines and 20 names, 1.0 for 8000 leading assignments, 1.6 for 5
unclosed `$(` openers before 85 KB, 1.2 for 400 write targets (1.3 for targets
of 180 characters, and the same under a bracket glob), 1.4 for 20 names and
380 other targets under a bracket glob, and 0.2 for 700 closed openers. 10000
leading `:` lines with 20 names are accepted in 1.1 seconds. The next larger
command of each of these shapes is refused, in at most 2.1 seconds.

These times were measured on macOS with bash 3.2. The Linux runner of the
continuous integration takes up to about twice as long for the shapes made of
many leading lines: the hook took 4.1 seconds for 40000 leading `:` lines. That
is under the fuse at 8 seconds and the time limit of 15 seconds. The tests
therefore allow 6 seconds for an accepted or refused command, and not the 3.75
seconds that was the aim on the first machine.

Commands of thousands of assignments, 20 names, targets and globs, in seconds
after the change, with the time before it in brackets: 5000 assignments, 380
targets and 30 globs 1.8 (5.5), 3000 assignments, 150 targets and 300 globs 1.5
(7.3), 8000 assignments, 20 targets and 1000 globs 1.7 (17.3). With a write
to a code file placed last, 8000 assignments with 200 targets and 300 globs,
and with 100 targets and 1000 globs, are refused in 1.7 seconds; they were
refused after 14.2 and 18.0 seconds before. 5000 assignments, 380 targets and
100 globs are refused in 1.8 seconds. Before the budget, 40000 leading `:` lines
with 20 names took 62 seconds because the walk ran once for each name, and 400
names took 26 seconds. The times before the change to the walk's variables are
from the review of the earlier version.

The length limit is 98304 bytes (96 KiB), counted over the whole command.
In a project that has a `.compass` folder, the hook refuses a longer command
with the code `bash-command-too-long`, and it never scans a part of a
command. The refusal names the size and the limit and does not quote the
command. It is not counted in `.compass/interruptions.log`, because that count
needs an issue and the hook does not know the issue yet. In a repository that
has not opted in to Compass, the hook does not refuse a command for its
length. It skips only the write scan there, and the approval and transcript
guards still read the whole command.

The time limit is 15 seconds. `hooks/hooks.json` sets `"timeout": 15` and
`"onFailure": "block"` on the pre-tool hook. From Claude Code 2.1.295 a hook
that fails or runs out of time can block the call.

The size limits are the main control and work on every version of Claude
Code. On an older version the length limit still refuses long commands, and
the other limits still refuse their commands, but a command that runs past
the time limit can let the call run. Not every timeout fails closed.

Not measured: only one version of Claude Code was available, so the
behavior of older versions is from its documentation.

A machine without `jq` has no time bound. The hook then reads the input with
`grep` before it knows the command's length, and that read slows quickly as
the command grows: 10 KB took 4.4 seconds, 20 KB took 33.9 seconds and 50 KB
did not end in 150 seconds. A command of 20 KB is a fifth of the length
limit and already runs past the 15-second time limit. The hook before this
change behaved the same way. On Claude Code 2.1.295 or later the 15-second
timeout is the only control there. `scripts/install.sh` and the Codex hook
file do not set these keys, so a source install and a Codex session keep the
default timeout of 600 seconds.

A shell script, makefile or extensionless script is not a built-in
production-code file type for red-before-green enforcement. A file that
`enforcement.code_globs` declares is guarded, whatever its type.

Inside a worktree, Edit and Write follow the worktree's own issue and failing
test, because they name their file and the hook resolves the project from it.
The worktree's pointer names the issue. COMPASS_ISSUE applies in the
session's own project, and in a worktree only when the worktree's pointer is
empty. A pointer that names a missing issue, or no issue to name at all,
refuses (`bad-session-issue`); the hook never guesses the most recently
changed issue there. An edit in a worktree of a different repository is
refused, and so is one in a tree git cannot read. A session with no Compass
project is not affected. A session in a worktree does not read that
worktree's session table, so `pointer-moved` applies in the session's own
project only.

A shell write is not followed that way: a shell write still resolves from the
session's project, because its targets are found against that project. GitHub
issue #104 tracks the gap. The results are:

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
cases and nowhere else. A change of behavior that no case exercises is not
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
