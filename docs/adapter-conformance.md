# Adapter behaviour checks

The local suite checks the shared kit behaviour that the Claude Code adapter
reaches. Compass 9.0.0 supports Claude Code only; the Codex adapter, which the
suite also compared, stays on 8.x. The suite starts scratch repositories and
runs real CLI commands through the adapter entry. It does not start the
runtime's model or grant hook trust.

```bash
python3 -m pytest tests/test_adapter_behaviour.py -q
```

The runner is in `tests/adapter_conformance/`. It removes inherited Git
repository selectors, binds each issue explicitly and keeps commands inside
scratch projects. The Claude Code entry is `bin/compass`.

## What the local suite checks

| Case | Observed behaviour |
|---|---|
| Assessment | The computed approach and required gates for each assessment. |
| Quick fix | Genuine failing and passing tests, recorded by the kit, and completed local checks. |
| Local handoff | A second entry reads the same issue and preserves manifest and evidence bytes before continuing. |
| Regular feature | Stored policy generation, required artifact and gate records, and genuine red/green evidence. Review gates remain pending. |
| Evidence comparison | Changed policy, gate or approval subjects differ; tampered raw evidence fails the kit check before comparison. |
| Hook payloads | File, move and shell decisions for unassessed, assessed without red, recorded red and spike states. |
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
A capture passes only when it matches the expected result.

## What needs a native session

Local handoff checks file compatibility. A native session must separately show
that the host loads instructions, invokes the kit, dispatches trusted hooks,
binds session identity and resumes after a cold start or context compaction.
The local suite cannot establish those behaviours.

Use the [install smoke test](install-smoke-test.md). For a resume journey,
start a fixed issue in one session and resume it in another. Keep the original
manifest, policy generation and evidence files. Compare their meaning with the
rules above after the kit accepts the raw records. Do not clear pending review
gates with synthetic approvals.

Record each native case with:

- framework revision, host version, OS and installation method;
- hook discovery, trust state and the action the tester tried;
- issue, assessment, required artifacts and gate decisions;
- commands, exit codes and paths to unchanged raw records;
- expected and observed behaviour;
- `passed`, `failed`, `unsupported` or `unmeasured`, with the reason;
- tester identity and whether the tester is independent of the implementation.

A clean-machine install needs a machine without a prior Compass installation. An
independent acceptance run needs another person to install Compass and complete
an issue. Temporary configuration on the author's machine proves neither.
These results remain unmeasured until the matching evidence exists.

See [the portability contract](portability.md) for the adapter boundary.
