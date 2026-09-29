# Implementation Plan: Grade Summary

**Branch**: `001-grade-summary` | **Date**: 2026-09-27 | **Spec**: specs/001-grade-summary/spec.md

**Input**: Feature specification from specs/001-grade-summary/spec.md

## Summary

Add summarize(scores), a pure function in src/grades.py that turns the
(name, score) pairs parse_scores already returns into the average score
and the top and bottom scorer.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: none - standard library and pytest only

**Storage**: N/A

**Testing**: pytest

**Target Platform**: N/A - a library function

**Project Type**: library

**Performance Goals**: N/A

**Constraints**: no new dependency

**Scale/Scope**: one function, src/grades.py

## Constitution Check

No project constitution file. No gate applies.

## Project Structure

### Documentation (this feature)

```text
specs/001-grade-summary/
├── plan.md              # This file
├── spec.md              # Feature specification
└── tasks.md             # Task list
```

### Source Code (repository root)

```text
src/
└── grades.py

tests/
└── test_grades.py
```
