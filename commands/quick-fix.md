---
description: Start, change and finish an issue in three commands
argument-hint: "<what needs fixing>"
allowed-tools: Read, Write, Edit, Bash(compass *), Glob, Grep
---

# /compass:quick-fix

**Issue:** $ARGUMENTS

One path serves every change. One request is one issue. Do not open a second
issue for follow-on work in the same request; add it to this one. No `--help`
is needed.

1. Start, once:

   ```
   compass quick-fix start <slug> --intent "<what will be true afterwards>" \
     --request <issue URL or owner/repo#N> --requester "<who asked>"
   ```

   Add `--labels <label,...>` only for `auth`, `payments`, `personal-data`
   or `migrations`.

2. Only with one of those labels: write every scenario in the
   `acceptance-criteria.md` that `start` names, each in the form of the first
   one. Run `compass evidence request --checkpoint specify`, ask the person to
   type `/compass:approve <n>`, and stop. Code edits are refused until then.

3. Write the tests and the code. Run the tests directly. A change needs a
   test file that fails without it.

4. Finish:

   ```
   compass quick-fix finish -m "<commit message>" -- <test command>
   ```

   It writes the whole record and requests the approvals owed. Do what its
   `next:` line says. After more edits, run it again.

5. When the person asks for a commit, switch to the branch they want and run
   `compass ship-commit`. It commits the code with the record under
   `.compass/` and `docs/compass/`; that is intended.

