---
name: story-illustrator
description: Plan and create QC Kindergarten story illustrations from memorable narrative beats, preparing reusable missing scene and guest-character references when needed. Use when the user asks to illustrate stories, choose story scenes, make episode art, or add images under stories/assets. Always propose scenes and required supporting assets in text and wait for explicit user approval before generating any image.
---

# Story Illustrator

Turn a story into one to five illustrations while preserving character identity, story continuity, and the project's felted-wool chibi visual language.

The workflow is a hard state machine:

`PROPOSAL → REVISION → APPROVED → ASSET PREP → RENDERED`

Never skip from `PROPOSAL` to `RENDERED`. If no proposal has been explicitly approved in the current conversation, do not call an image-generation tool and do not create a draft image.

## Project sources

Read only the material needed for the requested story:

- Story truth, cast, type, timeline, and memories: `stories/<story>.md`
- Character identity and behaviour: `character reference/<Character>-<mbti>/性格设定.md`
- Primary appearance: the character's root PNG
- Shape and outfit consistency: latest `turnaround/*_turnaround_vN.png`
- Approved expressions: latest `expressions/*_expressions_vN.png`
- Important props: `props/` and the character bible
- Location design when applicable: `Scene Reference/`
- Reusable scene registry: `website/src/data/characters.config.mjs`, `scenes`
- Minor or one-episode character references: `character reference/其他人物/`
- Asset naming rules: `stories/README.md`

English display names use initial-cap format (`Fufu`, `Haide`, `Lukos`, `Whiskle`, `Mimi`, `Liiie`); `QC` remains uppercase. Lowercase values such as `haide` are stable data slugs, not display names.

## Phase 1: propose, do not draw

Read the complete story before selecting scenes. Identify its setup, strongest reversal, funniest or most emotional reaction, reveal, and ending image. Prefer moments that communicate the story without needing a paragraph of explanation.

Before completing the proposal, audit every proposed illustration for reusable source assets:

- A location is ready only when a suitable reusable image exists in `Scene Reference/` and its file is registered in the `scenes` array in `website/src/data/characters.config.mjs`.
- A recurring cast member is ready only when its normal `character reference/<Character>-<mbti>/` identity sources exist.
- Any visually present person who is not a recurring cast member needs a lightweight guest-character reference under `character reference/其他人物/`.

Do not silently substitute a generic background or anonymous human shape when either source is missing. List each missing asset under `需先补齐的可复用资产` in the proposal. For a new scene, give its proposed `SceneKey`, Chinese and English display names, defining visual features, and intended reference filename. For a guest character, give its proposed identifier, narrative role, silhouette, clothing, and the reason the person should remain visually secondary.

Choose the illustration count from both story length and visual beats:

- 1 image: one dominant event or a very short story
- 2 images: setup plus reveal, or conflict plus punchline
- 3 images: clear beginning, turn, and ending
- 4 images: several distinct locations or emotional reversals
- 5 images: long episode with five genuinely different, essential visual beats

Do not inflate the count. Two variations of the same pose are one beat. A long story may still need only two images when only two moments are visually memorable.

Return a proposal with this structure:

```markdown
## 插画提案

建议数量：3 幅
理由：一句话说明叙事节奏与取舍。

需先补齐的可复用资产：
- 场景：`SceneKey` — 生成内容、登记位置与文件名（如无则写“无”）
- 其他人物：`人物标识` — 三视图和简要设定的内容与文件名（如无则写“无”）

### 1. 插画暂定名
- 对应段落：故事中的具体时刻
- 记忆点：为什么值得画
- 视角：客观事件 / 某角色主观记忆 / 番外夸张视角
- 构图与镜头：景别、机位、人物前后关系、视觉焦点
- 角色状态：每个人的动作、表情和视线
- 场景与光线：地点、时间、气氛
- 必须准确：服装、道具、身份与剧情事实
- 建议插入位置：放在哪一段之后
- 预计文件名：stories/assets/<story-stem>-p1-v1.png
```

End by asking the user to confirm all, confirm selected numbers, or provide revisions. Do not append an image prompt disguised as completed work.

## Approval gate

The following count as approval:

- “确认全部”
- “确认 1 和 3”
- “按这个方案画”
- A revision that explicitly says to apply the change and generate

Comments, questions, preferences, or requested revisions without an explicit request to generate are not approval. Revise the proposal and wait again.

Approval is scoped to the confirmed scenes. Generate only those scenes. If the user approves some scenes and leaves others undecided, render the approved subset and keep the rest in proposal state.

Approval of a scene also approves only the supporting scene and guest-character assets explicitly listed for that scene. If the required asset design changes materially after approval, return to revision and ask for approval again.

## Asset readiness gate

After approval and before rendering story art, create and register all approved missing assets. Finish and inspect this stage before using those assets in an illustration.

### Missing locations

When the story needs a location without a suitable reference:

1. Generate a clean, reusable establishing view of the empty location in the project's felted-wool / knitted-toy visual language. Do not include story-specific action, characters, captions, or temporary damage unless that state is a permanent property of the location.
2. Save it as `Scene Reference/<SceneKey>.png`, using a stable PascalCase English key consistent with the existing scene files. Never overwrite an existing reference; revise the key or create a deliberate new version when necessary.
3. Add `{ file: '<SceneKey>', zh: '<中文名>', en: '<English name>' }` to the `scenes` array in `website/src/data/characters.config.mjs`. Treat this registry as the website's reusable scene database.
4. If the story's `location` frontmatter was blank or used a provisional value, set it to the registered `SceneKey`; do not change a deliberate existing location merely to match a generated image.
5. Inspect the reference for architectural coherence, usable composition space, correct materials and lighting, and absence of people or accidental text.

### Missing guest characters

Long-term cast and one-episode/background people must be visually distinguishable at a glance. Do not promote a guest into the 12-character main cast or add it to `characters.config.mjs`.

For every visually present person without an existing main or guest reference:

1. Create `character reference/其他人物/<guest-id>/`.
2. Write a concise `性格设定.md` containing: display name or role label, story/function, body silhouette, hair/head shape, clothing palette, signature prop if any, and the mandatory eyeless treatment. Keep personality and backstory minimal unless the story establishes them.
3. Generate a consistent front / three-quarter / side / back turnaround and save it under `turnaround/<guest-id>_turnaround_v1.png`, incrementing the version rather than overwriting later revisions.
4. In the turnaround and every story illustration, draw no visible eyes, pupils, irises, sclera, eye highlights, eyelids, eye outlines, or closed-eye lines. By default, replace the entire eye region with one contiguous, clean-edged, smooth matte shadow block whose upper edge is hidden by fringe, a hat, or the facial plane. The default shadow block has no felt, wool, knit, fiber, pore, grain, mottling, gradient, or feathered texture. An explicitly approved guest bible or latest approved turnaround may override the default boundary softness, texture, or eyebrow treatment; preserve that character-specific treatment exactly rather than normalizing every guest to the default. The face may retain a nose or mouth below the shadow when useful, but the treatment must make the guest immediately read as a temporary/background person rather than a main character.
5. Keep the same felted-wool / knitted-toy rendering style as the main cast while using simpler shapes, fewer signature accessories, and lower visual contrast. Inspect all turnaround views for identity consistency, verify that no eyes have been generated, and compare shadow boundaries, texture, and eyebrow treatment against that guest's approved bible and latest approved turnaround.

## Phase 2: render approved scenes

After approval:

1. Complete the asset readiness gate and use the registered scene and guest-character references; do not generate the story illustration first.
2. Re-read the approved scene description and the exact source paragraph.
3. Inspect the relevant character, guest-character, scene, and prop images before generating.
4. Use the available image-generation skill/tool. Supply the smallest complete set of references that preserves every visible character. For a crowded scene, use a labeled identity sheet or staged composition reference instead of dropping identities.
5. State character count and left-to-right placement explicitly in the generation prompt. Treat the root poster as the main-character identity authority, turnaround as the outfit/body authority, expression sheet as the main-character face authority, guest turnaround as the guest identity and eyeless-treatment authority, scene reference as the location authority, and prop sheet as the prop authority.
6. Preserve the approved camera, action, expression, POV, cast, and story facts. Prompt refinement may fix rendering defects but must not silently redesign the scene.
7. Save without overwriting existing art. Use `stories/assets/<story-stem>-p<N>-v<N>.png`; find the next free version number. A single cover image may use `<story-stem>-v<N>.png` only when the user explicitly wants it to be the story cover.
8. Inspect every result. Verify character identity, character count, anatomy, main-character eye direction, guest characters' complete lack of visible eyes, hands/paws, props, clothing, location, readable silhouettes, and absence of unintended text or extra people.
9. Retry defects within the approved composition. If fixing the image would require a meaningful content or composition change, return to proposal/revision state and ask for approval.

Show each finished image with its absolute local path and identify which proposal number it implements. Do not commit or push unless the user separately asks.

## Continuity rules

For `type: memory` stories, the proposal must label its POV. A subjective illustration can show only what that character knew or believed at that moment. Do not leak another character's secret into that POV.

For `type: extra` stories, visual exaggeration is allowed, but character identity, approved costume changes, and story-specific props remain binding. Extra-story art does not update character bibles or memories.

When a story has no suitable visual beat, explain why and propose one cover-like symbolic image instead of inventing a new event.
