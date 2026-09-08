---
name: fieldnotes
description: Set up and maintain a shared `.ai/` knowledge base in a repository - architecture notes, symptom-indexed debug records, shared AI memory, and a handoff file. Use when a project's hard-won knowledge lives only in one person's local AI memory or in commit messages, when onboarding a collaborator, when asked to write down a debugging finding or an architecture decision, or when asked where a piece of information should go.
---

# Fieldnotes — shared project knowledge

Most of what a project costs to learn never reaches a file. It lives in one person's
local AI memory, in the seventh paragraph of a commit message, or nowhere. The next
person - or the same person in three months - pays for it again.

This skill maintains a `.ai/` directory that holds that knowledge where both humans and
AI sessions can read it, and where a second contributor gets it for free.

## The one structural idea

**Organize by how long something stays true, not by topic.**

Topic-based docs grow until updating one thing means reading past three others. A
thousand-line technical document usually turns out to be four documents with different
lifetimes stapled together:

| Lifetime | What | Where |
|---|---|---|
| Nearly permanent | Platform/SDK behaviour that is not obvious | `CLAUDE.md` constraints section |
| Reversible | Decisions, with the alternatives that lost | The project's decision doc |
| One-off, but must stay findable | Incidents and how they were diagnosed | `.ai/debug/` |
| Expires by design | Progress, work in flight, next step | `.ai/handoff.md` |

## Layout

```
.ai/
├── README.md          index + the routing table below
├── architecture.md    end-to-end data flow: what happens to one unit of work
├── debug/
│   ├── INDEX.md       symptom -> file
│   └── YYYY-MM-DD-<symptom>.md
├── decisions/         only if the repo has no decision doc already
│   └── <slug>.md
├── memory/            shared AI memory, one fact per file
│   ├── MEMORY.md
│   └── <slug>.md
└── handoff.md         current state; expires
```

`templates/` holds a starting point for each of these.

**Do not scaffold folders you cannot fill today.** A skeleton of empty directories is
worse than three living files: people stop trusting the structure and go back to putting
everything in one README. Create a folder when there is a first entry for it.

## Routing: where does this piece of information go

This table is the skill. Everything else is filing.

| Observation | Goes to | Test (all must hold) |
|---|---|---|
| Non-obvious platform/SDK behaviour | `CLAUDE.md` constraints | Still true in a year **and** you would not guess it from the docs |
| A choice was made, alternatives rejected | Decision doc | You can write "why not the other one" |
| A fault whose symptom was far from its cause | `.ai/debug/` | Next time it will be searched for **by symptom** |
| Progress, in-flight work, next step | `.ai/handoff.md` | It will go stale - that is the point |
| How a particular person likes to work | **Local memory, not the repo** | It is about the person, not the project |

**What not to write:** code structure, bugs already fixed, anything git history already
says. These rot immediately and the original source is always more accurate.

## Debug records

Index **by symptom, not by cause**. When you start looking you know "the face is frozen";
you do not yet know "the device is returning a stale buffer with the valid flag still
set". A cause-indexed file is unfindable at the moment you need it.

Name files `YYYY-MM-DD-<symptom-phrase>.md`. Each entry carries:

- **Symptom** - what was visible, including what was *not* there. Zero errors is a clue.
- **Why it was hard** - which evidence pointed the wrong way
- **What was true** - with the measurement, not only the conclusion
- **How to find it in two minutes next time** - the specific number to read, command to run

Only write up faults that were expensive *because the evidence misled*. A typo that took
four minutes is not a debug record.

## Decision records

The routing table sends "a choice was made, alternatives rejected" to the decision doc.
What makes that entry worth having is narrower than it looks.

**Record the rejected alternative, or do not record anything.** "We use X" is a
description of the code, and the code is more accurate than a document about it. The only
part a reader cannot recover by looking is *what else was on the table and what it lost
on*. If you cannot write that sentence, this was a default, not a decision.

**Write down what the decision rests on**, separating the assumptions you verified from
the ones you did not, and for the unverified ones the specific check that would settle
them. A decision made on an unverified assumption is normal; one that does not say so is
a trap for whoever inherits it.

**Give every decision a reversal trigger** — a measurement crossing a threshold, a phase
starting, an assumption failing its check. Decisions are the *reversible* row of the
lifetime table, and without triggers a decision doc silently becomes an archive nobody
dares edit.

**When one is overturned, edit it in place.** Change its status, say what replaced it, and
keep the original reasoning visible along with why it stopped applying — most often
because the reasoning was sound but belonged to a different question. That record tells
the next person the obvious objection was already considered and on what grounds it was
set aside. Deleting it makes the decision look like it was never made, and the same
argument gets had again.

Where these live depends on the repo: if there is already a working decision document,
these are the shape of an *entry* in it. If there is not, `.ai/decisions/` with one file
per decision. Do not fragment a decision doc that is working.

## Shared memory

One fact per file, so two people's edits merge without conflict. A single large memory
file guarantees conflicts.

Keep the same format as the local AI memory so promotion is a file move, not a rewrite:
frontmatter with `name` / `description` / `type`, then the fact, then why it matters and
how to apply it.

**Promotion test:** *would this still be true for a different person on this project?*
Yes promotes; "how I like to be asked before you touch X" stays local.

## Fighting rot

Wrong code fails a build. **Wrong documentation does nothing at all**, so it survives -
and AI writes it faster than anyone verifies it. Four habits, each costing seconds:

1. **Write what can be checked, not what was concluded.** "Compare the built assembly's
   timestamp against the source" beats "the build sometimes doesn't run".
2. **Cite `file:line` or a command** for any claim someone might need to confirm.
3. **Debug entries record measurements.** `changed=0/72` survives; "the device was broken"
   does not.
4. **Date-stamp each document** so staleness is visible rather than assumed away.

## What to do when invoked

**Scaffolding** - create only what has content now. If the repo already has a working
decision document, do not fragment it into per-decision files; add what is missing
around it.

**Routing** - given a new finding, apply the table, write it in the right place, update
the relevant index in the same pass. An index that lags is worse than no index.

**Promotion** - read the local AI memory, apply the promotion test, propose which entries
belong in the repo. Do not move anything without saying which and why.

**Hygiene** - report, do not silently fix:

- Index entries with no file, and files missing from the index
- `handoff.md` older than the last commits that changed behaviour
- Leftover instruction files from a template or upstream project that describe something
  else - these actively mislead, and are common in forks
- Documents with no verified-on date

## First run on an existing project

Start from what already happened rather than from the template. Read the recent commit
history and the local AI memory, and write up the two or three most expensive incidents
you can reconstruct. A structure proved on real content is worth more than a complete
empty one - and the exercise usually reveals the routing decisions the project actually
needs.
