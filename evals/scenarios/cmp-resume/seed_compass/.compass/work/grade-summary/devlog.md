# Devlog - grade-summary

- Done: parse_scores is implemented and tested, in the grades module's
  own test file.
- Next: implement summarize(scores) in the grades module. It takes the
  (name, score) pairs parse_scores returns and reports the average
  score, and the name of the student with the highest and the lowest
  score - a tie goes to whichever comes first in the list. Raise a
  ValueError when scores is empty. Write a test named
  test_summarize_reports_average_highest_and_lowest first.
