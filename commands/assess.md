---
description: Start the issue for a request, or start a spike
argument-hint: "<the request> [--reassess --reason <why>]"
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:assess

**Request:** $ARGUMENTS

One request is one issue. Never start a second issue for follow-on work or
feedback in the same request; add it to this one.

1. Start, once:

   ```
   compass quick-fix start <slug> --intent "<what will be true afterwards>" \
     --request <issue URL or owner/repo#N> --requester "<who asked>"
   ```

   Add `--labels <label,...>` only for `auth`, `payments`, `personal-data`,
   `migrations` or a label the project adds, and `--risk "critical - <why>"`
   only for critical risk.

2. Only with one of those: write every scenario in the
   `acceptance-criteria.md` that `start` names, each in the form of the first
   one, with the next `TRC-` id. Run `compass evidence request --checkpoint
   specify`, ask the person to type `/compass:approve <n>`, and stop. Code
   edits are refused until then.

3. Write the tests and the code. Run the tests, and the project's linters
   and type checker if it has them.

4. Finish:

   ```
   compass quick-fix finish -m "<commit message>" -- <test command>
   ```

   It writes the whole record. When its `next:` line asks for a person's
   approval, stop. It commits once a person has approved, on a new branch if
   you are on the default one. Do not check that commit again.

5. After feedback, edit and run `finish` again, once.

If you cannot state what will be true afterwards, it is a spike: follow
`${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md`. Follow it also for
`/compass:assess --reassess --reason "<why>"`, when an issue outgrew its
assessment: it logs the reason in the manifest's `reassessments:`.
