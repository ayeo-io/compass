# Tasks: Grade Summary

**Input**: Design documents from `specs/001-grade-summary/`

**Prerequisites**: plan and spec, both already written

## Format

Each line is a checkbox and a short description; `[P]` means it can run
in parallel with its neighbours.

## Setup

- [x] T001 grades.py exists, with parse_scores implemented and tested

## Grade summary

- [ ] T002 Write the failing test for summarize in test_grades.py
- [ ] T003 Implement summarize(scores) in grades.py: the average score,
      and the highest and lowest scorer by name - a tie goes to
      whichever student comes first in scores, and an empty list raises
      a ValueError
- [ ] T004 Run the tests and check they pass
