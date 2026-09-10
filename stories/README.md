# stories（故事集）

12 个角色的情景喜剧故事。每个故事一个文件，故事文件是跨人物事件的唯一正式来源；人物 bible 只保留长期性格、背景和关系。

## 两种故事

- `type: memory`：在世界观里真实发生，会进入指定角色的记忆，也可以影响后续故事。
- `type: extra`：番外、假想或恶搞，不进入任何角色的记忆，也不改变连续性。

“真实发生”不代表所有出场人物都知道真相。记忆事件使用 `memories` 分别记录每个人知道多少、如何理解，以及事件留下的影响。没有列入 `memories` 的角色不会在人物页获得这段记忆。

- 命名 `YYYY-MM-DD-<slug>.md`，日期取故事写成那天，slug 用英文或拼音短语
- 每份开头写 frontmatter：

```yaml
---
title: 故事标题
cast: [Haide, 艾莎, QC]        # 出场角色，用 character reference/ 下的文件夹名前缀
location: Courtyard             # 对应 Scene Reference/ 的场景名，可空；多个地点写成列表 [NapRoom, HighwayNight]
date: 2026-09-08                # 故事写成的日期
source: user | claude | gpt     # 谁写的
type: memory | extra            # 记忆事件或番外剧场
timeline: 1                     # 世界观顺序；番外可省略
open_ending: true               # 可选。结尾是刻意留的悬念：不续写、不揭晓、不解释
memories:                       # 仅 memory 使用，key 推荐写稳定 slug
  haide:
    title: 角色自己的记忆标题
    knowledge: witnessed        # witnessed | heard | inferred | partial | secret
    summary: 他记得或相信的版本
    impact: 这段记忆如何影响后续行为
---
```

- `date` 是创作日期，`timeline` 才是世界观内的先后顺序。
- `open_ending: true` 标记结尾是刻意留白的故事（目前是《午夜的金色法拉利》和《王者兰特定榜夜》）。强行续接会同时破坏两篇的氛围，所以故事流水线会把它们标成不可续写，后果位也不会拿它们当起点。
- 可选字段 `teaser: 一句不剧透的话`，Discord 通知会优先用它；没有就取正文第一句。
- 英文版放在同名的 `<故事文件名>.en.md`：frontmatter 只写 `title`、`framing`（番外）和 `memories`（每个角色的 `title` / `summary` / `impact`），`cast`、`location`、`date`、`type`、`timeline` 沿用中文文件；正文翻译后保留 `<!-- illustration:N|英文说明 -->` 标记。翻译规范见 `.agents/skills/translate-en/SKILL.md`。
- `cast` 表示与故事有关、可用于筛选的角色；`memories` 表示真正拥有该段记忆的角色，两者不必相同。
- 故事产生的长期性格变化可以回写 bible，但不要把完整事件重复复制过去。bible 里改放一个 `## 事件档案` 段，只列指向故事文件的链接。

### `## 事件档案` 这一段的约定

- **它只服务于直接读 markdown 的人和 agent，网站上任何地方都不渲染。** 它既不在 `characters.config.mjs` 的 `descriptionOrder` 里，也不会被 `parse.mjs` 的 `isExtra()` 当成补充设定。角色页上的「记忆」区是另一条路径，由 `stories.json` 生成，跟这一段无关。
- 因此**英文 bible 不需要写这一段**。`tools/audit_en.py` 里 `canon()` 把它归一成 `事件档案`，中英覆盖检查再显式跳过它——这是中英章节数可以不相等的唯一合法原因。
- 段落内容只写链接和一句话，长期影响写进上面的常驻段落。完整叙述永远只有故事文件这一份。

## 配图

- 放在 `stories/assets/`，命名 `<故事文件名>-vN.png`，N 从 1 起是草稿版本号，例：`2026-09-08-four-witches-v3.png`
- 需要高分辨率版本时在版本号后加 `-4k`，例：`2026-09-08-four-witches-v5-4k.png`
- 网站取版本号最大的那张（不含 `-4k`）。**定稿后删掉被取代的旧版本**，只留在用的那一版加可选的 `-4k`；过程稿留在仓库里只会让每次 clone 更慢，需要回看旧稿去 git 历史里翻
- 一个故事有多张不同画面时，在版本号前加画面序号：`<故事文件名>-p2-v1.png`
- 网站会把记忆事件和番外剧场分开展示。人物页只显示该人物自己的记忆摘要，番外另列为“出演番外”。
- 客串角色放在 `character reference/_guests/`，只供插画和故事引用，**不在网站上单独成页**，也不进角色卡网格。
