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
3. Stable rules in [references/taste-profile.md](references/taste-profile.md)
4. Repeated rules, then provisional rules
5. The model's default creative preference

A current instruction may override the profile for one task without changing the profile permanently.

## Apply mode

For story, character, episode-art, or other creative work, read [references/taste-profile.md](references/taste-profile.md). Read the relevant story, bibles, and visual references rather than relying on the profile for canon.

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

`EVIDENCE → CANDIDATE DIFF → HUMAN REVIEW → APPROVED UPDATE`

Never edit the canonical profile or structured rules before QC explicitly approves the candidate diff. Periodic runs may automatically collect and compare evidence, but silence, non-response, and AI-authored suggestions are not approval.

## Boundaries

- Do not infer private facts, identity traits, or broad personality claims from creative choices.
- Do not convert a one-off task constraint into a global taste rule.
- Do not let AI outputs become self-validating evidence; they count only through a human seed, selection, rejection, revision, or approval.
- Keep project canon separate from transferable taste. A fact about Haide belongs in the bible or story; a repeated preference for reversals built from character contradictions may belong here.
- Preserve uncertainty and counterexamples. Do not force every work to display every taste rule.

The current profile is version 0.1, derived from available records through 2026-09-09. It is a working hypothesis, not a claim to fully represent QC.
