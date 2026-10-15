<!--
TEMPLATE: bug-report.md
Role in the pipeline: the intake artifact for a bug fix. The failing
reproduction test is written from this before any fix; the report is what
the reproduction is checked against. Keep it short and observational -
diagnosis belongs to the fix, not the report.

Fill every {{PLACEHOLDER}}.
-->

# Bug report - {{ISSUE_SLUG}}

<!-- compass:render document-header -->
<!-- /compass:render -->

## Observed behaviour

{{What actually happens, stated as an observation - the output, the error,
the wrong state. Paste real output where you have it.}}

## Expected behaviour

{{What should happen instead, and on what authority - a spec, a doc, an
acceptance criterion, or plain reasonable expectation. Cite it if it
exists.}}

## Reproduction steps

1. {{Step}}
2. {{Step}}
3. {{Observe: ...}}

**Reproducibility:** {{always | intermittent - include the rate if known}}
**First seen / version:** {{when or where this started, if known}}

## Impact

{{Who or what is affected, and how badly - one or two sentences. This feeds
the risk assessment at assess; it does not decide it.}}
