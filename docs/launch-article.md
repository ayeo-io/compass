# My spec-driven dev tool works for me. That's the problem.

A few weeks ago I noticed which Compass command I was running most. Not the one
that sizes a piece of work, or the one that checks it. It was the one that quietly
admits I got the assessment wrong and re-does it. I built the tool to stop me
skipping steps under pressure, and the part I reach for most is the part that
says "you called this one wrong, start that bit again."

That's an odd thing to admit about something you built. It's also the most useful
thing I can tell you about it.

Here's the situation. I've been using Compass on my own work for a few weeks. It's
held up. I'm less annoyed than I was, the small changes stay small, and the scary
ones get the full treatment. But "it works for me" is one of the weakest claims
there is. A tool whose whole job is to decide how much process a piece of work
needs has so far had only one judge: me. That isn't tested.
It's just my own taste, automated. So I'm putting it out to find out whether the
idea survives other people.

## The quick version of what it does

In case you've not seen it. Most spec-driven setups run every change through the
same steps. What actually happens then is that people run the full process on
the big, scary change and quietly skip it on the typo, because doing the whole
routine
for a one-line fix is daft and everyone knows it. So the process ends up covering
the changes that were never going to hurt you, and getting skipped on some that
might.

Compass tries to fix that by splitting the rules in two. There are a few hard
guardrails that never move: tested before it lands, acceptance defined before it's
built, a human signs off on anything irreversible. And there's a set of softer
strategies, like TDD and BDD, which are the usual way of meeting those guardrails
but which you can step off, with a reason. Then it reads a few plain things about
the work, how risky it is, how big, whether it's new ground or you're cutting into
something that already exists, and works out how much process to apply. A small
change gets a light path. A new subsystem gets the full set. The hard rules hold
either way.

I wrote that part up properly a little while back, if you want the longer version.
[The one-size-fits-all problem](https://medium.com/@James.edwards_75381/spec-driven-development-has-a-one-size-fits-all-problem-ff81378f69f0)

## What it looks like when it chooses

That is the half that never moves. The other half is the point.

Fix a typo and it wants one worked example of the behaviour, a one-line note
saying which file you are editing, and a test. No written design, no separate
review of the requirements, no plan for splitting the work up, because there is
nothing to split and nothing to review.

Yes, a test, even for that - and I know that is more than "just fix it". It is
the one line that never moves, and it is the one I would keep if I had to throw
the rest away. A typo fix that breaks something is still a broken thing, and the
test costs a minute.

Add authentication to something that has none and it wants all of it: every
step at full weight, and a written description of how the existing behaviour
works before anything is allowed to change it.

For scale, on a heavy one: this release was a change to the project's own
writing rules, and it ran to forty-two worked examples across eight documents.

You do not argue it into either. You answer four plain questions - how risky,
how big, new ground or existing, what you are actually trying to do - and it
tells you what it decided and why. Asked about adding authentication to an app
that has none, it printed this:

```
  policy rules fired:
    You cannot safely change behaviour you have not first
    written down (RP-FLOOR-002, floor)
        - stage 'define' forced full-weight
    Domain risk overrides size. A one-line auth change is not
    small (RP-FLOOR-003, floor)
        - approach raised feature -> initiative
```

Wrapped to fit the page and otherwise exactly what it prints. A "floor" is a
rule that can only push the process up, never down, so no assessment can push
the process below one. The codes are how you look a rule up, and they
come after the sentence rather than before it - which is a rule this same
release added, and then caught me breaking on this very screen.

That second sentence - a one-line auth change is not small - is the whole idea,
so I will put it plainly:

**The question is not how much work it is. It is what happens if you get it
wrong.**

The typo cannot hurt you. The auth change can, and it gets the full treatment
whether or not it looks small. Most process I have worked under sizes itself by
effort, which is why the dangerous one-liner gets no review and the harmless
refactor gets a full one.

## The bit that made me trust it

I want to give you a concrete thing rather than a claim, and it's the only part of
this I'd point at if you asked why I still use it.

Compass keeps a record of what proved each change. Each record has a type, and the
types are a hierarchy of who can check it: at the top, a test run a machine
ran and recorded; below that, output from a command someone captured; below
that, a judgement a person wrote down for a reviewer to weigh. The gates read
those types. It's the part I was least sure about when I built it, because a
record of your own work is the easiest thing in the world to quietly write in your
favour.

Last week I found out what it does when I'm the one being sloppy.

I'd run the test suite and watched it pass. I'd run it in a way that produced no
machine record, and rather than run it again I wrote a small file saying it had
passed. Which was true. The gate refused it: the file claimed to be a recorded
test run and had no exit code in it, no trace of a process having actually run and
returned something.

So I fixed that one and re-ran the check. It refused the next one. Then the next.
Six records in a row, every one written by me, every one labelled as the strongest
kind of proof, and not one of them was. They were honest notes about work I had
genuinely done - and every one was claiming a machine had confirmed it when only I
had.

The fix wasn't to add fake exit codes. It was to relabel each one truthfully: my
transcription of a test run is captured output, and my write-up of an experiment is
a judgement for a reviewer to assess. Nothing about what happened changed. What
changed was the claim attached to it. After that the gate passed, resting only on
the nine records a machine had actually produced.

I built the thing, I knew the rule, I had good reasons to be in a hurry, and it
wouldn't take my word for it six times running.

And it wasn't a one-off. Building that same release, five different parts of the
tool refused me:

- the evidence gate, on six records in a row, as above
- a rule I'd just written banning obscure words, which caught me writing one of
  those words into the rule itself, inside a minute
- a test holding the list of rules the tool ships, which blocked two rules I'd
  just written until I confirmed I meant to add them rather than having let them
  drift in
- a scan I'd widened to cover more files, which found a stray reference in the
  newly covered ones within seconds
- a check on the project's own write-ups, which caught one still saying "sixteen
  checks passed" when there are now fifteen

Every one was correct. None was a bug I then had to fix; they were the tool
declining to let me skip a step, five times, in one week, on my own project.

That's the behaviour you're buying. Not process for its own sake - a system that
won't accept "it's fine, I checked" from anybody, including the person who wrote
it. I'd rather show you that than tell you it's rigorous.

## Where the evidence is still weak

Let me save you the trouble of finding the obvious gaps, because I've found a few
of them already.

It's all been solo. I've never run it with a team, which is awkward, because half
the point of process is getting people to agree, and I've no idea how it behaves
when two people assess the same work differently. The whole thing depends on
the assessment being roughly right, and as I said, the command I reach for most
is the one for when it isn't. I haven't pointed it at a big, messy, legacy codebase and
watched it struggle. And there's a fair chance that some of the things I think are
clever are just things that happen to suit the way I work.

And there's an obvious one I'll say before you do: a guardrail that demands a
human signs off on anything irreversible, on a project with one human, is me
approving my own work. That's fair. What it still buys, even solo, is that I
have to write down what I actually checked - and as the six refusals above show,
the tool won't let me pass that off as something stronger than it was. It's
weaker than a second reviewer. It's a good deal better than nothing, and it
is the first thing that gets properly tested the day someone else uses it.

None of that is false modesty. It's the actual state of it.

## Two things I'd genuinely like help with

First, use it on something small and throwaway, and tell me where it works
against you.
Not just the obvious bugs, though do tell me those. I mean where the process it
picks feels wrong, or a guardrail gets in the way for no good reason, or you'd
plainly have done it differently. I learn far more from "this annoyed me, and
here's why" than from a star on the repo.

Second, tell me where to take it next. Right now it only plugs into Claude Code,
because that's what I use and it's all I've had time to build. The routing and the
checks are kept separate from any of that on purpose, so it could in principle run
elsewhere, but "could" is not a promise, and porting it
properly is real effort. So before I spend that time, I'd rather know what people
actually want: Cursor, Codex, Gemini, or just a plain command-line version with no
agent attached at all. If you've got a preference, that's the sort of thing that'll
decide what I do next.

Building the thing was the easy part, as it usually is. The bit I can't do on my
own is find out whether an adaptive take on this holds up once it meets work that
isn't mine and habits that aren't mine. That's the whole reason it's out this
early, imperfections included. I'd rather hear where it breaks now than keep
polishing something that only ever made sense to one person.

If you want to try it, it's on GitHub at
[github.com/ayeo-io/compass](https://github.com/ayeo-io/compass). In Claude Code you
can add it as a plugin:

```
/plugin marketplace add ayeo-io/compass
/plugin install compass@compass
```

Then start with `/compass:assess "..."`. You need Python 3; the plugin
carries everything else, and the shipped defaults work as they are - nothing
to configure first. It's early, so point it at a throwaway branch.
