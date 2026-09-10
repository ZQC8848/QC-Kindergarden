#!/usr/bin/env python3
"""Announce new stories and illustrations to Discord through a webhook.

Run from anywhere inside the repository:

  python .agents/skills/discord-notify/scripts/notify_discord.py --dry-run
  python .agents/skills/discord-notify/scripts/notify_discord.py --teaser <slug>="一句不剧透的话"
  python .agents/skills/discord-notify/scripts/notify_discord.py --force <slug>
  python .agents/skills/discord-notify/scripts/notify_discord.py --init      # record current content, post nothing

What counts as new is decided against state.json next to this skill. See SKILL.md for the rules.
Webhook URL: DISCORD_WEBHOOK_URL in the environment, the repository-root .env, or ResearchAssets/config/notify.env (private submodule).
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')

SKILL_DIR = Path(__file__).resolve().parents[1]
ROOT = SKILL_DIR.parents[2]
STORIES = ROOT / 'stories'
ASSETS = STORIES / 'assets'
CONFIG = ROOT / 'website' / 'src' / 'data' / 'characters.config.mjs'
STATE = SKILL_DIR / 'state.json'
DEFAULT_SITE = 'https://qc-kindergarten.vercel.app'

COLOR = {'memory': 0x2C4A88, 'extra': 0xD39A34}
KIND_LABEL = {'memory': '记忆事件', 'extra': '番外剧场'}
MAX_TEASER = 60


# ---------------------------------------------------------------- config / names
def load_config():
    """Read character and scene names straight from characters.config.mjs (regex, no JS runtime)."""
    text = CONFIG.read_text(encoding='utf-8')
    chars = {}
    for m in re.finditer(r"\{\s*slug:\s*'([^']+)',\s*folder:\s*'([^']+)'.*?en:\s*\{\s*name:\s*'([^']+)'", text, re.S):
        slug, folder, en = m.group(1), m.group(2), m.group(3)
        chars[slug] = {'zh': folder.split('-')[0], 'en': en}
    scenes = {}
    for m in re.finditer(r"\{\s*file:\s*'([^']+)',\s*slug:\s*'([^']+)',\s*zh:\s*'([^']+)',\s*en:\s*'([^']+)'", text):
        scenes[m.group(1)] = {'slug': m.group(2), 'zh': m.group(3), 'en': m.group(4)}
    lookup = {}
    for slug, n in chars.items():
        for key in (slug, n['zh'], n['zh'].lower(), n['en'], n['en'].lower()):
            lookup[key] = slug
    return chars, scenes, lookup


def resolve_cast(raw, lookup):
    out = []
    for item in raw:
        s = lookup.get(item) or lookup.get(item.lower())
        if s and s not in out:
            out.append(s)
    return out


# ---------------------------------------------------------------- stories
def frontmatter(md):
    """Minimal YAML subset: scalars, [a, b] lists, and a `memories:` block whose children are counted."""
    m = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n?(.*)$', md, re.S)
    if not m:
        return {}, md
    data, body = {}, m.group(2)
    block = m.group(1)
    in_mem = False
    mem_count = 0
    for line in block.splitlines():
        if not line.strip():
            continue
        if not line.startswith(' '):
            in_mem = False
            key, _, val = line.partition(':')
            key, val = key.strip(), val.strip()
            if key == 'memories':
                in_mem = True
                continue
            if val.startswith('[') and val.endswith(']'):
                data[key] = [v.strip().strip('"\'') for v in val[1:-1].split(',') if v.strip()]
            else:
                data[key] = val.strip('"\'')
        elif in_mem and re.match(r'^  \S', line):
            mem_count += 1
    data['_memories'] = mem_count
    return data, body


def first_sentence(body):
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    for line in body.splitlines():
        t = line.strip()
        if not t or t.startswith('#') or t.startswith('---') or t.startswith('**'):
            continue
        # cut at the first sentence end
        m = re.search(r'[。！？!?]', t)
        s = t[: m.end()] if m else t
        return s if len(s) <= MAX_TEASER else s[: MAX_TEASER - 1] + '…'
    return ''


def load_stories():
    stories = {}
    for f in sorted(STORIES.glob('*.md')):
        if f.name == 'README.md' or f.name.endswith('.en.md'):
            continue
        data, body = frontmatter(f.read_text(encoding='utf-8'))
        loc = data.get('location') or []
        if isinstance(loc, str):
            loc = [loc] if loc else []
        en = f.with_name(f.stem + '.en.md')
        en_title = None
        if en.exists():
            en_data, _ = frontmatter(en.read_text(encoding='utf-8'))
            en_title = en_data.get('title')
        stories[f.stem] = {
            'slug': f.stem,
            'title': data.get('title') or f.stem,
            'kind': 'extra' if data.get('type') == 'extra' else 'memory',
            'cast': data.get('cast') or [],
            'locations': loc,
            'memories': data.get('_memories', 0),
            'teaser': data.get('teaser') or first_sentence(body),
            'en_title': en_title,
        }
    return stories


def load_illustrations():
    """{stem: [ {panel, version, path} ]}; panel 0 is the cover. -4k files are ignored."""
    found = {}
    if not ASSETS.exists():
        return found
    for f in sorted(ASSETS.glob('*.png')):
        m = re.match(r'^(.+?)-p(\d+)-v(\d+)\.png$', f.name)
        if m:
            found.setdefault(m.group(1), []).append({'panel': int(m.group(2)), 'version': int(m.group(3)), 'path': f})
            continue
        m = re.match(r'^(.+?)-v(\d+)\.png$', f.name)
        if m:
            found.setdefault(m.group(1), []).append({'panel': 0, 'version': int(m.group(2)), 'path': f})
    return found


def illustration_key(stem, item):
    return f"{stem}-p{item['panel']}-v{item['version']}" if item['panel'] else f"{stem}-v{item['version']}"


# ---------------------------------------------------------------- state
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding='utf-8'))
    return {'stories': {}, 'illustrations': {}}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


# ---------------------------------------------------------------- webhook
def webhook_url():
    """Environment first, then repo-root .env (gitignored), then the private submodule's config."""
    url = os.environ.get('DISCORD_WEBHOOK_URL')
    if url:
        return url
    for env in (ROOT / '.env', ROOT / 'ResearchAssets' / 'config' / 'notify.env'):
        if env.exists():
            for line in env.read_text(encoding='utf-8').splitlines():
                k, _, v = line.partition('=')
                if k.strip() == 'DISCORD_WEBHOOK_URL':
                    return v.strip().strip('"' + "'")
    return None


def post(url, payload, image=None):
    """Send one embed; attach `image` (Path) as the embed image when given. Retries once on 429."""
    for attempt in range(3):
        if image:
            with open(image, 'rb') as fh:
                r = requests.post(url, data={'payload_json': json.dumps(payload, ensure_ascii=False)},
                                  files={'files[0]': (image.name, fh, 'image/png')}, timeout=60)
        else:
            r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 429:
            wait = float(r.headers.get('Retry-After', '2'))
            time.sleep(wait + 0.5)
            continue
        if r.status_code >= 300:
            raise RuntimeError(f'Discord returned {r.status_code}: {r.text[:300]}')
        return r
    raise RuntimeError('Discord kept rate-limiting the request')


# ---------------------------------------------------------------- message
def build_message(story, new_story, new_illus, all_illus, chars, scenes, site, image_choice, no_image):
    slug = story['slug']
    cast = [chars[s]['zh'] for s in story['cast'] if s in chars]
    places = [scenes[l]['zh'] for l in story['locations'] if l in scenes]
    zh_url = f"{site}/zh/stories/{slug}/"
    en_url = f"{site}/en/stories/{slug}/"

    if new_story and new_illus:
        head = f"📖 新故事：{story['title']}"
    elif new_story:
        head = f"📖 新故事：{story['title']}"
    else:
        head = f"🖼️ 插图更新：{story['title']}"

    lines = []
    if new_story:
        lines.append(story['teaser'])
    if new_illus:
        panels = [i for i in new_illus if i['panel']]
        covers = [i for i in new_illus if not i['panel']]
        first_time = [i for i in panels if not any(o['panel'] == i['panel'] and o['version'] < i['version'] for o in all_illus)]
        redone = [i for i in panels if i not in first_time]
        bits = []
        if first_time:
            bits.append(f"新增 {len(first_time)} 张插图")
        for i in redone:
            bits.append(f"第 {i['panel']} 张插图更新到 v{i['version']}")
        if covers:
            bits.append('封面更新' if any(o['panel'] == 0 and o['version'] < covers[0]['version'] for o in all_illus) else '新增封面')
        lines.append('，'.join(bits) + '。')
    meta = []
    if cast:
        meta.append('出场  ' + ' · '.join(cast))
    if places:
        meta.append('地点  ' + ' · '.join(places))
    kind = KIND_LABEL[story['kind']]
    if story['kind'] == 'memory' and story['memories']:
        kind += f" · {story['memories']} 个记忆视角"
    meta.append(kind)
    lines.append('')
    lines.extend(meta)
    lines.append('')
    lines.append(f"🔗 {zh_url}")
    if story['en_title']:
        lines.append(f"English: {en_url}")

    embed = {
        'title': head,
        'url': zh_url,
        'description': '\n'.join(lines),
        'color': COLOR[story['kind']],
    }

    image = None
    if new_illus and not no_image:
        candidates = sorted([i for i in new_illus if i['panel']], key=lambda i: (i['panel'], -i['version']))
        if image_choice is not None:
            candidates = [i for i in candidates if i['panel'] == image_choice] or candidates
        if candidates:
            image = candidates[0]['path']
            embed['image'] = {'url': f"attachment://{image.name}"}
    return {'embeds': [embed]}, image


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true', help='print messages, post nothing, keep state unchanged')
    ap.add_argument('--init', action='store_true', help='mark everything in the repo as announced without posting')
    ap.add_argument('--force', action='append', default=[], metavar='SLUG', help='announce this story again even if recorded')
    ap.add_argument('--teaser', action='append', default=[], metavar='SLUG=TEXT', help='spoiler-free one-liner for a story')
    ap.add_argument('--image', action='append', default=[], metavar='SLUG=PANEL', help='which panel to attach for a story')
    ap.add_argument('--no-image', action='store_true', help='attach no images')
    ap.add_argument('--site', default=DEFAULT_SITE, help='live site base URL')
    ap.add_argument('--test', action='store_true', help='send a connection test message; state unchanged')
    args = ap.parse_args()

    if args.test:
        url = webhook_url()
        if not url:
            print('DISCORD_WEBHOOK_URL not set (environment or repo-root .env)', file=sys.stderr)
            return 2
        payload = {'embeds': [{
            'title': '🔔 QC Kindergarten 通知已接通',
            'url': f'{args.site}/zh/',
            'description': '以后有新故事或新插图，会在这里收到一条不剧透的更新提醒。' + chr(10) * 2 + '🔗 ' + f'{args.site}/zh/',
            'color': COLOR['memory'],
        }]}
        post(url, payload)
        print('test message posted')
        return 0

    chars, scenes, lookup = load_config()
    stories = load_stories()
    for st in stories.values():
        st['cast'] = resolve_cast(st['cast'], lookup)
    illus = load_illustrations()
    state = load_state()

    teasers = {}
    for t in args.teaser:
        k, _, v = t.partition('=')
        teasers[k.strip()] = v.strip().strip('"\'')
    image_choice = {}
    for t in args.image:
        k, _, v = t.partition('=')
        image_choice[k.strip()] = int(v)

    if args.init:
        for slug in stories:
            state['stories'].setdefault(slug, {'announced': now(), 'note': 'baseline'})
        for stem, items in illus.items():
            for it in items:
                state['illustrations'].setdefault(illustration_key(stem, it), now())
        save_state(state)
        print(f"baseline recorded: {len(state['stories'])} stories, {len(state['illustrations'])} illustration files")
        return 0

    # what is new
    jobs = []
    for slug, st in stories.items():
        new_story = slug not in state['stories'] or slug in args.force
        new_illus = [it for it in illus.get(slug, []) if illustration_key(slug, it) not in state['illustrations'] or slug in args.force]
        if new_story or new_illus:
            if slug in teasers:
                st['teaser'] = teasers[slug]
            jobs.append((st, new_story, new_illus))
    # illustrations whose story file does not exist yet are skipped with a note
    for stem in illus:
        if stem not in stories:
            print(f"note: assets for '{stem}' have no stories/{stem}.md; skipped")

    if not jobs:
        print('nothing new to announce')
        return 0

    url = None if args.dry_run else webhook_url()
    if not args.dry_run and not url:
        print('DISCORD_WEBHOOK_URL not set (environment or repo-root .env)', file=sys.stderr)
        return 2
    if not args.dry_run and requests is None:
        print('python package `requests` is required to post', file=sys.stderr)
        return 2

    for st, new_story, new_illus in jobs:
        payload, image = build_message(st, new_story, new_illus, illus.get(st['slug'], []), chars, scenes,
                                       args.site, image_choice.get(st['slug']), args.no_image)
        if new_story and len(st['teaser']) > MAX_TEASER:
            print(f"warning: teaser for {st['slug']} is longer than {MAX_TEASER} characters")
        print('=' * 60)
        print(payload['embeds'][0]['title'])
        print(payload['embeds'][0]['description'])
        print(f"[image: {image.name if image else 'none'}]")
        if args.dry_run:
            continue
        post(url, payload, image)
        state['stories'][st['slug']] = {'announced': now()}
        for it in new_illus:
            state['illustrations'][illustration_key(st['slug'], it)] = now()
        save_state(state)
        print('posted')
        time.sleep(1.2)
    if args.dry_run:
        print('=' * 60)
        print(f'dry run: {len(jobs)} message(s) would be sent; state unchanged')
    return 0


if __name__ == '__main__':
    sys.exit(main())
