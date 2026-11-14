# My spec-driven dev tool works for me. That's the problem.

I have used Compass on my own work for a few weeks, and it has held up. The
command I run most is the one that re-does an assessment I got wrong.

"It works for me" is a weak claim. The tool decides how much process a
piece of work needs, and it has had one judge so far: me. I am publishing
it to find out whether the idea holds for other people.

## The quick version of what it does

Most spec-driven setups run every change through the same steps, so
people skip the process on small changes. Some small changes are the
dangerous ones.

Compass splits the rules in two:

- **Guardrails never move.** A change is tested before it lands. Acceptance
  is defined before it is built. A human signs off on anything
  irreversible.
- **Strategies are defaults.** TDD and BDD are the usual way to meet the
  guardrails. You can depart from one, with a reason.

Then it reads how risky the work is, how big, and whether it is new ground
or existing code, and works out how much process to apply. A small change
gets a light path. A new subsystem gets the full set. The guardrails hold
in both.

The longer version:
[The one-size-fits-all problem](https://medium.com/@James.edwards_75381/spec-driven-development-has-a-one-size-fits-all-problem-ff81378f69f0)

## What it looks like when it chooses

- **Fix a typo.** It wants one worked example of the behaviour, a one-line
  note that names the file you are editing, and a test. It wants no written
  design, no separate review of the requirements and no plan for splitting
  the work.
- **Add authentication to something that has none.** It wants every step at
  full weight, and a written description of how the existing behaviour works
  before anything changes it.

Yes, a test, even for the typo. It costs a minute, and it is the one rule
I would keep.

For scale: this release was a change to the project's own writing rules,
and it ran to forty-two worked examples across eight documents.

You answer four plain questions - how risky, how big, new ground or
existing, what you are trying to do - and it tells you what it decided and
why. For adding authentication to an app that has none, it printed this:

```
  policy rules fired:
    You cannot safely change behaviour you have not first
    written down (RP-FLOOR-002, floor)
        - stage 'define' forced full-weight
    Domain risk overrides size. A one-line auth change is not
    small (RP-FLOOR-003, floor)
        - approach raised feature -> initiative
```

This is wrapped to fit the page and otherwise exactly what it prints. A
"floor" is a rule that can only push the process up, never down. The codes
are how you look a rule up.

**The question is not how much work it is. It is what happens if you get it
wrong.**

The auth change gets the full treatment even when it looks small. Process
sized by effort gives the dangerous one-liner no review and the harmless
refactor a full one.

## The bit that made me trust it

Compass keeps a record of what proved each change. Each record has a type,
and the gates read the type:

1. a test run that a machine ran and recorded;
2. output from a command that someone captured;
3. a judgement a person wrote down for a reviewer to weigh.

Last week I ran the test suite in a way that produced no machine record.
I did not run it again. I wrote a small file saying it had passed, which
was true. The gate refused it: the file claimed to be a recorded test run
and had no exit code in it.

I fixed that one, and the gate refused the next. Six records in a row,
every one written by me and labelled as the strongest kind of proof, and
not one of them was. Each was an honest note that claimed a machine had
confirmed it.

I relabelled each one truthfully: my transcription of a test run is captured
output, and my write-up of an experiment is a judgement for a reviewer.
Then the gate passed, resting only on the nine records a machine had
produced.

In the same release, five different parts of the tool refused me:

- the evidence gate, on six records in a row, as above;
- a rule I had just written banning obscure words, which caught me writing
  one of those words into the rule itself, inside a minute;
- a test holding the list of rules the tool ships, which blocked two rules
  I had just written until I confirmed I meant to add them;
- a scan I had widened to cover more files, which found a stray reference
  in the newly covered ones within seconds;
- a check on the project's own write-ups, which caught one still saying
  "sixteen checks passed" when there are now fifteen.

Every one was correct, and none was a bug: five refusals, in one week, on
my own project. The tool does not accept "it's fine, I checked" from
anybody, including the person who wrote it.

## Where the evidence is still weak

- **It has all been solo.** I have never run it with a team. I do not know
  how it behaves when two people assess the same work differently.
- **It depends on the assessment being roughly right.** The command I run
  most is the one for when it is not.
- **I have not pointed it at a big, messy, legacy codebase.**
- **Some of it may only suit the way I work.**
- **On a project with one human, I approve my own work.** The human
  sign-off still makes me write down what I checked, and the six refusals
  show the tool will not let me pass that off as something stronger. It is
  weaker than a second reviewer. It gets tested properly the day someone
  else uses it.

## Two things I'd like help with

**Use it on something small and throwaway, and tell me where it works
against you.** Tell me the bugs, and also where the process it picks feels
wrong or a guardrail gets in the way for no good reason.

**Tell me where to take it next.** Right now it plugs into Claude Code
only. The routing and the checks are separate from that, so it could run
elsewhere, but a proper port is real effort. Before I spend that time, I
want to know what people want: Cursor, Codex, Gemini, or a plain
command-line version with no agent attached.

It is on GitHub at
[github.com/ayeo-io/compass](https://github.com/ayeo-io/compass). In Claude
Code, add it as a plugin:

```
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Then start with `/compass:assess "..."`. You need Python 3; the plugin
carries everything else, and the shipped defaults work with nothing to
configure. It is early, so point it at a throwaway branch.
