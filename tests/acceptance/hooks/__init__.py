"""Acceptance tests for the pre-tool hook, in four layers.

- `test_*.py`: executable specifications, one DSL call per Given, When or Then.
- `dsl.py`: the vocabulary; it fills in defaults and makes no checks.
- `drivers/`: the only code that runs the hook, and the only code that checks.
- The system under test: a Compass install and a project, each a real folder,
  with the hook run as a real client runs it.

The pilot is ayeo-io/compass-delivery#306.
"""
