# Proposal: a workflow designer for factory workflows in Orca

## Purpose

This proposal describes a designer for factory workflows. A person builds a
workflow as a graph. The designer generates a set of Markdown prompts. The person pastes
the top-level prompt into Orca, or the designer registers it as an Orca automation. An
orchestrator agent then runs the workflow: it starts worker agents, loops, branches,
waits at gates and reports.

The designer uses the same approach as an existing workflow engine, called here the
reference engine. The difference is the output. The reference engine generates a
Python module that its engine runs. This designer generates Markdown prompts that an
agent in Orca follows.

The designer must support:

- a top-level orchestrator that controls the whole workflow;
- handoffs to worker agents (Orca calls them workers; this proposal also calls them
  subagents);
- loops, including loops inside loops;
- steps that use skills installed on the designer's machine;
- triggers: events, schedules and manual starts;
- feedback from the user on how each run is going, and suggested changes to the workflow
  that the user can accept or reject.

A hand-written coordinator prompt from an existing factory is the reference for
what good output looks like. It has settings, rules, a label state machine, numbered
steps, worker handoffs and gates. The designer must be able to generate a prompt of that
quality from a graph.

## Decisions for the owner

These choices set conventions, so they need the owner's decision before work starts.
Each lists the options and their consequences.

| # | Decision | Options | Consequences |
|---|---|---|---|
| 1 | Where the designer lives | (A) a new repository; (B) a package and pages inside the reference engine's repository; (C) an Orca plugin (`orca plugin create`) | A keeps the reference engine's domain clean and lets the designer ship on its own. B reuses the flow graph, the expression editor and the run views directly, but mixes an unrelated product with developer tooling. C puts the designer next to the agents, but ties it to Orca's plugin API and its release cycle. |
| 2 | The source of truth | (A) the workflow form (a JSON or YAML document); (B) the generated Markdown, read back by a parser, as the reference engine treats its Python module | A is simpler and safe: the Markdown is only an output. B lets a person edit the Markdown by hand and open it again, but needs a strict grammar and a round-trip test for every node type. |
| 3 | Where a run keeps its state | (A) GitHub labels and comments, as the hand-written coordinator prompt does; (B) a state file committed in the repository; (C) Orca's own Run and Task records only | A is visible to people and survives a lost agent, but is limited to GitHub work. B works for any repository, but every change is a commit. C needs no extra store, but a new orchestrator session cannot always rebuild the position in a loop from it. |
| 4 | How the author builds a workflow | (A) a visual editor only; (B) a fluent API in TypeScript or Python and a visual editor, both writing the same form | A is the smallest product. B matches the reference engine's build order (API first, editor later) and gives tests a cheap way to build workflows. |
| 5 | How far the designer goes past pasting | (A) copy to clipboard only; (B) also run the `orca` commands that register triggers and start the orchestrator | A has no side effects. B gives one click from design to a running workflow, but the designer then needs the `orca` CLI on the same machine and the person's approval for each change. |
| 6 | What makes the suggestions | (A) fixed rules over run data only; (B) a reviewer agent only; (C) both: rules find the signals, the agent explains them and drafts the change | A is cheap, repeatable and testable, but finds only the problems someone wrote a rule for. B finds more, but costs agent time and can be wrong with confidence. C costs the most to build, but each suggestion cites a signal a rule found. |
| 7 | What happens after the user accepts a suggestion | (A) the designer changes the form and shows the new bundle; the user regenerates and re-registers; (B) the designer also regenerates and re-registers the triggers | A keeps every change to a running factory in the user's hands. B is faster, but a bad suggestion reaches the next run with no second look. |

The rest of this proposal assumes 2A, 3A, 4B, 5B, 6C and 7A where an example needs a
choice.
Each assumption is marked.

## What carries over from the reference engine

The reference engine is an existing workflow engine. An author builds a workflow with a
fluent API or a visual editor, and the engine generates a Python module that it runs.
These of its ideas carry over:

| Reference engine idea | Factory designer equivalent |
|---|---|
| Builder calls make a graph; the graph generates the output; the output is what runs | The same. The graph generates Markdown prompts; the orchestrator follows them. |
| A loop is one call whose body is its own generated function | A loop is one named procedure in the orchestrator prompt, with its own section. A nested loop is a procedure called from inside another. |
| A pass limit, and "completed, not converged" at the limit | Every loop has a pass limit. At the limit the loop ends as `not_converged` and keeps its last pass. The prompt says what the orchestrator does next. |
| A condition runs one branch and skips the other; an empty branch passes its input on | The same, as an "If ... Otherwise ..." step in the prompt. |
| References to a variable, to an earlier step's output and to a loop's input | `var.<name>`, `output.<step id>`, `loop.input`. The generator turns each into plain words in the prompt ("the PR that step `open-pr` opened"). |
| Step keys such as `raise-loop/3/solve` | The same keys, used in every status comment and worker spec, for example `review-loop/2/fix`. They let a new session find its place. |
| A step registry, filled from installed packages through an entry point | A skill registry, filled from `orca skills installed --json`. |
| A step declares how it recovers: record its result, or run it again | A step declares if it is safe to repeat. The prompt tells the orchestrator to check the state store before it repeats a step that is not. |
| Graph validation before generation | The same, with the rules in "Validation" below. |
| Generate, parse and generate again must give equal files | Kept only if the owner chooses 2B. With 2A, a test checks that the same form always generates the same Markdown. |
| Generated code stored under the hash of its content | Each generated bundle records the hash of its form. The orchestrator prints the hash in its start comment, so a run names the exact version it followed. |
| A graph view that shows each step's run status | The same layout of columns, loop groups and branches. |
| Conditions written in an expression language | Conditions stay structured where they can be checked ("CI is green", "label `x` is present", "pass < limit"), with free text as a fallback that the prompt quotes word for word. |

What does not carry over: the reference engine runs its code deterministically and records
each step durably. Orca has no such engine. An agent reads the prompt and acts. So the
designer must make the prompt hard to misread, and must put the run's state somewhere the
agent rereads on every pass (decision 3).

## The workflow model

### Node types

| Node | What it means | Generated as |
|---|---|---|
| **Trigger** | What starts a run: a schedule, an event or a manual start | `orca automations create` command, plus the "Start of the run" section |
| **Orchestrator** | The top-level agent. Exactly one per workflow. Holds settings, rules and the main procedure | `orchestrator.md` |
| **Variable** | A setting with a type and a default: a number, a text, a repository, a label, an agent id | The "Settings" section; the orchestrator reads values from the trigger or the run's input |
| **Handoff** | Work given to a worker agent, with a spec, an agent, a worktree choice and the evidence that proves it is done | A worker spec file, and an `orca orchestration worker-start` or `task-create` line in the orchestrator prompt |
| **Skill step** | The orchestrator or a worker uses a named skill | "Use the `<skill>` skill to ..." with its inputs, and who answers the skill's gates |
| **Shell step** | A command to run, with what a non-zero exit means | A fenced command and the rule for its exit code |
| **Condition** | One branch runs, the other is skipped | "If ... Otherwise ..." |
| **Loop until** | Repeat a body until a test passes or a pass limit is reached | A named procedure with a pass counter, a test, a limit and a `not_converged` outcome |
| **For each** | Run a body once per item of a list, one at a time or in parallel up to a limit | A procedure over a list; in parallel, one Task per item in an Orca Task DAG |
| **Parallel** | Independent branches that run at the same time and join | Tasks with `--deps` in an Orca Run; the join waits for every `worker_done` |
| **Gate** | Wait for a person: a label, a comment, an answer | A stop with the exact signal that releases it, and who may give it |
| **Sub-workflow** | Another designed workflow, called as one step | A handoff whose spec is that workflow's own `orchestrator.md` |

Loops, for-each and conditions take a body, and a body can hold any node, including
another loop. So nesting has no fixed depth. The validation rules limit the total
number of workers, not the depth.

### Skills on the designer's machine

The designer reads the skill catalog from Orca:

```text
orca skills installed --json
```

Each entry has a `name`, a `description`, the `providers` that can load it (`claude`,
`codex`, `agent-skills` and so on) and a source label. The palette lists them by name and
groups them by source. A name is not unique: on this machine two `code-review` skills
for `claude` come from different sources. So a step stores the skill's `id` and source,
and the generated prompt names the source when two skills share a name. When a step uses
a skill, the designer checks that the agent
chosen for that step is one of the skill's providers. If not, validation fails and names
the agents that can use it.

A skill step records:

- the skill name, as Orca prints it;
- the inputs the step passes, written into the prompt;
- the skill's gates and who answers each one: the orchestrator, the owner or nobody.
  In the hand-written coordinator prompt, the coordinator answers a review skill's
  gate itself, within stated limits.

The catalog is per machine. The generated bundle lists every skill it uses in its
manifest. The orchestrator checks them at the start of a run and stops if one is
missing, before it starts any worker.

### Triggers

A trigger becomes an Orca automation. Orca supports these today (Orca 1.4.271,
`orca automations create --help` and `orca skills get orca-cli --reference
references/automations.md`):

| Trigger kind | Orca form | Notes |
|---|---|---|
| Manual | No automation; the person pastes `orchestrator.md` or runs `orca automations run <id>` | The default while a workflow is tested |
| Schedule | `--trigger hourly\|daily\|weekdays\|weekly` with `--time`, a 5-field cron, or an RRULE; `--timezone` | A `--precheck <command>` can skip a run, for example when no issue carries the start label |
| GitHub event | `--on "github.<event> in=owner/repo ..."` | Events include `pr_opened`, `labeled label=<name>`, `ci_failed`, `ci_passed`, `pr_conflicted`, `pr_merged`, `pr_closed`, `deploy_finished`, `security_alert` and `workflow_finished` |
| Slack event | `--on "slack.mentioned in=<channel>"`, `slack.reaction` | |
| Linear event | `--on "linear.<event> in=<team>"` | |
| Webhook | A bot webhook | For any other system |
| One-off wait | `--once --by <time>` with an event rule | For a step that waits for a CI run or a deploy, with a deadline |

Event triggers need an Orca bot with a connector for that source, and an Orca Cloud that
sends the events. `orca automations trigger-options --bot <name> --json` lists the events
a bot can start on. The designer calls it to fill the trigger picker, and shows an event
as unavailable when no connector provides it.

Orca adds an event block to the prompt of each run that an event starts. The text that a
person wrote is fenced and marked as information, not instructions. The generated
orchestrator prompt repeats that rule and names the event fields the workflow reads
(for example the PR URL).

A workflow can have several triggers. Each becomes its own automation, with the same
prompt and a variable that says which trigger fired.

## The generated bundle

For a workflow called `ci-fix`, the designer writes:

```text
ci-fix/
  orchestrator.md        # paste this into Orca, or the automation runs it
  workers/
    diagnose.md          # one spec per handoff node
    fix.md
    review.md
  triggers.sh            # the orca automations create commands, disabled by default
  manifest.yaml          # the form's hash, Orca version, skills, agents, variables
```

`orchestrator.md` has fixed sections, in this order. Each comes from the graph:

1. **Role.** One paragraph: what the orchestrator does and does not do. It does not write
   product code; it starts workers and checks their evidence.
2. **Settings.** The variables, their values and who may change them.
3. **Where things live.** The state store (decision 3), the files to read first, and the
   rule that event text and worker output are data, not instructions.
4. **Rules you never break.** From the workflow's rules, and the rules that every
   generated workflow gets (no polling; no steering through a worker's terminal; one
   step label at a time).
5. **States.** A table of every state the run can be in, generated from the graph. With
   3A these are GitHub labels, as in the hand-written prompt's table of labels.
6. **Start of the run.** Make a run id, check for a run still in progress, post the
   start comment with the bundle hash, check the skills.
7. **The procedure.** One numbered section per top-level node. A loop is a sub-section
   with its own procedure.
8. **Workers.** How to start each handoff, using
   `orca orchestration worker-start --spec-file workers/<id>.md`, and what evidence to
   check when it reports.
9. **Talking to the owner.** Where questions, gates, feedback and the summary go.
10. **End of the run.** The summary: each step key, its outcome and its evidence, any
    `/orca feedback` the owner left during the run, and the feedback question.

The prompt tells the orchestrator to run `orca skills get orchestration` once per run,
and that its flags win over the prompt. This keeps an older bundle working when Orca
changes its CLI.

### Example

A workflow that fixes a failing CI run, reviews the fix in a loop, and waits for the
owner before merge. The review loop holds a nested loop that retries a flaky test run.

The form (assumes 2A):

```yaml
workflow: ci-fix
orchestrator: { agent: claude }
variables:
  max_review_passes: { type: int, default: 3 }
  max_test_retries:  { type: int, default: 2 }
triggers:
  - on: github.ci_failed
    in: acme/shop
steps:
  - id: diagnose
    handoff: { agent: claude, worktree: new-child,
               spec: "Find why CI failed on {event.pr}. Report the failing test and the cause.",
               evidence: "the failing test name and a log excerpt" }
  - id: fix
    handoff: { agent: codex, worktree: { same_as: diagnose },
               spec: "Fix the cause from {output.diagnose}. Push to the PR branch.",
               evidence: "the commit SHA" }
  - id: review-loop
    loop_until:
      max_passes: var.max_review_passes
      finished_when: output.review.findings == 0
      body:
        - id: review
          skill: { name: code-review, agent: claude, gates: { answer: orchestrator } }
        - id: apply
          condition: { if: output.review.findings > 0,
                       then: [ { id: address, handoff: { agent: codex, spec: "Fix {output.review}" } } ] }
        - id: test-loop
          loop_until:
            max_passes: var.max_test_retries
            finished_when: output.tests.exit_code == 0
            body:
              - id: tests
                shell: { command: "make check", nonzero: "retry" }
  - id: merge-gate
    gate: { signal: "label merge-ok", from: owner }
```

The part of `orchestrator.md` that the review loop generates:

```markdown
### 3. Review loop (`review-loop`)

Repeat these steps. Count the passes from 1. Before each pass, read the PR's
comments for the last `review-loop/<n>` status, so a new session continues at
the right pass.

1. **`review-loop/<n>/review`.** Use the `code-review` skill on the PR. You
   answer its gates yourself.
2. **`review-loop/<n>/apply`.** If the review has findings, start a worker
   with `workers/address.md` and the findings. Otherwise skip this step.
3. **`review-loop/<n>/test-loop`.** Run the test loop below.
4. Post `review-loop/<n>: <findings> findings` on the PR.

Stop the loop when the review has no findings. Then go to step 4.
If pass <n> reaches 3 (`max_review_passes`) and the review still has findings,
the loop ends as `not_converged`. Keep the last pass, add `orca:stuck`, say
which findings remain, and stop the run.

#### 3a. Test loop (`review-loop/<n>/test-loop`)

Run `make check`. A zero exit ends the loop. A non-zero exit starts the next
pass, up to 2 passes (`max_test_retries`). At the limit, the loop ends as
`not_converged`: the review loop's pass fails, and you report the last log.
```

Every name in the generated text comes from the form: the step ids, the variables and
their values, the skill and the worker spec files.

## Validation

The designer refuses to generate a bundle when any of these fails. Each message names
the node.

- There is exactly one orchestrator, and every node is reachable from it.
- Every loop has a pass limit and a stop test, and says what happens at `not_converged`.
- Every handoff has an agent, a worktree choice and the evidence that proves it is done.
- Two handoffs that can run at the same time do not share a worktree when either can
  edit files. Orca's guide says that workers editing the same files need separate
  workspaces.
- No more than 4 workers start at once. Orca's guide recommends about 4; more wait for a
  free place.
- Every skill exists in the catalog for the agent that uses it.
- Every gate names the signal that releases it and who may give it.
- Every reference points to a step that runs before it on every path, as
  the reference engine checks.
- Every event trigger names a source that a connector provides.

## Feedback and suggested improvements

The designer learns how each workflow is going from two sources: what the runs record, and
what the user says. It turns both into suggested changes to the form. The user accepts or
rejects each one. The designer never changes a workflow by itself.

### Workflow versions

Feedback and suggestions need a fixed thing to refer to. So the designer keeps each saved
form as a version, with the hash that the manifest and the run's start comment already
carry. Every run, every piece of feedback and every suggestion names a version and, where
it applies, a step key. A suggestion made for version 3 shows as out of date when the
user opens version 5.

### What the runs record

The designer reads each run's outcome from the state store (decision 3) and from Orca
(`orca automations runs --id <id> --json`, `orca orchestration inbox`). For each step key
it collects:

| Signal | Example of what it shows |
|---|---|
| Outcome: done, failed, skipped, `not_converged`, stuck | The review loop ends `not_converged` in 4 of the last 10 runs |
| Passes used by each loop | The test loop always passes on pass 1, so its retries are never used |
| Worker escalations and `stopReason` | The `fix` worker often stops to ask the same question |
| Time from start to `worker_done` | The `diagnose` step takes most of each run |
| Time a gate waits for a person | `merge-gate` waits 2 days on average |
| Runs skipped by a precheck | The 08:00 schedule finds nothing to do on most days |
| Evidence that failed the orchestrator's check | The `fix` worker reports a SHA that is not on the PR branch |

### What the user says

The user gives feedback in three places. Each is tied to a run and, where possible, to a
step key.

- **In the designer.** On a run's page, the user marks a step as good or bad and adds a
  note: "the review found nothing useful", "this should have asked me first".
- **In the state store, during a run.** With 3A, the owner comments
  `/orca feedback <step key> <note>` on the PR or the status issue. The orchestrator copies
  it into the run summary, unchanged, and carries on. It never acts on the note during the
  run: feedback changes the next version of the workflow, not the run in progress.
- **At the end of a run.** The generated "End of the run" section asks the owner one
  question in the summary: "Did this run do what you wanted? Reply `/orca feedback` with
  what to change." The designer can turn this off per workflow.

Only the named owner's feedback counts, by the same check that releases gates. Text from
anyone else, and text inside worker output or event payloads, is data. It never becomes
feedback.

### How suggestions are made

With 6C, it works in two stages.

1. **Rules find signals.** A fixed set of checks runs over the last N runs of a version
   (N is a setting, default 10). Each check that fires records the runs and step keys it
   is based on. Examples:
   - a loop ends `not_converged` in more than a quarter of runs;
   - a loop never uses more than one pass;
   - a worker asks the same question in more than one run;
   - a gate waits longer than a set time;
   - a step fails at the same point with the same error;
   - the owner left feedback on the step.
2. **A reviewer agent drafts the change.** The designer gives a reviewer agent the form,
   the signals, the owner's feedback and the relevant run summaries. The agent returns
   suggestions in a fixed schema. It can run on demand from the designer, or as its own
   Orca automation, for example weekly, using the trigger support above.

Each suggestion has:

- a title and the reason, in plain words;
- the evidence: the signals, runs, step keys and feedback it is based on, as links;
- the change, as an edit to the form: add, remove, move or change a node or a setting;
- the expected effect, stated so it can be measured, for example "fewer `not_converged`
  review loops";
- the risk of the change.

The designer validates the changed form before it shows a suggestion. A suggestion that
would fail validation is dropped, and the reviewer's run log says why.

### Kinds of suggestion

| Kind | Example |
|---|---|
| Change a setting | Raise `max_review_passes` from 3 to 5; remove the unused test retries |
| Tighten a worker spec | Add the evidence the orchestrator keeps rejecting; answer the question the worker keeps asking |
| Add or remove a step | Add a `diagnose` step before `fix`; remove a check that never fails |
| Add or move a gate | Ask the owner before `fix` pushes, after the note "this should have asked me first" |
| Change the agent, model or effort | Move `review` to another agent that the owner rated better |
| Use a skill | Replace a free-text review step with an installed review skill |
| Run in parallel | Two independent handoffs that always run one after the other |
| Change a trigger | Add a `--precheck` to a schedule that is usually skipped; move from a schedule to an event |
| Add a rule | Add a rule to the orchestrator after the owner's feedback names the same mistake twice |

### Accepting a suggestion and checking the result

The designer shows each suggestion as a diff of the form and a diff of the generated
Markdown. The user can:

- **accept** it: the designer saves a new version with the change and records which
  suggestion made it;
- **edit then accept** it;
- **reject** it, with an optional reason. The reviewer gets rejected suggestions and their
  reasons as input next time, so it does not suggest the same change again;
- **defer** it.

With 7A, an accepted change reaches Orca only when the user regenerates the bundle and
re-registers its triggers.

After a change has run N times, the designer compares the new version with the old one on
the effect the suggestion stated, and shows the result beside the suggestion: improved,
no change, worse, or not enough runs yet. A change that made things worse comes with a
one-step way back to the previous version.

## Risks

| Risk | Effect | Mitigation |
|---|---|---|
| An agent does not follow a prompt as an engine runs code | A step is skipped, repeated or done out of order | Step keys in every status comment; explicit stop tests and pass limits; the orchestrator rebuilds its position from the state store on every pass |
| Orca's CLI changes | Generated commands stop working | The manifest records the Orca version. The prompt loads `orca skills get orchestration` at run start, and its flags win. A test generates each example and runs `orca <command> --help` for each command it uses |
| A skill is renamed or removed on one machine | A run fails mid-way | The orchestrator checks every skill in the manifest before it starts a worker |
| Event text tries to steer the orchestrator | A stranger's comment changes what the factory does | Every prompt treats event and worker text as data. Only the named owner's labels and comments release gates, and the orchestrator checks who applied a label |
| Long nested loops spend many agent hours | Cost and noise | Pass limits on every loop, a total worker limit per run, and a `--precheck` on scheduled triggers |
| A suggestion fits one bad run, not the workflow | A change that helps once and hurts after | Rules need a signal over N runs, or the owner's feedback; each suggestion states a measurable effect, and the designer checks it after the change |
| The reviewer agent suggests a change that is wrong | The factory gets worse | Every suggestion cites its evidence, passes validation and needs the user's acceptance; a worse result has a one-step way back |
| Feedback text tries to steer the orchestrator during a run | A run does something the workflow does not say | The orchestrator records feedback and never acts on it during the run; only the owner's feedback counts |

## Milestones

Each milestone ends with a workflow that runs in Orca, as the reference engine's milestones each end
with a proving workflow.

1. **Form, generator and validation.** The workflow form, the generator for
   orchestrator, handoff, condition and loop-until nodes, the validation rules, and the
   skill catalog. Proving workflow: the `ci-fix` example, run by hand by pasting
   `orchestrator.md`.
2. **Nested loops, for-each and parallel.** Orca Task DAGs for parallel and for-each
   nodes. Proving workflow: review three PRs in parallel, each with a fix loop.
3. **Triggers.** Schedules and event rules, written to `triggers.sh`, and with 5B
   registered through `orca automations create`. Proving workflow: `ci-fix` started by
   `github.ci_failed`.
4. **Visual editor.** The graph, the palette of skills and agents, and a side-by-side
   view of the generated Markdown, built on the same layout as
   the reference engine's graph view.
5. **Runs.** Read the state store and show each run's step keys and outcomes on the
   graph, as the reference engine's run page does. Workflow versions, and the hash in each run's
   start comment.
6. **Feedback and suggestions.** Feedback in the designer and through `/orca feedback`,
   the signal rules, the reviewer agent, accept and reject, and the comparison of a
   version with the one before. Proving workflow: `ci-fix` with a review pass limit of 1,
   so its review loop often ends `not_converged`; the designer must suggest a higher
   limit, and after the change the comparison must show fewer `not_converged` loops.
7. **Generate the hand-written coordinator prompt.** Build that factory in the designer
   and compare its output with the hand-written prompt. Every difference is either a
   gap in the designer or a fix to the prompt.

## Open questions

- Should a sub-workflow run as a worker of the parent orchestrator, or as its own Orca
  Run that reports back? A worker is simpler; a Run keeps the two state machines apart.
- How many runs (N) must a version have before the signal rules and the comparison of
  versions give a result? A workflow that runs weekly takes N weeks to reach it.
- Does the owner want the generated prompts to follow the owner's house style
  (Simplified Technical English) by default?
