# Writing voice

**communicate the decision, do not perform the process - say what happened and what is needed, never announce which stage you are in**

That is the whole rule. A session narrates the framework when it says "I will
now proceed to the requirements review stage" - the human can already see the
pipeline; naming the stage tells them nothing they did not know. It
communicates a decision when it says what changed and what it needs next. The
difference is not vocabulary - both sentences can use exactly the same v2
terms - it is whether the sentence acts out a process or reports on one.

**The calibration sample.** Before writing anything in this register, read the
"Never stash across a worktree hop" section of
`skills/worktree-multiagent/SKILL.md`. It tells a real incident - a stash popped
inside a temporary worktree destroyed work when the worktree was removed - in
plain sentences, with no stage name announced and no field left to do the
talking. That is the voice every surface below is asking for.

## Before and after, from the real archive

Every "before" below is a verbatim quote from a file under `.compass/work/`,
cited by path. Nothing here is invented - invented examples teach the person
who wrote them, and nobody else. The bar every "after" had to clear: read it aloud - would you say this sentence to a colleague at your desk?

### Pair 1 - a stage announcement reads like a log line

Source: `cross-task-architectural-integrity/devlog.md`

Before:

> **Status:** Distribute complete. Ready for `/compass:build`.

After:

> All six worktrees are set up on the foundation commit. The builders can start.

What changed: says what actually exists (six worktrees, on a named commit) instead of a status word and the name of the next command.

### Pair 2 - a status line drops the two facts that matter

Source: `cross-task-architectural-integrity/devlog.md`

Before:

> **Status:** Build phase green across all 6 streams. Local evidence (red.json + green.json per scenario) lives in each worktree's spine. Ready for `/compass:verify`.

After:

> All six streams are green, and each one has its red and green evidence saved. Time to pull them together and check the whole thing.

What changed: keeps the two facts a reader actually needs (all green, evidence saved) and turns the next step into something a person would say, not a command name to queue behind.

### Pair 3 - "ready for the next command" is not news

Source: `swarm-script-strips-markdown/devlog.md`

Before:

> **Status:** Verify PASS. Ready for `/compass:land`.

After:

> It passed review. This is ready to ship.

What changed: tells the reader the thing they actually want to know - that it is safe to release - instead of a status word and a queue ticket for the next command.

### Pair 4 - a bare command name is not a sentence

Source: `compass-self-architecture/devlog.md`

Before:

> **Invoked:** `/compass:clarify` (Standard, light pass).

After:

> Ran the requirements review as a lightweight pass, since this was feature-sized work.

What changed: says why the pass was lightweight in the same sentence as what ran, instead of a bare command name with its parameters trailing in parentheses like a log line.

### Pair 5 - a field label does the talking

Source: `compass-self-architecture/devlog.md`

Before:

> **Status:** Land complete on local; PR open awaiting CI + merge.

After:

> It's merged locally; the PR is open, waiting on CI.

What changed: says the two things a person actually wants to know - merged, and what is still pending - instead of a status word plus a semicolon-joined checklist.

### Pair 6 - "resolved" is a checkbox, not a decision

Source: `friction-loop/requirements-review.md`

Before:

> **Status:** resolved

After:

> We settled on two - it's the smallest honest pattern at this scale, and it lines up with calibration's own threshold.

What changed: gives the actual number and the reasoning behind it, not a word confirming a form field got filled in.

### Pair 7 - the "Decided by" field that hides the decision

Source: `make-receipt-render/requirements-review.md`

Before:

> **Decided by:** jed72 (engineer) via Clarify reasoning recorded here; defaults if not overridden.

After:

> jed72 decided this one; nobody pushed back.

What changed: says who decided and whether it was contested, in a sentence, without losing either fact.

### Pair 8 - a label-and-value row instead of a next step

Source: `make-receipt-render/requirements-review.md`

Before:

> **Spec change:** **Required**

After:

> The scenarios need updating to match.

What changed: tells the reader directly that action follows, instead of a label-and-value row answering a question nobody asked out loud.

## The terms a reader cannot follow, and what to say instead

A cold reader hit six of these in one message on 2026-08-15 and named every one
unprompted. Their words are kept because that is what makes the next such
term noticeable: the failure was not ignorance of the rule, it was not noticing these
words were jargon. Someone a day inside the vocabulary cannot see them.

| Written | What the reader said | Say instead |
|---|---|---|
| "papercuts" | "what the hell is papercuts?" | a list of small irritations |
| "work the issue owes" | "would be better as 'outstanding work'" | outstanding work |
| "a stale green on record" | "I have no idea what a stale green is - is it green or not?" | the tool checks a recorded result, not the tests, and the record can be old |
| "keys only on the define stage's weight, with no role condition" | "pretty meaningless to me" | it asks how much work the step is doing and never asks who is involved |
| "at full weight" | "what is 'at full weight'?" | when that step is being done properly rather than skipped |
| "borrowed process weight" | "a meaningless sentence to me" | the list of steps that were skipped earlier and have to be gone back and done |

**The four families these come from**, so the next leak is recognisable before a
reader has to ask:

- **stage weights** - thorough, lightweight, collapsed, skipped. Say what actually happens
  to the step.
- **borrowed process weight** - the follow-ups list. Say what is outstanding and why.
- **evidence types** - `test-run`, `command-output`, `manual-review`,
  `human-approval`. Say what the thing is: a recorded test run, the output of a
  command, someone's written review, a person's sign-off.
- **delivery approaches** - quick fix, regular, full, hotfix, spike. Say how
  much process the change is getting and why.

Not one of these is a hard idea. Each took a single sentence to say plainly.

## A rival product is named by its code

When the project keeps a names key - a private file, never committed, that
maps codes such as R1 to rival product names - write the code, never the
name, alias, repository slug or URL, in anything committed or synced: files,
paths, branch names, commit messages, pull requests and the delivery record.
Compass's own repository keeps its key, untracked, under `.compass/private/`,
and checks with `scripts/rival-name-gate.py`.

## The tells

Nine habits mark this narration. Three of them a fixed string can find -
`scripts/voice-tells.py` greps those three over the current issue's
artifacts, advisory only. The other six need a reader; no string reliably
tells them apart from an honest sentence that happens to share a word. This
is the one place this list lives - every other surface that names a tell
links back here, or names only the three the check greps.

1. **"I will now proceed"** - **findable**. The check greps this exact
   string.
2. **"successfully" suffixed to a completed verb** - **judgement**. Look for
   a report of a thing already done ("added successfully", "ran
   successfully") standing in for what actually changed.
3. **"the X stage" used as dialogue** - **judgement**. Look for a pipeline
   stage name doing the work of a sentence - "ready for the verify stage"
   reports to a dashboard, not to a person.
4. **"accordingly"** - **judgement**. It has honest uses in conditional prose,
   so a grep for it would raise false alarms; a repository-wide search
   turned up exactly one hit, a sentence nobody would touch, so it stays a
   reader's call.
5. **"utilize"** - **findable**. The check greps this exact string; "use"
   always beats it.
6. **"Upon completion"** - **findable**. The check greps this exact string.
7. **headings inside conversation** - **judgement**. Look for a heading
   *labelling* the prose beneath it - "## Summary" over a summary, "## Status"
   over a status. The test is whether the heading answers a question the reader
   was already going to ask. "## Summary" does not; nobody asked for a summary.
   "What I need from you" does - it is one part of the reply shape (what I
   did, outstanding questions, what I need from you, what I intend to do
   next) working rather than this tell firing. A label is the tell; an
   answer is not.
8. **restating the request before answering it** - **judgement**. Look for a
   paragraph that repeats what was asked before it answers it - the person
   already knows what they asked.
9. **status-report framing of something the person just watched happen** -
   **judgement**. Look for a bare status word or field ("Status: PASS")
   standing in for the sentence a person would actually say about what
   happened - most of the pairs above are exactly this tell.
