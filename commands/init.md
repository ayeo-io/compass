---
description: Write the project's compass.yml
allowed-tools: Read, Write(./.compass/**), Write(./docs/**), Write(./compass.yml), Edit(./.compass/**), Edit(./docs/**), Edit(./compass.yml), Bash(compass *), Glob
---

# /compass:init

`/compass:init` is **optional**, and it is not what creates your project.

The `compass init` verb creates `.compass/` - a state file and the work
directory, and no settings file - and your first Compass command runs it for you and says that it
did. So the command you wanted to run initializes the project,
not a setup step you had to know about first.

What `/compass:init` adds is **`compass.yml`**, the one file a person edits. It
holds the project's settings (name, test command, autonomy, adoption mode) and,
when the team wants them, its own edits to the shipped governance. Compass
ships a default set of guardrails, method strategies and routing rules, all in
force from install, and `/compass:assess` computes delivery approaches against
them from the first issue. You do not have to run this command before the
first issue.

`/compass:init` copies nothing. Compass runs one fixed set of checks (ADR-094),
so a new project's `compass.yml` holds only its settings, and "the shipped
defaults and nothing project-specific yet" is a complete, valid configuration. 5.x versions of this command copied `governance/` into
a project. `compass policy migrate` on 8.x converts such a copy; 9.0.0 removed
that command (ADR-094).

Run it whenever the team is ready. It does not change application code, so
it is exempt from assessment.

## Steps

1. **Check what the project already has.** Look for these, in order:
   - A `compass.yml` with a top-level `schema:` key. Compass already has its
     configuration. Stop and report that. Offer `compass policy lint` and
     `compass policy show`, which show the check set, its digest and the
     settings that tighten it. Do not overwrite the file.
   - A `compass.yml` with no `schema:` key. Compass does not read it, so it is
     another tool's file. Stop and report that. Do not overwrite it and do not
     write a second file beside it. Tell the person to move it to another name
     or to add `schema: 1`.
   - A `.compass/config.yml`, or copied governance: both
     `governance/routing-policy.yml` and `governance/guardrails.yml` in the
     project, a copy made under 5.x. Go to step 2.
   - None of these. Go to step 3.

   Then go on to the status line step below, which runs every time.

2. **Stop on an older project.** Never write a fresh `compass.yml` beside an
   older settings file: Compass refuses a project that holds settings in both.
   9.0.0 has no command that converts the old files (ADR-094). Stop and report
   that the project must run `compass policy migrate` on Compass 8.x first, and
   that the upgrade guide names the 9.0.0 settings. Change nothing.

3. **Write a minimal `compass.yml` for a new project.** Ask for the project's
   name, its test command and who approves waivers (the owner). Write
   `compass.yml` at the project root:

   ```yaml
   schema: 1
   owner: <the person who approves waivers>
   project:
     name: <the project's name>
     test_command: <the command that runs the tests, such as "pytest -q">
   ```

   Then ask one optional question: "Which language should the agent write
   prose in, such as `en-US` or `de`? Leave it blank to set none." Add
   `language: <the tag>` to the file only when the person answers. A blank
   answer adds no key, and nothing is written in its place. Do not guess the
   language from anywhere else. The tag is a BCP 47 tag, and
   `docs/configuration.md` lists the usual ones.

   The name is `project.name` and the command is `project.test_command`.
   `compass init` writes no settings file, so this is the first one. Run
   `compass policy lint` and report that it passes. If it reports a `language`
   finding, show it, ask again and lint again. Write no tag that lint has not
   passed. Do not add keys the team has
   not asked for: every other setting has a default (see
   `docs/configuration.md`), and a missing key is a complete state.

4. **Help the team extend the defaults, if it wants to** - a few
   questions at a time, in each role's own language. The team does not need to
   add anything.
   - **Settings** go in `compass.yml` beside `project:`: `autonomy`,
     `adoption` (`advisory` to pilot Compass, `enforced` once the team is
     ready), `enforcement.code_globs`, `multiagent`, `record`. Routing rules do
     not go there.
   - **Changes to the shipped checks, gates, rules and approaches** are entries in
     the file's catalog keys, and each is checked against the default:
     tightening needs nothing, and loosening needs a waiver with an approver.
     Add one only when the team finds a problem that must never happen again. Run
     `compass policy lint` after every edit, and `compass policy show` to
     see the result.

   Replace every `<...>` placeholder from step 3 before you write the file.

5. **Check working state.** `compass init` already made `.compass/work/`. Add
   a `.gitkeep` if it is empty. Remind the user that `.compass/work/` **is committed** - it is
   the audit trail, not temporary files. `/compass:assess` will later write
   `.compass/current-task` (the pointer the CLI uses to resolve which issue
   a `compass` call acts on); it does not need to be created now.

6. **Report.** Summarize what was created, what the team chose to
   leave at the default (a valid state, not owed work), and the next
   command: `/compass:go` for a change, or `/compass:assess` to rate one
   first.

## The status line, even when step 1 stops

Run this whether or not step 1 stopped for an existing install: a project
that adopted Compass long ago still needs its status line.

1. Ask which settings file the person wants: their own `settings.json` in
   `~/.claude`, or the project's `settings.json` in its `.claude` folder.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/statusline-setup.py" --settings <that file>`.
   It finds the launcher this plugin's session-start hook keeps under
   `~/.claude/plugins/data/`, prints the change it would make, and writes
   nothing.
3. Show the person that output. If it is a change, ask: "Add the Compass
   status line to this file?" Only on a yes, run the same command again with
   `--apply`. A person approves a change to their settings (guardrail 5).
4. If it says the file already has a status line that is not Compass's,
   pass on its advice for combining the two, and change nothing.

## Gate

Init is complete when `compass.yml` exists with `schema:`, `compass policy lint`
passes, and no placeholder remains in it. For an older project, init is complete
when it has reported that the project must migrate on 8.x first and the old files
are untouched. The shipped defaults are in force regardless.
