# stories（故事集）

12 个角色的情景喜剧故事。每个故事一个文件，只放故事本身，不改角色 bible。

- 命名 `YYYY-MM-DD-<slug>.md`，日期取故事写成那天，slug 用英文或拼音短语
- 每份开头写 frontmatter：

```yaml
---
title: 故事标题
cast: [haide, 艾莎, QC]        # 出场角色，用 character reference/ 下的文件夹名前缀
location: courtyard             # 对应 Scene Reference/ 的场景名，可空
date: 2026-09-08                # 故事写成的日期
source: user | claude | gpt     # 谁写的
---
```

- 故事里出现的新设定**默认不回写**到 `character reference/<角色>/性格设定.md`。每新建一个故事文件，Claude 会确认一次是否要回写；确认后才改 bible（hook 在 `.claude/hooks/story_added.py`，只在新建时触发，改已有故事不触发）

## 配图

- 放在 `stories/assets/`，命名 `<故事文件名>-vN.png`，N 从 1 起是草稿版本号，例：`2026-09-08-four-witches-v3.png`
- 需要高分辨率版本时在版本号后加 `-4k`，例：`2026-09-08-four-witches-v5-4k.png`
- 所有版本都留着，不删旧稿；网站默认取版本号最大的那张（不含 `-4k`）
- 一个故事有多张不同画面时，在版本号前加画面序号：`<故事文件名>-p2-v1.png`
- 网站 `website/` 的故事集页从这里读取（见 `website/DESIGN.md` 首页第三层）
