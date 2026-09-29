# Devlog - grade-summary

- Done: parse_scores is implemented and tested, in the grades module's
  own test file.
- Next: implement summarize(scores) in the grades module. It takes the
  (name, score) pairs parse_scores returns and returns a dict with
  three keys: "average" (the mean score, as a float), "highest" (the
  name of the student with the highest score) and "lowest" (the name
  of the student with the lowest score). A tie for highest or lowest
  goes to whichever student comes first in the list. Raise a
  ValueError when scores is empty. Write a test for it first.
