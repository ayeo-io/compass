# Status

Done:
- parse_scores, in the grades module, reads the raw lines into (name,
  score) pairs. It has its own tests.

Next:
- summarize(scores) is not written yet. It should take the list of
  (name, score) pairs parse_scores returns and return a dict with
  three keys: "average" (the mean score, as a float), "highest" (the
  name of the student with the highest score) and "lowest" (the name
  of the student with the lowest score). On a tie for highest or
  lowest, use whichever student comes first in the list. Raise a
  ValueError if scores is empty.
