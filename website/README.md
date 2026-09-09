# website

QC Kindergarten 的项目网站。Astro 静态站，中英双语，部署在 Vercel。设计定案见 [DESIGN.md](DESIGN.md)，合照构思见 [GROUP-PHOTO.md](GROUP-PHOTO.md)。

## 跑起来

```bash
cd website
npm install
npm run dev      # 先同步内容，再起 dev server（http://localhost:4321/zh/）
npm run build    # 输出到 dist/
```

## 内容从哪来

网站不手抄任何角色资料。`scripts/sync-content.mjs` 在每次 dev / build 前运行，从仓库根目录读取：

| 来源 | 生成 |
|---|---|
| `character reference/<角色>/性格设定.md` | `src/data/characters.json`（按 `## ` 标题切块，转成 HTML） |
| `character reference/<角色>/*.png`（立绘、表情表、三视图最新版） | `src/assets/characters/<slug>/` |
| `stories/*.md` + `stories/assets/<故事>-vN.png`（封面）+ `<故事>-pN-vN.png`（分镜插图） | `src/data/stories.json` + `src/assets/stories/` |
| `Scene Reference/*.png` | `src/assets/scenes/` |
| `website/group-photo/group-photo-final-v1.png` + `composition.json` | 首页合照与热区坐标 |

生成的 JSON 和拷贝的图片都在 `.gitignore` 里，不进仓库。改了 bible 或故事，重跑 `npm run sync` 或重启 dev 即可。

故事封面和每个分镜编号都会自动选择最高版本号。没有独立封面的故事会用第一幅分镜插图作为列表缩略图与详情页头图，其余插图按分镜编号显示在正文之后。

角色的 slug、强调色、悬停表情格、英文名在 `src/data/characters.config.mjs`。加新角色只需要在那里加一行。

## 页面

- `/zh/` `/en/`：首页四层（合照热区、角色卡、分为记忆事件与番外剧场的故事集、环境）
- `/zh/characters/<slug>/`：角色页（立绘、口头禅、三视图折叠、补充设定、主观记忆、出演番外、关系）
- `/zh/stories/<slug>/`：故事页；记忆事件附带多人物视角，番外明确标注不进入记忆
- 根路径跳 `/zh/`。英文页缺翻译时显示中文并标注

英文 bible 放在 `character reference/<角色>/性格设定.en.md`，标题结构与中文一致，有了会自动被用上。

## 部署

Vercel 项目的 Root Directory 设为 `website`，Framework Preset 选 Astro，其余默认。

## 还没做的（对应 DESIGN.md 待办）

- 关系图（现在是列表 + 头像）
- 3D 槽位（现在折叠里放三视图）
- 合照分层视差（现在是整图 + 热区）
- 环境全景热区（现在是房间横滑 + 平面图）
- 英文翻译
