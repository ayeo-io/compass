# the-approval-guard-judges-words-not-text

## Decided by

compass:architect, for jed72 (the maintainer). jed72 has not yet confirmed it.

## Date

2026-10-19

## Supersedes

Nothing. It narrows what "name" means in `architecture/decisions/ADR-068-*.md` decision 10 and `ADR-069-*.md` decisions 4 and 8, which stand.

## Decision

The approval guard reads a simple Bash command as words and judges every other command by its whole text. The guard is defense in depth against an accidental or injected read of the session transcript and of approval requests. It is not a hard boundary, because a Write tool call that writes a script, followed by a Bash call that runs it, was open before this change: the earlier hook allowed both calls. The stored hash, the 64-bit code and the person's typed approval are unchanged. The six statements below are the decision. The rule that holds all of them: the guard allows a call that the earlier guard refused only in the places of statement 2, and only for a simple command that holds the protected name in message text or in a listed exemption. A command that is not simple gets the earlier whole-text judgement.

1. **What is a simple command, and what is text.** A command is simple when it is one command, or plain commands joined by `&&`, `;` or a new line, and each of them starts with `git`, `gh`, `ls`, `wc`, `stat` or `cat`, holds no `VAR=` word, function or alias before it, no pipe, `&`, `||`, parenthesis, backtick, comment, heredoc, here-string, process substitution or `eval`, no `$'...'` or `$"..."`, no unquoted brace, glob, tilde, `^` or `#` character, no zsh number range such as `<1-3>`, no `>!`, no descriptor of two digits, no quoted or escaped digit before a redirect, no command that is only a redirect, no `$` outside message text and no `$(`, `${` or backtick inside it. The gate fails closed: a shape it does not name is not simple. The shell expands an unquoted word before the command runs, and the guard judges words as typed, so an unquoted `{a,b}`, `*` or `~` makes the command not simple. What is text is a fixed list, and only a simple command has any: the value of `-m`, `-am` and `--message` of `git commit`, `tag`, `merge` and `revert`, and the value of `--title`, `--body`, `--notes`, `-t` and `-b` of `gh issue`, `gh pr` and `gh release` for the subcommands that take them. A text value must be one quoted word, not joined to its option and not starting with `@`. An option that the gate does not list makes the command not simple, because it may take the next word as its value (`--author -m <path>`) or read a file or a commit (`-F`, `-c`, `-C`, `-t`, `--template`, `--body-file`). A global option before the verb (`git -C`, `git -c`, `gh -R`) makes the command not simple. The guard judges every other word and every redirect target of a simple command by its text.

2. **The loosenings.** The change allows what the guard refused before in these places. Every other call is judged as before.

   | Decision of the requirements review | What it allows or keeps refused |
   |---|---|
   | Which part of a command names a protected thing | The message text of a simple `git` or `gh` command is not judged, including a text that names the delegation folder or `--delegated`. |
   | Where the line falls for `wc`, `stat`, `cd` and a listing | `ls`, `wc` and `stat` may name a request path when they stand alone: a request folder, or a request file for `wc -l` and `stat`. The command takes one operand and only plain options, and the path holds no `..` segment. |
   | Which commands may name the prompt hook script | `cat` alone may name it as a bare argument. Every other command stays refused, including `chmod`, `git add`, `cp`, every runner, `--output`, `--pre` and `--exec`. |
   | Bash on the auto-memory folder | A Bash command on the folder stays refused, although the issue lists `cat` of a memory file as a symptom. |
   | Which paths open to the tools | Read, Grep, Edit and Write open `projects/<one folder>/memory/...` only. Edit and Write need a file inside the folder. A Grep glob with `..` or a brace expansion that holds `..`, `memory/..` and a symbolic link out of the folder stay refused. |
   | A refusal that names the judged word | A refused word, and a refused tool path, lose their control, format and line-separator characters and are cut to 80 characters around the protected part, so a refusal names the part it judged. |

3. **A command that is not simple gets the whole-text judgement, and an unknown command stays refused.** Any text that names a protected thing is refused, as before the change. A command outside the list is not simple, so it has no text position and no exemption. This fails closed. The cost is a harmless call that is still refused when it names a protected thing, such as a commit message built with `$(cat <<'EOF' ... EOF)`. The fix is a visible one-line addition to a list with a test row. A test reads the lists from the code and needs every exempt command to have at least 3 calls that stay refused, so a widening without them fails.

4. **A script written by one command and run by another is not followed.** One call writes and another call runs: not detected. This is an accepted limit. A Write tool call followed by a shell command that runs the file did the same before this change. The same holds for a command, function or alias that an earlier Bash call defined and a later simple command then runs, and for a git alias, git hook or git config that runs a command. The limit rests on different reasons for each protected thing. For the delegation files, the stored hash and the 64-bit code hold, because the hash is stored and the code is not. For the transcript, the confirmation code is written there in clear, so the 64 bits do not hold. What holds is that only a person's typed command confirms a delegation, and the agent cannot type it. A prompt suggestion accepted with Tab can still word that command for the person, so the person's Enter is the only barrier. A broader word reader, which followed text through pipes, heredocs, substitutions and files written in one call, was written and not shipped: two adversarial reviews each found further ways through it. It moves to ayeo-io/compass-delivery-record#247.

5. **No exemption applies inside a pipe or a substitution.** A pipe or a substitution makes the command not simple, so it is judged by its whole text. An exemption also holds only when its command stands alone, with no redirect to a file (a copy of a descriptor such as `2>&1` names no file), one operand, only the plain options `ls -lah1` and `wc -lcwm` allow, and no `..` segment in the path.

6. **The rule this replaces.** The earlier rule was that any text that names the folder is refused. That rule still holds for every command that is not simple. For a simple command, a word that names the folder is refused unless an exemption of statement 5 covers it, and message text is not judged. This reads "name" as a path word for a simple command. ADR-068 decision 10 and ADR-069 decisions 4 and 8 stand in every other respect, and no earlier record changes.

## Why

The guard refused harmless calls: a commit message or a `gh` comment that only mentioned a request folder, the prompt hook script, the transcript folder or `~`. Each refusal cost the agent a turn and the person a confusing message. A call that reads, writes, enters or runs the protected state is still refused, because the guard judges every word of a simple command and the whole text of any other. The loosenings are the places where message text, or a bare path argument of a listing, cannot read, write, enter or run the protected state, and each has a test of the harmful twin that must stay refused.

## Evidence

- Requirements review of issue `hooks-stop-refusing-harmless-work`: the decisions on the text positions, the listing commands, the reader of the prompt hook script, the auto-memory folder, the refused word and the accepted write-then-run limit, and the architect's decision to narrow the change to the simple-command gate.
- GitHub issue ayeo-io/compass-delivery-record#238, "Stop the approval guard refusing harmless work and name the real cause of a refusal".
- GitHub issue ayeo-io/compass-delivery-record#222, "Stop the pre-tool hook blocking writes to the auto-memory folder".
- GitHub issue ayeo-io/compass-delivery-record#247, the broader word reader that this change did not ship.
- Tests: `tests/test_approval_guard_*.py`, `tests/test_approval_words.py` and `tests/approval_guard_cases.py`, which hold the refused and allowed calls. `tests/test_approval_guard_review_fixes.py` and `tests/test_approval_guard_fail_closed.py` hold the calls that the adversarial reviews found.
