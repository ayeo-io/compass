# the-approval-guard-judges-words-not-text

## Decided by

jed72

## Date

2026-10-19

## Supersedes

Nothing. It narrows what "name" means in `architecture/decisions/ADR-068-*.md` decision 10 and `ADR-069-*.md` decisions 4 and 8, which stand.

## Decision

The approval guard reads a Bash command as words and judges each command name, redirect target and argument. It does not judge text. The six statements below are the decision. The rule that holds all of them: the guard never allows a call that the earlier guard refused, unless the call holds only harmless text.

1. **What is text, and what is judged again.** What is text is a fixed list: every argument of `echo` and `printf`; the value of `-m` and `--message` of `git commit`, `tag`, `merge` and `revert`; the value of `--grep`, `-S` and `-G` of `git log`; the search pattern of `grep`, `egrep`, `fgrep`, `rg` and `git grep` (not of `rg --files`, which takes none); the value of `--body`, `-b`, `--title` and `-t` of `gh`; the value of `--title`, `--note`, `--reason`, `--scope` and `--description` of `compass`; and the heredoc body or here-string of `cat`, `tee`, `compass`, `git` (in a `commit`, `tag`, `merge` or `revert`) and `gh` (in `gh issue`, `gh pr` and `gh release`). Text is judged again, as it would be judged as words, in these cases:
   - Inside `$(...)`, backticks and `<(...)`. What a substitution prints is judged as the word it stands for, so `cat "$(echo <file>)"` and `x=$(echo 'cat <file>'); $x` name the file. A substitution stays text only when it stands in a text position of its outer command and of every command above it, such as a commit message. The commands inside are judged either way, so `git commit -m "$(cat <<'EOF' ... EOF)"` is allowed and `git commit -m "$(cat <file>)"` is refused.
   - When a later stage of its pipeline is not a command that only reads text. A stage given an option that starts `--fil`, such as `sort --files0-from=-`, reads the files its input names and is not such a command.
   - As a heredoc or here-string for a shell or any command outside the list, including `gh alias import -`, which reads aliases from standard input and runs a shell for an alias that starts with `!`.
   - As the argument of `bash -c` and `eval`.
   - As a script that one call writes and then runs (statement 4).

   The reader keeps a backslash and newline inside the body of a quoted heredoc and inside a comment, as the shell does. A line that ends in a backslash before the delimiter ends a quoted heredoc there, and the next line is a command.

2. **The nine loosenings.** The change allows what the guard refused before in nine places. Every other call is judged as before.

   | Decision of the requirements review | What it allows or keeps refused |
   |---|---|
   | Which part of a command names a protected thing, and the allowlist of text positions | Text in the named commands and options is not judged, and no exemption applies inside a pipe or a substitution. |
   | Where the line falls for `wc`, `stat`, `cd` and a listing | `ls`, `wc`, `stat`, `du`, `test` and `[` may name a request path when they stand alone. |
   | Which commands may name the prompt hook script | Readers and index commands may name it as a bare argument: `cat`, `head`, `tail`, `grep`, `rg`, `diff`, a `chmod` that keeps the execute bit, and `git log`, `show`, `diff`, `blame`, `status`, `ls-files` and `add`. `git mv`, `git rm`, `cp`, every runner, `--output`, `--pre` and `--exec` stay refused. |
   | Bash on the auto-memory folder | A Bash command on the folder stays refused, although the issue lists `cat` of a memory file as a symptom. |
   | Which paths open to the tools | Read, Grep, Edit and Write open `projects/<one folder>/memory/...` only. A Grep glob with `..` or a brace expansion that holds `..`, `memory/..` and a symbolic link out of the folder stay refused. |
   | A listing above the configuration folder | A non-recursive `ls` of a folder strictly above the configuration folder is allowed, after the path is normalized. `cd` into it stays refused. |
   | What counts as the word `compass` | The word `compass` means a word equal to it or ending in `/compass`, so `compass-700` no longer counts for ANSI-C quoting. |
   | A commit message that names the delegation folder | Text that names the delegation folder is allowed. A delegation path as a word stays refused for every command. |
   | A refusal that names the judged word | A refused word loses its control, format and line-separator characters and is cut to 80 characters around the protected part, so a refusal names the word it judged. |

3. **An unknown command stays refused.** A command outside the lists has no text positions and no exemption, so the guard judges every word of it as before. This fails closed. The cost is a harmless call outside the lists that is still refused, and the fix is a visible one-line addition to a list with a test row. A test reads the lists from the code and requires every exempt command to have at least 3 calls that stay refused, so a widening without them fails.

4. **A script written by one command and run by another is not followed.** One call writes and another call runs: not detected. This is an accepted limit. A Write tool call followed by `bash /tmp/s.sh` did the same before this change. Within one call the guard follows a script through these shapes: the text of `echo`, `printf` and a `cat` heredoc or here-string, through the pipe stages that only read text; a write by a redirect or `tee`, also through a brace group or a subshell; `cp`, `mv` and `ln` of the file; `cd` and a relative name; and a run by any command that is not a data command, as a word, inside a quoted word, or as a `<` redirect (`env bash f`, `bash -o pipefail f`, `bash -c 'source f'`, `find f -exec sh {} \;`, `rg --pre sh . f`). It does not follow a file written by another command (`dd`, `sed -i`, `curl -o`, an interpreter), a script built at run time, or a folder reached by `cd` with a variable or `~` (matched by file name alone). The limit rests on different reasons for each protected thing. For the delegation files, the stored hash and the 64-bit code hold, because the hash is stored and the code is not. For the transcript, the confirmation code is written there in clear, so the 64 bits do not hold. What holds is that only a person's typed command confirms a delegation, and the agent cannot type it. A prompt suggestion accepted with Tab can still word that command for the person, so the person's Enter is the only barrier.

5. **No exemption applies inside a pipe or a substitution.** An exemption holds only when its command stands alone. A listing command in a pipe, in `$(...)`, in backticks or in `<(...)` is judged as any other command.

6. **The rule this replaces.** The earlier rule was that any text that names the folder is refused. The replacement is that a word that names the folder is refused and text is not judged. This reads "name" as a path word. ADR-068 decision 10 and ADR-069 decisions 4 and 8 stand in every other respect, and no earlier record changes.

## Why

The guard refused harmless calls: a commit message, a `gh` comment, an `echo`, a `grep` pattern or a document heredoc that only mentioned a request folder, the prompt hook script, the transcript folder or `~`. Each refusal cost the agent a turn and the person a confusing message. A call that reads, writes, enters or runs the protected state is still refused, because the guard judges every word that can name a path. The loosenings are the places where a word cannot read, write, enter or run the protected state, and each has a test of the harmful twin that must stay refused.

## Evidence

- Requirements review of issue `hooks-stop-refusing-harmless-work`: the decisions on the allowlist of text positions, the listing commands, the readers of the prompt hook script, the auto-memory folder, the word `compass`, the delegation folder named in text, the refused word and the accepted write-then-run limit, and its table "Decisions that change what a guard allows".
- GitHub issue ayeo-io/compass-delivery-record#238, "Stop the approval guard refusing harmless work and name the real cause of a refusal".
- GitHub issue ayeo-io/compass-delivery-record#222, "Stop the pre-tool hook blocking writes to the auto-memory folder".
- Tests: `tests/test_approval_guard_*.py` and `tests/approval_guard_cases.py`, which hold the refused and allowed calls. `tests/test_approval_guard_review_fixes.py` holds the calls that the adversarial review of the first version found.
