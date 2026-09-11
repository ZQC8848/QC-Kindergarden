---
name: qc-taste
description: Apply and maintain QC's evidence-backed creative taste for QC Kindergarten stories, characters, visual concepts, and related creative decisions. Use when proposing, writing, revising, or evaluating creative work for this project, or when extracting taste updates from new human-AI creation records. Do not use for unrelated repository administration or generic technical work.
---

# QC Taste

Make creative decisions that QC is likely to recognize as their own while still producing new material. This skill models choice, rejection, revision, and stopping behavior; it is not a request to imitate surface wording or recycle existing jokes.

## Authority order

When guidance conflicts, use this order:

1. QC's explicit instruction in the current conversation
2. Story truth, character bibles, continuity, and approved project decisions
3. Stable rules in the taste profile under [references/taste/](references/taste-profile.md): the shared part plus the domain in use
4. Repeated rules, then provisional rules
5. The model's default creative preference

A current instruction may override the profile for one task without changing the profile permanently.

## Apply mode

For creative work, read the shared part of the profile and the domain you are working in. The English and Chinese files say the same thing; use whichever suits the task.

| Work | Read in `references/taste/` |
|---|---|
| Stories, premises, prose, characters, continuity | `_shared` + `story` |
| Character art, illustrations, posters, other still images | `_shared` + `image` |
| Storyboards (breaking a story into shots) | `_shared` + `storyboard` — no rules of its own yet |
| Generated video | `_shared` + `video` — no rules of its own yet |

Read the relevant story, bibles, and visual references rather than relying on the profile for canon.

Use the profile as a decision function:

- Preserve the human seed as the spine; expand it rather than replacing it with a more generic premise.
- Prefer the option with the strongest character-specific contradiction, causal escalation, ensemble reaction, and memorable concrete detail.
- Check negative boundaries before polishing. A fluent result that violates them is not QC-like.
- Add novelty by recombining character logic and relationships, not by repeating an old punchline or importing random spectacle.
- Keep hidden reasoning internal. Deliver the selected result or the requested alternatives; explain taste reasoning only when the user asks to compare or evaluate.

When used with `story-illustrator`, this skill guides scene selection, tone, visual hierarchy, and revision judgment. It never bypasses that skill's proposal and approval gate.

## Update mode

Use update mode when QC asks to learn from, refresh, extract, or update taste from new conversations or decisions. Read [references/update-protocol.md](references/update-protocol.md), then consult [references/evidence-index.md](references/evidence-index.md) and [references/taste-rules.yaml](references/taste-rules.yaml).

The hard state machine is:

`SCOPE → EVIDENCE → CANDIDATE DIFF → HUMAN REVIEW → APPROVED UPDATE`

Start by running `python tools/taste_scan.py`. An update reads **only the chat-history records added or extended since the last update**, tracked per file in `consumed_records` rather than by date. Never re-mine a record that is already consumed.

An update that changes nothing is a correct update. If the scan finds no new records, or the new records carry no human decision that bears on creative taste, say so and stop; advancing the cursor is the only write. Do not invent a rule to make a run look productive.

Never edit the canonical profile or structured rules before QC explicitly approves the candidate diff. Periodic runs may automatically collect and compare evidence, but silence, non-response, and AI-authored suggestions are not approval.

## Two languages

Every part of the profile exists in English and Chinese, and both must say the same thing before a task that touched either one ends. Translate only what changed, keep rule numbers, sections and list items parallel, and keep QC's quoted words verbatim; then run `python tools/taste_sync.py stamp <part>`. `python tools/taste_sync.py` reports any pair that has fallen out of step, and CI fails on it. In Claude Code a hook raises this after every edit to a taste file; Codex has no hook, so run the report yourself.

Translating is not a rule change and needs no approval. Changing what a rule says, in either language, is a rule change.

## Boundaries

- Do not infer private facts, identity traits, or broad personality claims from creative choices.
- Do not convert a one-off task constraint into a global taste rule.
- Do not let AI outputs become self-validating evidence; they count only through a human seed, selection, rejection, revision, or approval.
- Keep project canon separate from transferable taste. A fact about Haide belongs in the bible or story; a repeated preference for reversals built from character contradictions may belong here.
- Preserve uncertainty and counterexamples. Do not force every work to display every taste rule.

The current profile is version 0.4, derived from available records through 2026-09-09, and was split into four domains and two languages on 2026-09-10 without changing any rule. It is a working hypothesis, not a claim to fully represent QC.
