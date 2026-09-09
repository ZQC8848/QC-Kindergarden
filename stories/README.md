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
memories:                       # 仅 memory 使用，key 推荐写稳定 slug
  haide:
    title: 角色自己的记忆标题
    knowledge: witnessed        # witnessed | heard | inferred | partial | secret
    summary: 他记得或相信的版本
    impact: 这段记忆如何影响后续行为
---
```

- `date` 是创作日期，`timeline` 才是世界观内的先后顺序。
- `cast` 表示与故事有关、可用于筛选的角色；`memories` 表示真正拥有该段记忆的角色，两者不必相同。
- 故事产生的长期性格变化可以回写 bible，但不要把完整事件重复复制过去。旧的重复段落可保留为 `## 事件档案（已迁移）`，网站不会再把它当补充设定显示。

## 配图

- 放在 `stories/assets/`，命名 `<故事文件名>-vN.png`，N 从 1 起是草稿版本号，例：`2026-09-08-four-witches-v3.png`
- 需要高分辨率版本时在版本号后加 `-4k`，例：`2026-09-08-four-witches-v5-4k.png`
- 所有版本都留着，不删旧稿；网站默认取版本号最大的那张（不含 `-4k`）
- 一个故事有多张不同画面时，在版本号前加画面序号：`<故事文件名>-p2-v1.png`
- 网站会把记忆事件和番外剧场分开展示。人物页只显示该人物自己的记忆摘要，番外另列为“出演番外”。
