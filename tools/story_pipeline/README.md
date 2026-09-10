# story_pipeline

四模型并行出故事大纲 → QC 盲评裁决 → Claude 统一写正文。设计与理由见
[`docs/2026-09-09-story-pipeline-design.md`](../../docs/2026-09-09-story-pipeline-design.md)，
本文只讲怎么跑。

## 现在能跑到哪一步

| 步骤 | 状态 |
|---|---|
| brief 构建 | ✅ |
| 候选库 + 裁决状态机 | ✅ |
| 四个 adapter | ✅ 代码就绪，**四个当前都不可用**（见下） |
| 轮次编排 | ✅ `--dry-run` 已跑通全流程 |
| 终端盲评 | ✅ |
| Discord bot | ❌ 未做，先用终端盲评代替 |
| 成稿衔接 | ❌ 未做 |

## 先跑这个

```bash
python tools/story_pipeline/adapters.py --list
```

四个模型现在都不可用，缺的东西不一样：

- `kimi` / `deepseek` — 往根目录 `.env` 填 `MOONSHOT_API_KEY` / `DEEPSEEK_API_KEY`（`.env.example` 里有位置）
- `claude` / `codex` — 两个 CLI 都不在 PATH 上。桌面版 Claude 不提供 `claude` 命令行入口，需要单独装

**只要有一个能用就能跑真实轮次**，用 `--models` 指定即可。

## 一轮怎么跑

```bash
# 1. 生成（先看一眼模型会收到什么）
python tools/story_pipeline/brief.py --combos
python tools/story_pipeline/run_round.py --models kimi,deepseek

# 2. 盲评：列出待裁决的候选，不显示模型名
python tools/story_pipeline/review.py

# 3. 逐条裁决
python tools/story_pipeline/review.py c-a7f3 select
python tools/story_pipeline/review.py c-b1e9 discard --reason stale_joke
python tools/story_pipeline/review.py c-c4d2 shortlist
python tools/story_pipeline/review.py c-d0f1 revise --notes "把结尾收短"

# 4. 全部裁决完之后，才揭晓每个模型的表现
python tools/story_pipeline/review.py --stats
```

消融组跑 `run_round.py --no-taste`；带自己的点子跑 `--seed-text "..."`。

## 三条不要绕过的约束

**盲评在裁决完成前不揭晓模型。** `--stats` 在还有 `pending` 时会拒绝执行。知道作者是谁会把偏好变成习惯，同时毁掉选择本身和 per-model 数据。

**丢弃必须带理由。** 没有理由的废稿等于没留。理由集在 `store.REASONS`，跑几轮后按分布调整——如果大半都落在「就是不好笑」，说明标签太粗要拆。

**CLI 必须在干净目录里跑。** `adapters._run_cli()` 用临时目录，因为 Claude Code 和 Codex 会读工作目录的 `AGENTS.md`。在仓库里跑它们就等于偷偷多喂了整个项目，而 Kimi / DeepSeek 只看得到 brief——四个输入不再可比，且没有任何东西会报错。

## 文件

| 文件 | 作用 |
|---|---|
| `brief.py` | 构建自包含 brief；分配（人物组 + 场景）组合，四个模型收到同一份 |
| `adapters.py` | 四个模型统一成 `generate(brief) -> str`；容错的 JSON 解析 |
| `store.py` | 候选文件读写、裁决状态机、备选池衰减、per-model 统计 |
| `run_round.py` | 编排一轮，写 `round.json`（含每个组合的 brief sha256） |
| `review.py` | 终端盲评，Discord bot 的替身 |
| `test_pipeline.py` | 25 个用例，`python tools/story_pipeline/test_pipeline.py` |

候选数据落在 **私有子模块** `ResearchAssets/story-candidates/<轮次>/`——里面是 QC 对朋友虚拟分身的原始否决理由。选定并写完的故事才毕业到公开仓库的 `stories/`。

## 待定

- 组合目前由脚本按覆盖度加权指派（出场少的角色和场景权重更高）。设计文档里这一条是待定，倾向指派，跑几轮后再看要不要改成模型自选。
- 扩展位由四个模型轮流承担，按已有轮次数取模。中途更换模型组合的话轮换表要重置。
