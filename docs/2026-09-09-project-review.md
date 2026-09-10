# 项目整体检测：架构清晰度 · 代码质量 · 可维护性

日期：2026-09-09　基线：main `ce0bd54`　范围：主仓库全部 + ResearchAssets 结构（不评研究内容）

## 结论

| 维度 | 分 (5) | 一句话 |
|---|---|---|
| 架构清晰度 | 3.5 | 内容 / 网站 / 研究三层分离和"单一数据源"落实得好；双 agent 生态重复、命名残留、真源规则没执行到底 |
| 代码质量 | 3.5 | 网站与脚本职责清楚、有注释；类型检查有 2 个错误被 build 掩盖，UI 片段重复，风格在两个 AI 的提交之间已不一致 |
| 可维护性 | 2.5 | 没有 CI、没有测试、没有 schema 校验；素材全量入库，仓库会持续膨胀；文档已有 4 处漂移 |

验证过的事实：`npm run build` 通过，63 页，4.5 秒；`astro check` 2 错 0 警 2 提示；`audit_en.py` 通过；仓库 pack 60 MB，工作区素材约 310 MB。

## 架构清晰度

**做得对的**
- 网站不手抄内容：`website/scripts/sync-content.mjs` 在每次 dev / build 前从 `character reference/`、`stories/`、`Scene Reference/` 生成 JSON 和图片，生成物不入库。
- 研究材料放私有子模块，Discord webhook 等私密配置放 `ResearchAssets/config/`，公开仓库零密钥（已 grep 校验）。
- 故事系统有明确的数据模型：`type: memory | extra`、`memories.<slug>.{knowledge, summary, impact}`、`timeline`，中英文双文件同构，并有确定性审计脚本。

**问题**
1. **两套 agent 配置互为副本。** `CLAUDE.md` 与 `AGENTS.md` 除文件名互换外逐字相同；`fieldnotes` skill 在 `.claude/skills/` 和 `.agents/skills/` 各有一份，已漂移 2 行。Claude 侧的 hook `check_bilingual_consistency.py` 又去调用 `.agents/skills/translate-en/scripts/audit_en.py`，两个生态互相引用。
2. **改名残留。** 项目已更名 QC Kindergarten（提交 `31be12c`），但 GitHub 仓库、本地目录仍是 Kindergarden；子模块 URL 已改成 Kindergarten-Research。
3. **顶层目录命名混合中英文且含空格**：`character reference`、`Scene Reference`、`其他人物`，脚本里处处要引号，新工具容易踩坑。
4. **"故事是事件唯一真源"没执行到底。** `stories/README.md` 规定事件只在故事文件里，bible 保留长期性格。实际 Haide、点儿、QC 的 bible 里还留着完整事件叙述，只是标题改成"事件档案（已迁移）"（QC 两段、Haide 一段、点儿一段），网站不显示但两处都要改。
5. **游离资产。** `character reference/其他人物/` 五个客串角色有 bible 和三视图，但 config、网站、脚本都不认识它们；`website/站位图.png` 散在网站根目录；`website/group-photo/work/` 14 张过程稿（27 MB）入了库。

## 代码质量

**做得对的**
- `sync-content.mjs` 341 行，函数粒度合理（`parseBible`、`parseStoryContent`、`latestVersion` 等），注释说明了每个来源和输出。
- `content.ts` 集中了类型、图片查找和语言回退，页面里没有散落的路径拼接。
- hook 脚本结构一致、都处理了 Windows 的 UTF-8 stdout。

**问题**
1. **类型错误被掩盖。** `astro check` 报 2 个 `ts(2352)`：`charactersJson as Character[]` 和 `storiesJson as Story[]`。原因是 TS 从 JSON 推出的字面量类型与手写 interface 不兼容（`basic` 的可选键、`en.memories` 的 undefined 值）。Astro build 不跑类型检查，所以一直绿。更深的问题：JSON 形状在 sync 脚本里"写出来"，interface 在 `content.ts` 里"再写一遍"，两边靠人工同步。
2. **UI 片段重复。** 圆形头像（`object-position: 50% 15%`）在 `StoryList`、`characters/[slug]`、`stories/[slug]` 三个文件五处各写一遍，类名分别叫 `.avatar`、`.face`、`.member`；`.notice`、`.crumbs` 样式在角色页和故事页各复制一份。
3. **sync 脚本内部重复。** `nameToSlug[x] ?? nameToSlug[x.toLowerCase()]` 出现 3 次而已有 `resolveSlug`；`location` 与 `locations` 同时输出；中英文 `memories` 解析逻辑几乎相同却写了两遍。
4. **风格不统一。** `StoryList.astro` 的 CSS 被压成单行，其它文件多行；没有 prettier / eslint / editorconfig，Claude 与 Codex 的提交风格已经分叉。
5. **Python 工具分散**在 5 个位置（`character reference/_tools`、`website/group-photo/_tools`、`.agents/skills/*/scripts`、`.claude/hooks`、`ResearchAssets/ai-chat-history/_tools`），没有 requirements 文件（`gen_reference.py` 依赖 `requests`）。
6. 小项：`characters/[slug].astro` 里 `sectionId` 的 `title` 参数未使用；`i18n.ts` 用 `as const` 手写两套字典，键对齐靠外部审计而不是 TS。

## 可维护性

1. **没有 CI。** build、类型检查、双语审计都只在本地跑，且类型检查从没跑过。
2. **没有测试。** `parseBible` 对标题、表格、口头禅引号的解析全靠约定，改一个 bible 格式就可能静默丢字段。
3. **frontmatter 无校验。** `type` 拼错会静默变成 `memory`；`knowledge` 写了非法值会原样进 JSON；`location` 未知只 warn。
4. **仓库体积。** 所有 PNG 直接入 git，pack 已 60 MB；历史里有 `FUFU→Fufu` 这类重命名，同一张图存了两份；`stories/README.md` 规定"所有版本都留着"，加上 4K 版本，每个故事会带 5 到 8 张 2 到 8 MB 的图。
5. **文档漂移**（4 处）：`website/README.md` 页面列表没有 places 页；`DESIGN.md` 待办第 6 条"英文翻译"已完成未勾；第 4 层"环境全景"描述与现状（房间页 + 平面图）不符；`CLAUDE.md` 说 `.claude/skills/fieldnotes/` 是项目 skill，实际主力 skills 在 `.agents/skills/`。
6. **hook 成本。** `check_bilingual_consistency` 在每次写 bible / 故事 / i18n 时跑完整审计（上限 30 秒）。目前 12 角色 6 故事还快，规模翻倍后会明显拖慢编辑。

## 建议的处理顺序

**P0（一小时内，零风险）**
- 修 2 个类型错误：把两处 `as X[]` 改成 `as unknown as X[]` 只是止血；正确做法见 P1 第一条。删掉 `sectionId` 未用参数。
- `AGENTS.md` 为唯一正本，`CLAUDE.md` 改成一行 `@AGENTS.md`；删除 `.claude/skills/fieldnotes/`，让两个生态都读 `.agents/skills/`。
- 更新四处漂移的文档。
- 把 `website/站位图.png` 移到 `website/group-photo/work/`。

**P1（一天）**
- 给 sync 输出加 schema：用 zod 定义 `Character` / `Story`，sync 脚本写出前 `parse()`，`content.ts` 用 `z.infer` 取类型，删掉手写 interface。frontmatter 非法值直接报错退出。
- 抽三个组件：`Avatar.astro`、`Notice.astro`、`Crumbs.astro`；`.notice` / `.crumbs` 样式进 `global.css`。
- sync 脚本：统一走 `resolveSlug`；`memories` 解析抽成一个函数供中英文复用；`location` 字段删掉只留 `locations`。
- 加 prettier + editorconfig，`npm run check` 跑 `astro check`，`npm run lint`。
- GitHub Actions：push 时跑 sync + build + astro check + audit_en，Vercel 继续负责部署。
- `node:test` 给 `parseBible`、`parseStoryContent`、`resolveSlug` 各写 3 到 5 个用例，用真实 bible 做快照。

**P2（有空再做）**
- 素材策略二选一：Git LFS 管所有 PNG；或者过程稿（`work/`、v1 到 v(n-1) 草稿）不入库，仓库只留最终版 + 4K。改 `stories/README.md` 的"所有版本都留着"。
- bible 里"事件档案（已迁移）"四段删掉，或压成一行"见 stories/xxx.md"。
- `其他人物/` 要么进 config 成为一等公民（`guest: true`，网站不列卡片但故事页可引用），要么移到 `stories/assets/guests/`。
- 顶层目录去空格、统一英文：`content/characters`、`content/scenes`、`content/stories`。这是大改，配合一次 sync 脚本路径常量修改即可，但会让 git 历史里的重命名再多一轮，建议和 LFS 迁移一起做。
- 仓库改名与本地目录改名对齐 Kindergarten。
- Python 工具集中到 `tools/`，加 `requirements.txt`。

## 附：检查方法

- 结构：`git ls-files` 按目录计数、`du`、最大文件 top 15
- 重复：`md5sum` / `diff` 比对 CLAUDE.md 与 AGENTS.md、两份 fieldnotes；`grep` 统计 UI 片段与样式块出现位置
- 构建：`npm run build`；类型：`npm i --no-save @astrojs/check typescript && npx astro check`（未改动 package.json）
- 内容一致性：`audit_en.py`；config 与磁盘目录逐一比对；故事中英文 `memories` 键数与插图标记数比对
- 密钥：grep 各家 key 前缀，零命中
