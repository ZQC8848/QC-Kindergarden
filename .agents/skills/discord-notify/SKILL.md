---
name: discord-notify
description: Announce new QC Kindergarten stories and new or updated story illustrations to a Discord channel through a webhook, with a link to the updated page on the live site and a short spoiler-free teaser. Use when a story or illustration has just been added, when the user asks to notify the group / Discord / 群友, or to check what has not been announced yet. Never post before the content is on the live site.
---

# Discord notify

Tell the group that something new is up, make them click, and don't tell them what happens.

## What gets announced

| Change | Detected by | Message |
|---|---|---|
| New story | a `stories/<slug>.md` whose slug is not in the state file | "📖 新故事" with title, teaser, cast, place, link |
| New illustration | a `stories/assets/<slug>-p<N>-v<M>.png` (or cover `<slug>-v<M>.png`) not in the state file | "🖼️ 插图更新" with the count and one attached image |
| Both at once | story and its images land together | one message combining the two |

One message per story. `-4k` files are ignored (same picture, larger). English twins (`.en.md`) do not trigger anything; the message links both languages when the English page exists.

## Workflow

1. **Deploy first.** The message links `https://qc-kindergarten.vercel.app`. If the new content is not live yet, deploy (see `website/README.md` → 部署) and confirm the story URL returns 200 before posting.
2. **See what is pending.**
   ```bash
   python .agents/skills/discord-notify/scripts/notify_discord.py --dry-run
   ```
   Prints the messages it would send and the files it would attach. Nothing is posted.
3. **Write the teaser yourself** for every new story. Pass it with `--teaser <slug>="…"`. The script's fallback (first sentence of the story) is acceptable for setups, but a written teaser is better. Rules below.
4. **Decide the image.** The script attaches the lowest-numbered new panel. If that panel gives away the ending (a reveal, a punchline shot), pass `--no-image` or `--image <slug>=<panel>` to pick a safer one.
5. **Post.**
   ```bash
   python .agents/skills/discord-notify/scripts/notify_discord.py --teaser 2026-09-10-new-story="一句不剧透的话"
   ```
   The script records what it announced in `.agents/state/discord-notify.json`; commit that file with the story so nobody double-posts.
6. **Report** to the user what was sent (title, teaser, which image) and paste the message link if Discord returned one.

Re-announce something on purpose with `--force <slug>` (for example after a big illustration redo). Record the current repository as "already announced" without posting with `--init` (used once, when the skill was set up).

## Teaser rules (不剧透)

- One sentence, at most 60 Chinese characters. It sets up the situation; it never states the reversal, the reveal, or the last line.
- Name who is involved and where, not what they did about it. "QC 收到了一张他没开过的车的罚单" is fine. "Haide 会开法拉利" is not.
- Never quote a punchline, an illustration caption, or a memory title; those are written to be read after the story.
- For a side story (番外), say it is one; people should know it does not count.
- Illustration updates get no plot text at all, only "新增 N 张插图" or "第 N 张插图更新到 v2".
- Tone matches the site: short, dry, affectionate. No exclamation marks unless a character would use one.

## Message layout

Discord embed, colour by kind (memory events blue, side stories gold):

```
📖 新故事：午夜的金色法拉利
QC 偶尔会收到凌晨两三点的超速罚单。车牌是他的，人不在车上。
出场  QC · Haide · 点儿
地点  午夜高速
记忆事件 · 3 个记忆视角
🔗 https://qc-kindergarten.vercel.app/zh/stories/2026-09-09-midnight-ferrari/
English: https://qc-kindergarten.vercel.app/en/stories/2026-09-09-midnight-ferrari/
[attached: first new panel]
```

## Configuration

- Webhook: `DISCORD_WEBHOOK_URL`, looked up in this order: environment variable → repository-root `.env` (gitignored) → `ResearchAssets/config/notify.env` (the private submodule, committed there). The main repository is public, so the URL must never be committed to it. Create it in Discord: channel settings → Integrations → Webhooks → New Webhook → Copy URL.
- Site base URL: `--site` flag, default `https://qc-kindergarten.vercel.app`.
- Names and place labels come from `website/src/data/characters.config.mjs`; the script reads that file directly so it never drifts from the site.
- State: `.agents/state/discord-notify.json`, committed. It lives outside the skill folder because the skill is a definition and the state changes on every announcement.

## Files

- `scripts/notify_discord.py` — detection, message building, posting; Python 3 plus `requests`.
- `.agents/state/discord-notify.json` — what has been announced, keyed by story slug and illustration file stem (outside this folder).
