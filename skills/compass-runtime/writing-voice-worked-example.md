# Requirements review, in the target register: make-receipt-render

This is a rewrite of `make-receipt-render/requirements-review.md`,
one real requirements review from the archive, cited here so both versions can
be read side by side. The original is untouched - it stays exactly as it was
written, bolded label rows and all, because a rewritten "before" would teach
nothing. Below are the same four decisions, said the way a colleague would say
them.

## Where the receipt's command lives

The spike sketch said a `--format` flag on `status` or `check`. `status` does
not exist on this branch. `check` does, so folding the renderer into it was
one of the three real options jed72 weighed, alongside a new top-level verb
and a sibling sub-verb under `compass issue`. He picked the sibling:
`compass issue receipt --issue <slug>`. `compass issue` is already where a
single issue's tools live (`lint` checks one, `receipt` renders one), and
folding a renderer into `compass check` would have made a checking command
do something that is not checking. If anyone would rather keep the spike's
literal wording, every scenario only needs its invocation string swapped -
the behavior does not move.

## Whether the receipt re-runs anything

`compass check` re-runs the guardrail checks live; the receipt does not. jed72
decided the receipt reads recorded state straight out of `manifest.yml`, with no
re-execution, because a live re-run could disagree with whatever was actually
accepted at ship time - and a receipt that could contradict its own record
would undermine the entire point of an audit trail read from disk.

## How much fits on one screen

Fifty lines, a hundred columns wide, not configurable. jed72's call,
following the five-minute-legibility principle this project already holds
itself to: a standard terminal shows that much without scrolling, and if a
receipt cannot fit, the fix is a less verbose renderer, not a setting nobody
asked for.

## What exit code a caveat gets

Two of the receipt's three cases already exited 0; the third, a failed gate,
exited 1, and the original ledger left that asymmetry as an open question
rather than defending it as a decision. jed72 unified the three on exit 0 for a
successful render, keeping the non-zero exit for `compass check` itself: the
receipt is a renderer reporting what is on disk, even when what is on disk
is a recorded failure, and a renderer that refuses to render a caveat is a
checker, not a receipt.
