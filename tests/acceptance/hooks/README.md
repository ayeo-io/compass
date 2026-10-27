# Pre-tool hook acceptance tests

The pilot ayeo-io/compass-delivery#306 ("Pilot the four-layer acceptance test model on the pre-tool hook tests", in the project's private delivery record) moved the client-observable scenarios of the pre-tool hook onto the four-layer model: executable specifications, a domain-specific language (DSL), protocol drivers and the system under test.

| Layer | File | Holds |
|---|---|---|
| Specification | `test_hook_refusals.py` | 16 scenarios, one DSL call per Given, When or Then line |
| DSL | `dsl.py` | `install`, `project`, `machine`, `agent`, `hook`; no checks |
| Driver | `tests/acceptance/hooks/drivers/base.py`, `tests/acceptance/hooks/drivers/claude_code.py`, `tests/acceptance/hooks/drivers/codex.py` | every set-up, every check, and how each client sends a call |
| System under test | a real install and a real project, in a folder of their own | |

Each scenario runs once through Claude Code's hook interface and once through the Codex adapter. `COMPASS_HOOK_CLIENT=claude-code` or `codex` runs one client only. A scenario a client is known to fail is marked in `conftest.py` with its issue, and the mark is strict.

## What the pilot found

1. **The Codex adapter cannot refuse without `python3`.** Its hook command runs `python3`, so with no `python3` it exits 127 where the Claude Code hook refuses as `python-missing`. ayeo-io/compass-delivery#308 ("Refuse a Codex tool call when python3 is missing", in the private delivery record) tracks it.
2. **Compass has no review form for the second and third stages of the `atdd` skill** (stage 2 writes the drivers, stage 3 tidies up and proves isolation). `compass evidence request --checkpoint` takes assess, define, refine and plan only.
3. **Compass does not accept the red that ends the skill's first stage.** An import red (a driver that does not exist yet) is a setup error to `compass tdd-red`, not a failing test.

## What a change to the hook's layout touches

Splitting `hooks/pre-tool.sh` into parts (ayeo-io/compass#699) changed 22 test files for the layout alone:

| Kind of change | Files |
|---|---|
| A fake or a copy that runs the hook to see a refusal | 4 |
| A planted fault in the hook's internals, checked on purpose | 4 |
| Text read from the hook's source | 14 |

Only the first kind is client-observable. With those scenarios on the drivers, the same change touches one driver file in their place. `test_layering.py::test_trc_p3_*` shows it: a hook that keeps its parts in another folder passes the same specifications with a driver of 20 lines.

| | Test files a hook-layout change touches |
|---|---|
| Before (#699) | 22 |
| After | 19 |

## Recommendation for ayeo-io/compass-delivery#307

ayeo-io/compass-delivery#307, in the private delivery record, proposes making the four-layer model a Compass strategy for the projects Compass governs, for changes a real client can observe.

- **For Compass's own tests, do not extend the model further.** Most of the churn comes from tests that read the hook's source or check its internals on purpose. The model does not reach either kind; a shared helper such as `tests/hook_text.py` already confines most of the source-reading change.
- **For the projects Compass governs, the model is worth it where the behavior is client-observable**, which is the scope #307 already sets. The specifications and the DSL survived a layout change unchanged, and the same specifications ran through two clients and found a real gap in one of them.
- **Before #307 adds checks, settle the two Compass gaps above:** a review form for stages 2 and 3, and a way to record an import red.
