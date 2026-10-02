---
description: Optionally adopt and extend project governance
allowed-tools: Read, Write, Edit, Bash, Glob
---

# /compass:init

`/compass:init` is **optional**, and it is not what creates your project.

The `compass init` verb creates `.compass/` - a config file and the work
directory - and your first Compass command runs it for you and says that it
did. So the command you wanted to run initialises the project,
not a setup step you had to know about first.

What `/compass:init` adds on top is the governance conversation below. Compass
ships with five default guardrails, a set of default method strategies
(including BDD and TDD), and a default routing policy, all active from
install, and `/compass:assess` computes delivery approaches against them on day
one. This command is not a gate you must clear before the first issue.

What init *is*: the step where a project starts to **build up its own
governance**. It copies `governance/` into the project so the team can
extend it - adding project-specific guardrails and strategies, and tuning
the routing policy to the project's real risk surface. A project can adopt
governance a piece at a time: "the shipped
defaults and nothing project-specific yet" is a complete, valid governance
state. Init is how a team adds to its own governance, when it has formed
opinions worth writing down - not before.

Run it whenever the team is ready. It does not change application code, so
it is exempt from assessment.

## Steps

1. **Check for an existing install.** If a project `governance/` directory
   or `.compass/config.yml` already exists, stop and report what is
   present. Do not overwrite live governance; offer to show a diff against
   the shipped defaults instead.

2. **Copy `governance/` into the project.** Place the shipped `governance/`
   files named here at the project root, and no others: the Compass
   repository's own `review-rules.yml` and `decisions/` stay behind. Copy
   the prose `guardrails.md`, `strategies.md`,
   `strategies-rationale.md`, `routing-policy.md`, `README.md`, **and the
   machine-readable `guardrails.yml` and `routing-policy.yml`** - the latter two are what
   the `compass` CLI runs (`compass approach evaluate`, `compass check`,
   `compass policy lint`). These arrive with their defaults already active
   and in force - they are not empty templates. The `cli/` and `schemas/`
   directories ship with the framework and are not copied per-project; the
   CLI walks up to find a project-local `governance/`, falling back to the
   shipped defaults. The five default guardrails and the default method
   strategies are real content from the moment they land.
   `strategies-rationale.md` holds the incidents behind the rules in
   `strategies.md`, which links to it - copying one without the other leaves
   that link pointing at nothing.

3. **Walk the team through extending them** - additively, in each role's
   own language, a few questions at a time. The team does not need to fill
   any section; an empty project section is a valid, complete state.
   - **`guardrails.md` - project guardrails section.** Add a guardrail only
     when the team hits something that must *never* recur and can be
     checked with evidence. Guardrails are slow to add and slower to
     remove. Leave the section empty rather than padding it.
   - **`strategies.md` - project strategies section.** Add freely -
     strategies are meant to build up. Product, engineering, and voice &
     positioning preferences all live here. A strategy is directional and
     assessed, not checkable or blocking.
   - **`routing-policy.md` / `routing-policy.yml`.** Tune them to the
     project, keeping the prose and the YAML in step - the YAML is
     authoritative for what the CLI runs. The soft biases
     (`default_shapes`, `biases`) are meant to be adjusted as the team
     learns how its work distributes. The hard rules (floors, caps,
     immovable_gates, role_rules) bound the computed delivery approach -
     adjust them deliberately; loosening one weakens the framework for
     everyone. Run `compass policy lint` after any edit to the governance
     YAML.
   Fill `{{PROJECT_NAME}}`, `{{DATE}}` (today), and each file's
   amendment-log first row. Do not leave `{{...}}` placeholders behind.

4. **Create the config.** `compass init` has already written a minimal
   `.compass/config.yml` if one was missing. Set
   `project.name` and `project.test_command`. It holds only project
   settings - routing rules (the default shape, the worktree caps) live in
   `governance/routing-policy.yml`, which is authoritative; tune routing
   there, not here.

5. **Create working state.** Make `.compass/work/`. Add a `.gitkeep` if
   empty. Remind the user that `.compass/work/` **is committed** - it is
   the audit trail, not scratch. `/compass:assess` will later write
   `.compass/current-task` (the pointer the CLI uses to resolve which issue
   a `compass` call acts on); it does not need to be created now.

6. **Report.** Summarise what was created, which project sections the team
   chose to leave empty (a valid state, not owed work), and the next
   command: `/compass:assess` for an engineer, or a role entry point -
   `/compass:intent` (product owner/manager), `/compass:position` (product
   marketer), or `/compass:design` (designer).

## Gate

Init is complete when the project `governance/` files are in place with no
remaining `{{...}}` placeholders in their headers and amendment logs, and
`.compass/config.yml` is set. The project guardrail and strategy *sections*
can be left empty - that is a project section not yet built up, not an
unfinished step. The shipped defaults are in force regardless.
