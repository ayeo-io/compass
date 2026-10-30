# the-strategy-follows-the-pinned-major-and-the-settings-key

## Decided by

jed72

## Date

2026-10-30

## Supersedes

Nothing.

## Decision

Three answers about the four-layer acceptance strategy (`S17`):

- It applies only to a project whose `compass.yml` extends the shipped default at major 8 or later. A project pinned at `compass:default@6` or `compass:default@7` gets no stored applicability at assess and no row from the strategy's checks, as before 8.0.0. A project with no `compass.yml`, no `extends:` or a git parent names no shipped major and runs on the live default.
- `compass policy lint` refuses `acceptance_strategy: suspended` on any approach that ships. The spike keeps `suspended`. The settings key `acceptance_strategy: {state: off, reason: <why>}` is the one way to turn the strategy off.
- A major bump of the shipped preset may move the two entries of the frozen command corpus that name the live major: `policy-effective-shipped` and `policy-update-major-not-kept` in `tests/fixtures/compat/contract-4-commands.yml`. No other frozen entry moves.

## Why

Compass resolves every issue against the live preset, whatever major `extends:` names, so the pin is what keeps a project that has not moved off the strategy. A suspended routing on a shipping approach would turn the strategy off with no recorded reason, which the settings key requires. The two corpus entries record the live major itself, so they cannot stay true across a major bump.

## Evidence

The answers to decisions Q1 and Q4 of the requirements review of the Compass issue `acceptance-strategy-core` and to the reviewer's question about the routing override, given on 2026-10-30, for ayeo-io/compass-delivery#321 [Add the four-layer acceptance strategy with applicability and opt-out].
