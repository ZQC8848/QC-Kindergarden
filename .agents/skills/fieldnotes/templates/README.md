# `.ai/` — shared project knowledge

For two readers: **whoever picks this project up next**, and **the AI helping them**.

It exists for one reason: this project contains things that cost hours to work out and
that neither the code nor the git history will tell you.

## What is here

| Path | Holds | Lifetime |
|---|---|---|
| [architecture.md](architecture.md) | End-to-end data flow: what happens to one unit of work | Follows the architecture |
| [debug/](debug/) | Incidents, **indexed by symptom** | One-off, must stay findable |
| [decisions/](decisions/) | Choices, what the rejected options lost on, what would reverse them | Reversible — edited in place |
| [memory/](memory/) | Shared AI memory, one fact per file | Long |
| [handoff.md](handoff.md) | Progress, work in flight, next step | **Expires by design** |

Elsewhere in the repo but part of the same system:

- `CLAUDE.md` — the entry point; platform constraints that are not obvious
- *(the project's decision document)* — decisions and their rejected alternatives

## Where a new piece of information goes

All conditions must hold.

| You observed | Write it to | Test |
|---|---|---|
| Non-obvious platform/SDK behaviour | `CLAUDE.md` constraints | True in a year **and** not guessable |
| A choice made, alternatives rejected | Decision doc, or `.ai/decisions/` | You can write "why not the other one" |
| A fault whose symptom was far from its cause | `.ai/debug/` | Next time it is searched **by symptom** |
| Progress, in-flight work, next step | `.ai/handoff.md` | It will go stale |
| How a person likes to work | **Local memory, not the repo** | About the person, not the project |

**Do not write** code structure, fixed bugs, or anything git history already says. Those
rot immediately and the original source is more accurate.

## Promoting local memory

**Would this still be true for a different person on this project?** Yes promotes.

## One fact per memory file

So two people's edits merge. A single large file guarantees conflicts.

## Fighting rot

Wrong code fails a build; wrong documentation does nothing, so it survives.

1. Write what can be **checked**, not what was concluded
2. Cite `file:line` or a command for anything someone may need to confirm
3. Debug entries record **measurements**, not conclusions
4. Date-stamp documents so staleness is visible
