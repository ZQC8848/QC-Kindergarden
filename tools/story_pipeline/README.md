# story_pipeline

四模型并行出故事大纲 → QC 盲评裁决 → 选中的进入成稿。设计与理由见
[`docs/2026-09-09-story-pipeline-design.md`](../../docs/2026-09-09-story-pipeline-design.md)，
本文只讲怎么跑。

## 一轮怎么跑

```bash
# 1. 先看模型会收到什么
python tools/story_pipeline/brief.py --slots            # 五个位子分别是什么
python tools/story_pipeline/brief.py --slot escalation  # 完整 brief

# 2. 生成（四个模型 × 四个位子 + 一个扩展位 = 17 次调用）
python tools/story_pipeline/run_round.py
python tools/story_pipeline/run_round.py --models kimi,deepseek   # 只用其中几个
python tools/story_pipeline/run_round.py --no-taste               # 消融组

# 3. 推到 Discord 评审频道（一篇一帖，不显示模型名）
python tools/story_pipeline/publish.py --dry-run     # 先看排版
python tools/story_pipeline/publish.py

# 4. 盲评：列出待裁决的故事，不显示模型名
python tools/story_pipeline/review.py
python tools/story_pipeline/review.py --show c-a7f3      # 单看一条

# 5. 逐条裁决
python tools/story_pipeline/review.py c-a7f3 select
python tools/story_pipeline/review.py c-b1e9 discard --reason too_everyday
python tools/story_pipeline/review.py c-c4d2 shortlist --notes "好在哪，缺什么"   # 必须带意见
python tools/story_pipeline/review.py c-d0f1 revise --notes "把结尾收短"

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

**丢弃必须带理由。** 理由集在 `store.REASONS`，是 r01 之后按 QC 实际用词重写的。`too_everyday` 和 `bland` 是分开的：前者是前提根本没离开现实，后者是离开了但仍然没味道。

**CLI 必须在干净目录里跑，且 brief 走 stdin。** 前者因为 Claude Code 和 Codex 会读工作目录的 `AGENTS.md`——在仓库里跑等于偷偷多喂整个项目，而 HTTP 那两个只看得到 brief，四个输入不再可比且不报错。后者因为 Windows 命令行上限 32767 字符而 brief 约 36000 字节，当参数传会直接失败或截断。

**这一步只出大纲，上限 200 字。** r02 试过让模型写完整短篇，产出 817–4895 字，整轮被否——既读不动，也不是这一步该做的事。正文由后面的环节统一执笔，这里要挑的是**值得被写成故事的前提**。

两个上限是分开的，不要合并：`MAX_OUTLINE_CHARS = 200` 管生成阶段的大纲，`MAX_PROSE_CHARS = 2286` 管成稿正文（已定稿最长篇 2086 + 200，其余五篇 387–517、中位数 488）。测试钉住了这两个数不能被合并。超限只标记不拒收——多几个字但确实好的大纲仍然该送到 QC 面前。

**brief 带着知情者和留白标记。** 每篇已有故事都列出 `memories` 里的知情者及其程度，没列出的角色不知道那件事；`open_ending: true` 的故事标为不可续写，后果位也不会拿它们当起点。2026-09-10 这一轮之前 brief 丢掉了全部 `memories`，于是只有三个人知道的法拉利被整个幼儿园拿去开庭，而后果位的 4 条全部去续了那两篇刻意留白的故事。

**候补必须带 QC 的意见。** `shortlist` 不带 `--notes` 会被拒绝：候补以后要被拿出来重写，没有「好在哪、缺什么」就只会把同一个毛病再生成一遍。

**`stands_beside` 不是 `differs_from`。** r01 用的是「这条和哪篇最接近，区别在哪」，模型全都通过"更小、更静、更少人物"来达成区别——那是最便宜的差异化方式，而且**正在制造寡淡**。现在问的是「凭什么配站在那一篇旁边」，并明确写了不要靠写得更小来制造区别。

## 文件

| 文件 | 作用 |
|---|---|
| `brief.py` | 五个位子的 brief 构建；压缩 12 份 bible、场景、客串、已有故事、taste profile |
| `adapters.py` | 四个模型统一成 `generate(brief) -> str`；容错的 JSON 解析 |
| `store.py` | 候选文件读写、裁决状态机、备选池衰减、per-model 统计 |
| `run_round.py` | 编排一轮，写 `round.json`（含每个位子的 brief sha256） |
| `publish.py` | 把一轮推到 Discord 评审频道，一篇一帖 |
| `review.py` | 终端盲评与裁决 |
| `test_pipeline.py` | `python tools/story_pipeline/test_pipeline.py` |

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

## 待定

- 扩展位由四个模型轮流承担，按已有轮次数取模。中途更换模型组合的话轮换表要重置。
- 位子的配比目前是四个各一次。跑几轮后可以按采纳率调整——如果某个位子稳定产出好东西，值得给它更多次。
