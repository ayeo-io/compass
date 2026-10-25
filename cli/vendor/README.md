# `cli/vendor/` - third-party code Compass ships, unmodified

This directory exists so a machine with nothing but `python3` can run
Compass: the plugin carries its own copy of the one library it needs to
parse and write YAML, instead of asking the reader to `pip install`
anything first.

## What is here

| Path | What it is |
|---|---|
| `yaml/` | PyYAML's pure-Python package - `lib/yaml/` from the upstream sdist. |
| `LICENSE-PyYAML` | PyYAML's own licence text, copied byte-for-byte from the sdist. |
| `README.md` | This file. |

Nothing else goes in this directory. It is not a place for Compass's own
code, and it is not a place for a second dependency to accumulate quietly -
see "who updates it" below.

## Provenance

- **Package:** PyYAML
- **Version:** 6.0.2 (pinned - see `THIRD-PARTY-NOTICES.md` at the
  repository root for the sha256 of the sdist this tree was taken from)
- **Upstream:** https://pypi.org/project/PyYAML/
- **Licence:** MIT (see `LICENSE-PyYAML` in this directory)
- **Taken from:** `lib/yaml/` inside the upstream sdist (`pyyaml-6.0.2.tar.gz`)
- **Changed:** no. Every file here is byte-identical to the upstream
  source. Compass does not patch it, reformat it, or trim unused code out
  of it.

Only the pure-Python code is vendored. PyYAML's optional C extension
(`libyaml` bindings, `_yaml.*`) is a compiled binary for one platform and one
Python build, which a zero-install plugin cannot use. So `yaml.__with_libyaml__`
is `False` and `CSafeLoader` is not available. Nothing in `cli/` uses it:
every call site in Compass is `safe_load`, `safe_dump`, or `YAMLError`.

## How every caller reaches it

`cli/compass_pkg/__init__.py` is the one place the path to this directory
is written down: it inserts `cli/vendor` at the front of `sys.path` before
anything else in the package runs, so it wins over any PyYAML already on
the machine, deliberately and unconditionally. Every shell script that
embeds Python reaches the same thing through `scripts/lib/compass-python.sh`,
which puts `cli/` on `PYTHONPATH` and lets that same package `__init__`
do the rest. See `THIRD-PARTY-NOTICES.md` and `docs/security.md` for the
full account, including what carrying someone else's code obliges and how
an auditor reproduces this tree from upstream and checks it.

## Reproducing this tree, to check it

The full, runnable command is in `THIRD-PARTY-NOTICES.md` at the repository
root, under "PyYAML" - one copy, not restated here, so there is one copy to
keep up to date. In short: download the pinned sdist, check its
hash, extract it, and diff its `lib/yaml/` against this directory.

## Who updates it, and when

The maintainer, on one of two triggers: a PyYAML security advisory, or a
contributor hitting a bug that is already fixed upstream. There is no
promised cadence - a cadence nobody honours is worse than an honest
"updated on trigger". Updating is an ordinary Compass issue: replace this
directory from a fresh sdist, update the version and sha256 in
`THIRD-PARTY-NOTICES.md` and in this file, run the suite, and commit. A
user finds out which version they have by running `compass --version`,
which reports the resolved PyYAML version and where it came from.
