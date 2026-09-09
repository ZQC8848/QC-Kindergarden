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

- 故事里出现的新设定**默认不回写**到 `character reference/<角色>/性格设定.md`。每加一个故事，Claude 会确认一次是否要回写；确认后才改 bible
- 网站 `website/` 的故事集页从这里读取（见 `website/DESIGN.md` 首页第三层）
