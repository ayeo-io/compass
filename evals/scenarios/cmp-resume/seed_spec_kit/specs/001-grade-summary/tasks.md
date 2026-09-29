# Tasks: Grade Summary

**Input**: Design documents from `specs/001-grade-summary/`

**Prerequisites**: plan.md and spec.md, both already written

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with its neighbours
- **[Story]**: Which user story this item belongs to

## Phase 1: Setup

- [x] T001 [US1] src/grades.py exists, with parse_scores implemented and
      tested in tests/test_grades.py

## Phase 2: User Story 1 - Read a grade summary (Priority: P1)

- [ ] T002 [US1] Write the failing test for summarize in tests/test_grades.py
- [ ] T003 [US1] Implement summarize(scores) in src/grades.py: a dict
      with "average", "highest" and "lowest" - a tie goes to whichever
      student comes first in scores, and an empty list raises a
      ValueError
- [ ] T004 [US1] Run tests/test_grades.py and check it passes
