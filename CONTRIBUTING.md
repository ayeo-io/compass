# Contributing to Compass

This guide says what judges a pull request to Compass, so you know before you
open one. Compass is built with Compass: a change goes through the same
pipeline it gives its users.

## What judges a pull request

A pull request merges when all of these hold:

1. **The `self-check` job passes.** It is the one check the `protected-main`
   ruleset needs. It runs the full test suite, `compass ci` and the
   repository's own checks. The four `bdd-adapter` jobs also run; a failure
   there needs fixing too.
2. **The maintainer has reviewed it.** Review is by a person. Compass also has
   an automatic Claude review, but it starts only by hand
   (`governance/decisions/2026-10-03-ci-review-manual-only.md`), so do not
   wait for one.
3. **It meets the review rules.** `governance/review-rules.yml` lists the rules
   a reviewer applies to the files you changed, each with the incident behind
   it. `compass policy review-rules --changed-files <paths>` prints the ones
   that apply.

`.github/CODEOWNERS` names who reviews each path. Today that is the maintainer
for every path.

## What a reviewer checks first

- **A failing run for every new test.** Show each new test failing before your
  change, as the `FAILED` lines in the pull request body. `compass tdd-red`
  records it; a test that has never failed has not been shown to test anything.
- **The house rules.** No em dash anywhere: write a plain hyphen. No line
  crediting an AI agent in a commit or pull request. British English, except
  "artifact". `tests/test_house_style.py` enforces the first two in tracked
  files; read your commit message and pull request body yourself.
- **The frozen vocabulary.** Words Compass has retired fail
  `tests/test_terminology.py`. `governance/terminology.yml` lists them.
- **Plain English.** `CLAUDE.md` sets the writing rules. Lead with the point,
  one point per sentence, no idioms.

## Running the checks yourself

```
make test        # the full suite; install pytest-xdist to run it in parallel
make ci          # policy lint, issue lint and compass check on recent issues
```

Compass needs Python 3.10 or later. `docs/five-minutes.md` walks through a
small change from start to finish.

## Where to start

Issues labelled
[good first issue](https://github.com/jed72/compass/labels/good%20first%20issue)
are small, checked against the current code, and each says what to change.
Comment on one before you start, so two people do not do the same work.

## Licence

By contributing, you agree that your contribution is licensed under the
Apache License 2.0, as the rest of Compass is (`LICENSE`).
