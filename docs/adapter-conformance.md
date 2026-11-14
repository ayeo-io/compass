# Adapter behaviour checks

The local suite checks the shared kit behavior that the Claude Code adapter
reaches. It starts scratch repositories and runs real CLI commands through
the adapter entry, `bin/compass`. It does not start the runtime's model or
grant hook trust.

```bash
python3 -m pytest tests/test_adapter_behaviour.py -q
```

Compass 9.0.0 supports Claude Code only. The Codex adapter stays on 8.x.

The runner is in `tests/adapter_conformance/`. It removes inherited Git
repository selectors, binds each issue explicitly and keeps commands inside
scratch projects.

## What the local suite checks

| Case | Observed behavior |
|---|---|
| Assessment | The computed approach and required gates for each assessment. |
| Quick fix | Real failing and passing tests, recorded by the kit, and completed local checks. |
| Local handoff | A second entry reads the same issue and keeps the manifest and evidence bytes before it continues. |
| Regular feature | Stored policy generation, required artifact and gate records, and real red and green evidence. Review gates stay pending. |
| Evidence comparison | Changed policy, gate or approval subjects differ. Tampered raw evidence fails the kit check before comparison. |
| Hook payloads | File, move and shell decisions for an unassessed issue (refused), a started issue and one with a recorded red (allowed), an issue that owes approval of its scenarios (refused until it is on record) and a spike (allowed). |
| Approval scope | Synthetic inputs tell a matching guardrail approval from a missing or unrelated subject. No person signs these fixtures. |
| Worktree ceiling | The shared provisioner's dry run permits the boundary and refuses requests over it. No worktrees or agents start. |
| Isolation | Inherited Git settings cannot select another repository. |

The comparator:

1. Checks raw state with `compass issue lint` and `compass check`.
2. Removes only record identifiers, digests, test timestamps, test log
   presentation and artifact approval timestamps.
3. Keeps policy, tree bindings, results, gate links, approval subjects and
   other stored meaning. Absent optional claims and follow-ups become empty
   lists. Raw records stay intact.

The capture helper records its format version, entry, revision, runner
digest, environment, commands, expected result and observed result.

- A local result is `passed` or `failed`. A capture passes only when it
  matches the expected result.
- Native and independent results stay `unmeasured`.

## What needs a native session

The local suite cannot show that the host loads instructions, invokes the
kit, dispatches trusted hooks, binds session identity, or resumes after a
cold start or context compaction. A native session must show each of those.

1. Run the [install smoke test](install-smoke-test.md).
2. For a resume journey, start a fixed issue in one session and resume it in
   another.
3. Keep the original manifest, policy generation and evidence files.
4. After the kit accepts the raw records, compare their meaning with the
   comparator rules above.

Do not clear pending review gates with synthetic approvals.

Record each native case with:

- framework revision, host version, OS and installation method;
- hook discovery, trust state and the action the tester tried;
- issue, assessment, required artifacts and gate decisions;
- commands, exit codes and paths to unchanged raw records;
- expected and observed behavior;
- `passed`, `failed`, `unsupported` or `unmeasured`, with the reason;
- tester identity and whether the tester is independent of the
  implementation.

Two results stay unmeasured until their evidence exists:

- A clean-machine install needs a machine with no earlier Compass
  installation.
- An independent acceptance run needs another person to install Compass and
  complete an issue.

Temporary configuration on the author's machine shows neither.

See [the portability contract](portability.md) for the adapter boundary.
