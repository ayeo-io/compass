---
id: ADR-075
title: A readiness command's process group stops with SIGTERM, then SIGKILL after two seconds
status: accepted
date: 2026-10-19
supersedes: ''
superseded_by: ''
---

Decided for adr-061-process-group-fix on 2026-10-19, from ayeo-io/compass-delivery-record#7. The code described here is already merged (ayeo-io/compass#556, scenario PRC-45).

## Context

ADR-061 decision 5 says that at its limit a command's whole process group is sent `SIGKILL`. The code does more. `cli/compass_pkg/readiness_run.py` stops the group on every exit path, and it sends `SIGTERM` first so a build tool can clean up. A reader who trusts ADR-061 alone would think a command that exits, is interrupted or fails is not stopped. ADR-061 is an accepted record, so a correction is a new entry and not an edit.

## Decision

This record amends decision 5 of ADR-061. It does not supersede ADR-061. The rest of ADR-061 stands.

1. **Each command runs in its own session**, as ADR-061 says, so its process group can be signalled without touching the run.
2. **The group is sent `SIGTERM`, then `SIGKILL` after `STOP_GRACE_SECONDS`.** `STOP_GRACE_SECONDS` is 2. A group with no process left is not signalled again.
3. **The group is stopped on every exit path**: normal exit of the command, its time limit, an interrupt (Ctrl-C or `SIGTERM` to the run) and an error raised in the runner.
4. **The group is stopped before the temporary worktree is removed**, so no child process can outlive the run or write into a deleted tree.

## Alternatives considered

- **`SIGKILL` at the limit only (ADR-061 decision 5 as written).** A child of a command that exits normally, or of a run that is interrupted, stays alive. Rejected.
- **`SIGKILL` at once on every path.** A build tool gets no chance to clean up its own files. Rejected.
- **Wait without a bound after `SIGTERM`.** A command that ignores `SIGTERM` would hold the run. The two-second bound avoids that.

## Consequences

- No process from a readiness command outlives the run, on any exit path.
- A command that needs more than two seconds to clean up after `SIGTERM` is killed.
- `docs/readiness.md` and `docs/security.md` already describe this behaviour. They stay as they are.
- A reader of ADR-061 decision 5 must read this record for the stop sequence.

## References

- ADR-061 - Measuring a repository runs project commands under the trust order (decision 5).
- `cli/compass_pkg/readiness_run.py` - `_stop` and `STOP_GRACE_SECONDS`.
- `docs/readiness.md` and `docs/security.md` - the user-facing statements.
- ayeo-io/compass#556 - Cap autonomous work by repository readiness.
- ayeo-io/compass-delivery-record#7 - Correct ADR-061 on when a readiness command's process group stops.
