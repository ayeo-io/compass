# Adapter behaviour checks

The local suite checks that Claude Code and Codex reach the same shared kit
behaviour. It starts scratch repositories and runs real CLI commands through
each adapter entry. It does not start either runtime's model or grant hook trust.

```bash
python3 -m pytest tests/test_adapter_behaviour.py -q
```

The runner lives in `tests/adapter_conformance/`. It removes inherited Git
repository selectors, binds each issue explicitly and keeps commands inside
scratch projects. The Claude Code entry is `bin/compass`. The Codex entry gets
the shared source root from the adapter's context command, then calls its CLI.

## What the local suite checks

| Case | Observed behaviour |
|---|---|
| Assessment | Equal computed approaches and required gates, including the marketer's claims gate. |
| Quick fix | Genuine failing and passing tests, recorded by the kit, and completed local checks. |
| Local handoff | The other entry reads the same issue and preserves manifest and evidence bytes before continuing, in both directions. |
| Regular feature | Stored policy generation, required artifact and gate records, and genuine red/green evidence. Review gates remain pending. |
| Evidence comparison | Changed policy, gate or approval subjects differ; tampered raw evidence fails the kit check before comparison. |
| Hook payloads | Equivalent file, move and shell decisions for unassessed, assessed without red, recorded red and spike states. |
| Approval scope | Explicitly synthetic inputs distinguish a matching guardrail approval from a missing or unrelated subject. No person signs these fixtures. |
| Worktree ceiling | The shared provisioner's dry-run permits the boundary and refuses excess requests. No worktrees or agents start. |
| Isolation | Inherited Git settings cannot select another repository. |

The comparator checks raw state with `compass issue lint` and `compass check`
first. It then removes only record identifiers, digests, test timestamps, test
log presentation and artifact approval timestamps. It keeps policy, tree
bindings, results, gate links, approval subjects and other persisted meaning.
Optional absent claims and follow-ups become empty lists. Raw records stay intact.

The capture helper records its format version, entry, revision, runner digest,
environment, commands, expected result and observed result. A local result is
`passed` or `failed`. Native and independent results remain `unmeasured`.
Two adapters agreeing on a wrong result does not pass an expected-behaviour check.

## What needs a native session

Local handoff checks file compatibility. A native session must separately show
that the host loads instructions, invokes the kit, dispatches trusted hooks,
binds session identity and resumes after a cold start or context compaction.
The local suite cannot establish those behaviours.

Use the [install smoke test](install-smoke-test.md) in each runtime. For a
cross-runtime journey, start the same fixed issue in each runtime and resume it
in the other. Keep the original manifest, policy generation and evidence files.
Compare their meaning with the rules above after the kit accepts the raw records.
Do not clear pending review gates with synthetic approvals.

Record each native case with:

- framework revision, host version, OS and installation method;
- hook discovery, trust state and the action the tester tried;
- issue, assessment, required artifacts and gate decisions;
- commands, exit codes and paths to unchanged raw records;
- expected and observed behaviour;
- `passed`, `failed`, `unsupported` or `unmeasured`, with the reason;
- tester identity and whether the tester is independent of the implementation.

A clean-machine install needs a machine without prior Compass wiring. An
independent acceptance run needs another person to install Compass and complete
an issue. Temporary configuration on the author's machine proves neither.
These results remain unmeasured until the matching evidence exists.

See [the portability contract](portability.md) and
[Codex installation and control support](codex.md) for the adapter boundary.
