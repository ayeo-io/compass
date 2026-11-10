# The records of the older record commands

Reference for the records that `compass tdd-red`, `compass tdd-green` and
`compass acceptance record` write. `compass quick-fix finish` writes the red
and the green of a change itself, so read this only where the project's
settings add evidence (`require_evidence` in `compass.yml`) or a red is
recorded before the code.

## Records that meet a Definition of Done item

The Definition of Done is owed only where the project's settings add
`definition-of-done`. An item is then met by a record in the manifest, never by a
tick on the page: `compass gate pass ... --meets <item>` or `compass evidence
add ... --meets <item>` records evidence, `compass follow-up add FU-<id>
--defers <item> --github owner/repo#N --summary "..."` carries the item to the
GitHub issue that tracks it (on a path issue a follow-up with no `--github`
meets nothing), and a person ticks an item by typing `/compass:approve` for a
`compass evidence request --check <item>`, or with `compass evidence approve
--check <item>` at a terminal. `dod-evidence-typed` fails an item with no
record. `compass check` lists each item's state.

## The loop a red or green belongs to

`compass tdd-red` and `compass tdd-green` write `loop` on each record:
`outer` with `--loop outer`, for a run of the acceptance suite through a
client interface, and `inner` with `--loop inner`, for a unit test. With no
flag the loop is `outer` on a path issue whose `S17` routing is
`existing-dsl`, because its declared test is its acceptance
test, and on an issue assessed before the path as a quick fix the
four-layer acceptance strategy applies to; it is `inner` everywhere else. `compass quick-fix finish` takes the same flag. A
record with no field reads as inner. Where the four-layer acceptance strategy (`S17`)
applies, the check `outer-loop-recorded` needs an outer-loop red and an
outer-loop green recorded on the tree as it is now (ADR-080). `suite-passed`
reads every green, whatever its loop. An outer-loop record has its own file,
`red-<id>.outer.json` or `green-<id>.outer.json` (`red.outer.json` unbound),
and its own registry entry, so later inner-loop work keeps it (ADR-082).

An outer-loop green names what the suite ran against and through (ADR-085):
`--candidate <build id>|local` writes `candidate` and `candidate_kind`
(`deployed`, or `local` with the record's own `tree_id` as the candidate),
and `--client api|web|cli` writes `client`. Any other client is refused. Where
the four-layer acceptance strategy applies, `compass tdd-green` and `compass
quick-fix finish` refuse an outer-loop green that names no candidate or no
client before the command runs, `compass evidence add` refuses to register
one, and `outer-loop-recorded` fails one registered another way. A unit-test
green names neither: `compass tdd-green --loop inner` refuses the flags, and
`compass quick-fix finish`, which chooses its own loop, does not write them
on the inner loop. With `--loop outer`, `compass tdd-red` and `compass
tdd-green` take `--scenario` more than once, or `--every-scenario`: one run
writes one record per scenario, sharing a `run_id`. A green needs its red first.
`compass quick-fix finish` reuses a green already on record only when it is of
the same loop and names the same candidate and client.

Each loop keeps its own `attempts` count per scenario, so an outer-loop green
counts outer-loop runs only (ADR-084). An outer-loop run that fails counts as
a run and writes no record, so a pass on the same tree with the same
command after it has `attempts` 2 and `rerun_without_change: true`, which
`no-trusted-rerun` fails unless the test is quarantined. An outer-loop green
bound to a scenario writes `test`, the scenario's first declared test, which
`no-trusted-rerun` looks up in `governance/quarantine.yml`. Where the
four-layer acceptance strategy applies, `outer-loop-attempts-recorded` fails
an outer-loop green with no `attempts` or with one that is not a whole number
of 1 or more. A green run again keeps the time of its first run in `first_timestamp` (ADR-088).
Each record holds `file_sha256` and `file_modes`, the SHA-256 and git mode of each changed file and declared test; `evidence/SHA256SUMS` lists them and each record file for `sha256sum -c` (ADR-089); `trail.md` writes its lines in the same form (`evidence_sums.sum_line`, `docs/delivery-record.md`).

For the outer loop, a pytest setup error that names a missing module of the
project is an import red, as a collection error is, and the record lists
`missing_modules`. A missing module outside the project is refused. Exit 4 is
never a red: the refusal quotes pytest's first error line, and names the fix
when `conftest.py` imports the driver at module level. A red that ends stage 1
writes `before_implement: true`, no `.red` marker and moves no document
(ADR-081). On a path issue that is an outer-loop red while specify is not
done. On an issue assessed before the path, it is an outer-loop red on an
approach that runs refine, before plan is handed off and with no technical
design, distribution map or subtask registered. A runner that is not pytest is read from the JUnit report its adapter writes to `COMPASS_JUNIT_REPORT` (ADR-087).
Only `compass isolation record` and `compass layering record` write the isolation and layering records (ADR-086).

## The scenario sign-off and the freeze

On a path issue that owes `scenario-approval`, `compass tdd-red` refuses
(`scenarios-not-approved`) before the test runs, with no record or `.red`
marker, until the `specify` checkpoint has a person's answer (ADR-095). On a
path delivery issue each red's `content_digest` holds `spec_sha256`, the
`sha256sum` of the spec file (null with no file). The first red writes the
manifest's `scenario_freeze`, never rewritten: `at`, `red` (relative to the
issue folder), `spec`, `spec_sha256` and the scenario ids (`scenarios`).
`compass check` prints `Scenarios: frozen at the first red (sha256 <12
characters>)` as a notice, not a row, adding "the spec has changed since" when
the digest differs; the default view shows it only then. An issue assessed
before the path writes neither (module `scenario_freeze`).

## Records that move no document

`compass tdd-red` and `compass acceptance record` are the first records of the
build stage. Since 9.0.0 no document has a status for a record to move
(ADR-091). No gate accepts an `artifact-approval` record from an older release
or a `--decisions` approval, and the `G5` sign-off check never reads one.

`compass acceptance record --release-note "<text>"` also stores the issue's
release line in `release_note`, once the command passes. A failed run stores
nothing, and the flag is refused on a completed or closed issue
(`docs/release-line.md`).
