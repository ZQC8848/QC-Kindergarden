# website

QC Kindergarten 的项目网站。Astro 静态站，中英双语，部署在 Vercel。设计定案见 [DESIGN.md](DESIGN.md)，合照构思见 [GROUP-PHOTO.md](GROUP-PHOTO.md)。

## 跑起来

```bash
cd website
npm install
npm run dev      # 先同步内容，再起 dev server（http://localhost:4321/zh/）
npm run build    # 输出到 dist/
npm test         # 解析器单元测试（scripts/parse.test.mjs）
npm run verify   # sync → prettier → astro check → build → check:build，提交和部署前跑这个
```

`npm run verify` 的最后一步 `scripts/check-build.mjs` 检查的是 **dist 本身**：每页恰好一个 `<h1>`、有 title / description / canonical / og:title、`og:image` 是绝对地址且文件真的在 dist 里，以及 `sitemap.xml`、`robots.txt`、`404.html` 都在。因为部署走的是本地 prebuilt（见下），上线的 dist 是在本机构建的，而 CI 构建的是另一份——校验产物本身才管用。

## 内容从哪来

网站不手抄任何角色资料。`scripts/sync-content.mjs` 在每次 dev / build 前运行，从仓库根目录读取：

| 来源 | 生成 |
|---|---|
| `character reference/<角色>/性格设定.md` | `src/data/characters.json`（按 `## ` 标题切块，转成 HTML） |
| `character reference/<角色>/*.png`（立绘、表情表、三视图最新版） | `src/assets/characters/<slug>/` |
| `stories/*.md` + `stories/assets/<故事>-vN.png`（封面）+ `<故事>-pN-vN.png`（分镜插图） | `src/data/stories.json` + `src/assets/stories/` |
| `Scene Reference/*.png` | `src/assets/scenes/` |
| `website/group-photo/group-photo-final-v1.png` + `composition.json` | 首页合照与热区坐标 |

生成的 JSON 和拷贝的图片都在 `.gitignore` 里，不进仓库。改了 bible 或故事，重跑 `npm run sync` 或重启 dev 即可。同步结束会清理 `src/assets/` 下源文件已经不存在的图片：`src/lib/content.ts` 用 `import.meta.glob(..., { eager: true })` 全量收集，残留文件会被 Astro 优化并打包上线。

脚本自身分成三块：`scripts/sync-content.mjs` 只做文件读写与拷贝，纯解析函数在 `scripts/parse.mjs`（由 `scripts/parse.test.mjs` 覆盖），生成的两个 JSON 在写盘前用 `src/data/schema.ts` 的 zod schema 校验，不合格直接中断构建。`src/lib/content.ts` 的类型就是从这份 schema 推导的。

故事封面和每个分镜编号都会自动选择最高版本号。没有独立封面的故事会用第一幅分镜插图作为列表缩略图；故事正文通过 `<!-- illustration:N|插图标题 -->` 标记控制插图位置，并将标题显示在图片下方。

角色的 slug、强调色、悬停表情格、英文名在 `src/data/characters.config.mjs`。加新角色只需要在那里加一行。

## 页面

- `/zh/` `/en/`：首页四层（合照热区、角色卡、分为记忆事件与番外剧场的故事集、环境）
- `/zh/characters/<slug>/`：角色页（立绘、口头禅、三视图折叠、补充设定、主观记忆、出演番外、关系）
- `/zh/stories/<slug>/`：故事页；记忆事件附带多人物视角，番外明确标注不进入记忆
- `/zh/places/<slug>/`：地点页；每个场景一页，列出在这里发生过的故事
- 根路径跳 `/zh/`。英文页缺翻译时显示中文并标注
- `/404.html`：中英双语，站外链接失效时不掉出站点视觉
- `/sitemap.xml`、`/robots.txt`：由 `src/pages/` 下的两个端点生成，域名取 `astro.config.mjs` 的 `site`，换域名只改一处

每个页面都带 canonical、`hreflang`（自指 + 另一语言 + `x-default`）和 OG / Twitter 分享卡。卡图由 `Base.astro` 的 `image` prop 决定：首页用合照，角色页用立绘，故事页用封面或第一张分镜，地点页用场景图。`discord-notify` 往群里发的链接靠这些标签才能展开成卡片。

英文 bible 放在 `character reference/<角色>/性格设定.en.md`，章节结构与中文一致、标题用 `scripts/parse.mjs` 里 `SECTION_ALIASES` 列出的英文名（`tools/audit_en.py` 直接读这张表）；故事的英文版放在 `stories/<故事>.en.md`，frontmatter 只需 `title`、`framing`、`memories`，正文保留插图标记。两者有了会自动被用上，缺失时英文页回退显示中文并标注。翻译工作流见 `.agents/skills/translate-en/`。

## 部署

线上地址 https://qc-kindergarten.vercel.app ，Vercel 项目 `zqc8848s-projects/qc-kindergarten`。

不用 Git 集成，用本地构建再上传（prebuilt）：同步脚本要读 `website/` 上一级的角色、故事和场景文件，Vercel 只上传 Root Directory 的话读不到；仓库还带私有 submodule，云端克隆会出问题。

代价是**上线的 dist 是在本机构建的，CI 构建的那份只用于校验**。两者一旦输入不同就会分叉：仓库根的 `.gitattributes` 把换行符统一成 LF 就是为了消掉这个差异（曾经 Windows 检出成 CRLF，一个解析器 bug 让所有故事页的标题渲染了两遍，CI 在 Linux 上完全看不到）。所以**部署前先 `npm run verify`**，它最后会检查即将上传的这份 dist。流程：

```bash
cd website
npx vercel login                                   # 第一次
npx vercel link --yes --project qc-kindergarten    # 第一次，生成 .vercel/（已 gitignore）
npx vercel pull --yes --environment production
npx vercel build --prod --yes
npx vercel deploy --prebuilt --prod
```

`vercel build` 会在本地重新跑 `npm install`。如果用户级 `~/.npmrc` 里有 `allow-scripts=…`，npm 11 会报 `EALLOWSCRIPTS`；构建时让 npm 忽略用户级配置即可：`npm_config_userconfig=<空文件路径> npx vercel build --prod --yes`（PowerShell：`$env:npm_config_userconfig="<空文件路径>"`）。

## 还没做的（对应 DESIGN.md 待办）

- 关系图（现在是列表 + 头像）
- 3D 槽位（现在折叠里放三视图）
- 合照分层视差（现在是整图 + 热区）
- 环境全景热区（现在是房间横滑 + 平面图）
