# the-approval-guard-judges-words-not-text

## Decided by

jed72

## Date

2026-10-19

## Supersedes

Nothing. It narrows what "name" means in `architecture/decisions/ADR-068-*.md` decision 10 and `ADR-069-*.md` decisions 4 and 8, which stand.

## Decision

The approval guard reads a Bash command as words and judges each command name, redirect target and argument. It does not judge text. The six statements below are the decision.

1. **What is text, and what is judged again.** What is text is a fixed list: every argument of `echo` and `printf`; the value of `-m` and `--message` of `git commit`, `tag`, `merge` and `revert`; the value of `--grep`, `-S` and `-G` of `git log`; the search pattern of `grep`, `egrep`, `fgrep`, `rg` and `git grep`; the value of `--body`, `-b`, `--title` and `-t` of `gh`; the value of `--title`, `--note`, `--reason`, `--scope` and `--description` of `compass`; and the heredoc body or here-string of `cat`, `tee`, `gh`, `git` and `compass`. Text is judged again, as it would be judged as words, inside `$(...)`, backticks and `<(...)`; when a later stage of its pipeline is not a command that only reads text; as a heredoc or here-string for a shell or any command outside the list; as the argument of `bash -c` and `eval`; and as a script that one command writes and then runs.

2. **The nine loosenings.** The change allows what the guard refused before in nine places. Every other call is judged as before.

   | Entry in the requirements review | What it allows or keeps refused |
   |---|---|
   | Q1 and Q2 | Text in the named commands and options is not judged, and no exemption applies inside a pipe or a substitution. |
   | Q3 | `ls`, `wc`, `stat`, `du`, `test` and `[` may name a request path when they stand alone. |
   | Q4 | Readers and index commands may name the prompt hook script as a bare argument. `cp`, every runner, `--output`, `--pre` and `--exec` stay refused. |
   | Q5 | A Bash command on the auto-memory folder stays refused, although the issue lists `cat` of a memory file as a symptom. |
   | Q6 | Read, Grep, Edit and Write open `projects/<one folder>/memory/...` only. A Grep glob with `..`, `memory/..` and a symbolic link out of the folder stay refused. |
   | Q7 | A non-recursive `ls` of a folder strictly above the configuration folder is allowed, after the path is normalised. `cd` into it stays refused. |
   | Q8 | The word `compass` means a word equal to it or ending in `/compass`, so `compass-700` no longer counts for ANSI-C quoting. |
   | Q9 | Text that names the delegation folder is allowed. A delegation path as a word stays refused for every command. |
   | Q16 | A refused word is cut to 80 characters and loses its control characters, so a refusal names the word it judged. |

3. **An unknown command stays refused.** A command outside the lists has no text positions and no exemption, so the guard judges every word of it as before. This fails closed. The cost is a harmless call outside the lists that is still refused, and the fix is a visible one-line addition to a list with a test row.

4. **A script written by one command and run by another is not followed.** The guard follows a script only when one command writes and runs it. The two cases rest on different reasons. For the delegation files, the stored hash and the 64-bit code hold, because the hash is stored and the code is not. For the transcript, the confirmation code is written there in clear, so the 64 bits do not hold. What holds is that only a person's typed command confirms a delegation, and the agent cannot type it. A prompt suggestion accepted with Tab can still word that command for the person, so the person's Enter is the only barrier.

5. **No exemption applies inside a pipe or a substitution.** An exemption holds only when its command stands alone. A listing command in a pipe, in `$(...)`, in backticks or in `<(...)` is judged as any other command.

6. **The rule this replaces.** The earlier rule was that any text that names the folder is refused. The replacement is that a word that names the folder is refused and text is not judged. This reads "name" as a path word. ADR-068 decision 10 and ADR-069 decisions 4 and 8 stand in every other respect, and no earlier record changes.

## Why

The guard refused harmless calls: a commit message, a `gh` comment, an `echo`, a `grep` pattern or a document heredoc that only mentioned a request folder, the prompt hook script, the transcript folder or `~`. Each refusal cost the agent a turn and the person a confusing message. A call that reads, writes, enters or runs the protected state is still refused, because the guard judges every word that can name a path. The loosenings are the places where a word cannot read, write, enter or run the protected state, and each has a test of the harmful twin that must stay refused.

## Evidence

- Requirements review of issue `hooks-stop-refusing-harmless-work`, entries Q1 to Q9, Q16, Q17 and Q24 and the table "Decisions that change what a guard allows".
- GitHub issue ayeo-io/compass-delivery-record#238, "Stop the approval guard refusing harmless work and name the real cause of a refusal".
- GitHub issue ayeo-io/compass-delivery-record#222, "Stop the pre-tool hook blocking writes to the auto-memory folder".
- Tests: `tests/test_approval_guard_*.py` and `tests/approval_guard_cases.py`, which hold the refused and allowed calls.
