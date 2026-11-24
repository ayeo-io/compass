# Factory Workflow Designer

A tool for designing factory workflows as graphs, and generating the Markdown
prompts that run them in Orca.

## Language

### People

**Author**:
The person who builds and changes a Workflow in the designer.
_Avoid_: user, designer (for the person)

**Owner**:
The person who approves Gates and gives Feedback while a Workflow runs. One person can be
both Author and Owner.
_Avoid_: user, approver

### Workflows

**Workflow**:
A graph of Steps, Variables and Triggers, which the designer generates prompts from.
_Avoid_: factory (for one workflow), pipeline

**Workflow Form**:
The saved definition of a Workflow, and its single source of truth. The generated
Markdown is output only.
_Avoid_: spec, definition file

**Workflow Bot**:
The Orca Bot that runs one Workflow. Its automations are the Workflow's Triggers. It
works on GitHub as the Owner.
_Avoid_: factory bot, agent (for the Bot)

**Trigger**:
A schedule or an event that starts a Workflow Run.
_Avoid_: hook, cron

**Intake Rule**:
The rule that decides which issues and pull requests become Work Items of a Workflow.
_Avoid_: admission, filter

**Workflow Version**:
One saved state of a Workflow Form, named by the hash of its content.

**Bundle**:
The set of Markdown prompts and commands generated from one Workflow Version.
_Avoid_: output, package

### Agents

**Coordinator**:
The one top-level agent of a Workflow. It starts Workers, checks their evidence, and
moves the work on. It does not write product code.
_Avoid_: orchestrator

**Worker**:
A separate Orca agent that a Coordinator starts to do one piece of work and report back.
_Avoid_: subagent

**Handoff**:
The Step that starts a Worker, with its spec, agent, worktree and the evidence that proves
it is done.
_Avoid_: delegation, dispatch (for the Step)

### Running

**Work Item**:
One issue or pull request that a Workflow moves from start to finish. It holds its own
progress in the State Store, across many Workflow Runs. Not an Orca Task, which Orca's
docs also call a "work item".
_Avoid_: slice, ticket, job, task

**Workflow Run**:
One Coordinator session that moves every open Work Item of a Workflow forward until each
is waiting at a Gate, stuck or done. It is one Orca Run, and each Handoff in it is one
Orca Task.
_Avoid_: execution, job

**Approval**:
A stop where a Work Item waits until the Owner says it may go on. The Owner gives it in
Slack, where the Workflow Bot posts as itself. Not an Orca decision gate, which the
Coordinator owns and resolves.
_Avoid_: gate, sign-off

**Feedback**:
What the Owner says about how a Workflow is going, tied to a Workflow Version and, where it
applies, a Step Key. It changes later Workflow Versions, never the Run in progress.
_Avoid_: comment, rating

**Suggestion**:
A proposed change to a Workflow Form, with the signals and Feedback it is based on, which
the Author accepts or rejects.
_Avoid_: recommendation, improvement

**Step Key**:
The path that names one Step for one Work Item in one pass of every Loop around it, such
as `#12/review-loop/2/fix`.

**State Store**:
Where a Workflow Run records its progress so that a new Coordinator session can find its
place. GitHub labels and comments are the first State Store.
_Avoid_: memory, database
