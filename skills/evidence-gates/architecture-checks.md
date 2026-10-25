# Architecture checks and the verify.architecture gate

Applies only when a project has declared an architecture check, which most
have not.

## Architecture checks and the verify.architecture gate

The `verify.architecture` gate is the pattern where a routing floor promotes
architecture checks to blocking - project-declared `command-passes`
guardrails that assert structural properties of the codebase (e.g. "modules
respect the dependency direction", "no cyclic imports in the domain layer").
Adopters declare each architecture check as a project guardrail in
`governance/guardrails.yml` with `check: command-passes` and a
`params.command:` that exits 0 on pass. The gate:

- is advisory by default;
- is promoted to blocking by routing floors `RP-REQUIRE-003` (risk ∈
  {cross-cutting, critical}) and `RP-REQUIRE-004` (labels ∈ irreversible
  domains) - following the same promotion pattern as `verify.analyze`
  (`architecture/decisions/ADR-007-conditional-gate-promotion-via-floors.md`);
- clears without checking anything when no project guardrails declare
  `command-passes`: a project that has not yet declared any architecture
  checks sees no behavioral change
  (`architecture/decisions/ADR-006-backward-compat-is-non-negotiable.md`;
  `architecture/decisions/ADR-009-fitness-functions-are-project-guardrails.md`). <!-- vocabulary-scan: allow - the record's own filename; ADR-009 keeps the words its decision was about, so a citation must name the real file -->

Evidence type accepted: `command-output`
(the subprocess result) or `test-run` (if the architecture check is run as part
of a test suite).

See `architecture/decisions/ADR-009-fitness-functions-are-project-guardrails.md` <!-- vocabulary-scan: allow - the same record's filename -->
- titled *"Architectural fitness functions are project guardrails, not <!-- vocabulary-scan: allow - ADR-009's title quoted verbatim; section 4's quoted-term exception, and rewording it would misquote the record -->
framework guardrails"* (a fitness function is an automated check that a <!-- vocabulary-scan: allow - the parenthetical the quoted-term exception needs: it has to use the term to define it -->
codebase keeps a structural property) - for the ownership-boundary decision
and the full list of alternatives considered.
