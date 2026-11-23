# Factory Workflow Designer: design hand-off

This folder hands over the design of a **Factory Workflow Designer**. It is a tool in
which a person builds a factory workflow as a graph. The tool then generates the
Markdown prompts that run that workflow in Orca (an agent IDE). Nothing is built yet.
This folder holds the design work so far, so that someone else can pick it up.

## Status

- **Design stage.** The design was reviewed question by question, and every open
  decision was settled. The settled decisions are below, in `CONTEXT.md` and in `adr/`.
- **`proposal.md` is older than that review.** It still lists seven open decisions and
  uses some terms that the review replaced, such as "orchestrator" for **Coordinator**,
  "gate" for **Approval**, and a GitHub `/orca feedback` comment for Feedback. Where
  `proposal.md` disagrees with `CONTEXT.md` or an ADR, the glossary and the ADRs are
  correct. Rewriting `proposal.md` to match is the first open task.
- **The UI design exists as a mockup** (see "Designs"). Nobody has checked it in a
  browser or run an accessibility review on it yet.

## What to read, in order

| File | What it holds |
|---|---|
| `README.md` | This page: the status, the settled decisions and the open tasks |
| `CONTEXT.md` | The glossary. Every term the design uses, with the words to avoid |
| `adr/` | Five decision records, one paragraph each, for the decisions that are hard to reverse |
| `proposal.md` | The full proposal: the workflow model, triggers, skills, the generated bundle, a worked `ci-fix` example, validation, Feedback and Suggestions, risks and milestones |

## Designs

- **UI mockup:** <https://claude.ai/artifact/2AaYW45Mj4pccTLd3Mb4CQ>. A canvas of five
  screens:
  1. Workflows (the home list, with a "Needs you" strip);
  2. the Workflow editor (palette, graph with nested loops, inspector);
  3. Bundle and deploy (the generated files, and the `orca` commands to confirm);
  4. Work Items (state of each issue or PR, step by step, with Owner Feedback);
  5. Suggestions (evidence, expected effect, the change to the Workflow Form, and accept
     or reject).
- **Design system:** the Nexus Design System,
  <https://claude.ai/artifact/VfQHnuW9Br4GRGycBuqmQY>. The mockup uses its tokens and its
  Button, Badge, Dot, Icon, Input and MetricTile components.

Both links are private to the owner's claude.ai account. Another account cannot open
them until the owner shares them from each page's Share menu.

## Settled decisions

### People and terms

- An **Author** builds Workflows and accepts or rejects Suggestions. An **Owner** gives
  Approvals and Feedback. One person can hold both roles.
- The agent at the top is the **Coordinator**, the agents it starts are **Workers**, and
  the Step that starts a Worker is a **Handoff**. Do not use "orchestrator", "subagent"
  or "gate" for these.

### Structure

- The **Workflow Form** is the source of truth. The generated **Bundle** of Markdown
  prompts is never parsed back (`adr/0001`).
- The designer is a new repository, written in TypeScript. It runs as a local app that
  calls the `orca` CLI, and it runs each command only after the Author confirms it.
- Each Workflow is its own Orca Bot, the **Workflow Bot** (`adr/0004`). The Bot's
  automations are the Workflow's **Triggers**. A sub-workflow is a handoff from one Bot
  to another.
- The Author picks the host for each Workflow. The designer warns when a Workflow with
  event Triggers is on a laptop, because events that arrive while it sleeps are missed.

### Running

- A **Workflow Run** is one Orca Run. It moves every open **Work Item** (an issue or
  pull request) forward until each is waiting, stuck or done. Progress belongs to the
  Work Item, for example `#12/review-loop/2/fix` (`adr/0003`).
- Only one Run per Workflow is active at a time. Before it ends, the Coordinator lists
  the open Work Items again and reads its Slack threads again, so nothing that arrived
  during the Run is lost.
- GitHub labels and comments are the **State Store**, behind an interface (`adr/0002`).
  Labels have the form `<workflow-id>:<state>`.
- The **Intake Rule** decides which issues and pull requests become Work Items. The
  default is the Owner's label, picked up by a scheduled Run. Admission by an event is
  allowed only when the Trigger is limited to named people or places.
- **Approvals** are given in Slack, where the Bot posts as itself, and are recorded on
  the pull request. The Bot reminds the Owner after 2 days and never approves by itself
  (`adr/0005`). A GitHub label cannot carry an Approval, because the Bot works on GitHub
  as the Owner.
- A Worker's permission prompt is denied unless its Handoff lists that prompt as
  allowed.
- The Bot's memory holds nothing about Work Items or how to work. Every change in
  behavior goes through a new Workflow Version.

### Feedback and Suggestions

- The Owner gives Feedback in Slack or in the designer. The Coordinator copies Slack
  Feedback to GitHub with a link to the Slack message, so the designer reads only GitHub.
- Fixed rules find signals over the last 5 Work Items that reached a Step. A reviewer
  agent drafts **Suggestions**, and each one must cite a signal or a piece of Feedback.
- Accepting a Suggestion creates a new **Workflow Version** and regenerates the Bundle.
  The redeploy is shown as `orca` commands, which run after the Author confirms them.
- The generated prompts use the Owner's house style by default.

## Open tasks

1. Rewrite `proposal.md` to match the settled decisions above.
2. Check that a Slack mention from the Bot's own Owner starts that Bot's automation.
   Orca's documents exclude only the Owner's own GitHub and Linear actions, so this is
   expected to work, but nobody has tested it. `adr/0005` depends on it.
3. Check that `orca automations edit` accepts `--precheck`. The deploy screen in the
   mockup assumes it does.
4. Review the mockup: a design critique, an accessibility review, and a check at phone
   width.

## Sources

- Orca facts come from Orca 1.4.271 (`orca --help`, `orca skills get orchestration`,
  `orca skills get orca-cli`) and its public repository, <https://github.com/stablyai/orca>.
  Orca's orchestration is marked Experimental and its flags change between releases.
  Check them against the installed version before relying on them.
- The approach comes from an existing workflow engine, called "the reference engine" in
  these files, that builds a workflow as a graph and generates Python from it. Its code is
  private and is not needed to use this design.
