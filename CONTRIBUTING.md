# Contributing to Compass

This guide says what judges a pull request to Compass.

## What judges a pull request

A pull request merges when all of these hold:

1. **The `self-check` job passes.** It is the one check the `protected-main`
   ruleset needs. It runs the full test suite, `compass ci` and the
   repository's own checks. The four `bdd-adapter` jobs also run; fix a
   failure there too.
2. **The maintainer has reviewed it.** Do not wait for the automatic Claude
   review: it starts only by hand
   (`governance/decisions/2026-10-03-ci-review-manual-only.md`).
3. **It meets the review rules.** `governance/review-rules.yml` lists them.
   `compass review-rule list --changed-files <paths>` prints the ones that
   apply to your files.

`.github/CODEOWNERS` names who reviews each path. Today that is the
maintainer for every path.

## What a reviewer checks first

- **A failing run for every new test.** Put the `FAILED` lines in the pull
  request body. `compass quick-fix finish` proves the failure on a copy of
  the base commit.
- **The house rules.** No em dash anywhere: write a plain hyphen. No line
  crediting an AI agent in a commit or pull request. US English.
  `tests/test_house_style.py` checks tracked files only, so read your
  commit message and pull request body yourself.
- **No rival product name.** Name another product only by its code, R1 to
  R9, in files, paths, branch names, commit messages and pull requests. CI
  checks all of them. To check your commit messages before the push, run
  `git config core.hooksPath scripts/git-hooks` once.
- **The frozen vocabulary.** `governance/terminology.yml` lists the retired
  words. `tests/test_terminology.py` fails on one.
- **Plain English.** `CLAUDE.md` sets the writing rules.

## Running the checks yourself

```
make test        # the full suite; install pytest-xdist to run it in parallel
make test-clean  # the suite in a fresh clone of HEAD, as CI sees it
make ci          # policy lint, issue lint and compass check on recent issues
```

Compass needs Python 3.10 or later. `docs/five-minutes.md` walks through a
small change.

## What the repository contains

```
commands/        the slash commands, under the /compass: namespace
skills/          procedures a session loads, such as atdd
hooks/           pre-tool.sh, post-tool.sh, stop.sh, session-start.sh,
                 prompt-approval.sh, approval-summary.sh
cli/compass      the CLI
bin/compass      the shim that puts the CLI on your PATH
governance/      the guardrails and the check set
approaches/      the path a change takes, and the spike
architecture/    Compass's own decision records
.claude-plugin/  the plugin manifest
```

## Where to start

Issues labeled
[good first issue](https://github.com/ayeo-io/compass/labels/good%20first%20issue)
are small and say what to change. Comment on one before you start, so two
people do not do the same work.

## Security and conduct

Report a vulnerability privately, as `SECURITY.md` describes, never in a
public issue. Everyone taking part follows `CODE_OF_CONDUCT.md`.

## License

Your contribution is licensed under the Apache License 2.0, as the rest of
Compass is (`LICENSE`).
