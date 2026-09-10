# 项目整体检测 · 第二轮（2026-09-09）

第一轮检测（[2026-09-09-project-review.md](2026-09-09-project-review.md)）提出的架构清晰度、代码质量、可维护性三组问题已全部整改并推送（`11142ed` / `ca34c94` / `59133a3`）。这一轮是整改后的复检，检测范围与上一轮相同，另加线上产物核对。

复检基线：`59133a3`，工作区干净。

## 先说结论

上一轮的整改全部生效，自动化门槛也确实在工作（`npm test` 26/26、`npm run verify` 63 页 0 错、`audit_en.py --dist` 通过、`skill_stubs.py` 同步）。

但这一轮查出一个**线上正在发生的显示 bug**：所有故事页的标题重复渲染两遍。它躲过了刚建好的 CI，原因不是 CI 写错了，而是 CI 校验的构建产物和真正上线的构建产物不是同一个。这是本轮最重要的发现，下面第 1 条和第 3 条是同一件事的两半。

## P0 · 线上 bug：故事页标题渲染两次

**现象**（线上实测，`curl https://qc-kindergarten.vercel.app/zh/stories/2026-09-08-four-witches/`）：

```html
<h1 data-astro-cid-fpwy6p6l>幼儿园四大魔女</h1>
<h1>幼儿园四大魔女</h1>
```

6 篇故事 × 中英双语 = 12 个页面全部如此。一个是页面模板从 frontmatter 渲染的标题，另一个是正文 markdown 里那行没被剥掉的 `# 标题`。

**根因**，`website/scripts/sync-content.mjs:128` 与 `:146`：

```js
const body = content.replace(/^\s*# .+\n/, '');
```

JavaScript 正则里 `.` 不匹配任何行终止符，而**行终止符包含 `\r`**。文件是 CRLF 时，`.+` 走到 `\r` 前就停下，接着要匹配 `\n` 却遇到 `\r`，整条正则失配，标题原样留在正文里。实测：

```
regex test     : false
body head      : "\r\n# 幼儿园四大魔女\r\n\r\n绘画教室，下午。…"
```

`git ls-files --eol` 显示 `stories/*.md` 全部 `i/lf w/crlf`——仓库里存 LF，Windows 工作区因 `core.autocrlf=true` 检出成 CRLF。仓库没有 `.gitattributes`，所以换行符完全取决于每台机器的 git 配置。

**为什么 CI 没抓到**：CI 在 Linux 上检出，工作区就是 LF，这条正则在那里工作正常，构建出来的页面是对的。见第 3 条。

同一文件里只有这两处正则对 CRLF 敏感。`parse.mjs` 的解析器全部走 `split(/\r?\n/)`，实测生成的两个 JSON 里 0 个字段含 `\r`，12 个角色的 tagline、口头禅、关系全部正常。

## P1 · 流水线正确性

### 2. 同步脚本只拷贝、不清理，残留文件会被打包上线

`copyIfNewer()` 把源图拷进 `src/assets/`，但从不删除源端已经消失的文件。现存证据：`src/assets/scenes/Kindergarden-Map.png`——9 月 9 日 `Kindergarden` 改名 `Kindergarten` 后，源目录只剩新拼写，生成目录里旧拼写还在。

它不是躺着不动，而是会被打包：`src/lib/content.ts:37` 用 `import.meta.glob('/src/assets/scenes/*.png', { eager: true })` 全量收集，Astro 于是把这个孤儿也优化成 3 个 webp 变体：

```
dist/_astro/Kindergarden-Map.BMnMzpon_4mkBg.webp     365 KB
dist/_astro/Kindergarden-Map.BMnMzpon_Z1STzf2.webp   249 KB
dist/_astro/Kindergarden-Map.BMnMzpon_Z13hV5v.webp   132 KB
```

合计 745 KB，跟着 prebuilt 部署上传到线上。今后每一次重命名或删除素材都会留下同样的残渣，而且 `eager: true` 保证残渣一定会被打包。

### 3. CI 校验的构建 ≠ 上线的构建

`website/README.md` 记录的部署方式是本地 prebuilt：

```
npx vercel build --prod --yes
npx vercel deploy --prebuilt --prod
```

即真正上线的 `dist/` 是在这台 Windows 机器上构建的。CI 在 ubuntu-latest 上构建，产物只用于校验、随后丢弃。两者的输入（换行符）不同，产物就不同——P0 正是从这个缝里漏到线上的：CI 全绿，线上有 bug，两者都不算撒谎。

这不是要求改掉 prebuilt（README 里已经写清楚为什么必须本地构建：同步脚本要读 `website/` 上一级的目录，仓库还带私有 submodule）。要补的是：让本地构建和 CI 构建的输入一致（`.gitattributes` 固定换行符），并且让上线前的检查跑在**将要上传的那份 dist** 上。

## P2 · 缺口

### 4. 页面没有任何分享元数据

`grep og:|twitter:|canonical` 在 `src/` 下为空。`Base.astro` 的 `<head>` 只有 charset、viewport、favicon、title、description、字体 preload 和一条 `hreflang`。

这一条之所以值得单列，是因为项目里有个 `discord-notify` skill，专门往 Discord 发新故事的网站链接——而这些链接在 Discord 里现在渲染不出任何卡片：没有标题、没有配图、没有摘要。素材是齐的：`astro.config.mjs` 已配 `site`，每个页面都已经在往 `Base` 传 `description`，故事页有封面图、角色页有立绘。

顺带：`hreflang` 只有指向另一语言的一条，没有自指，也没有 `x-default`。

### 5. 没有 sitemap.xml、没有 robots.txt

`site` 已配置，`@astrojs/sitemap` 是一行配置的事。63 个静态页目前只能靠外链被发现。

### 6. 没有 404 页

`src/pages/` 下只有 `[lang]/` 和 `index.astro`。静态站访问不存在的路径会落到 Vercel 的默认 404，跳出站点视觉。

### 7. `事件档案` 段落在网站上不渲染，且英文 bible 完全没有

四个中文 bible（Haide、Liiie、QC、点儿）有 `## 事件档案` 指针段，四个对应的英文 bible 都没有。网站上这个段落**渲染在任何地方都看不到**——`grep -rl 事件档案 dist/` 无结果：它既不在 `descriptionOrder` 里，`isExtra()` 也把它排除。故事在角色页上是通过 `stories.json` 生成的「记忆」区呈现的，不走 bible。

也就是说这个段落只服务于直接读 markdown 的人和 agent，这本身没问题。有问题的是这条约定**没有写在任何文档里**，唯一的执行处是 `tools/audit_en.py:129` 的一行 `if sec == '事件档案': continue`。中英不对称之所以不报错，全靠这一行。

## P3 · 卫生问题

### 8. 文档漂移，而且是同一处漂移的第四次

`website/README.md` 写着英文 bible 的标题要用「`scripts/sync-content.mjs` 里 `SECTION_ALIASES` 列出的英文名」。上一轮 `SECTION_ALIASES` 已经随解析函数搬到 `scripts/parse.mjs`——就是那次搬迁让 `audit_en.py` 报出 216 个假阳性。脚本修好了，README 没跟上。

同一份 README 还缺：`scripts/parse.mjs`、`scripts/parse.test.mjs`、`src/data/schema.ts`、`npm test`、`npm run verify`、`.github/workflows/ci.yml`——全是上一轮新加的东西。`AGENTS.md` 的目录清单也没有 `.github/`。

另有两处过期表述：`DESIGN.md:57` 仍写 `性格设定.en.md`「（待翻译）」，README 的「还没做」清单仍列着「英文翻译」，而 DESIGN.md 待办 6 已标记 2026-09-09 完成、`audit_en.py` 也确认覆盖完整。

### 9. `.faces` 连续声明两次

`website/src/pages/[lang]/characters/[slug].astro:385-391`，两条相邻的 `.faces {}` 规则，应合并为一条。

### 10. `state.json` 是提交进仓库的可变运行时状态

`.agents/skills/discord-notify/state.json` 由 `notify_discord.py` 写入，却放在 skill 的正本目录里，每次发通知都产生一次仓库 diff。它现在还记着上一轮已删除的插图版本（`四大魔女-v1` 到 `-v4`、`midnight-ferrari-p1-v1`）。跨机器保持「哪些已通知」确实需要持久化，所以这是个设计取舍而不是错误——但状态和 skill 定义混在一个目录里，值得挪开。

### 11. `KNOWLEDGE` 导出但只在本文件使用

`website/src/data/schema.ts:55`，只被同文件的 `z.enum(KNOWLEDGE)` 用到，可以不导出。

## 复检通过的部分

以下是本轮实测确认健康、无需处理的：

| 项 | 结果 |
|---|---|
| `npm test` | 26/26 通过，165 ms |
| `npm run verify` | sync → prettier → astro check → build 全绿，63 页，0 错 0 警告 |
| `python tools/audit_en.py --dist` | English coverage complete. |
| `python tools/skill_stubs.py` | skill stubs in sync (5 skills). |
| 密钥泄漏 | 追踪文件中 0 命中（OpenRouter / Anthropic / OpenAI / GitHub / AWS / Discord webhook 全部模式）；`.env` 未追踪，`.env.example` 只有占位符 |
| `content.ts` 导出 | 23 个导出全部有使用方，无死代码 |
| Python 脚本 | 6 个脚本全部 `py_compile` 通过；`except Exception` 共 6 处，全部是 stdin/stdout 编码兜底，均有注释 |
| CRLF 对解析器的影响 | 生成的两个 JSON 中 0 个字段含 `\r`；12 个 tagline、口头禅、关系全部正确 |
| CSS 分层 | `.avatar` / `.wrap` / `.plate` / `.chip` / `.prose` / `.crumbs` / `.notice` 均只在 `global.css` 定义一次，页面内只做局部覆盖 |
| 合照热区 | `composition.json` 12 个 layer，12 个都有 `spot`，与 12 人 cast 一一对应 |
| 仓库体积 | `size-pack` 295.43 MiB，与上一轮一致（上一轮删除 27.8 MB 不缩小历史，符合预期） |

## 建议的处理顺序

1. **P0 + 第 3 条一起修**：改掉两处正则（`/^\s*#[^\n]*\r?\n/` 或直接按行处理），同时加 `.gitattributes` 固定 `*.md` 的换行符，让本地和 CI 输入一致。修完重跑 sync 并核对 `dist` 里每页只剩一个 `<h1>`，再重新部署。
2. **第 2 条**：同步前清空（或对账清理）`src/assets/` 的生成目录，并删掉当前的 `Kindergarden-Map.png` 残留。
3. **第 4 条**：`Base.astro` 补 OG / Twitter / canonical，让 Discord 通知的链接能出卡片。这是投入产出比最高的一项。
4. **第 5、6 条**：sitemap + robots + 404 页。
5. **第 7、8 条**：把 `事件档案` 只存在于 markdown 这条约定写进 `stories/README.md` 或 `AGENTS.md`，并补完 README 的漂移。
6. **第 9、10、11 条**：随手清理。

---

# 整改执行记录（2026-09-09）

11 项全部处理完毕。下面按发现顺序记录实际做法与验证结果。

## P0 · 故事页标题重复

`stripLeadingH1()` 移进 `website/scripts/parse.mjs`，改成按行处理而不是一条正则：

```js
export function stripLeadingH1(content) {
  const lines = content.split(/\r?\n/);
  let i = 0;
  while (i < lines.length && lines[i].trim() === '') i++;
  if (i < lines.length && /^#\s+\S/.test(lines[i])) lines.splice(0, i + 1);
  return lines.join('\n');
}
```

用 `\n` 重新拼接顺带把正文的换行符归一了，所以生成的 JSON 和构建出的 HTML 在 CRLF 与 LF 检出下完全一致。`sync-content.mjs` 两处调用点都换成这个函数。

新增 5 个用例（LF、CRLF、换行归一、不该剥的三种情形、空正文），`parse.test.mjs` 从 26 增至 31，全部通过。CRLF 那条用例带注释写明它对应的就是这次线上 bug。

验证：`stories.json` 六篇故事的 `content` 与 `en.content` 中 0 个 `<h1>`；`dist/zh/stories/2026-09-08-four-witches/index.html` 只剩一个 `<h1>`；浏览器实测标题后直接进正文。

同时新增仓库根 `.gitattributes`：`* text=auto eol=lf` 加二进制类型清单。工作区 103 个文件转成 LF，`git diff` 对这 103 个文件显示 0 处改动——因为仓库里本来存的就是 LF，这次只是让工作区与之对齐。

## P1 · 流水线

**同步脚本加了 `prune()`**（`sync-content.mjs`）。`copyIfNewer()` 把每个应当存在的目标路径记进 `written` 集合，同步末尾遍历 `characters/`、`stories/`、`scenes/`、`group-photo.png` 这四个由脚本拥有的位置，删掉不在集合里的文件并清理空目录。范围限定在这四处，手工加进 `src/assets/` 其他地方的素材不会被误删。首次运行即报 `removed orphan src/assets/scenes/Kindergarden-Map.png`，dist 里那三个 webp 变体随之消失。

**新增 `website/scripts/check-build.mjs`**，接在 `npm run verify` 最后（`npm run check:build`），断言的是 dist 本身：每页恰好一个 `<h1>`、有 title / description / 绝对 canonical / og:title、`og:image` 是绝对地址且文件确实在 dist 里，以及 `sitemap.xml`、`robots.txt`、`404.html` 存在。根目录那个 meta-refresh 跳转页按内容识别后跳过。

这一条配合 `.gitattributes` 才算完整：`.gitattributes` 消掉本地与 CI 的输入差异，`check-build.mjs` 保证无论在哪台机器构建，上线前检查的都是即将上传的那份产物。README 的部署段落也补了「部署前先 `npm run verify`」和这条的来由。

## P2 · 缺口

- **分享卡**：`Base.astro` 新增 `image` / `imageAlt` 两个 prop，输出 canonical、三条 `hreflang`（自指 + 另一语言 + `x-default`）、完整 OG 与 Twitter card。卡图用 `getImage()` 生成 webp，宽度取 `min(1200, 源宽)` 不上采样，高度按源比例算而不是从返回值里读，保证两个尺寸互相一致。四类页面各自传图：首页合照、角色页立绘、故事页封面或第一张分镜、地点页场景图。实测故事页产出 `og:image` 1200×675 绝对地址。
- **sitemap / robots**：`src/pages/sitemap.xml.ts` 与 `robots.txt.ts` 两个端点，不引 `@astrojs/sitemap`——页面清单本来就在 `content.ts` 里，理由同 `schema.ts` 用 `astro/zod`。62 条 URL，每条带 `xhtml:link` 语言对。域名取 `astro.config.mjs` 的 `site`，换域名只改一处。
- **404**：`src/pages/404.astro`，中英并列（这一页在 `/[lang]/` 之外，语言无从判断，与其猜不如都给）。`i18n.ts` 加 `notFound` / `notFoundBody` 两个键，`Dict` 类型强制两边都补。宽屏下第一版两栏被 `.wrap` 撑到屏幕两端、读起来不像一段话，加了 `max-width: 46rem` 居中。
- **`事件档案` 约定**：写进 `stories/README.md` 一个小节，说明它只服务于读 markdown 的人与 agent、网站上不渲染、因此英文 bible 不需要、以及这是中英章节数可以不等的唯一合法原因。`tools/audit_en.py` 那行 `continue` 上方也加了注释指回文档。

## P3 · 卫生

- `website/README.md`：`SECTION_ALIASES` 的位置改成 `parse.mjs`；补上 `npm test` / `npm run verify` / `check:build`、`parse.mjs` / `parse.test.mjs` / `schema.ts` 的分工、同步末尾的清理行为、新增的四个页面与分享卡；「还没做」里删掉已完成的英文翻译。
- `website/DESIGN.md`：英文 bible 的「（待翻译）」改成已齐全。
- `AGENTS.md`：目录补 `.github/` 与 `.agents/state/`，并写明 CI 构建的 dist 只用于校验。
- `characters/[slug].astro`：两条相邻的 `.faces` 合并。
- `state.json` 移到 `.agents/state/discord-notify.json`，脚本与 SKILL.md 同步更新，`save_state()` 增加目录创建与「文件已不存在的插图键自动清理」。清理后条目 21 → 14，正好是上一轮删掉的 7 个。`--dry-run` 从新位置读写正常。
- `schema.ts` 的 `KNOWLEDGE` 取消导出。

## 验证

| 检查 | 结果 |
|---|---|
| `npm test` | 31/31 通过 |
| `npm run verify` | astro check 0 错 0 警告；64 页构建；`[check-build] 64 pages OK` |
| `python tools/audit_en.py --dist` | English coverage complete. |
| `python tools/skill_stubs.py` | skill stubs in sync (5 skills). |
| 浏览器实测 | 故事页标题一次、404 中英双栏、角色页英文版正常 |

## 一处未处理的既有告警

构建时有一条 `Could not render `` from route `/` as it conflicts with higher priority route `/``。移走本次新增的三个页面后重新构建，告警依旧存在——它来自 `src/pages/index.astro` 与 Astro i18n 的 `redirectToDefaultLocale` 都想生成 `/`，不是这次改动引入的。`dist/index.html` 正常产出跳转页，功能无碍，所以没有动它。要消掉的话就是删掉 `index.astro` 交给 i18n 路由，但那会改变根路径的行为，留给单独决定。
