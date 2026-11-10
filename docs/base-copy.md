# The base copy

`compass quick-fix finish` must show that the tests of a change fail without
the change. It does this on the base copy: a copy of the commit the issue
started from, with the test files of the change laid over it. This page says
what the copy holds, what its result shows, and where it has limits. The
code is `prove_red` and `_build_base_copy` in `cli/compass_pkg/lean.py`.

## What `finish` does

1. It writes the tracked files of the base commit to a temporary directory.
   The base commit is the `base_commit` that `compass quick-fix start`
   stored in the manifest.
2. It copies each test file of the change over them. A test file the change
   deleted is deleted in the copy too. A test file is a changed file under a
   folder such as `tests/`, `test/`, `spec/` or `fixtures/`, or one whose
   name matches a pattern such as `test_*`, `*_test.*`, `*.test.*`,
   `*.spec.*` or `conftest.py`.
3. It links `node_modules`, `.venv` and `venv` from the working tree into
   the copy, where they exist, and each path of `project.base_copy_links`.
4. It runs the test command in the copy, from the same folder it was given
   in. The command must fail.
5. It removes the copy, then runs the same command on the working tree,
   where it must pass.

## What `proved_on: base-copy` means

The red record of each scenario says `proved_on: base-copy` and names the
`base_commit`. It shows one thing: the tests of the change fail on the base
commit and pass with the change.

It does not show:

- the order of the work. `finish` proves the red after the code exists. A
  red recorded earlier with `compass tdd-red` still counts, and is the only
  proof that a test was written before the code;
- which scenario each test proves. One run gives every scenario of the
  issue its red;
- that the failure is the one you meant, for a runner that writes no JUnit
  report. For pytest, and for a runner that writes its JUnit report where
  Compass names it, Compass reads the report. A failed test is a red, and so
  is a test file that cannot import a module of the project. A run in which
  no test ran for another reason is refused. For any other runner the red
  is the exit code: any exit other than 0, 126 and 127 counts.

## Limits

- **Tests that need untracked build output.** The copy holds tracked files
  only. A test that reads a file the build writes fails in the copy for that
  reason, and `finish` records the failure as the red. Name the path in
  `project.base_copy_links`.
- **An editable install of the project.** When the Python environment names
  the working tree as the place to import the project from, the tests in the
  copy can import the changed code. They pass, and `finish` refuses. With
  pytest, the setting `pythonpath` in the project's pytest configuration
  (for example `pythonpath = src`) makes the copy import its own files.
- **Tests that pass without the change.** A test that does not call the
  changed code passes on the base commit, and `finish` refuses. A change
  with no test file is refused too.

The refusal when the tests pass on the base commit is one line:

```text
compass quick-fix finish: the tests pass on the base commit without the change, so they prove nothing. Likely causes: the test does not exercise the change, or an editable install makes the base copy import the working tree (docs/base-copy.md). Add a test that fails without the change.
```

## The setting `project.base_copy_links`

A list of untracked paths the tests need, each relative to the project root.
`finish` links each one that exists in the working tree into the copy. The
default is none.

```yaml
project:
  base_copy_links:
    - build
    - generated/schema.json
```

`finish` refuses a value that is not a list of paths, and a path that is
absolute or leaves the project:

```text
compass quick-fix finish: project.base_copy_links names '../other', which is not a path inside the project.
```
