<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/compass-header-dark.svg">
    <img src="assets/compass-header-light.svg" alt="Compass" height="64">
  </picture>
</h1>

**Adaptive spec-driven development for Claude Code.**

[![Self-check](https://github.com/ayeo-io/compass/actions/workflows/compass.yml/badge.svg?branch=main)](https://github.com/ayeo-io/compass/actions/workflows/compass.yml)
[![Docs](https://github.com/ayeo-io/compass/actions/workflows/docs.yml/badge.svg?branch=main)](https://docs.ayeo.io/compass/)
[![Latest release](https://img.shields.io/github/v/release/ayeo-io/compass)](https://github.com/ayeo-io/compass/releases)
[![License](https://img.shields.io/github/license/ayeo-io/compass)](LICENSE)

> Enough process for the work at hand. No more.

A typo fix should not need an architecture pack. A payments rewrite should
not begin with an unstructured prompt.

Compass assesses each change by **risk, familiarity and size**, then a
deterministic policy composes the delivery approach: which stages run at what
depth, which documents are worth writing, which checks run, and where a person
decides. In a project that uses Compass, five guardrails apply to every
approach that ships code, and no assessment for that work removes one. A spike
ships nothing, so two spike guardrails replace them: it must record a
conclusion and change no production file
([safety contract](docs/safety-contract.md#4-a-spike-cannot-silently-become-delivery)).

<p align="center">
  <img src="assets/compass-explainer.svg" alt="Three sliders for risk, familiarity and size feed a policy. As the work changes from a typo fix to a payments rewrite, the eight stage bars grow from a quick fix to the full approach, dots mark the stages where a person decides, and five guardrail lines stay the same." width="960">
</p>

Judgment goes into the assessment. Everything after it is computed from three
inputs: the assessment, the project's resolved configuration and the documents
the issue has on disk. The same three inputs give the same approach, every
time ([safety contract](docs/safety-contract.md#1-routing-is-deterministic-after-assessment)).

## Install

From a shell, in one line:

```bash
claude plugin install compass --marketplace ayeo-io/compass
```

Or from inside Claude Code, in two commands:

```text
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Or from source:

```bash
git clone https://github.com/ayeo-io/compass.git
cd compass
bash scripts/install.sh --global
```

Add `bin/` to your `PATH` to make `compass` invokable, or call it as
`python3 cli/compass`. Needs Python 3.10 or later. See
[docs/install-smoke-test.md](docs/install-smoke-test.md) for checks and
troubleshooting.

## The first issue

Describe the work:

```text
/compass:go "Add rate limiting to the public API"
```

`/compass:go` assesses the change, shows the plan in three lines and starts.
`/compass:assess` does the assessment alone. When the approach reaches a stage
that waits for a person, the session stops and shows a request. You answer
in the same session:

```text
/compass:approve
/compass:reject "the criteria miss the burst case"
```

`/compass:status` reports what is blocked, moving and done. `/compass:resume
<issue>` picks an issue up in a later session, from its record on disk.
To write the specs and plans an issue asks for, read
[docs/writing-specs-and-plans.md](docs/writing-specs-and-plans.md).

The shipped guardrails are active from the first command. Project settings,
and a project's own changes to the shipped defaults, live in one file,
`compass.yml` ([docs/configuration.md](docs/configuration.md)). Upgrading from
6.x? Read [docs/upgrade-7-0-0.md](docs/upgrade-7-0-0.md); from 5.x, read
[docs/upgrade-6-0-0.md](docs/upgrade-6-0-0.md) first. To mirror an issue's
labels on its GitHub issue, see [docs/github-labels.md](docs/github-labels.md).

Compass complements your normal CI. It does not replace tests, linting,
security scanning, builds or deployment checks.

## What Compass changes

Compass chooses the process for each change from its assessment of risk,
familiarity and size.

| Work | Typical Compass response |
|---|---|
| **Quick fix** | One clear criterion, a focused change and evidence that it works. |
| **Regular** | Behavioral specification in Gherkin, proportionate technical design and review. |
| **Full** | Intent document, acceptance criteria, a thorough requirements review and technical design, and a distribution map for parallel work. |
| **Hotfix** | Reproduce first, fix safely, then do the follow-up work skipped for speed. |
| **Spike** | Time-boxed exploration. Record the learning; ship nothing directly. |

These are reference shapes, not fixed levels. A one-file authentication change
can get more protection than a large throwaway prototype, because risk and
size are different things. Optional switches for goal and urgency pick the
spike, and the hotfix for a small live defect.

## Rigor without ritual

Compass keeps two kinds of rule apart:

- **Guardrails** are few and checkable: tested before shipping, acceptance
  defined before implementation, every change traced to a criterion,
  evidence rather than assertion, and a person's approval for a change
  labelled `auth`, `payments`, `personal-data` or `migrations`. `compass
  check` fails on a breach under enforced adoption, and the
  [safety contract](docs/safety-contract.md) lists what it cannot see.
- **Strategies** are strong defaults that improve the work without becoming
  bureaucracy: BDD, TDD, decision records, architecture models and other
  practices that apply when they add value.

An approach can reduce the amount of process. On an approach that ships, it
cannot remove a guardrail. A project can make failures non-blocking with
`adoption: advisory` ([configuration](docs/configuration.md#adoption)), and
can depart from the shipped guardrails only through the owner's recorded
waiver, after which every `compass check` reports the project as
non-conformant
([safety contract](docs/safety-contract.md#2-a-declared-guardrail-cannot-silently-become-advice)).

## A person stays in control

- **Approvals are a person's act.** In Claude Code you type
  `/compass:approve` or `/compass:reject`; at a terminal you run `compass
  evidence approve`. An agent cannot type the command that records an
  approval, because Claude Code does not let the model run `/compass:approve`.
  An agent records one only under a delegation you made, and a program
  running as your own user account is not stopped
  ([safety contract](docs/safety-contract.md#5-irreversible-work-needs-recorded-human-approval)).
- **You set the bounds of a delegation.** A bare `/compass:delegate` lets the
  agents of this session approve for you on every issue, until
  `/compass:revoke` ends it. Flags set its bounds: `--agent` names one agent,
  in any session; `--until`, `--on`, `--for` and `--max` narrow it. `--for g5`, which covers irreversible work, needs a code that
  you type back. Compass lists each delegation with no end time at each new
  session start. Every delegated approval is on record, and you can overrule
  one; overruling a guardrail 5 sign-off does not undo work already landed.
- **Autonomy is a setting, not a promise.** `autonomy: controlled | balanced
  | autonomous` in `compass.yml` says how often a session stops for a person.
  An autonomous project must first pass the readiness floor: an agent
  instructions file, a build, a test suite under two minutes and a clean
  lint, measured by `compass readiness`. Below the floor, assess refuses.
- **Decisions an agent takes for you are listed.** On `balanced` and
  `controlled`, the next checkpoint waits for you to confirm or change them.

## Resumable and auditable

Every issue leaves a reviewable record. Its documents are in
`docs/compass/<created>-<issue>/`; its manifest, evidence and markers are in
`.compass/work/<issue>/`. Another session can resume from that record without
the chat history, and a reviewer can open the evidence behind each gate.

`compass board render` shows every issue on one page, with a lane for each
stage. This example is an invented invoicing product:

![The Compass board for an invented invoicing product: a backlog lane, one lane per stage from assess to ship, and a done lane, with cards such as sso-saml-login blocked in implement and four issues done this week](assets/board-example.png)

## One pipeline, five roles

```text
assess → define → refine → plan → breakdown → implement → verify → ship
```

The stages stay the same while their depth adapts. Engineer, product owner,
designer, product marketer and QA each enter the same issue through their own
command; a product owner starts upstream with `/compass:intent`. A role is a
perspective a session consults. A document a role writes, such as
`positioning.md`, adds the gates that check it. See
the [roles guide](docs/roles-guide.md).

## Built to port

Compass runs on Claude Code today, but its core is split on purpose:

- **Methodology:** plain-language guidance, governance and templates.
- **Kit:** the runtime-neutral Python CLI, schemas and policy engine.
- **Adapter:** the commands, agents, skills and hooks for Claude Code.

The slash commands are the pipeline; they call the CLI, which does the work
([docs/cli.md](docs/cli.md)). A future runtime adapter calls the same kit
rather than reimplementing the rules ([docs/portability.md](docs/portability.md)).

## What the repository contains

```
commands/     the stage interface, under the /compass: namespace
agents/       distinct contexts - router, spec-author, planner, builder,
              orchestrator, verifier, reviewer, product-owner,
              product-marketer, architect
skills/       loadable procedures - adaptive-routing, bdd-specification,
              tdd-discipline, worktree-multiagent, intent-interview and the rest
hooks/        pre-tool.sh, post-tool.sh, stop.sh, session-start.sh,
              prompt-approval.sh, approval-summary.sh - mechanical enforcement
cli/compass   the kit: routing, checks and the manifest
bin/compass   the shim that puts the kit on your PATH
governance/   guardrails, strategies, routing policy, frozen vocabulary
approaches/   the reference shapes, and the artifacts each one earns
architecture/ Compass's own invariants and decision records
.claude-plugin/  the plugin manifest and marketplace entry
```

The first four are the Claude Code adapter and are rebuilt for another
runtime. Everything below them is reused unchanged.

## What Compass runs, sends and fetches

Compass works on your machine and in your repository. It reaches the network
only in the cases below, and each one starts only when you ask for it. The
full account is in [docs/security.md](docs/security.md).

- **Fetches** a brief you name over HTTPS, with `compass intent ingest --from
  <url>`. It refuses any scheme but `https`, on redirects too.
- **Fetches** a git parent when the project's `extends:` names one. It runs
  `git` for the one pinned commit and reads its `compass.yml` as data.
  Only `compass policy lint`, `compass policy show`, `compass policy diff`,
  `compass policy update`, `compass preset test` and `compass approach
  evaluate --write` fetch, and only a commit that is not cached yet; never
  `compass check`. `compass policy update` always asks the remote which
  commit its ref names, unless `COMPASS_OFFLINE=1` is set.
  `--offline` or `COMPASS_OFFLINE=1` stops the others fetching;
  `COMPASS_PARENT_REMOTE_BASE` names a mirror in place of `https://github.com`
  ([docs/git-parents.md](docs/git-parents.md)).
- **Sends** your delivery record to a git repository you configure, with
  `compass record sync`, which `compass ship-commit` also runs. It happens
  only when `compass.yml` names a `record:` remote, and it redacts
  credentials.
- **Starts** host sessions (`claude -p`) with `compass run`, which sends their
  prompts through Claude Code as any session does. Compass denies those
  sessions `git push` and `gh pr merge` by command prefix.
- **Runs** commands on your machine: the test command you give `compass
  tdd-red`, `compass tdd-green` and `compass quick-fix finish`, and, when
  `allow_project_commands` is true, your project's own guardrails declared
  with `check: command-passes` and the readiness commands in `compass.yml`;
  also git in your repository, and the CLI itself from the plugin's hooks.
- **Writes** to the linked GitHub issue with `gh`, only when `github_labels`
  is on in `compass.yml`: label names and, with `page` on, the issue's README
  as a comment ([docs/security.md](docs/security.md)).
- **Reads** the current Claude Code session's own transcript when a quick fix
  finishes, keeping only token counts, model names and times.
- **Clones and installs** other frameworks only in the evaluation harness,
  `evals/harness.py`, which maintainers run by hand.

## Read next

- **[Five-minute walkthrough](docs/five-minutes.md):** install Compass and ship a small issue.
- **[Methodology](docs/methodology.md):** the design and reasoning behind adaptive delivery.
- **[Safety contract](docs/safety-contract.md):** what Compass guarantees and what it does not.
- **[Security](docs/security.md):** hooks, dependencies, what runs and what is sent.
- **[Contributing](CONTRIBUTING.md):** what judges a pull request, and where to start.

## License

Apache 2.0. See [LICENSE](LICENSE).
