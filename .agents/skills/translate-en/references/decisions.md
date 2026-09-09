# Translation decisions log

Every non-literal choice made by a translation run, newest first. Status is `pending` until QC confirms (`approved`) or replaces (`replaced by …`). Approved reusable terms are copied into [glossary.md](glossary.md).

Format per run:

```
## YYYY-MM-DD — <scope>

| 原文 | 译文 | 为什么 | 其他方案 | 出现位置 | 状态 |
|---|---|---|---|---|---|
```

Keep the "为什么" column short: what the Chinese does, what the English does to match. "其他方案" lists the real alternatives considered with one clause on why each lost.

## 2026-09-09 — full site: 12 bibles, 6 stories

All rows below were approved by QC on 2026-09-09; reusable terms are in the glossary.

### Game and IDs

| 原文 | 译文 | 为什么 | 其他方案 | 出现位置 | 状态 |
|---|---|---|---|---|---|
| 王者兰特 | Kings of Rant | 中文是《王者荣耀》的谐音戏仿。"Kings of" 保住"王者"和 MOBA 味，"Rant"和"兰特"同音，又是英文里"喷"的意思，正好是排位夜的气氛。 | Honor of Rants（更贴原梗但作为标题不顺口）；Kingslant（纯音译，没有笑点）；Rank of Kings（太像真游戏，失去戏仿感） | kings-rank-night.en.md，Dianer / Liiie 的 bible | approved |
| 狗不理 | NoDogsAllowed | 天津包子梗保不住。这个 ID 的功能是：像一个真实玩家 ID，让人猜不到是狗，揭晓时又觉得"原来早有暗示"。"NoDogsAllowed"三点都满足，而且第一名的 ID 叫"禁止狗入内"，本人是狗，反差最强。 | TopDog（太直白，揭晓前就露馅）；Goubuli（音译，英文读者什么都读不出）；Fetch（有狗味，但不像排行榜第一的 ID） | kings-rank-night.en.md ×4，Dianer / Liiie / Haide bible | approved |
| 点到为止 | PointTaken | 原 ID 取自点儿的名字，也是他"算好了就收手"的打法。"Point"对应"点"，"PointTaken"本义是"我明白了，到此为止"，正好是"点到为止"的意思，而且像一个真实 ID。 | JustEnough（意思对，丢了名字）；CleanStop（打法对，丢了名字）；Dianer（直接用名字，太露） | kings-rank-night.en.md，Dianer / Liiie bible | approved |
| 夜行玫瑰 | NightRose | 直译，只是并成一个词，符合游戏 ID 习惯。 | Night Rose（两个词，像笔名不像 ID） | kings-rank-night.en.md，Dianer / Liiie bible | approved |
| 定榜 | the rankings lock / ranking night | 中文"定榜"是造词，英文没有对应，用"lock"表达"定"。标题用 Ranking Night。 | settlement night（太像财务）；leaderboard day（丢了"夜"） | kings-rank-night.en.md | approved |
| 别看了，学不会的。 | Stop watching. You can't learn it. | 两个短句，保持 Haide 头也不回的冷淡。 | Don't bother, you'd never learn（多了一层劝，太软） | kings-rank-night.en.md，Dianer / Haide bible | approved |

### Titles and names

| 原文 | 译文 | 为什么 | 其他方案 | 出现位置 | 状态 |
|---|---|---|---|---|---|
| 幼儿园四大魔女 | The Four Witches of the Kindergarten | 直译即可，"Four Witches"本身就有戏仿感。 | The Kindergarten's Four Witches（弱） | four-witches.en.md | approved |
| 贪婪 / 嫉妒 / 愤怒 / 懒惰魔女 | Witch of Greed / Envy / Wrath / Sloth | 四个词正好是七宗罪的英文，Haide 的"评级"因此更像一本正经的胡说。 | Greedy Witch 等形容词形式（没有七宗罪的联想） | four-witches.en.md | approved |
| QC 的连环噩梦 | QC's Nightmare in Three Acts | "连环"直译成 chain 很怪，正文本来就是三层梦，用"三幕"点题。 | QC's Chain Nightmare（生硬）；QC's Nightmare, Three Layers Deep（长） | qc-nightmare.en.md，QC bible | approved |
| 七天追咬事件 | The Seven-Day Bite | 去掉"事件"，英文标题不需要。 | The Seven-Day Chase（丢了"咬"）；The Seven-Day Bite Incident（累赘） | seven-day-bite.en.md | approved |
| 午夜的金色法拉利 | The Gold Ferrari at Midnight | 直译。 | Midnight Gold Ferrari（像车型名） | midnight-ferrari.en.md | approved |
| Haide 变成狗的那一天 | The Day Haide Became a Dog | 直译。 | | haide-became-a-dog.en.md | approved |
| 牧师 | Mushi | 沿用 config 里已定的英文名，正文里保留"clerical collar / prayer book"的神职意象。 | Pastor（当名字用太像职务） | 全站 | 已由 config 定 |
| 处理方案 001 / 014 | Case 001 / Case 014 | 艾莎的编号计划。"Case"短、冷、像档案，比"Handling Plan"像她。 | Handling Plan 001（直译，啰嗦）；Protocol 001（太机构化） | 多处 | approved |
| 红书 | the Red Book | 大写，当专名，它在故事里几乎是一个角色。 | the red notebook（太随便） | 多处 | approved |
| 董事长 | the Chairman | 大写当外号用；陆姚和艾莎口中的"董事长"都带讽刺，大写保住这个味道。 | the Director（不准确） | 多处 | approved |
| 阿姨（QC 的女伴） | Auntie | 保留孩子的叫法，加引号首次出现。 | the lady / companion（丢了小孩视角） | QC / Mushi bible | approved |
| 小手术 | a little operation, the kind dogs get | QC 的委婉语。英文同样委婉，让 Haide"听懂了"成立。 | getting him fixed（更地道但一说就懂，Haide 反应就不够戏剧）；neutering（直白，破坏笑点） | seven-day-bite.en.md，多个 bible | approved |
| 兔兔 | Bun-bun | 软软给兔子的昵称，需要叠字感。 | Bunny（普通）；Mr. Bunny（多了性别） | 软软 bible | approved |
| 呆毛 | cowlick | 英文没有"ahoge"这个通用词，cowlick 最接近。 | ahoge（动漫圈术语，一般读者不懂） | 多个 bible | approved |

### Lines and jokes

| 原文 | 译文 | 为什么 | 其他方案 | 出现位置 | 状态 |
|---|---|---|---|---|---|
| 匹夫无罪，怀璧其罪 | As they say: an innocent man, a guilty jade. | 原文是 Haide 掉书袋，牧师听不懂追问。英文保留一句听起来像古谚但英语读者也不懂的话，让"什么意思？"这一问成立。 | "Don't hate the player, hate the game"（读者懂了，牧师就不该问）；直接省略成语（丢了 Haide 装腔的笑点） | four-witches.en.md | approved |
| 我就问问价！ | I just want a quote! | Fufu 追着问"值多少钱"。"quote"在英文里既是报价也是引语，保住她一本正经的荒谬感。 | I just want to ask the price!（平） | four-witches.en.md | approved |
| 我 tm 撞死你！你 tm 才是狗！你下辈子当狗去吧！ | I'll f\*\*\*ing flatten you! YOU'RE the f\*\*\*ing dog! Come back as a dog next time! | 原文用"tm"缩写自我审查，英文用星号对应。"下辈子"改成"next time"更像卡车司机的吼法。 | 保留完整脏字（比原文更粗）；"in your next life"（准确但太文） | qc-nightmare.en.md | approved |
| 伪娘人设 | written so pretty that everyone takes him for a girl | 英文没有不冒犯的对应词，改用描述。 | "trap"（网络俚语，含贬义，弃）；"femboy"（同上） | qc-nightmare.en.md | approved |
| 我说过的。 | I told you. | Mimi 三个字，英文也要三个词。 | I said so.（弱）；Told you so.（太得意，Mimi 是平的） | haide-became-a-dog.en.md，Mimi bible | approved |
| 有我在。 | I've got you. | 比 "I'm here" 更像队长。 | I'm here.（牧师那句用了 "It's okay, I'm here."，两人区分开） | Mimi bible | approved |
| 这个嘛……不能白说哦。 | Well… this doesn't come free. | 牧师端架子的口头禅，要短，要能被 Haide 三秒盯垮。 | This information has a price（太长） | 牧师 bible，four-witches.en.md | approved |
| 别逼我骂你。 | Don't make me swear at you. | 直译即可。 | Don't push me.（丢了"骂"） | 陆姚 bible | approved |
| 靠 / 滚 / 你他妈 | "Damn", "get lost" and "you f—" | bible 明确列出脏话，英文降一档并截断，符合 skill"脏话暗示不拼写"的原则。 | 完整拼写（超出原文尺度） | 陆姚 bible | approved |
| 理论上可行，但需要极高的智商。 | Theoretically feasible. Requires an extremely high IQ. | 拆成两句，像点儿的笔记。 | 一句话版本（少了笔记感） | midnight-ferrari.en.md，点儿 / QC bible | approved |
| 处理方案 014：转交董事长。结果：失败。董事长不可靠。 | Case 014: escalated to the Chairman. Result: failed. Chairman unreliable. | 保持档案语气，末句无冠词像批注。 | | seven-day-bite.en.md，艾莎 bible | approved |
| 软软发呆时的眼神，不像在害怕，像在加速。 | When Ruanruan stares into space, she doesn't look scared. She looks like she's accelerating. | 两句，最后一个词落在 accelerating。 | | 艾莎 / 软软 bible | approved |
| 变回去还得穿裤子。 | （事件档案，未翻译） | 事件档案章节不在网页渲染，本次未翻。 | | Haide / 点儿 / Liiie / QC bible 的 Archive 章节 | 未翻 |
| peace and love | keep the peace and love | 原文就是英文，保留。 | | Mimi bible | approved |

### Deliberately not translated

- `## 事件档案（已迁移）` sections in Haide, Dianer, Liiie and QC bibles: not rendered by the site, and their content already lives in the stories. Translate on request.
