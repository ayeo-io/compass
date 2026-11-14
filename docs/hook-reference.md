# Hook reference

This page gives the exact rules by which the pre-tool hook reads a tool call,
and the exact content of a test-run record and a manifest save. The
[safety contract](safety-contract.md) states the guarantees and the limits.
Read this page when you need to know why one call was refused or allowed.

## The approval guard

The guard is `cli/compass_pkg/approval_guard.py`. It reads a Bash command
with `cli/compass_pkg/approval_words.py`. Each path check ignores letter
case, because macOS opens a path in any case. The decision record is
[the approval guard judges words, not text][guard-decision].

### A simple command

The guard reads a simple command as words and judges any other command by its
whole text. The gate fails closed: a shape it does not name is not simple. A
command is simple when all of these hold:

- it is one command, or plain commands joined by `&&`, `;` or a new line;
- each command starts with `git`, `gh`, `ls`, `wc`, `stat` or `cat`, with no
  path, no `VAR=` word before it and no function or alias definition;
- it holds no pipe, `&`, `||`, parenthesis, backtick, comment, heredoc,
  here-string, process substitution, `eval`, `$'...'` or `$"..."`;
- it holds no unquoted brace, glob, tilde, `^` or `#` character
  (`{ } * ? [ ~ ^ #`), because the shell expands such a word before the
  command runs and the guard judges the word as typed;
- it holds no zsh number range such as `<1-3>`, no `>!`, no descriptor of two
  digits, no descriptor move (`>&2-`) and no quoted or escaped digit before a
  redirect;
- it is not only a redirect, because zsh runs `cat` for it;
- a copy of a descriptor (`2>&1`, `>&2`) ends at a blank, a new line, `;` or
  `&`. Any other white space character is part of a file name in the shell,
  so a copy followed by one is not simple;
- it holds no `$` outside message text, and no `$(`, `${` or backtick inside
  message text;
- a message value is one quoted word, never joined to its option, and never
  starts with `@`;
- a `git commit`, `tag`, `merge` or `revert` holds only a message option and
  the options without a value that `GIT_FLAGS` and `GIT_LETTERS` list in
  `approval_words.py`, such as `-a`, `--amend`, `--no-edit` and
  `--allow-empty`. Any other option may take the next word as its value
  (`--author -m <path>`) or read a file or a commit (`-F`, `-c`, `-C`, `-t`,
  `--template`);
- a `gh issue`, `pr` or `release` `create`, `edit` or `comment` (and `pr
  review` and `pr merge`) holds only a message option;
- no global option stands before the verb (`git -C dir`, `git -c`, `gh -R`).

### What the guard judges

| Command | What is judged |
|---|---|
| Simple | Each command name, each redirect target and each argument, by its text, with quotes removed as the shell removes them. Message text is not judged. |
| Not simple | The whole text. Any text that names a protected thing is refused, and text that names none is allowed. |

Message text is a fixed list. A widening is a visible change that needs a
test row.

- The quoted value of `-m`, `-am` and `--message` of `git commit`, `tag`,
  `merge` and `revert`. A command with `-F`, `--file`, `-c` or `--exec` is
  not simple.
- The quoted value of `--title`, `--body`, `--notes`, `-t` and `-b` of `gh
  issue`, `gh pr` and `gh release`, only for the subcommands above.
  `--body-file` makes the command not simple.
- `gh api`, `gh alias`, `gh extension` and `gh pr checkout` have no message
  text, and the guard judges every word of them.

A command that is not simple covers a pipe, a heredoc, an `echo` or `printf`
that names a request, a search pattern, a message built with `$(...)`, a
script written and run in one call, and a command that the gate does not
list. For example `git commit -m "$(cat <<'EOF' ... EOF)"` is refused when
its text names a protected thing and allowed when it names none.

### The exemptions

An exemption removes one thing from one word. It holds only when all of
these hold:

- the command stands alone;
- it has no redirect to a file (a copy of a descriptor such as `2>&1` names
  no file);
- it has one operand;
- it carries only the plain options `ls -lah1` and `wc -lcwm` allow. `stat`
  and `cat` carry none. `--` and any other option void the exemption;
- the path has no `..` segment, so `ls <request folder>/../../../delegations`
  is refused.

| Command | May name, as a bare path argument |
|---|---|
| `ls`, `wc`, `stat` | A request path, a folder or a file, with no glob, brace or tilde. `wc -l <request>` and `stat <request>` show a count or the file's metadata, not its content. |
| `cat` | `hooks/prompt-approval.sh`. Every other command that names the script is refused, including `chmod`, `git add`, `cp`, a runner and a listing, and a `cat` in a pipe or beside another command. |

- `ls .compass/delegations` is refused: the delegation folder has no
  exemption.
- A `VAR=` word, an option such as `--output=<path>`, and the word after
  `-f`, `--file`, `--files0-from`, `--output`, `--pre` or `--exec` are never
  bare arguments.

### The auto-memory folder

Read, Grep, Edit and Write may name a file inside
`<configuration folder>/projects/<one folder>/memory/`, in any `.claude*`
configuration folder.

- The guard joins the path to the call's `cwd`, collapses `..`, folds letter
  case and resolves each symbolic link. The result must still be inside that
  folder.
- Edit and Write need a file inside the folder. Read and Grep may name the
  folder itself.
- Refused: a path with a glob or brace character, a Grep glob with a `..`
  segment or a brace expansion that holds `..` (such as `{..,x}/*.jsonl`), a
  path that leaves the folder and a symbolic link that points out of it.
- A Bash command that names the folder stays refused, because the guard
  cannot follow `cd` out of it.

### A name split across lines

For the request folder and the delegation folder, a Bash command is read with
each backslash and newline removed where the shell removes them, outside
quotes and inside double quotes. So `.compass/deleg\<newline>ations` counts
as the whole name.

- In a simple command, the shell keeps the two characters inside single
  quotes, and so does the guard.
- A command that is not simple is read with every backslash and newline
  removed, because an apostrophe there may not be a quote to the shell. A
  split name inside single quotes is refused there too.

### A glob on the delegation folder

The hook tests a Grep glob, or a Bash word with `*`, `?` or `[`, with
`fnmatch`:

- against the folder `.compass/delegations` and two sample files in it, one
  named like a delegation record and `confirm-s.yml`;
- against an ordinary path of the same shape: a folder `zz` and a file
  `file.yml` in it, both under `.compass`.

It refuses the glob (`delegation-protected`) when it matches a delegation
path and not the ordinary one.

| Verdict | Globs |
|---|---|
| Refused | `d*/*`, `deleg*/*`, `deleg?tions`, `**/confirm-*`, `cat .compass/deleg*/*`, `'.*delegat*'`, `*.yml,deleg*/*` |
| Refused as a known cost | `**/*-*.yml`, `**/D*`, `d*` and `**/*s.yml` as Grep globs |
| Accepted in a Grep | `*`, `**/*`, `**/*.md`, `*.yml`, `**/*.yml`, `src/**/*.py`, `.compass/*`, `'.*delegat.*'` |
| Accepted in Bash | `ls .compass/*`, `ls .compass/work/*`, `cat .compass/work/*/manifest.yml`, `ls .compass/**`, `ls src/*.py`, `cat docs/*.md` |

- A Grep glob counts only when the search path is the delegation folder or a
  folder above it, so `src` and `.compass/work` pass.
- A Grep glob is also split on commas.
- A Bash word is read after the shell's quotes are removed, in any letter
  case, and also inside `bash -c`, `sh -c` and `eval`.
- The glob is read as the shell reads it: `[^y]` counts as `[!y]`, and a
  POSIX class such as `[[:lower:]]` counts as one character.
- A quoted regular expression is read as a glob too.
- The hook starts the guard only when a glob character follows `.compass/`
  or `deleg`. It tests the command twice, so `cat .c*/delegations` starts
  the guard and is refused.

### A delegated approval

The guard refuses a delegated approval whose `--as` is not exactly the agent
Claude Code reports (`delegation-caller-mismatch`).

- A Bash command counts as a delegated approval when a word is `approve` and
  a word is `--delegated`, a prefix of it of five characters or more, or
  `--delegated=...`. `evidence approve` beside any word that starts `--del`
  also counts.
- The words of `bash -c`, `sh -c`, `eval` or a quoted command piped into a
  shell are read too.
- Every `--as` must name the caller, since the CLI keeps the last one.
- The call is the main agent only when the hook input has neither
  `agent_type` nor `agent_id`.
- The CLI takes no abbreviated flag, so `--deleg` cannot pass unseen.
- A command that is not a delegated approval, such as `git update-index
  --assume-unchanged`, is not checked.
- The message of a simple `git commit` or `gh pr` that names `--delegated` or
  `evidence approve` is text and is not judged. A real `compass evidence
  approve --delegated` is not a simple command, and any command that names it
  is judged by its whole text and needs a matching `--as`.

How a word that holds `--as` is read:

| Rule | Examples |
|---|---|
| A word that holds `--as` and is neither exactly `--as` nor `--as=...` is refused, because the shell can turn it into a second `--as` that the hook cannot read. | `--as${IFS}compass:architect`, `--as$IFS`, `--as$X`, `x--as`, `--asmain`, `--as-main`, `--assume-yes` |
| Quotes are removed first. | `"--as"` and `--a''s` count as `--as` |
| A backslash and newline inside a word are removed first. | `--a\<newline>s` counts as `--as` |
| A word with white space is read again as its parts. This is a known cost: the refusal names the word, so a person can rephrase it. | `--reason 'fix--assets'` and `--reason 'fix --assets'` are refused |
| A word without white space that holds a brace expansion (a `{` with a `,` or `..` before the closing `}`) is refused, because the shell expands it into two `--as=` words. | `--a{s=main,s=compass:architect}` |
| A quoted value with a space, or with no comma and no `..`, passes. | `--reason '{"a": 1}'` |
| A compact JSON value with a comma and no space is refused as a known cost, in any `compass evidence` command (`--note`, `--reason` and the rest). | `'{"a":1,"b":2}'` |
| A command with the word `compass` (or an escape-spelled `compass` in command position) and a word of ANSI-C quoting with an escape is refused. | `compass $'\x65vidence' $'appro\x76e'` |
| A command that names `evidence` (a word `evidence`, a quoted word that holds `compass evidence`, or a `--delegated` flag) and holds ANSI-C quoting with an escape, or a brace expansion in any word, is refused with the word named. The hook does not decode either spelling. | `$'--a\x73'`, `$'appro\x76e'`, `--{delegated,x}`, `appr{ove,x}` |

### The transcript

The guard refuses a Read or Grep on the session transcript's folder, inside
it or on any folder above it (`transcript-protected`).

- A relative path is read from the call's `cwd`, and a Grep with no path
  searches its `cwd`. The hook reads a Grep's path with or without `jq`.
- A Bash word is refused when it names the transcript, a `.claude*/projects`
  folder, a configuration folder directly under the home folder (such as
  `~/.claude-ayeo`), or a folder above the transcript, such as `~`, `~<name>`
  or `$HOME`, once the shell's quotes are removed.
- A word with a glob or a brace counts by the folder before it, so a `cat` of
  a glob under `~/.claude-ayeo` is refused.
- `ls ~`, `cd ~` and `grep -r x ~` are refused.
- A project's own `.claude` folder is not refused.

### An approving review of a pull request

The hook refuses these (`pr-review-protected`):

- `gh pr review` with `--approve`, `--approve=...` or `-a`, also when `-a`
  is joined to other short options (`-ab text`);
- `gh api` on a path that names `pulls/<n>/reviews` (with a review id or
  `events` after it, or none) when the method is not `GET` or `HEAD`;
- `gh api` on that path with a field `event=APPROVE`, with any method;
- `gh api` with a GraphQL mutation `addPullRequestReview` or
  `submitPullRequestReview`, whatever the event.

How the method is read:

- The method is the value of `-X`, `-XPOST`, `--method` or `--method=`, in
  any argument order.
- With no method, a field (`-f`, `-F`, `--field`, `--raw-field`) or `--input`
  makes it a `POST`, as `gh` sends it.

How the command is read:

- The hook reads each command of a chain (`&&`, `||`, `;`, `|`, a new line)
  and, to eight levels, each quoted word that names a review. So `bash -c`,
  `sh -c`, `eval` and a quoted command piped into `sh` are read too.
- A `gh` given as a path (`/usr/local/bin/gh`) or after `command` or a `VAR=`
  word counts.
- The hook starts the guard for a Bash command that names `gh` and then
  `review`, in any letter case.
- Allowed: `gh pr view`, `gh pr review --comment` and `--request-changes`, a
  `gh api` read of the reviews (no method, or `GET`, with `--jq` or
  `--paginate`), a write to another path, and the message of a simple `git
  commit` or `gh pr create` that names a refused form.
- Known cost: a quoted word that holds a refused form in a command that is
  not simple, such as `grep 'gh pr review -a' docs`, is refused.

## The comment-only check

On an issue assessed before 9.0.0, an Edit of a `.py`, `.yml` or `.yaml`
file that changes only comments, docstrings or layout runs with no failing
test and no assessed issue. The check is
`cli/compass_pkg/comment_only_edit.py`. The decision record is
[a comment-only edit of code needs no failing test][comment-decision].

The hook proves the Edit is comment-only from the file on disk and never from
the text of the Edit: it reads the file once, applies the Edit in memory and
compares the file before and after. It prints nothing on an allow.

| Language | Files | The Edit is comment-only when | Code, so refused |
|---|---|---|---|
| Python | `*.py` | the syntax trees are the same; a docstring's text may change only when it stays the first statement of its module, class or function, is not an f-string, and the file mentions none of `__doc__`, `getdoc`, `help`, `doctest`, `exec` and `eval` | a string that is not a docstring, a second string statement, an f-string first statement, a `#` inside a string, a line joined to code by a backslash |
| YAML | `*.yml`, `*.yaml` | the parser's events are the same: data, key order, anchors, aliases, tags and merge keys; quote style and layout do not count | a duplicate key, aliases that expand to more than 100000 nodes, a `#` inside a block scalar or a quoted string |
| Shell | files that `enforcement.code_globs` declares | never | every edit keeps its verdict |
| Any other language | JavaScript, Go, SQL, Terraform, Dockerfile and the rest | never | every edit keeps its verdict |

Shell and every other language are not covered. `NotebookEdit` and
`MultiEdit` are not wired to the hook. A Write is never judged this way: a
Write that replaces a file is judged as a code change.

### A comment that is code

A comment that carries a pragma is code. The hook refuses an Edit that adds,
changes or removes one:

- `# type: ignore`, `# noqa`, `# nosec`, `# fmt: off` and `# fmt: on`,
  `# pragma: no cover`, `# pylint:`, `# mypy:`, `# pyright:`, `# ruff:`,
  `# flake8`, `# isort:`, `# yamllint`, `# shellcheck`, a shebang line and an
  encoding line (`# -*- coding` or `# coding:`);
- the directives of scanners and formatters: `# nosemgrep`, `# gitleaks`,
  `# checkov`, `# lgtm`, `# NOSONAR`, `# codeql`, `# yapf`, `# trivy` and
  `# tfsec`.

The test is a superset of this list, so a prose comment that mentions one of
these words needs a failing test. An Edit that adds a hidden character is
refused too: a control character, a NUL byte, a bidirectional control or a
zero-width character.

The encoding cookie of the file is read for every Python Edit (PEP 263: a
comment on line 1, or on line 2 when line 1 is blank or a comment, that holds
`coding:` or `coding=` and a name). A cookie such as `utf-7` or
`unicode_escape` turns text inside a comment into a line break, and the hook
reads UTF-8. So the Edit is code when:

- the cookie before or after the Edit is not `utf-8`, `utf8` or `ascii`;
- the Edit adds, removes, changes or moves the cookie;
- the cookie is `ascii` and the Edit leaves a non-ASCII character in the
  file.

A file whose first line starts with `#` and `template:` (cloud-init's
`## template: jinja`) is rendered as a template before a YAML parser reads
it, so an Edit of it is code too.

### The check fails closed

In each of these cases the Edit is judged as before the check existed, so it
is refused unless a failing test is on record:

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
`python-missing`.

### The cost of the check

The check is charged to the work budget (see "Hook time limits") by the size
of the larger of the two texts, before any parse. The constants are in the
hook's cost table, in microseconds:

- COST_EDIT_START 40000: python3 with the package and the YAML reader loaded
- COST_EDIT_PARSE_PY 5000 and COST_EDIT_PARSE_YAML 5000: one parse and
  comparison of a text of three lines, charged twice
- COST_EDIT_KB_PY 3000 and COST_EDIT_KB_YAML 10000: for each KiB of both texts
- EDIT_ALARM_SECONDS 3: the longest the check may run

The charge is the start, plus twice the parse, plus the KiB of the larger
text times the rate.

- An Edit whose charge is past what is left of the budget is not parsed. At
  these values a Python file is read up to about 780 KiB and a YAML file up
  to about 230 KiB, and a larger file keeps the old verdict.
- The bound that holds for a hostile file is `signal.alarm`. Its default
  action ends the process even inside C code, and the hook then gives the old
  verdict and charges the whole alarm.
- The alarm is the smaller of EDIT_ALARM_SECONDS and what is left before the
  8 second fuse, less one second. With less than one second left no check
  starts.
- A YAML file whose aliases expand to more than 100000 nodes is refused
  without expanding it.
- A slower machine refuses a file that is close to the limit. The refusal is
  safe: the Edit keeps the old verdict.

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

`tests/test_pre_tool_hook_comment_only_edit.py` holds each bound: the time of
the hook is between 0.2 and 3 times the work it charged, and every hostile
shape ends within 6 seconds.

### Path classes and messages

- Path classes. In any project, `evals/*/seed/` by convention holds input
  that an evaluation harness copies into a sandbox and never runs in place,
  so it is not production code and needs no failing test. The pattern starts
  at the project root, and a path with a `..` step cannot get the exemption.
  These stay guarded: `examples/`, `cli/vendor/`, `.github/scripts/`,
  `evals/` outside `seed/`, `src/examples/` and `db/seed/`. The setting
  `enforcement.code_globs` only ratchets up. The same classification serves
  a shell redirect.
- Shell files. A file that `enforcement.code_globs` declares is guarded. A
  shell script, makefile or extensionless script is not a built-in
  production-code file type, so a project declares the ones it wants guarded.
- Messages. On an issue assessed before 9.0.0, the refusal for a missing
  failing test (`no-red-on-record`) names `compass tdd-red` and `compass
  acceptance start`, for a change that has no natural test.
- A `.compass/current-task` that names an issue with no folder under
  `.compass/work/` is not a missing pointer: the hook says so, names the
  issue it falls back to (the issue that changed most recently) and judges
  the Edit by that issue.
- `bad-session-issue` is for a worktree and says to run `compass issue use
  <slug>` there. `bad-session-issue-restart` is for the session's own
  project, where `COMPASS_ISSUE` outranks the pointer: the person restarts
  the session with `COMPASS_ISSUE` naming an existing issue, or without it.

## Shell-write detection

For shell commands the hook recognizes these write shapes, and only these:

- `>`, `>>` and `>|` redirects, including the `cat > file <<EOF` heredoc
  form and a quoted target such as `> "src/app.ts"`
- `sed -i`, and `perl` and `ruby` with `-i` in any flag group, such as
  `-pi`, `-lpi`, `-i.bak` or a `-i` after `-e '...'`, also inside a
  `bash -c` or `sh -c` string
- the arguments of `tee`, and the last argument of `cp` and `mv`, found in
  the same simple command as the `tee`, `cp` or `mv` word, including behind
  a wrapper such as `sudo` or `timeout`. A file that another command in the
  same line only reads is not a target. A `$(...)`, `<(...)`, backtick span
  or line continuation inside the command does not split it, and a write
  inside such a span is found
- `patch -p<n>` and `git apply` - writers with unknowable targets
- an inline interpreter script (`python3 -c`, `node -e`, a heredoc) whose
  write call names its target as a string, or as a name the same script
  assigns a string to (`p = 'app.ts'`). A name that no write call takes is
  not a target

The write calls of an inline script:

| Call | Target |
|---|---|
| `open` with a write mode | first argument, when the mode is the second argument |
| `Path(...).write_text`, `write_bytes` | the path |
| `os.replace`, `os.rename`, `shutil.copy`, `shutil.copy2`, `shutil.copyfile`, `shutil.move` | second argument |
| `writeFileSync`, `appendFileSync`, `File.write` | first argument |

### A target that starts with a variable

A target such as `$S/plant.ts` is judged at the variable's value only when
the same command states that value for certain:

- the command assigns the variable once, to a plain absolute path with no
  `..` step, in a statement that always runs before the write;
- nothing after the assignment names the variable, other than to use it, or
  runs `eval`, `source`, `read`, `declare` or another command that can set a
  variable without naming it.

Any other variable, including one from the environment or from `$(...)`, is
judged as a path inside the project.

### Where a path points

- Before the hook decides whether a path is inside the project, it resolves
  `.`, `..` and repeated slashes as text. A path that differs from the
  project only in letter case counts as inside it.
- A `..` after a part the hook cannot know, such as an unexpanded variable or
  `~`, leaves the real location unknown, so that path is judged inside the
  project. The directories named before the `..` do not exempt it:
  `$X/../tests/../src/app.ts` is judged as production code, not as a test.
- A symbolic link is not followed.

## Hook time limits

Where Compass is in use, the hook refuses a Bash command it cannot scan in
time. In a repository that has not opted in, it skips only the write scan,
and the approval and transcript guards still read the whole command.

| Limit | Value | Refusal code |
|---|---|---|
| Length of the whole command | 98304 bytes (96 KiB) | `bash-command-too-long` |
| Different write targets | 400 | `bash-command-too-complex` |
| Length of one write target, counted in bytes by awk in the C locale | 2048 bytes | `bash-command-too-complex` |
| Different variable names at the start of a write target | 20 | `bash-command-too-complex` |
| `$(` openers | 700 | `bash-command-too-complex` |
| Work budget, shared by the scans that grow with the command | 2400000 microseconds | `bash-command-too-complex` |
| Wall-clock fuse | 8 seconds | `bash-command-too-complex` |
| Time limit of the hook (`"timeout": 15` and `"onFailure": "block"` in `hooks/hooks.json`) | 15 seconds | Claude Code blocks the call, from 2.1.295 |

The length limit:

- The hook never scans a part of a command.
- The refusal names the size and the limit and does not quote the command.
- It is not counted in `.compass/interruptions.log`, because that count
  needs an issue and the hook does not know the issue yet.

The work budget:

- The flattening of substitutions, the walk over the leading statements, the
  reading of the command for each variable name and the judging of each write
  target all add their steps to it.
- The budget is an estimate from a table and reads no clock.
- The text of a command is never read as the count: a write target named
  `compass-scan-work=5000000000000000000` is a target like any other.
- A glob in `enforcement.code_globs` that bash cannot match itself is matched
  by Python once for all the write targets of a command.

The fuse:

- The hook reads bash's own count of seconds (`$SECONDS`) when the script
  starts, and checks it at each write target, at each variable name and at
  each pass of the walk.
- The count has a granularity of one second, so the fuse trips between 7 and
  8 seconds after the script starts. No setting in the environment changes
  it.
- The fuse does not interrupt a process that is running, such as the
  settings reader, or one write target. The work on one target grows with
  the square of its length, which is why a target over 2048 bytes is refused
  and not left to the fuse.

Timings, measured on macOS with bash 3.2, on a machine with 14 cores and a
load average of 2 to 4:

- The largest accepted commands, in seconds: 1.9 for 260 write targets under
  a project whose settings hold 300 globs, 1.9 for 19900 leading `:` lines
  and 1 name, 1.8 for 18200 such lines and 20 names, 1.6 for 9000 leading
  `cd` lines and 20 names, 1.0 for 8000 leading assignments, 1.6 for 5
  unclosed `$(` openers before 85 KB, 1.2 for 400 write targets, 1.4 for 20
  names and 380 other targets under a bracket glob, and 0.2 for 700 closed
  openers.
- The next larger command of each of these shapes is refused, in at most 2.1
  seconds.
- The worst accepted single target, 2048 bytes, took 0.2 seconds in the
  whole hook.
- The Linux runner of the continuous integration takes up to about twice as
  long for the shapes made of many leading lines: the hook took 4.1 seconds
  for 40000 leading `:` lines. The tests therefore allow 6 seconds.
- Without `jq` the hook reads the input with `grep`: 10 KB took 4.4 seconds,
  20 KB took 33.9 seconds and 50 KB did not end in 150 seconds.

## Worktrees

Inside a worktree, Edit and Write follow the worktree's own issue and failing
test, because they name their file and the hook resolves the project from it.

A Bash call whose working folder is in a worktree of the session's repository
is judged by that worktree's issue, by the same rules. The hook reads the
working folder from the `cwd` field of the call, walks up from it to the
nearest `.compass/` folder, and uses that tree when it is not the session's
own project and git ties it to the session's repository. The rules for such
a call:

- A relative path is read against the worktree.
- A path that lands outside the worktree - an absolute path, or a relative
  path that climbs out with `..` - and a path with a part the hook cannot
  know (`~`, a variable it does not expand, a backtick or a brace) are judged
  first, against the session's project and issue. When one of those needs a
  failing test, the session's issue judges the whole command.
- A command that can change its folder has every target judged first against
  the session's project, and a relative path in it is read against the
  session's project.
- A `patch` or `git apply` in a command that can change its folder is judged
  by the session's issue; without one, by the worktree's.
- The `no-red-on-record` refusal names the project whose issue judged the
  write.

The hook matches these folder-changing forms in the command text:

- `cd`, also quoted, inside `bash -c` or a subshell
- `pushd` and `popd`
- a `chdir` call in an inline script
- `env -C`
- `sudo -D` or `--chdir`
- `ruby -C`
- `find -execdir`
- `patch -d` or `--directory`

A shell write resolves from the session's project in these cases:

- the call has no `cwd`;
- the `cwd` is relative or not a folder;
- no `.compass/` folder is found above it;
- the tree is the session's own, or is not tied to the session's repository.

## Records and the manifest

### A test-run record

| Field | Holds |
|---|---|
| `tree_id` | The git tree id of the tracked files on disk plus the issue's own new files. |
| `file_sha256` | The SHA-256 of each of the issue's changed files and of each test file its scenarios declare. |
| `file_modes` | The mode git would record for each of those files. |
| `test_files` | The test files among them. |
| `changes_id` | In a record written before ADR-089: a git tree id of the same files, in place of `file_sha256`. It is still read. |

- The commit side is read as a checkout writes it, so line-ending conversion
  does not count as a change.
- Tracing a file into the issue between two runs of the same command changes
  `file_sha256`, because the traced file joins `changed_files`. It changes
  `tree_id` too only when the file was untracked.
- `evidence/SHA256SUMS` in the issue folder is in the format `sha256sum`
  reads. It holds the SHA-256 of each record file the CLI wrote and of each
  file in the `file_sha256` of the record written last.

### `compass ship-commit`

- In the committed record mode, `ship-commit` writes the landing and
  `trail.md` before the commit and stages the issue record itself.
- A pre-commit step that rewrites a record file before the commit is
  handled: `trail.md` is written again.
- The land commit of a committed record is read from git history.
- When `git commit` leaves HEAD where it was, `ship-commit` stops with the
  lines git printed, in git's own words, then says HEAD did not advance and
  the land did not happen. It adds that a pre-commit hook may be the cause
  only when git can run one here: the hook file exists, at the path git
  reports for `hooks/pre-commit` (so `core.hooksPath` counts), and is marked
  as runnable. A missing author identity therefore reports "Author identity
  unknown" and does not point at a hook.

With nothing staged, `compass ship-commit --issue <slug>` walks the first
parent from HEAD:

- A commit that changes only the living spec, which a branch made before
  9.0.0 can still hold, is passed over.
- A commit judged in full keeps the living spec among its paths, so a hand
  edit of it is refused unless the issue owns it.
- A merge whose merged-in commits are all on the base branch, such as a merge
  of `origin/main`, counts only the paths it changed against every parent,
  which is its conflict resolution, without the living spec.
- Any other merge, such as a multiagent integration merge, is judged in full
  and ends the walk, whatever commit the merged branch started from.
- The walk stops at the issue's newest other commit, which is judged in full.
- The base branch is the remote's default branch (`origin/HEAD`), or
  `origin/main`. When neither resolves, such as in a clone with no remote,
  every merge is judged in full, and the refusal says that the base was not
  found.

### A manifest save

`compass` commands save an issue's `manifest.yml` through
`core.save_manifest`, which `manifest_store.py` implements.

- The save writes a temporary file in the same folder and renames it over
  the manifest. A reader sees the old manifest or the new one, never an
  empty or partial file.
- Reading a manifest takes no lock. A load records the bytes it read. The
  record goes when nothing holds the manifest any more.
- Under `.manifest.lock`, the save reads the file again. When another save
  changed it after this command's load, the save merges this command's
  changes into the file as it is now. The command's manifest then holds the
  merged result, so its next save keeps both commands' changes.
- The merge updates the command's own nested records and does not replace
  them, so a record the command still holds stays part of the manifest.

How the merge treats each kind of value:

| Value | Merge |
|---|---|
| A value both commands changed to different values | The save stops with an error that names the key, and writes nothing. Run the command again. A value of another type, such as `true` for `1`, counts as a different value. |
| A list of records that each carry a distinct `id`, such as `gates` or `evidence` | Record by record, matched by `id`. A record one command removed stays removed when the other left it alone. When the other command changed it, the save stops with an error. The result keeps this command's order of records. A record only the other command added goes after the record it follows in the other's list. |
| Any other list | Position by position. A position both commands changed differently is a conflict. Items each added at the end are all kept, and an item both added is kept once. A list one command shortened while the other changed it is a conflict. |

- A save merges only a manifest that `load_manifest` or
  `manifest_store.load_file` returned, or a copy of one. A save of a mapping
  built any other way, such as the new manifest `compass quick-fix start`
  writes, overwrites the file.
- A test fails when a function in the CLI assigns the result of `load_yaml`
  to the name it then passes to `save_manifest`. It does not follow a mapping
  through other functions.
- The release-line write does not go through `save_manifest`. It holds the
  same lock, reads the file again inside it and replaces the file atomically.
- Every manifest write, the release-line write and `compass migrate`
  included, writes its YAML with `manifest_store.dump`. It writes no anchor
  or alias: a value held under two keys, such as the assessment's `labels`
  list, is written in full under each. A manifest written before can still
  hold `&id001` and `*id001`, and every reader reads it.

[guard-decision]: https://github.com/ayeo-io/compass/blob/main/governance/decisions/2026-10-19-the-approval-guard-judges-words-not-text.md
[comment-decision]: https://github.com/ayeo-io/compass/blob/main/governance/decisions/2026-10-19-a-comment-only-edit-of-code-needs-no-failing-test.md
