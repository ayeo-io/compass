---
description: Start the issue for a request, or start a spike
argument-hint: "<the request>"
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:assess

**Request:** $ARGUMENTS

One request is one issue. Do not open a second issue for follow-on work in
the same request; add it to this one.

No `--help` is needed.

1. Start, once:

   ```
   compass quick-fix start <slug> --intent "<what will be true afterwards>" \
     --request <issue URL or owner/repo#N> --requester "<who asked>"
   ```

   Add `--labels <label,...>` only for `auth`, `payments`, `personal-data`
   or `migrations`.

2. Only with one of those labels: write every scenario in the
   `acceptance-criteria.md` that `start` names, each in the form of the first
   one, with the next `TRC-` id.
   Run `compass evidence request --checkpoint specify`, ask the person to type
   `/compass:approve <n>`, and stop. Code edits are refused until then.

3. Write the tests and the code. Run the tests directly.

4. Finish:

   ```
   compass quick-fix finish -m "<commit message>" -- <test command>
   ```

   It proves the tests fail without the change, traces the changed files,
   runs the checks and requests the approvals owed. Do what its `next:` line
   says. After more edits, run it again.

5. When the person asks for a commit, switch to the branch they want and run
   `compass ship-commit`. It commits the code with the record under
   `.compass/` and `docs/compass/`; that is intended.

If you cannot state what will be true afterwards, it is a spike: follow
`${CLAUDE_PLUGIN_ROOT}/approaches/assess-procedure.md`.
