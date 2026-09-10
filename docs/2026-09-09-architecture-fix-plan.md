# 架构清晰度：修复方案

日期：2026-09-09　基线：main `9a94556`　状态：已执行（见文末执行记录）　上位文档：[2026-09-09-project-review.md](2026-09-09-project-review.md)

## 先更正上一份报告的两处错误

写方案时逐条复核，发现检测报告里有两条判断不成立，已在原文件修正：

1. **"CLAUDE.md 说 skill 在 `.claude/skills/`"是错的。** 当前 `CLAUDE.md` 和 `AGENTS.md` 都已正确指向 `.agents/skills/`，列全了 5 个 skill。我看的是 pull 之前的旧内容。真正的问题是反过来的：`.claude/skills/fieldnotes/` 是一份**没有任何文档引用的孤儿副本**。
2. **"重命名让同一张图存了两份"是错的。** 实测 `FUFU-enfp.png → Fufu-enfp.png` 在 git 里是 `R100` 纯重命名，blob 只有一个（`848e78d3`）。git 重命名不复制内容，所以目录改名对仓库体积几乎没有影响。这也让 A3 的成本评估从"贵"变成"便宜"。

同时补一条新发现的问题，见 A5。

---

## A1. 双 agent 生态：Claude 看不到一半的自动化

**现状（已验证）**

| 目录 | 内容 | 谁能读 |
|---|---|---|
| `.agents/skills/` | fieldnotes、qc-taste、story-illustrator、translate-en、discord-notify | Codex |
| `.claude/skills/` | 只有 fieldnotes，且与正本差 2 行 | Claude Code |

后果有三个，都在这次会话里实际发生了：

- **qc-taste、story-illustrator、translate-en、discord-notify 四个主力 skill，Claude Code 的 skill 列表里根本不出现**，只能靠人手动说"去读那个文件"。项目一半的工作流对两个常用 agent 之一是隐形的。
- fieldnotes 两份已经漂移，没有任何机制会发现。
- `.claude/hooks/check_bilingual_consistency.py` 按路径调用 `.agents/skills/translate-en/scripts/audit_en.py`，一边的钩子伸进另一边的 skill 目录。

**方案：一份正本 + 三行转发桩**

- `.agents/skills/` 是唯一实现，不动。
- `.claude/skills/<name>/SKILL.md` 每个只写 frontmatter 加一句指路：

```markdown
---
name: qc-taste
description: <与正本逐字相同>
---

正本在 `.agents/skills/qc-taste/SKILL.md`，先读它再执行。参考文件在同目录的 `references/`。
```

这样 Claude 的 skill 列表能看到全部 5 个（触发靠 description），正文只多一次 Read。不用符号链接，Windows 和 git 都不会出问题。

- 两边共用的脚本移到 `tools/`：`audit_en.py` 被 translate-en skill 和 bilingual hook 共用，移到 `tools/audit_en.py`，钩子和 skill 都按 `tools/` 调用，跨界依赖消失。`notify_discord.py` 只被 discord-notify 用，留在原处。
- 加 `tools/check_skill_stubs.py`：校验每个桩的 name / description 与正本逐字一致，不一致退出码 1。进 CI，也能当 pre-commit。

**影响面**：新建 5 个桩文件、删 `.claude/skills/fieldnotes/`（8 个文件）、移 1 个脚本、改 3 处引用（hook 1、translate-en SKILL.md 1、README 1）、新增 1 个校验脚本。

**风险**：低。唯一副作用是 Claude 用这些 skill 时多一次文件读取。

**验证**：`python tools/check_skill_stubs.py` 通过；重开一次 Claude 会话，确认 skill 列表里出现 5 个；`python tools/audit_en.py` 仍通过；手动触发一次 bilingual hook。

**耗时**：约 40 分钟。

---

## A2. 改名残留：Kindergarden vs Kindergarten

**现状**：项目已更名 QC Kindergarten（提交 `31be12c`），子模块 URL 也已经是 `QC-Kindergarten-Research.git`。但主仓库还是 `github.com/ZQC8848/QC-Kindergarden.git`，本地目录还是 `Desktop/QC-Kindergarden`。网站页脚的 GitHub 链接指向旧名。

**方案**：分两步，第二步建议单独找时间做。

1. GitHub 网页里 Settings → Rename 改成 `QC-Kindergarten`。GitHub 会永久重定向旧地址，现有 clone 不会断。然后本地 `git remote set-url origin https://github.com/ZQC8848/QC-Kindergarten.git`，并改 `website/src/layouts/Base.astro` 里的 GitHub 链接。
2. 本地目录改名 `QC-Kindergarden → QC-Kindergarten`。这会让当前 Claude 会话的工作目录失效，`~/.claude/projects/C--Users-10451-Desktop-QC-Kindergarden/` 下的历史会话与新路径对不上（历史仍在，只是不再挂到这个项目）。改完要重开会话。Codex 的 rollout 记录同理。

**需要你拍板**：改 GitHub 仓库名是对外动作，我不会自己执行。本地目录改不改、什么时候改，也由你定。

**风险**：仓库改名低风险（有重定向）。本地目录改名会打断会话历史的关联，仅此而已。

**耗时**：仓库改名 5 分钟；本地目录改名 2 分钟加重开会话。

---

## A3. 目录命名：带空格与中文

**现状**：`character reference/`（空格）、`Scene Reference/`（空格）、`character reference/其他人物/`（中文）。全仓库 17 个文件引用这些路径，其中代码 6 个：`sync-content.mjs`(5 处)、`characters.config.mjs`(2)、`gen_reference.py`(2)、`audit_en.py`(2)、`build_identity_sheet.py`(1)、两个 hook 各 1。

**重新评估**：更正错误后成本比原估低（git 重命名不涨体积），但收益也确实有限：现有 6 个脚本都已经正确处理了空格，改名主要是让**将来**的新工具不容易踩坑。

**方案：只改中文目录，两个英文目录保留**

- `character reference/其他人物/` → `character reference/_guests/`。中文目录名的实际风险最高：CI 容器的 locale、非 UTF-8 的工具链、Windows 与 Linux 的编码差异都可能出问题，而这个目录以后会随客串角色增长。改动只涉及 3 个文件（story-illustrator SKILL.md 4 处、audit_en.py 1 处、mimi-sister 的 bible 标题 1 处）。下划线前缀也和已有的 `_tools/` 一致，天然表示"不是正式角色"。
- 两个带空格的英文目录**不动**。理由：引用面 17 个文件、会产生一次巨大 diff、所有历史文档里的路径说明同时失效，换来的只是不用打引号。

**如果你要全改**（可选，我不推荐现在做）：目标 `content/characters/`、`content/scenes/`、`content/characters/_guests/`，用 `git mv` 一次性做，然后把 6 个脚本里的路径提成常量，最后跑 build + audit + 全文 grep 确认零残留。建议和别的大改分开，单独一个提交。

**风险**：只改 `_guests` 的话极低。

**耗时**：15 分钟。

---

## A4. 真源规则没执行到底

**现状（已验证）**：`stories/README.md` 规定跨人物事件只存在于故事文件，bible 只留长期性格。但 4 个 bible 里还留着 6 段完整事件叙述，共 **105 行**：

| 角色 | 段落 | 行数 | 对应故事 |
|---|---|---|---|
| Haide | 他以前不是狗 | 22 | `2026-09-09-haide-became-a-dog.md` |
| QC | 噩梦 | 30 | `2026-09-09-qc-nightmare.md` |
| 点儿 | 王者兰特 | 17 | `2026-09-09-kings-rank-night.md` |
| QC | 小手术事件与月底派对 | 13 | `2026-09-09-seven-day-bite.md` |
| Liiie | 王者兰特原始记录 | 12 | `2026-09-09-kings-rank-night.md` |
| QC | 超速罚单与狗毛 | 11 | `2026-09-09-midnight-ferrari.md` |

六段全部有对应的故事文件。它们目前是**纯死代码**：`sync-content.mjs` 的 `isExtra()` 只认 `额外设定` 前缀，网站不显示；`audit_en.py` 第 50 行显式把 `事件档案` 归为跳过项，所以英文 bible 里压根没有这些段落，中英文结构已经不对称。

**方案**：删掉这 6 段，各留一行指针，例如：

```markdown
## 事件档案
本段事件已迁移到 [stories/2026-09-09-haide-became-a-dog.md](../../stories/2026-09-09-haide-became-a-dog.md)。长期影响见"和其他人的相处"与"额外设定"。
```

删之前逐段比对，确认故事文件确实覆盖了该段的所有信息点，有遗漏的先补进故事文件再删。

**影响面**：4 个中文 bible，减约 100 行。英文版不用动（本来就没有）。网站输出零变化。

**风险**：中。唯一实质风险是某段里有故事没写进去的细节。逐段比对可以消除。

**验证**：`npm run build` 页面数不变；`audit_en.py` 仍通过；diff 里只有删除和新增的指针行。

**耗时**：20 分钟（含逐段比对）。

---

## A5. 游离资产与死引用（含新发现）

**现状（已验证）**

- **`website/group-photo/work/` 是死引用的重灾区。** `composition.json` 指向 `work/background-16x9-v1.png` 和 `work/concept-v1.png`，`GROUP-PHOTO.md` 另外还提到 `identity-sheet.png`。**这三个文件全都不存在。** 目录里实际躺着 13 张随机名的 `exec-<uuid>.png` 和一张 `合照 (2).png`，共 27 MB，没有任何文档或代码引用它们。`build_identity_sheet.py` 的产物也已丢失。
- `website/站位图.png`（48 KB）在网站根目录，除了我自己的检测报告没人引用。
- `character reference/其他人物/`：**这条我上次说重了。** 它其实是工作流的一等公民，story-illustrator 的 SKILL.md 用 4 处定义了它的用途，`audit_en.py` 也显式跳过它。真正的缺口只有一个：网站不展示客串角色。

**方案**

1. **work/ 清理**：先确认那 13 张 exec 图是不是分层素材的最终版。如果是，改成有意义的文件名并更新 `composition.json`；如果只是过程稿，`git rm` 掉，仓库直接瘦 27 MB。同时修 `composition.json` 和 `GROUP-PHOTO.md` 里的三处死路径。**这一步需要你确认那些图还有没有用**，我不会自己删。
2. `站位图.png` 移到 `website/group-photo/work/layout-sketch.png`。
3. 客串角色：两条路，选一条。
   - **不上网站**（推荐）：现状即可，只在 `stories/README.md` 补一句说明它们不进角色页，避免下次又被当成缺陷。
   - **上网站**：`characters.config.mjs` 加 `guest: true` 字段，首页角色卡过滤掉，故事页的 `cast` 可以链接到一个简版客串页。约 1.5 小时。

**风险**：删图不可逆（虽然 git 历史里还在），所以要你先确认。

**耗时**：确认后 20 分钟。

---

## 需要你拍板的三件事

| # | 问题 | 我的建议 |
|---|---|---|
| 1 | GitHub 仓库改名 Kindergarden → Kindergarten？本地目录跟着改吗？ | 仓库改（有重定向，零风险）；本地目录等你有空再改，改完重开会话 |
| 2 | `group-photo/work/` 那 13 张 exec 图还有用吗？ | 如果是过程稿就删，仓库瘦 27 MB |
| 3 | 客串角色要不要上网站？ | 暂时不上，只补一句文档说明 |

## 执行顺序

不需要你拍板、我可以立刻做的：**A1**（skill 桩 + 脚本归位 + 校验）、**A4**（清 105 行死设定）、**A3 的 `_guests` 改名**、**A5 的 `站位图.png` 归位与三处死路径修正**。四项约 1.5 小时，全部走一个提交，做完跑 build + audit + 类型检查验证。

等你回答后再做的：A2 的仓库改名、A5 的 work/ 删图、客串角色方案。


---

## 执行记录（2026-09-09）

QC 的三个决定：仓库已改名、`work/` 图片可删、客串角色不上网站。据此全部执行。

| 项 | 结果 |
|---|---|
| A1 双 agent 生态 | `.agents/skills/` 为唯一实现；`.claude/skills/` 下五个转发桩由 `tools/skill_stubs.py` 生成并校验；孤儿 `fieldnotes` 副本（8 文件）删除；共用的 `audit_en.py` 移到 `tools/`，钩子不再跨界 |
| A2 改名 | remote 改指 `QC-Kindergarten.git`（`Base.astro` 的链接此前已更新）；本地目录名保持不变 |
| A3 目录命名 | `其他人物/` → `_guests/`；两个带空格的英文目录按方案保留 |
| A4 真源规则 | 六段"事件档案（已迁移）"共 105 行删除，改为指向故事的指针；两条会丢失的信息先补进正文 |
| A5 游离资产 | `group-photo/work/` 14 个文件（27 MB）删除，`work/` 加进 gitignore；`站位图.png` → `group-photo/layout-sketch.png`；三处死路径修正；客串角色规则写进 `stories/README.md` |

**执行中发现并修掉的额外问题**：`translate-en` 的 frontmatter 是无效 YAML（description 里有裸冒号），gray-matter 直接解析失败，Claude 的 skill 列表把正文当成了描述。已改写措辞去掉冒号，并在 `skill_stubs.py` 里加了这项检查，防止复发。

**两条差点丢失的信息，删档案段前已补**：
- QC 在派对上说的"感觉当狗也挺不错的"，以及由此变得更不积极 → 补进《七天追咬事件》中英文正文。
- Liiie 不争第一的态度"传说就该是传说呢" → 并进她的死宅常驻段。
- 另外两条（Haide 的贝壳、艾莎记的月度香水味）核对后确认已在 QC 的道具段和艾莎的关系段，无需动作。

**验证**：`tools/skill_stubs.py` 通过；`tools/audit_en.py` 通过；两个钩子端到端跑通；`npm run build` 63 页不变；五个 skill 现在都出现在 Claude 的 skill 列表里；正本与桩的 name / description 逐字一致。

**未做**：本地目录改名（等你有空，改完要重开会话）。
