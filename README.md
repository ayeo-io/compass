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

Compass assesses each piece of work, new or existing, by **risk, familiarity
and size**. Every change that ships then runs the same four stages: assess, specify,
build and ship. A deterministic policy selects the evidence the change owes
before it ships: which scenarios and tests, which reviews, and where a person
decides. Five guardrails apply to all work that ships code,
whatever the assessment. Every project runs one fixed check set: a project
can add checks of its own, report failures without blocking while it tries
Compass, or excuse one check on one issue with a waiver a person approves. A
person's sign-off for irreversible work cannot be waived ([safety contract](docs/safety-contract.md)).

<p align="center">
  <img src="assets/compass-explainer.svg" alt="Three sliders for risk, familiarity and size feed a policy. As the work changes from a typo fix to a live defect to a payments rewrite, the evidence each of the four stages judges grows from the light row to the standard row, dots mark the stages where a person decides, and five guardrail lines stay the same." width="960">
</p>

Judgment goes into the assessment. Everything after it is computed from two
inputs: the assessment and the project's policy, the check set with the
settings of `compass.yml`. The same
two inputs give the same evidence, every
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

`/compass:go` assesses the change, shows the plan in three lines and runs the
path: it writes the scenarios, records a failing test before the code and a
passing one after it, and checks the result with `/compass:ship`. Each step
prints a `next:` line with the one command to run next. `/compass:assess`
does the assessment alone. When the path reaches a checkpoint that waits for
a person, the session stops and shows a request. You answer in the same
session:

```text
/compass:approve
/compass:reject "the criteria miss the burst case"
```

`/compass:status` reports what is blocked, moving and done. `/compass:resume
<issue>` picks an issue up in a later session, from its record on disk.
To write the scenarios an issue asks for, read
[docs/writing-specs-and-plans.md](docs/writing-specs-and-plans.md).

The shipped guardrails are active from the first command. Project settings
live in one file, `compass.yml` ([docs/configuration.md](docs/configuration.md)).
A setting there can only add to the check set; to excuse one check on one
issue, see [docs/waivers.md](docs/waivers.md). Upgrading from
6.x? Read [docs/upgrade-7-0-0.md](docs/upgrade-7-0-0.md); from 5.x, read
[docs/upgrade-6-0-0.md](docs/upgrade-6-0-0.md) first. To link an issue to
its GitHub issue and pull request, see [docs/github-links.md](docs/github-links.md).

Compass complements your normal CI. It does not replace tests, linting,
security scanning, builds or deployment checks.

## What Compass changes

Compass chooses the evidence each change owes from its assessment of risk,
familiarity and size. Every change owes scenarios, a failing test before each
passing one, a green suite and three reviews. The rest depends on the work:

| Work | Evidence Compass adds |
|---|---|
| **Small, low risk** | Nothing more. One clear scenario, a focused change and evidence that it works. |
| **Larger or riskier** | The regression, security and clarity reviews and the Definition of Done. Cross-cutting or critical risk adds the architecture review. |
| **Live defect** | The setting `urgency: live-defect`: reproduce first, fix safely, then do the follow-up work skipped for speed. |
| **`auth`, `payments`, `personal-data` or `migrations`** | A person approves the scenarios before the code, and signs off before the change ships. |
| **Spike** | Time-boxed exploration, off the path. Record the learning; ship nothing directly. |

A one-file authentication change can owe more than a large throwaway
prototype, because risk and size are different things. `compass approach
show` prints the evidence an issue owes on one line.

## Rigor without ritual

Compass keeps two kinds of rule apart:

- **Guardrails** are few and checkable: tested before shipping, acceptance
  defined before implementation, every change traced to a criterion,
  evidence rather than assertion, and a person's approval for a change
  labeled `auth`, `payments`, `personal-data` or `migrations`. `compass
  check` fails on a breach under enforced adoption, and the
  [safety contract](docs/safety-contract.md) lists what it cannot see.
- **Strategies** are strong defaults that improve the work without becoming
  bureaucracy: BDD, TDD, decision records, architecture models and other
  practices that apply when they add value.

A small change owes less evidence. No assessment removes a guardrail from
work that ships code
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
  in any session; `--until`, `--on`, `--for` and `--max` narrow it. `--for
  g5`, which covers irreversible work, and `--for waivers` each need a code
  that you type back. Compass lists each delegation with no end time at each new
  session start. Every delegated approval is on record, and you can overrule
  one; overruling a guardrail 5 sign-off does not undo work already landed.
- **Autonomy is a setting, not a promise.** `autonomy: controlled | balanced
  | autonomous` in `compass.yml` says how often a session stops for a person.
  It changes no gate, check or hook.
- **Decisions an agent takes for you are listed.** On `balanced` and
  `controlled`, the next checkpoint waits for you to confirm or change them.
- **Each acceptance test stage ends with a review.** On `controlled`, an issue
  the four-layer acceptance strategy applies to also waits at build and
  ship, and the request lists the `atdd` skill's review questions.

## Resumable and auditable

Every issue leaves a reviewable record. Its documents are in
`docs/compass/<created>-<issue>/`; its manifest, evidence and markers are in
`.compass/work/<issue>/`. Another session can resume from that record without
the chat history, and a reviewer can open the evidence behind each gate.

`compass flow` lists every issue by state, with what is blocked and whose
evidence is stale.

## One path, one specification

```text
assess → specify → build → ship
```

The stages stay the same while the evidence they judge adapts. A brief from a
product owner, a designer or a marketer opens the acceptance criteria, which
everyone on the change reads.

## Built to port

Compass runs on Claude Code today, but its core is split on purpose:

- **Methodology:** plain-language guidance, governance and templates.
- **Kit:** the runtime-neutral Python CLI, schemas and policy engine.
- **Adapter:** the commands, skills and hooks for Claude Code.

The slash commands run the path; they call the CLI, which does the work
([docs/cli.md](docs/cli.md)). A future runtime adapter calls the same kit
rather than reimplementing the rules ([docs/portability.md](docs/portability.md)).

## What the repository contains

```
commands/     the path commands, under the /compass: namespace
skills/       loadable procedures - adaptive-routing, bdd-specification,
              tdd-discipline, intent-interview and the rest
hooks/        pre-tool.sh, post-tool.sh, stop.sh, session-start.sh,
              prompt-approval.sh, approval-summary.sh - mechanical enforcement
cli/compass   the kit: routing, checks and the manifest
bin/compass   the shim that puts the kit on your PATH
governance/   guardrails, strategies, routing policy, frozen vocabulary
approaches/   the path, the spike, and how assess selects the evidence
architecture/ Compass's own invariants and decision records
.claude-plugin/  the plugin manifest and marketplace entry
```

The first four are the Claude Code adapter and are rebuilt for another
runtime. Everything below them is reused unchanged.

## What Compass runs, sends and fetches

Compass works on your machine and in your repository. It reaches the network
only in the cases below, and each one starts only when you ask for it. The
full account is in [docs/security.md](docs/security.md).

- **Fetches nothing for a configuration.** Compass runs one fixed check set
  (ADR-094). An `extends:` that names a git parent is refused with
  `L-PARENT-REMOVED`, and no command runs `git` to fetch one: not `compass
  policy lint`, `compass policy show`, `compass approach evaluate --write` or
  `compass check`.
- **Sends** your delivery record to a git repository you configure, with
  `compass record sync`, which `compass ship-commit` also runs. It happens
  only when `compass.yml` names a `record:` remote, and it redacts
  credentials.
- **Runs** commands on your machine: the test command you give `compass
  tdd-red`, `compass tdd-green` and `compass quick-fix finish`, and, when
  `allow_project_commands` is true, your project's own checks declared
  under `project_checks` in `compass.yml`;
  also git in your repository, and the CLI itself from the plugin's hooks.
- **Reads** a pull request with `gh` when you run `compass issue link set
  --pr`: its number, state and merge commit. Compass writes nothing to GitHub
  ([docs/security.md](docs/security.md)).

## Read next

- **[Five-minute walkthrough](docs/five-minutes.md):** install Compass and ship a small issue.
- **[Methodology](docs/methodology.md):** the design and reasoning behind adaptive delivery.
- **[Safety contract](docs/safety-contract.md):** what Compass guarantees and what it does not.
- **[Security](docs/security.md):** hooks, dependencies, what runs and what is sent.
- **[Contributing](CONTRIBUTING.md):** what judges a pull request, and where to start.

## License

Apache 2.0. See [LICENSE](LICENSE).
