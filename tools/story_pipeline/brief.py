#!/usr/bin/env python3
"""Build the story brief: one self-contained text block sent, byte for byte, to all
four models.

Why self-contained matters more than it looks: Claude Code and Codex load AGENTS.md
from whatever directory they run in, while Kimi and DeepSeek only ever see the text
posted to them. If the CLIs run inside the repo they silently receive far more context
than the HTTP models, and every per-model number afterwards is measuring "who saw more"
instead of "who writes better". So the brief carries everything, the CLIs run in a
scratch directory, and run_round.py records the brief's sha256 so the claim that all
four got the same input can be checked afterwards.

Run standalone to inspect what the models will get:

    python tools/story_pipeline/brief.py            # with the taste profile
    python tools/story_pipeline/brief.py --no-taste # ablation arm
    python tools/story_pipeline/brief.py --combos   # show this round's assignment
"""
from __future__ import annotations

import argparse
import hashlib
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHARS = ROOT / 'character reference'
GUESTS = CHARS / '_guests'
STORIES = ROOT / 'stories'
CONFIG = ROOT / 'website' / 'src' / 'data' / 'characters.config.mjs'
TASTE = ROOT / '.agents' / 'skills' / 'qc-taste' / 'references' / 'taste-profile.md'


# --------------------------------------------------------------------------- sources

@dataclass
class Character:
    slug: str
    folder: str
    name: str
    mbti: str
    tagline: str
    contradictions: list[str]
    phrases: list[str]
    prop: str
    relations: list[str]


@dataclass
class Scene:
    file: str
    zh: str
    en: str


def _config_text() -> str:
    if not CONFIG.exists():
        sys.exit(f'[brief] not found: {CONFIG.relative_to(ROOT)}')
    return CONFIG.read_text(encoding='utf-8')


def load_roster() -> list[tuple[str, str]]:
    """(slug, folder) for the 12 main characters, read from characters.config.mjs."""
    text = _config_text()
    block = re.search(r'export const characters = \[(.*?)\n\];', text, re.S)
    if not block:
        sys.exit('[brief] could not find `export const characters` in characters.config.mjs')
    pairs = re.findall(r"slug:\s*'([^']+)',\s*\n?\s*folder:\s*'([^']+)'", block.group(1))
    if not pairs:
        sys.exit('[brief] characters.config.mjs parsed but no slug/folder pairs found; the parser needs updating')
    return pairs


def load_scenes() -> list[Scene]:
    """Scene files with a place page. The floor plan is not a location a story happens in."""
    text = _config_text()
    block = re.search(r'export const scenes = \[(.*?)\n\];', text, re.S)
    if not block:
        sys.exit('[brief] could not find `export const scenes` in characters.config.mjs')
    rows = re.findall(r"file:\s*'([^']+)',\s*slug:\s*'([^']+)',\s*zh:\s*'([^']+)',\s*en:\s*'([^']+)'", block.group(1))
    if not rows:
        sys.exit('[brief] scenes block parsed but no rows found; the parser needs updating')
    return [Scene(f, zh, en) for f, slug, zh, en in rows if slug != 'map']


def _section(md: str, title: str) -> str:
    m = re.search(rf'^## {re.escape(title)}\s*$(.*?)(?=^## |\Z)', md, re.S | re.M)
    return m.group(1).strip() if m else ''


def parse_character(slug: str, folder: str) -> Character:
    path = CHARS / folder / '性格设定.md'
    md = path.read_text(encoding='utf-8')

    basic = dict(re.findall(r'^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$', _section(md, '基本信息'), re.M))
    name = basic.get('名字', folder.split('-')[0])
    mbti = basic.get('MBTI', '')

    tagline = (re.search(r'^> 一句话[:：]\s*(.+)$', md, re.M) or [None, ''])[1]

    # Every `## 额外设定…` heading is a one-line statement of that character's
    # contradiction, which is exactly what a model needs to build a premise from.
    contradictions = [
        re.sub(r'^额外设定[一二三四五六七八九十]?[:：]?\s*', '', t).strip()
        for t in re.findall(r'^## (额外设定[^\n]*)$', md, re.M)
    ]

    habits = _section(md, '行为习惯')
    line = next((l for l in habits.splitlines() if '口头禅' in l), '')
    phrases = [p for p in re.findall(r'"([^"]+)"', line) if len(p) <= 24]

    prop = _first_sentence(_section(md, '道具的意义'))
    relations = [l.strip()[2:].strip() for l in _section(md, '和其他人的相处').splitlines() if l.strip().startswith('- ')]

    return Character(slug, folder, name, mbti, tagline.strip(), contradictions, phrases, prop, relations)


def _first_sentence(text: str) -> str:
    body = ' '.join(l.strip() for l in text.splitlines() if l.strip())
    body = re.sub(r'\*\*([^*]+)\*\*', r'\1', body)
    parts = re.split(r'(?<=[。！？])', body)
    return parts[0].strip() if parts else ''


def load_guests() -> list[tuple[str, str]]:
    """(display name, function) for reusable guests. Reuse is encouraged, so the models
    have to know these exist — a model cannot reuse a guest it was never shown."""
    out = []
    if not GUESTS.exists():
        return out
    for folder in sorted(p for p in GUESTS.iterdir() if p.is_dir()):
        path = folder / '性格设定.md'
        if not path.exists():
            continue
        md = path.read_text(encoding='utf-8')
        title = (re.search(r'^# (.+)$', md, re.M) or [None, folder.name])[1]
        func = (re.search(r'^- \*\*关系与功能\*\*[:：]\s*(.+)$', md, re.M) or [None, ''])[1]
        out.append((title.replace('（客串）', '').strip(), _first_sentence(func)))
    return out


def load_stories() -> list[dict]:
    """Existing stories, one line each. Feeds the models' `differs_from` field."""
    out = []
    for path in sorted(STORIES.glob('*.md')):
        if path.name == 'README.md' or path.name.endswith('.en.md'):
            continue
        md = path.read_text(encoding='utf-8')
        fm = re.match(r'^---\r?\n(.*?)\r?\n---', md, re.S)
        data = dict(re.findall(r'^(\w+):\s*(.+)$', fm.group(1), re.M)) if fm else {}
        body = md[fm.end():] if fm else md
        first = next(
            (
                l.strip()
                for l in body.splitlines()
                if l.strip() and not l.startswith(('#', '---', '**', '<!--'))
            ),
            '',
        )
        out.append(
            {
                'slug': path.stem,
                'title': data.get('title', path.stem),
                'kind': '番外' if data.get('type') == 'extra' else '记忆事件',
                'cast': data.get('cast', ''),
                'location': data.get('location', ''),
                'first': first,
            }
        )
    return out


# --------------------------------------------------------------------------- combos

def assign_combos(characters: list[Character], scenes: list[Scene], stories: list[dict], n: int, seed: int):
    """Pick n (character group, scene) combos for this round, biased toward coverage.

    All four models receive the *same* combos. Letting each model pick its own would
    confound the comparison — different casts, different scenes, no like-for-like read
    on which model wrote the better premise. Identical brief and identical combos are
    the same requirement.

    Bias, not determinism: characters and scenes that have appeared least are more
    likely to be drawn, but the draw stays random so rounds do not become a rota.
    """
    rng = random.Random(seed)
    char_uses = {c.slug: 0 for c in characters}
    scene_uses = {s.file: 0 for s in scenes}
    for st in stories:
        for slug in re.findall(r'[\w一-鿿]+', st['cast']):
            if slug in char_uses:
                char_uses[slug] += 1
        for f in re.findall(r'[A-Za-z-]+', st['location']):
            if f in scene_uses:
                scene_uses[f] += 1

    def weighted(pool, uses, key):
        # Least-used gets the most weight; +1 keeps every option reachable.
        weights = [1.0 / (uses[key(x)] + 1) for x in pool]
        return rng.choices(pool, weights=weights, k=1)[0]

    combos = []
    used_scenes: set[str] = set()
    for _ in range(n):
        group: list[Character] = []
        pool = [c for c in characters]
        size = rng.choice([2, 3, 3, 4])
        while len(group) < size and pool:
            pick = weighted(pool, char_uses, lambda c: c.slug)
            group.append(pick)
            pool.remove(pick)
            char_uses[pick.slug] += 1
        scene_pool = [s for s in scenes if s.file not in used_scenes] or scenes
        scene = weighted(scene_pool, scene_uses, lambda s: s.file)
        used_scenes.add(scene.file)
        scene_uses[scene.file] += 1
        combos.append({'cast': [c.slug for c in group], 'names': [c.name for c in group], 'location': scene.file, 'location_zh': scene.zh})
    return combos


# --------------------------------------------------------------------------- render

RULES = """\
## 世界与规则

- 这是一部人设先行的情景喜剧。故事发生在一所幼儿园，12 个角色以真实社交圈的性格为原型铸造。
- 故事分两类：**记忆事件**真实发生、会影响之后的人物关系与行为；**番外**是特别篇、假想与恶搞，不进入任何角色的记忆。你写的大纲要标明属于哪一类。
- 记忆是主观的：同一件事，每个角色记住的版本不同，有人只知道一部分，有人知情但保密。不要让角色仅仅因为读者知道就知道某件事。
- 长度：这一步只要**大纲**，不要正文。
"""

TASK = """\
## 你的任务

针对下面指定的（人物组 + 场景）组合，各写 **1 条**故事大纲。

每条大纲输出为一个 JSON 对象，字段如下：

- `hook`：一句话前提。
- `turn`：一句话转折。
- `kind`：`memory` 或 `extra`。
- `cast`：实际出场的角色 slug 列表。
- `location`：场景文件名。
- `differs_from`：这条与上面哪一篇已有故事最接近，区别在哪。**必填**，用于去重。
- `new_elements`：**只统计新的客串角色或新的场景**，两者都没有就填 `"none"`。
  新的情节、道具、笑点、以及关于现有角色的新事实，都**不算**新元素——那些是正常创作，不用在这里报备。
  确实需要一个不在上面 12 人里的人物，或一个不在场景清单里的地点时，才写成列表，每项一行说明。

只输出一个 JSON 数组，不要输出任何其他文字。
"""

EXPANSION_TASK = """\
## 你的任务

针对下面指定的（人物组 + 场景）组合，写 **1 条**故事大纲，要求这个故事**必须引入一个临时客串角色或一个新场景才能成立**——也就是说，光靠现有的 12 个角色和现有场景写不出来。

先看上面的「可复用的客串角色」清单：如果其中某位就能撑起这个故事，优先用他们，并在 `new_elements` 里写 `reuse: <名字>`。只有在现有客串都不合适时才提出全新的人或地点。

新地点的代价远高于新人物：新地点需要单独绘制场景参考图并生成地点页。所以如果新人物和新地点都能达成同一个效果，选新人物。

字段与常规大纲相同，`new_elements` 必须是列表而非 `"none"`，每项写明是什么、为什么非它不可。

只输出一个 JSON 对象组成的数组（长度 1），不要输出任何其他文字。
"""


def render(characters, scenes, guests, stories, combos, *, taste: bool, expansion: bool) -> str:
    out: list[str] = ['# QC Kindergarten 故事大纲任务', '', RULES, '## 角色', '']

    for c in characters:
        out.append(f'### {c.name}（{c.mbti}）· slug `{c.slug}`')
        if c.tagline:
            out.append(f'- 一句话：{c.tagline}')
        for x in c.contradictions:
            out.append(f'- 矛盾：{x}')
        if c.phrases:
            out.append('- 口头禅：' + '　'.join(f'“{p}”' for p in c.phrases))
        if c.prop:
            out.append(f'- 道具：{c.prop}')
        for r in c.relations:
            out.append(f'- 关系：{r}')
        out.append('')

    out += ['## 可复用的客串角色', '',
            '这些人已经存在，有现成的形象设定。**复用他们是鼓励的，不需要任何额外说明。**', '']
    for name, func in guests:
        out.append(f'- **{name}**：{func}')
    out.append('')

    out += ['## 场景', '']
    for s in scenes:
        out.append(f'- `{s.file}` — {s.zh} / {s.en}')
    out.append('')

    out += ['## 已有故事（不要重复，`differs_from` 要引用其中一篇）', '']
    for st in stories:
        out.append(f"- `{st['slug']}`（{st['kind']}）**{st['title']}** — {st['first']}")
    out.append('')

    if taste:
        out += ['## 创作偏好', '',
                '以下是这个项目作者的创作偏好，来自对其历史决策的提炼。它描述作者会选什么，不是质量标准。', '',
                TASTE.read_text(encoding='utf-8').strip(), '']

    out.append(EXPANSION_TASK if expansion else TASK)
    out += ['## 本轮指定的组合', '']
    for i, combo in enumerate(combos, 1):
        out.append(f"{i}. 人物：{'、'.join(combo['names'])}　场景：`{combo['location']}`（{combo['location_zh']}）")
    out.append('')
    return '\n'.join(out)


def build(*, taste: bool = True, expansion: bool = False, combos=None, n: int | None = None, seed: int = 0):
    """Returns (brief text, combos). Same seed + same sources = same brief.

    The expansion slot defaults to one combo: it asks for a single outline, so handing it
    three would tell the model to write one story about three different casts.
    """
    if n is None:
        n = 1 if expansion else 3
    characters = [parse_character(slug, folder) for slug, folder in load_roster()]
    scenes = load_scenes()
    guests = load_guests()
    stories = load_stories()
    if combos is None:
        combos = assign_combos(characters, scenes, stories, n, seed)
    return render(characters, scenes, guests, stories, combos, taste=taste, expansion=expansion), combos


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-taste', action='store_true', help='ablation arm: omit the taste profile')
    ap.add_argument('--expansion', action='store_true', help='the expansion slot prompt')
    ap.add_argument('--combos', action='store_true', help='print only the assigned combos')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('-n', type=int, default=None)
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    text, combos = build(taste=not args.no_taste, expansion=args.expansion, n=args.n, seed=args.seed)
    if args.combos:
        for i, c in enumerate(combos, 1):
            print(f"{i}. {'、'.join(c['names'])} @ {c['location']}")
        return 0
    print(text)
    print(f'\n<!-- {len(text)} chars, sha256 {sha256(text)[:12]} -->', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
