# Feature Specification: Grade Summary

**Feature Branch**: `001-grade-summary`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Add a summarize function that reports the
average score and the top and bottom scorer."

## User Scenarios & Testing (mandatory)

### User Story 1 - Read a grade summary (Priority: P1)

A teacher wants one summary of a set of scores: the average, and who
scored highest and lowest.

**Why this priority**: This is the whole feature - without it there is
nothing to ship.

**Independent Test**: Call summarize with a small, known list of scores
and check the average, highest and lowest it returns.

**Acceptance Scenarios**:

1. **Given** a list of (name, score) pairs, **When** summarize is
   called, **Then** it returns the mean score and the names of the
   highest and lowest scorer.
2. **Given** two students tied for the highest or the lowest score,
   **When** summarize is called, **Then** it returns whichever of them
   comes first in the list.
3. **Given** an empty list, **When** summarize is called, **Then** it
   raises a ValueError.

## Requirements (mandatory)

### Functional Requirements

- **FR-001**: The grades module MUST expose a function, summarize, that
  takes the (name, score) pairs parse_scores already returns.
- **FR-002**: summarize MUST return a dict with three keys: "average"
  (the mean score, as a float), "highest" (the name of the student with
  the highest score) and "lowest" (the name of the student with the
  lowest score).
- **FR-003**: On a tie for highest or lowest, summarize MUST return
  whichever student comes first in the list.
- **FR-004**: summarize MUST raise a ValueError when the list of scores
  is empty.

## Success Criteria (mandatory)

### Measurable Outcomes

- **SC-001**: summarize gives the same average, highest and lowest a
  person would compute by hand from the same scores.

## Assumptions

- parse_scores already turns raw lines into (name, score) pairs, and
  stays as it is.
