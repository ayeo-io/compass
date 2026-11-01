# Stage reviews

The questions for the review that ends each stage of the four-layer model. Each stage ends at the checkpoint of the Compass stage it runs in, and the checkpoint request reads the questions under that stage's heading. Answer each question with what you checked.

## Stage 1 - the refine stage

- Does each specification read like its scenario, with each Given, When or Then line one DSL call?
- Has an assertion got into the DSL?
- Does every identifier go through an alias?
- Does every scenario start by creating its own account, workspace or tenant?
- Is each implied failure mode settled with the person as a scenario, or descoped?
- Is the support code in place: the alias helper, the driver interface and its factory, the DSL root and the layering test?
- Does the suite fail with a red the runner reports, with the driver imported inside a fixture rather than at module level in `conftest.py`?

## Stage 2 - the implement stage

- Is the driver interface complete, with every method on the interface and on each implementation?
- Does every check live in the driver, passing by returning and failing by throwing, with a message that shows the expected and the actual value?
- Does the driver reach the system only the way real clients do, and wait by polling with a timeout, never by sleeping?
- Is anything stubbed other than a third party you do not control?
- Do the tests run, and does each scenario that still fails fail because the feature is not there yet?
- Was any scenario added that the specification does not state?

## Stage 3 - the verify stage

- Does the suite pass when run in parallel?
- Does each scenario give the same result when run twice in a row?
- Were driver methods that do nearly the same thing merged?
- Does every item of `checklist.md` hold?
- Does the project's layering test pass?
