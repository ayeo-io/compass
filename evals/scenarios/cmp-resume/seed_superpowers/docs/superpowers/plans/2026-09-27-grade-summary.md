# Grade Summary Implementation Plan

> Work through the tasks below in order, one step at a time, and tick each
> step's checkbox when it is done.

**Goal:** Add a summarize function that reports the average score and the
top and bottom scorer from parsed grades.

**Architecture:** One pure function added to the grades module, next to
the existing parse_scores.

**Tech Stack:** Python, pytest.

**Spec:** turn the (name, score) pairs parse_scores returns into an
average score, a top scorer and a bottom scorer.

## Global Constraints

- No new dependency.
- Keep parse_scores unchanged.

## Review Focus

- An empty list of scores.
- A tie for the top or the bottom score.

---

### Task 1: parse_scores

**Files:**
- Create: src/grades.py
- Test: tests/test_grades.py

- [x] **Step 1: Write the failing tests**
- [x] **Step 2: Run the tests to check they fail**
- [x] **Step 3: Implement `parse_scores(lines: list[str]) -> list[tuple[str, int]]` in src/grades.py**
- [x] **Step 4: Run the tests to check they pass**
- [x] **Step 5: Commit**

### Task 2: summarize

**Files:**
- Modify: src/grades.py
- Test: tests/test_grades.py

**Interfaces:**
- Consumes: `parse_scores(lines: list[str]) -> list[tuple[str, int]]`, already committed.
- Produces: `summarize(scores: list[tuple[str, int]]) -> dict[str, object]`, with keys `"average"`, `"highest"` and `"lowest"`.

- [ ] **Step 1: Write the failing test**

```python
def test_summarize_of_a_single_score():
    scores = parse_scores(["Ada,91"])
    result = summarize(scores)
    assert result["average"] == 91
    assert result["highest"] == "Ada"
    assert result["lowest"] == "Ada"
```

- [ ] **Step 2: Run the test to check it fails**

Run: `pytest tests/test_grades.py::test_summarize_of_a_single_score -v`
Expected: FAIL with "summarize not defined"

- [ ] **Step 3: Implement `summarize(scores: list[tuple[str, int]]) -> dict[str, object]` in src/grades.py**

The average is the mean score. The highest and lowest are the names of
the students with the greatest and least score; a tie goes to whichever
student comes first in scores. Raise a ValueError when scores is empty.

- [ ] **Step 4: Run the test to check it passes**

Run: `pytest tests/test_grades.py::test_summarize_of_a_single_score -v`
Expected: PASS

- [ ] **Step 5: Commit**
