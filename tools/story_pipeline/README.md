# story_pipeline

四模型并行出故事大纲 → QC 盲评裁决 → 选中的进入成稿。设计与理由见
[`docs/2026-09-09-story-pipeline-design.md`](../../docs/2026-09-09-story-pipeline-design.md)，
本文只讲怎么跑。

## 一轮怎么跑

平时用本地评审站：生成、打分、批注、两种重写都在一个页面里。用法见
[`tools/story_review/README.md`](../story_review/README.md)。

```bash
python tools/story_review/server.py             # 正式
python tools/story_review/server.py --dry-run   # 演练：临时副本 + 假模型
```

下面是同一套流程的命令行版本：

```bash
# 1. 先看模型会收到什么
python tools/story_pipeline/brief.py --slots                            # 五个位子分别是什么
python tools/story_pipeline/brief.py --slot escalation                  # 完整 brief
python tools/story_pipeline/brief.py --slot escalation --max-chars 300  # 指定大纲上限

# 2. 生成（四个模型 × 四个位子 + 一个扩展位 = 17 次调用，外加上一轮候补的重写）
python tools/story_pipeline/run_round.py
python tools/story_pipeline/run_round.py --min-chars 120 --max-chars 300   # 每个位子在范围内抽一个上限
python tools/story_pipeline/run_round.py --models kimi,deepseek            # 只用其中几个
python tools/story_pipeline/run_round.py --no-taste                        # 消融组
python tools/story_pipeline/run_round.py --no-waitlist                     # 这一轮不带回候补
python tools/story_pipeline/run_round.py --per-model 2                     # 每个模型最多同时几个调用（默认 4）
python tools/story_pipeline/run_round.py --format default                  # formats/<name>.json

# 3. 推到 Discord 评审频道（一篇一帖，不显示模型名；用评审站就不需要这一步）
python tools/story_pipeline/publish.py --dry-run     # 先看排版
python tools/story_pipeline/publish.py

# 4. 盲评：列出待裁决的故事，不显示模型名
python tools/story_pipeline/review.py
python tools/story_pipeline/review.py --show c-a7f3      # 单看一条

# 5. 逐条裁决（--score 可选，和评审站同一套 0–10 分）
python tools/story_pipeline/review.py c-a7f3 select --score 8
python tools/story_pipeline/review.py c-b1e9 discard --reasons too_everyday bland --notes "为什么"
python tools/story_pipeline/review.py c-c4d2 shortlist --notes "好在哪，缺什么"   # 必须带意见
python tools/story_pipeline/review.py c-d0f1 revise --notes "把结尾收短"
python tools/story_pipeline/rewrite.py c-d0f1        # 终端里 revise 不会自动重写，要手动触发

# 6. 全部裁决完之后，才揭晓每个模型的表现
python tools/story_pipeline/review.py --stats
```

## 五个位子

r01 问的是「把这三个人放进这个房间会发生什么」——那是个生活流问题，得到的是生活流答案和 6/6 全否决。**已被接受的六篇故事没有一篇是从房间出发的。** 所以现在给的是**前提的形状**，人物和地点由模型自己定：

| 位子 | 做什么 | 反推自 |
|---|---|---|
| `consequence` 后果位 | 拿一篇已有故事，写它留下的残留在几个月后长成的新麻烦 | 《七天追咬事件》 |
| `contradiction` 矛盾位 | 拿一个角色的矛盾，写它不再是笑点、变成真麻烦的那一刻 | 《Haide 变成狗的那一天》 |
| `escalation` 放大位 | 拿一条已确立的具体事实，推到不可能的量级 | 《午夜的金色法拉利》 |
| `transposition` 移植位 | 把全员搬进一个不属于幼儿园的类型，保留身份锚点 | 《幼儿园四大魔女》 |
| `expansion` 扩展位 | 必须引入新客串或新场景才能成立的故事，每轮一条，模型轮流 | — |

每轮 = 4 模型 × 4 个基础位 + 1 个扩展位 = **17 篇**。同一个位子，四个模型收到的 brief 逐字节相同——这是唯一的受控变量。

## 六条不要绕过的约束

**只用 webhook，不做 bot。** webhook 只写不读，裁决收不回来——读在 Discord，判在终端。每轮第一条消息附可复制的命令，每篇 footer 带 id。发送用 `urllib` 时必须带 `User-Agent`：Cloudflare 对默认的 `Python-urllib/3.x` 直接回 403，而隔壁 `discord-notify` 用 `requests` 所以从没撞上。

**盲评在裁决完成前不揭晓模型。** `--stats` 在还有 `pending` 时会拒绝执行。知道作者是谁会把偏好变成习惯，同时毁掉选择本身和 per-model 数据。

**丢弃必须说明为什么。** 理由标签和批注至少要有一样；评审站更严，批注必填，因为 QC 的反馈主要写在文字里，标签只是辅助（2026-09-10）。理由标签可以多选，第一个记为 `reason`，全部记在 `reasons`。理由集在 `store.REASONS`，是 r01 之后按 QC 实际用词重写的。`too_everyday` 和 `bland` 是分开的：前者是前提根本没离开现实，后者是离开了但仍然没味道。

**CLI 必须在干净目录里跑，且 brief 走 stdin。** 前者因为 Claude Code 和 Codex 会读工作目录的 `AGENTS.md`——在仓库里跑等于偷偷多喂整个项目，而 HTTP 那两个只看得到 brief，四个输入不再可比且不报错。后者因为 Windows 命令行上限 32767 字符而 brief 约 36000 字节，当参数传会直接失败或截断。

**这一步只出大纲，上限 200 字。** r02 试过让模型写完整短篇，产出 817–4895 字，整轮被否——既读不动，也不是这一步该做的事。正文由后面的环节统一执笔，这里要挑的是**值得被写成故事的前提**。

两个上限是分开的，不要合并：`MAX_OUTLINE_CHARS = 200` 管生成阶段的大纲，`MAX_PROSE_CHARS = 2286` 管成稿正文（已定稿最长篇 2086 + 200，其余五篇 387–517、中位数 488）。测试钉住了这两个数不能被合并。超限只标记不拒收——多几个字但确实好的大纲仍然该送到 QC 面前。

2026-09-10 起，大纲上限可以是一个范围（`--min-chars` / `--max-chars`，评审站顶栏的「字数上限」）。**每个位子**在范围内抽一个值，同一位子的四个模型共用，所以 brief 仍然逐字节相同；如果按篇抽，某个模型可能只是因为抽到了更大的篇幅而显得更好。抽到的值记在 `round.json` 的 `max_chars`，每篇候选也记了自己的 `max_chars`，超限按各自的上限判断。不传参数时仍是 200。

**brief 带着知情者和留白标记。** 每篇已有故事都列出 `memories` 里的知情者及其程度，没列出的角色不知道那件事；`open_ending: true` 的故事标为不可续写，后果位也不会拿它们当起点。2026-09-10 这一轮之前 brief 丢掉了全部 `memories`，于是只有三个人知道的法拉利被整个幼儿园拿去开庭，而后果位的 4 条全部去续了那两篇刻意留白的故事。

**候补必须带 QC 的意见。** `shortlist` 不带 `--notes` 会被拒绝：候补以后要被拿出来重写，没有「好在哪、缺什么」就只会把同一个毛病再生成一遍。

**`stands_beside` 不是 `differs_from`。** r01 用的是「这条和哪篇最接近，区别在哪」，模型全都通过"更小、更静、更少人物"来达成区别——那是最便宜的差异化方式，而且**正在制造寡淡**。现在问的是「凭什么配站在那一篇旁边」，并明确写了不要靠写得更小来制造区别。

## 输出格式

模型的输出格式在 `formats/default.json`，不在 `brief.py` 里。QC 发现格式本身会影响模型写故事的倾向（2026-09-10），所以格式要能低成本地改、也要能对照：

- 文件按顺序列出字段、每个字段怎么要求、哪个字段装大纲本身（`body_field`）。`brief.py` 按它渲染 brief，`run_round.py` 按它解析回复，评审站按它的 `show` 决定字段显示在哪。改格式不需要改代码。
- `Candidate` 没有的字段存进候选的 `extra`，不会丢。
- 占位符：`<<PREMISE_HINT>>` 换成位子的提示，`<<MAX_CHARS>>` 换成这个位子抽到的上限。
- 改了要升 `version`。每轮 `round.json` 记下格式的名字、版本和文件 sha256，每篇候选记 `format_version`。
- 对照实验：复制成 `formats/<新名字>.json`，用 `--format <新名字>` 跑。

抽成文件时校验过：新代码渲染出的 brief 和原来硬编码的版本逐字节相同，历史轮次记下的 brief sha256 仍然有效。

## 重写

`rewrite.py` 负责两种重写，都交给**写这篇的同一个模型**——重写要检验的是这个作者能不能改好 QC 指出的问题，换一个模型就成了披着旧 id 的新候选。brief 是原位子的 brief，加上原大纲、QC 的分数和批注，上限取 `rewrite_max_chars`（QC 单独设的）→ 原来的 `max_chars` → 200。

- **候补重写（waitlist）**：`run_round.py` 每轮开始时把候补池里的故事全部带回来，改写稿进新一轮，`round.json` 的 `waitlist_rewrites` 记下每篇重写的 brief sha256。改写稿继承父稿的 `revisit_count`，整条故事线共用 `MAX_REVISITS = 3` 次机会，用完以 `never_chosen` 退出。重写成功后父稿记 `rewritten_as`，离开候补池；模型失败时父稿不动，下一轮再来。
- **按意见重写（revise）**：`selected_with_notes` 在评审站提交后立刻在后台重写，改写稿进**同一轮**，等 QC 再批；不占候补的次数。终端里用 `python tools/story_pipeline/rewrite.py <id>` 手动触发。

改写稿记 `parent` 和 `rewrite`（`waitlist` / `revise`），**不计入** `store.stats` 的模型对比：那份对比建立在同位子四个模型收到相同 brief 上，而重写的 brief 每篇都不同。

## 文件

| 文件 | 作用 |
|---|---|
| `brief.py` | 五个位子的 brief 构建；压缩 12 份 bible、场景、客串、已有故事、taste profile；按格式文件渲染输出要求 |
| `formats/default.json` | 模型的输出格式：字段、要求、显示位置 |
| `adapters.py` | 四个模型统一成 `generate(brief) -> str`；容错的 JSON 解析 |
| `store.py` | 候选文件读写、裁决状态机、分数分档、备选池衰减、per-model 统计 |
| `run_round.py` | 编排一轮：按位子抽上限、带回候补重写，写 `round.json`（含每个位子的 brief sha256）；`run()` 供评审站调用 |
| `rewrite.py` | 候补重写与按意见重写，交给原模型 |
| `publish.py` | 把一轮推到 Discord 评审频道，一篇一帖 |
| `review.py` | 终端盲评与裁决 |
| `test_pipeline.py` | `python tools/story_pipeline/test_pipeline.py` |
| `../story_review/` | 本地评审站，见其 `README.md` |

候选数据落在 **私有子模块** `ResearchAssets/story-candidates/<轮次>/`——里面是 QC 对朋友虚拟分身的原始否决理由。选定的故事才毕业到公开仓库的 `stories/`。

## 模型

```bash
python tools/story_pipeline/adapters.py --list
python tools/story_pipeline/adapters.py --test deepseek
```

- `kimi` / `deepseek` — HTTP，key 在 `ResearchAssets/config/story-pipeline.env`。
  Moonshot 分 `api.moonshot.cn`（国内）与 `api.moonshot.ai`（国际）两套独立体系，key 互不通用，模型 id 也不同；本项目用 `.ai`。
- `claude` / `codex` — 子进程，用本机已登录的订阅态，不需要 key。两者都从 stdin 读 prompt。
  `codex exec` 需要 `--skip-git-repo-check`，因为临时目录故意不是 git 仓库。
  Codex 固定用 `gpt-5.6-sol`，并加 `--ignore-user-config` 和 `--ephemeral`：不读个人的 `~/.codex/config.toml`，否则默认模型、MCP 服务和插件都会跟着各台电脑的个人设置变（有一台电脑的默认模型是 ChatGPT 账号用不了的，会让每一篇 Codex 调用都失败）；也不把每轮的调用写进个人会话历史。

**并发与到达顺序。** 每个模型各自排队，最多同时 `PER_MODEL_CONCURRENCY = 4` 个调用，模型之间始终并行，每篇写完立刻落盘，评审站随即显示。之前是整轮共用 8 个并发，慢的 CLI 调用会占住名额，快模型后面的故事只能排队。2026-09-10 实测：Kimi、DeepSeek、Claude、Codex 各 4 个同时调用均无限流。

## 待定

- 扩展位由四个模型轮流承担，按已有轮次数取模。中途更换模型组合的话轮换表要重置。
- 位子的配比目前是四个各一次。跑几轮后可以按采纳率调整——如果某个位子稳定产出好东西，值得给它更多次。
