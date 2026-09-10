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


RULES = """\
## 世界与规则

- 这是一部人设先行的情景喜剧。故事发生在一所幼儿园，12 个角色以真实社交圈的性格为原型铸造。
- **前提必须是真实幼儿园里不可能发生的事。** 男孩发誓再犯就变成狗、然后真的变成了狗；金色法拉利在凌晨两点收超速罚单；四个女孩被画成飞车党魔女——这是这个项目已经被认可的量级。放开想象，不必回避明显的荒诞。
- **但荒诞必须跑在人物既有的逻辑上，不能与之相悖。** 没有锚点的荒诞就只是奇观。
- **日常小事不要提交。** 帽子掉进汤锅、午餐时间办个比赛、大家一起做点心——这类"任何一家托儿所任何一个星期二都可能发生"的前提会被直接否决，无论细节写得多贴合人设。
- 故事分两类：**记忆事件**真实发生、会影响之后的人物关系与行为；**番外**是特别篇、假想与恶搞，不进入任何角色的记忆。你要标明属于哪一类。
- 记忆是主观的：同一件事，每个角色记住的版本不同，有人只知道一部分，有人知情但保密。不要让角色仅仅因为读者知道就知道某件事。
- **写完整的短篇故事，不是大纲。** 要有对话、有动作、有场面。
- **长度上限 2286 字（不含空白），但这是上限不是目标。** 已定稿的六篇里，最长的《幼儿园四大魔女》是 2086 字，那是十二人群像的特例；其余五篇在 387 到 517 字之间，中位数不到 500 字。
  **五百字能写完的就用五百字。** 长度不是优点，写满上限通常意味着有该删的东西没删——交代太多、解释了笑点、或者把所有人都塞进了同一场戏。
- 讲法克制：短对话、具体动作、延迟反应、留一处让读者自己想明白。**不要在笑点之后解释笑点**，也不要用旁白讲解某人的性格。
- 结尾落在一个改不回去的东西上：一个道具、一个习惯、一句早先说过的话，含义变了。不要用总结或道理收尾。
"""

# The four premise templates, reverse-engineered from the six stories QC has accepted.
# Round r01 asked "what happens when these three people are in this room?" — a slice-of-life
# question, which got slice-of-life answers and a 6/6 rejection. Not one accepted story began
# from a room: they began from a consequence, a contradiction, an exaggerated fact, or a genre.
# The location is an output of the premise now, never an input to it.
SLOTS = {
    'consequence': {
        'zh': '后果位',
        'brief': """\
拿下面**已有故事**中的一篇，写它在之后引发的事。

不是续写，是**后果**：那件事留下的东西——一个改变了的习惯、一段没消化的记忆、一个还没还的人情、一个被埋起来的秘密——在几周或几个月后长成了一件新的、更麻烦的事。

《七天追咬事件》就是这么来的：Haide 变成狗之后适应了四条腿，于是幼儿园恢复了熟悉的混乱。""",
    },
    'contradiction': {
        'zh': '矛盾位',
        'brief': """\
拿**某一个角色**的矛盾，写它不再是笑点、变成真麻烦的那一刻。

每个角色的矛盾都写在上面的设定里。平时它是个有趣的反差；你要写的是它失控、或者被人当真、或者代价终于到账的那一次。

《Haide 变成狗的那一天》就是这么来的：一句"再犯就变成狗"的誓言本来是玩笑，然后当真了。""",
    },
    'escalation': {
        'zh': '放大位',
        'brief': """\
拿一条**已经确立的具体事实**——某个道具、某个习惯、某条额外设定——把它推到一个不可能的量级。

不要发明新事实，要放大旧事实。QC 的金色法拉利本来就在设定里，《午夜的金色法拉利》把它推到凌晨两点的超速罚单和一个没人敢承认的车速。艾莎的记仇本也在设定里——它可以被推到什么程度？""",
    },
    'transposition': {
        'zh': '移植位',
        'brief': """\
把全员或其中几个人搬进一个**不属于幼儿园的类型**：飞车党、黑帮、法庭、恐怖片、体育解说、宫斗、赛博朋克、纪录片——越不搭越好。

保留每个人的身份锚点：主题色、招牌道具、说话方式、核心矛盾。移植的是舞台，不是人，读者要能一眼认出谁是谁。

《幼儿园四大魔女》就是这么来的。这一类通常是**番外**，但如果你能让它成立为记忆事件也可以。""",
    },
}

EXPANSION_BRIEF = """\
写一个**必须引入一个临时客串角色或一个新场景才能成立**的故事——光靠现有的 12 个角色和现有场景写不出来的那种。

先看上面的「可复用的客串角色」清单：如果其中某位就能撑起这个故事，优先用他们，并在 `new_elements` 里写 `reuse: <名字>`。只有在现有客串都不合适时才提出全新的人或地点。

新地点的代价远高于新人物：新地点要单独绘制场景参考图并生成地点页。如果新人物和新地点能达成同一个效果，选新人物。
"""

OUTPUT_SPEC = """\
## 输出格式

输出一个 JSON 对象，字段如下：

- `title`：故事标题。
- `premise_line`：一行，说明你按本次的位子做了什么——接了哪篇的什么残留 / 用了谁的哪条矛盾 / 放大了哪条既有事实 / 移植进了什么类型。
- `kind`：`memory` 或 `extra`。
- `cast`：出场角色的 slug 列表。
- `location`：场景文件名，从上面的场景清单里挑最合适的一个。**地点由故事决定，不要为了用某个地点而编故事。**
- `nearest`：下面已有故事里与这篇**同类**的那一篇（slug）。
- `stands_beside`：这篇凭什么配站在那一篇旁边——它带来了那一篇没有的什么。**要求的是"配得上"，不是"比它小"：不要用更平淡、更安静、更少人物来制造区别。**
- `residue`：这个故事之后留下的、改不回去的那个东西。
- `new_elements`：**只统计新的客串角色或新的场景**，两者都没有就填 `"none"`。新的情节、道具、笑点、以及关于现有角色的新事实都**不算**——那些是正常创作。
- `story`：完整的短篇故事正文，markdown。长度不限。

只输出这一个 JSON 对象，不要输出任何其他文字。
"""


def render(characters, scenes, guests, stories, *, taste: bool, slot: str) -> str:
    """One brief. `slot` is a key of SLOTS, or 'expansion'."""
    out: list[str] = ['# QC Kindergarten 故事写作任务', '', RULES, '## 角色', '']

    for c in characters:
        out.append(f'### {c.name}（{c.mbti}）· slug `{c.slug}`')
        if c.tagline:
            out.append(f'- 一句话：{c.tagline}')
        for x in c.contradictions:
            out.append(f'- 矛盾：{x}')
        if c.phrases:
            out.append('- 口头禅：' + '　'.join(f'“{ph}”' for ph in c.phrases))
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

    out += ['## 场景', '', '故事写完之后，从这里挑一个最贴合的填进 `location`。', '']
    for sc in scenes:
        out.append(f'- `{sc.file}` — {sc.zh} / {sc.en}')
    out.append('')

    out += ['## 已有故事', '',
            '`nearest` 要从这里挑一篇同类的。不要重复它们，但也不要靠"写得更小"来制造区别。', '']
    for st in stories:
        out.append(f"- `{st['slug']}`（{st['kind']}）**{st['title']}** — {st['first']}")
    out.append('')

    if taste:
        out += ['## 创作偏好', '',
                '以下是这个项目作者的创作偏好，来自对其历史决策的提炼。它描述作者会选什么，不是质量标准。', '',
                TASTE.read_text(encoding='utf-8').strip(), '']

    if slot == 'expansion':
        out += ['## 你的任务：扩展位', '', EXPANSION_BRIEF]
    else:
        spec = SLOTS[slot]
        out += [f"## 你的任务：{spec['zh']}", '', spec['brief'], '']

    out.append(OUTPUT_SPEC)
    return '\n'.join(out)


def build(*, taste: bool = True, slot: str = 'contradiction') -> str:
    """The brief for one slot. Deterministic: same sources + same slot = same bytes.

    No seed and no combo assignment any more. Round r01 handed every model a
    (cast, room) pair and got twelve slice-of-life premises for it; the slot now supplies
    a *shape* — a consequence, a contradiction, an exaggeration, a genre — and the model
    chooses who and where. Cast rotation follows from the shapes rather than being imposed
    ahead of them, which also removes the coverage weighting that kept steering rounds
    toward the rooms nothing good had ever happened in.
    """
    if slot != 'expansion' and slot not in SLOTS:
        raise ValueError(f'unknown slot {slot!r}; expected expansion or one of {", ".join(SLOTS)}')
    characters = [parse_character(slug, folder) for slug, folder in load_roster()]
    return render(characters, load_scenes(), load_guests(), load_stories(), taste=taste, slot=slot)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slot', default='contradiction',
                    help='consequence | contradiction | escalation | transposition | expansion')
    ap.add_argument('--no-taste', action='store_true', help='ablation arm: omit the taste profile')
    ap.add_argument('--slots', action='store_true', help='list the slots and exit')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if args.slots:
        for name, spec in SLOTS.items():
            print(f"{name:15} {spec['zh']}  {spec['brief'].splitlines()[0]}")
        print(f"{'expansion':15} 扩展位  {EXPANSION_BRIEF.splitlines()[0]}")
        return 0

    text = build(taste=not args.no_taste, slot=args.slot)
    print(text)
    print(f'\n<!-- slot={args.slot} {len(text)} chars, sha256 {sha256(text)[:12]} -->', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
