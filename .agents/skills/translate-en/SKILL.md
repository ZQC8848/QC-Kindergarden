---
name: translate-en
description: Produce and maintain the English version of the QC Kindergarten website, covering character bibles (性格设定.en.md), stories (stories/<slug>.en.md), UI strings (website/src/i18n.ts) and config names, so that every page element except image content reads in English. Use when the user asks to translate the site, add English for a character or story, check English coverage, or review a liberal translation. Translate for literary and dramatic effect over literal accuracy, act first, then report every non-literal choice to QC with reasons and alternatives.
---

# Translate EN

Give the English site the same voice the Chinese site has: short sentences, dry humour, twelve distinct characters. A translation that is accurate but flat has failed. A translation that lands the joke with different words has succeeded, as long as QC hears about it afterwards.

## Coverage map

Every English-facing string lives in one of these places. "All page elements have English" means all five are complete.

| Layer | Source of truth | What the site does when it is missing |
|---|---|---|
| UI strings | `website/src/i18n.ts` (`zh` and `en` dictionaries must have identical keys) | Build error or Chinese leaking into `/en/` |
| Names and places | `website/src/data/characters.config.mjs` (`en.name`, scene `en`) | Chinese name shown |
| Character bibles | `character reference/<Character>/性格设定.en.md` | `/en/characters/<slug>/` shows the Chinese bible with a "not translated" notice |
| Stories | `stories/<slug>.en.md` | `/en/stories/<slug>/` and every story card show Chinese text with the notice |
| Illustration captions | the `<!-- illustration:N|caption -->` markers inside the `.en.md` body | Caption falls back with the rest of the story |

Image content (posters, expression sheets, illustrations, scene art) is out of scope.

## Workflow

1. **Audit first.** Run `python tools/audit_en.py` from the repository root. It lists missing `.en.md` files, structural mismatches between a Chinese file and its English twin, and, if `website/dist/` exists, every `/en/` page that still contains Chinese characters.
2. **Read before writing.** For a bible, read the full Chinese bible and the character's relationships in other bibles. For a story, read the Chinese story, its cast's bibles, and any earlier story it references. Never translate a paragraph in isolation.
3. **Translate one layer at a time**, in this order: config names → UI strings → bibles → stories → captions. Names decided in step one are used everywhere after.
4. **Sync and build.** In `website/`, run `npm run sync` then `npx astro build`. Fix build errors before continuing.
5. **Audit again** and repeat until the audit reports nothing for the scope you were asked to cover.
6. **Report** (see below). Append every non-literal decision to [references/decisions.md](references/decisions.md).

Do not ask QC for approval before translating. Act, then report. QC can reverse any decision; the decisions log makes that cheap.

## File formats

### Bible: `性格设定.en.md`

Mirror the Chinese file section for section. Headings use the English names in the alias table below (the sync script maps them onto the Chinese canonical names). Keep the same number of sections and the same bullet count in `Relationships`; relation bullets must bold the target's English display name (`**Aisha**`, `**Ruanruan**`) so the site can link it.

```
# Mimi (ENFJ) character bible

> One line: The kid with the baseball bat. Someone gets picked on, she is first in.

## Basics
| Item | Value |
|---|---|
| Name | Mimi |
| MBTI | ENFJ (Protagonist / big-sister type) |
| ... | ... |

## Core personality
## Personality in the design
## Habits            ← must contain a line starting with "- Catchphrases:" with quoted phrases
## Expressions and moods
## Likes / dislikes
## Strengths and growth
## Relationships
## Extra: <title>    ← one per 额外设定 section; "Extra one:", "Extra two:" also accepted
## Meaning of the props
```

Alias table (must match `SECTION_ALIASES` in `website/scripts/sync-content.mjs`):

| Chinese | English heading |
|---|---|
| 基本信息 | Basics |
| 性格核心 | Core personality |
| 外形里的性格线索 | Personality in the design |
| 行为习惯 | Habits |
| 表情与情绪 | Expressions and moods |
| 喜欢 / 讨厌 | Likes / dislikes |
| 优点与课题 | Strengths and growth |
| 道具的意义 | Meaning of the props |
| 和其他人的相处 | Relationships |
| 额外设定… | Extra: … |
| 事件档案（已迁移）… | Archive (migrated): … (kept for humans, not rendered) |

The first catchphrase is what the character card shows. Keep it under about 40 characters and make it something a person would actually say.

### Story: `stories/<slug>.en.md`

Only translated fields go in the frontmatter; cast, location, date, type and timeline are read from the Chinese file.

```
---
title: The Night Haide Became a Dog
framing: A side story; nothing here enters anyone's memory.   # extras only
memories:
  haide:
    title: An accidental but fairly practical upgrade
    summary: ...
    impact: ...
---

# The Night Haide Became a Dog

Body in English. Keep every <!-- illustration:N|caption --> marker at the
same position as in the Chinese body, with the caption translated.
```

Memory keys are character slugs (`haide`, `aisha`, `ruanruan`, `mushi`, `dianer`, `luyao`). Every memory in the Chinese file must appear in the English file.

## Style rules

- **Function over form.** Ask what a sentence does (sets up a beat, lands a punchline, reveals character, moves the plot) and write English that does the same thing. Literal wording is the fallback, not the target.
- **Rhythm.** The Chinese uses short declaratives and hard stops. Keep that. One idea per sentence. Punchlines end sentences.
- **Voice per character.** Fufu exclaims. Haide asks rhetorical questions and never apologises. Mimi gives orders in few words. Aisha uses no adjectives and stutters on the first word when she cares ("I, I told you"). Ruanruan trails off and asks permission; Bun-bun speaks for her. Lukos is soft and asks how you are. Whiskle is quiet and precise about plants. Mushi is warm and cannot keep a secret. Dianer explains mechanisms. Luyao barks and the swearing is implied, never spelled out. Liiie is polite at a distance. QC is breezy and delegates.
- **Names** come from [references/glossary.md](references/glossary.md) and `characters.config.mjs`. Never invent a new spelling.
- **Jokes that depend on Chinese** (puns, brand names, internet slang, homophones) get a functional equivalent, not a footnote. The reader must laugh in the same place. Record the decision.
- **Culture-bound nouns** (McDonald's, Ferrari, MBTI labels, kindergarten roles) stay concrete. Do not generalise "orange juice" to "a drink".
- **Register.** Peach-coloured site, adults written as kindergarteners. Keep it affectionate and deadpan; never cute-ify beyond what the Chinese does.
- **Do not add.** No explanatory clauses, no softening, no extra jokes. If the Chinese is three words, the English should not be a paragraph.
- **Consistency.** Reuse an existing decision from the decisions log before inventing a new one. If you must change an earlier choice, update every file that uses it and note the change.

## Reporting protocol (先斩后奏)

At the end of a translation task, tell QC in Chinese what was translated and then list every non-literal decision in this shape:

| 原文 | 译文 | 为什么 | 其他方案 | 出现位置 |
|---|---|---|---|---|
| 狗不理 | Fetch | 顶尖玩家 ID 要能被一条狗用得理直气壮，又要让点儿一眼认出。"Fetch" 是狗的本能动作，也是英文里"去拿第一"的动词；天津包子梗保不住，改保"这个 ID 只有狗会起"的功能。 | Dog Ignored（直译，读者不懂）；Top Dog（太直白，没有反差）；Goubuli（音译，梗全丢） | kings-rank-night.en.md ×4，Dianer 记忆 |

Rules for the report:

- One row per decision, grouped by story or bible. Include every pun, brand, slang term, catchphrase, proper noun and title that is not a word-for-word rendering.
- "其他方案" lists two or three real alternatives you considered, each with a short reason it lost.
- "出现位置" names the files and how many times, so QC can reverse it in one search.
- Write the same rows into `references/decisions.md` under a dated heading with status `pending`. When QC confirms a choice, change its status to `approved` and, if it is a reusable term, copy it into `references/glossary.md`.
- If QC rejects a choice, apply the replacement everywhere it appears, update the log, and re-run the audit.

## Audit script

`tools/audit_en.py` checks, without any dependency beyond Python 3:

- every character folder has `性格设定.en.md`, and its headings cover every Chinese section through the alias table
- every story has `<slug>.en.md`, with matching memory keys and matching illustration marker numbers
- `website/src/i18n.ts` has the same keys under `zh` and `en`
- if `website/dist/en/` exists, no built English page contains CJK text (the language switch label is allowed)

Exit code 1 means something is missing; the output says what and where.
