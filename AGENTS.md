# QC Kindergarten

以创作者及其社交圈熟人的真实性格为原型，用 AI 铸造一组虚拟角色，再生成符合人设的情景喜剧故事。

## 目录

- `character reference/` — 12 个角色，每人一个文件夹：参考图、三视图、表情表、`性格设定.md`（中文 bible）与 `性格设定.en.md`。生成脚本在 `_tools/`，客串角色在 `_guests/`（不上网站）。
- `stories/` — 情景喜剧故事，跨人物事件的唯一正式来源。规则见 `stories/README.md`。
- `Scene Reference/` — 场景参考图，故事的 `location` 与网站地点页都引用它。
- `website/` — Astro 双语站，构建时从上面三个目录同步内容。跑法见 `website/README.md`。
- `tools/` — 两个 agent 共用的脚本：`audit_en.py`（中英覆盖审计）、`skill_stubs.py`（skill 桩同步）、`taste_scan.py`（算出 `qc-taste` 这次该读哪些新增的对话记录）。
- `.github/workflows/ci.yml` — push 与 PR 上跑单元测试、`npm run verify`、英文覆盖审计、skill 桩校验。注意 CI 构建的 dist 只用于校验，上线的是本地 prebuilt 的那份（见 `website/README.md`）。
- `.agents/state/` — skill 的运行时状态（如 discord 通知记录）。skill 目录只放定义，会变的东西放这里。
- `docs/` — 项目检测与整改记录。
- `ResearchAssets/` — **私有 submodule**，研究 / 论文 / 申请材料。主仓库公开，这个目录不公开。改动流程见 `ResearchAssets/AGENTS.md`。

## Skill 放在哪

`.agents/skills/` 是唯一实现，五个 skill 都在这里。`.claude/skills/` 下是同名的三行转发桩，只重复 frontmatter，正文指回正本。Codex 直接读正本，Claude Code 读到桩后再打开正本，两边看到的是同一份指令。

改完 skill 跑 `python tools/skill_stubs.py --write` 更新桩，`python tools/skill_stubs.py` 校验（描述不一致会退出码 1）。**不要**在 `.claude/skills/` 下写内容，也不要在 skill 目录里放会变的状态文件。

- `fieldnotes` — 项目知识记录。
- `story-illustrator` — 故事插画提案、可复用资产准备与生成工作流。
- `qc-taste` — 从人类创作决策中提炼并延续 QC 的可更新创作 taste；正式规则更新需要 QC 批准。
- `translate-en` — 网站英文版翻译工作流：覆盖审计、文学性优先的译法、意译决策汇报。
- `discord-notify` — 新故事 / 新插图上线后，通过 Discord webhook 发不剧透的更新通知，附网站链接。

## 当前研究方向

- 社交图谱与真人性格原型驱动的生成式情景喜剧
- 被写者反馈进入虚构后的协商式表征
- 从人机共创中的人类选择、否决和修订提炼可更新的 `qc-taste`，研究创作者 taste 的延续与自主创作边界

## 研究背景（来自私有 submodule，无权限时此引用为空）

@ResearchAssets/AGENTS.md
