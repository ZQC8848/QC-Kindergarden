# QC taste profile

Since 2026-09-10 the profile is split by domain and kept in two languages. Rule text and numbers did not change.
自 2026-09-10 起，这份偏好按领域拆分，并维护中英两个版本。规则内容和编号没有改动。

| Domain / 领域 | English | 中文 |
|---|---|---|
| Shared, read with every domain / 共通，每个领域都一起读 | [taste/_shared.en.md](taste/_shared.en.md) | [taste/_shared.zh.md](taste/_shared.zh.md) |
| Story creation / 故事创作 | [taste/story.en.md](taste/story.en.md) | [taste/story.zh.md](taste/story.zh.md) |
| Image generation / 图片生成 | [taste/image.en.md](taste/image.en.md) | [taste/image.zh.md](taste/image.zh.md) |
| Storyboards / 分镜头 | [taste/storyboard.en.md](taste/storyboard.en.md) | [taste/storyboard.zh.md](taste/storyboard.zh.md) |
| Video generation / 视频生成 | [taste/video.en.md](taste/video.en.md) | [taste/video.zh.md](taste/video.zh.md) |

Read the shared part plus the domain you are working in.
使用时读共通部分，加上当前领域的文件。

Both languages must say the same thing. Check with `python tools/taste_sync.py`; after bringing a pair in line, run `python tools/taste_sync.py stamp <part>`.
中英两版必须一致。用 `python tools/taste_sync.py` 检查；改好一对之后运行 `python tools/taste_sync.py stamp <part>`。
