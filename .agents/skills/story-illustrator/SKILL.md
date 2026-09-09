---
name: story-illustrator
description: Plan and create QC Kindergarden story illustrations from the most memorable narrative beats. Use when the user asks to illustrate one or more stories, choose story scenes, make episode art, or add images under stories/assets. Always propose the scenes in text and wait for explicit user approval before generating any image.
---

# Story Illustrator

Turn a story into one to five illustrations while preserving character identity, story continuity, and the project's felted-wool chibi visual language.

The workflow is a hard state machine:

`PROPOSAL → REVISION → APPROVED → RENDERED`

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
- Asset naming rules: `stories/README.md`

English display names use initial-cap format (`Fufu`, `Haide`, `Lukos`, `Whiskle`, `Mimi`, `Liiie`); `QC` remains uppercase. Lowercase values such as `haide` are stable data slugs, not display names.

## Phase 1: propose, do not draw

Read the complete story before selecting scenes. Identify its setup, strongest reversal, funniest or most emotional reaction, reveal, and ending image. Prefer moments that communicate the story without needing a paragraph of explanation.

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

## Phase 2: render approved scenes

After approval:

1. Re-read the approved scene description and the exact source paragraph.
2. Inspect the relevant character and prop images before generating.
3. Use the available image-generation skill/tool. Supply the smallest complete set of references that preserves every visible character. For a crowded scene, use a labeled identity sheet or staged composition reference instead of dropping identities.
4. State character count and left-to-right placement explicitly in the generation prompt. Treat the root poster as the identity authority, turnaround as the outfit/body authority, expression sheet as the face authority, and prop sheet as the prop authority.
5. Preserve the approved camera, action, expression, POV, cast, and story facts. Prompt refinement may fix rendering defects but must not silently redesign the scene.
6. Save without overwriting existing art. Use `stories/assets/<story-stem>-p<N>-v<N>.png`; find the next free version number. A single cover image may use `<story-stem>-v<N>.png` only when the user explicitly wants it to be the story cover.
7. Inspect every result. Verify character identity, character count, anatomy, eye direction, hands/paws, props, clothing, location, readable silhouettes, and absence of unintended text or extra people.
8. Retry defects within the approved composition. If fixing the image would require a meaningful content or composition change, return to proposal/revision state and ask for approval.

Show each finished image with its absolute local path and identify which proposal number it implements. Do not commit or push unless the user separately asks.

## Continuity rules

For `type: memory` stories, the proposal must label its POV. A subjective illustration can show only what that character knew or believed at that moment. Do not leak another character's secret into that POV.

For `type: extra` stories, visual exaggeration is allowed, but character identity, approved costume changes, and story-specific props remain binding. Extra-story art does not update character bibles or memories.

When a story has no suitable visual beat, explain why and propose one cover-like symbolic image instead of inventing a new event.
