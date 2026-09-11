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
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHARS = ROOT / 'character reference'
GUESTS = CHARS / '_guests'
STORIES = ROOT / 'stories'
CONFIG = ROOT / 'website' / 'src' / 'data' / 'characters.config.mjs'
# QC's taste profile, split by domain and kept in two languages (2026-09-10). A story brief
# carries the shared part plus the story domain. Every round so far sent the English text, so
# English stays what the models get; switching language changes the brief and deserves its
# own ablation rather than riding along with another change.
TASTE_DIR = ROOT / '.agents' / 'skills' / 'qc-taste' / 'references' / 'taste'
TASTE_LANG = 'en'


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


def _memory_holders(frontmatter: str) -> list[tuple[str, str]]:
    """(slug, knowledge) for every character carrying the story's memory."""
    block = re.search(r'^memories:[ \t]*\n((?:[ \t]+.*\n?)*)', frontmatter + '\n', re.M)
    if not block:
        return []
    out = []
    for m in re.finditer(r'^  ([^\s:]+):[ \t]*\n((?:    .*\n?)*)', block.group(1), re.M):
        level = re.search(r'knowledge:\s*(\w+)', m.group(2))
        out.append((m.group(1), level.group(1) if level else 'witnessed'))
    return out


def load_stories() -> list[dict]:
    """Existing stories, one line each. Feeds the models' `differs_from` field."""
    out = []
    for path in sorted(STORIES.glob('*.md')):
        if path.name == 'README.md' or path.name.endswith('.en.md'):
            continue
        md = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        fm = re.match(r'^---\n(.*?)\n---', md, re.S)
        data = dict(re.findall(r'^(\w+):\s*(.+)$', fm.group(1), re.M)) if fm else {}
        knows = _memory_holders(fm.group(1)) if fm else []
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
                # Only these characters know the event happened, at these levels. The brief
                # used to drop this entirely, so a secret three people share could turn up
                # being argued in front of the whole kindergarten.
                'knows': knows,
                'open_ending': data.get('open_ending', '').strip() == 'true',
            }
        )
    return out


KNOWLEDGE_ZH = {
    'witnessed': '亲历',
    'heard': '听说',
    'inferred': '推测',
    'partial': '只知道一部分',
    'secret': '知情但保密',
}

RULES = """\
## 世界与规则

- 这是一部人设先行的情景喜剧。故事发生在一所幼儿园，12 个角色以真实社交圈的性格为原型铸造。
- **前提必须是真实幼儿园里不可能发生的事。** 男孩发誓再犯就变成狗、然后真的变成了狗；金色法拉利在凌晨两点收超速罚单；四个女孩被画成飞车党魔女——这是这个项目已经被认可的量级。放开想象，不必回避明显的荒诞。
- **但荒诞必须跑在人物既有的逻辑上，不能与之相悖。** 没有锚点的荒诞就只是奇观。
- **日常小事不要提交。** 帽子掉进汤锅、午餐时间办个比赛、大家一起做点心——这类"任何一家托儿所任何一个星期二都可能发生"的前提会被直接否决，无论细节写得多贴合人设。
- 故事分两类：**记忆事件**真实发生、会影响之后的人物关系与行为；**番外**是特别篇、假想与恶搞，不进入任何角色的记忆。你要标明属于哪一类。
- 记忆是主观的：同一件事，每个角色记住的版本不同，有人只知道一部分，有人知情但保密。不要让角色仅仅因为读者知道就知道某件事。
- **秘密只属于知情的人。** 下面「已有故事」每篇都列了知情者；没列出来的角色就是不知道，不能参与、议论、记录或追查那件事。
- **除了 QC，所有角色都是孩子。** 幼儿园另有园长、老师等大人，但他们不出现在故事里，也不需要解释他们为什么不在。孩子不掌握机构层面的权力：门禁、账本、广播、园主身份不会归到任何一个孩子名下。
- **这一步只写大纲，不写正文。** 大纲上限 **<<MAX_CHARS>> 字**（不含空白），写不满不要紧，写不下说明前提还没收干净。
  正文由另一个环节统一执笔，你要交的是一个值得被写成故事的前提。
- 大纲里要能看出：谁做了什么、什么翻转了、结束时什么变了。不需要对白，不需要场面描写，不需要铺垫。
- 讲法上仍然克制：**不要在大纲里解释笑点**，也不要用形容词替代事件。「他慌了」不如「他把项圈摘下来塞进了花盆」。
- 收尾落在一个改不回去的东西上：一个道具、一个习惯、一句早先说过的话，含义变了。
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

《七天追咬事件》就是这么来的：Haide 变成狗之后适应了四条腿，于是幼儿园恢复了熟悉的混乱。

**标了「刻意留白」的故事不能拿来接。** 那些结尾的悬念就是故事本身，续写、揭晓或解释都会同时毁掉两篇。""",
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

不要发明新事实，要放大旧事实。《午夜的金色法拉利》是这个形状：一件本来就在设定里的事，被推到凌晨两点、没人敢承认的车速。

**例子只说明形状。** 不要去放大例子里的同一件事，也不要去放大已有故事已经放大过的事——挑一条还没人动过的。""",
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

PREMISE_HINT = {
    'consequence': '说明你接的是哪一篇的哪个残留。',
    'contradiction': '说明你用的是谁的哪一条矛盾。这个位子不是续集，不要接任何已有故事。',
    'escalation': '说明你放大的是哪一条既有事实。这个位子不是续集，不要接任何已有故事。',
    'transposition': '说明你移植进了什么类型。这个位子不是续集，不要接任何已有故事。',
    'expansion': '说明引入的新人物或新地点是什么、为什么非它不可。这个位子不是续集，不要接任何已有故事。',
}

FORMATS = Path(__file__).resolve().parent / 'formats'
DEFAULT_FORMAT = 'default'
# The outline ceiling a brief states when the caller does not pass one. It must equal
# store.MAX_OUTLINE_CHARS; a test pins the two together.
DEFAULT_MAX_CHARS = 200

# The output format lives in formats/<name>.json rather than in this file. QC found
# (2026-09-10) that the format itself shifts what the models write, so it has to be cheap
# to change and possible to compare: the file lists the fields in order, what each one asks
# for, and which one carries the outline. Changing it needs no code change here, in
# run_round.py, or on the review site. Each round records the file's sha256, and the
# rendered text stays inside every slot's brief sha256 as before.


def load_format(name: str = DEFAULT_FORMAT) -> dict:
    path = FORMATS / f'{name}.json'
    if not path.exists():
        known = ', '.join(sorted(p.stem for p in FORMATS.glob('*.json'))) or 'none'
        raise ValueError(f'unknown output format {name!r}; formats/ has: {known}')
    spec = json.loads(path.read_text(encoding='utf-8'))
    spec.setdefault('name', name)
    spec.setdefault('version', '?')
    spec['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    keys = [f.get('key') for f in spec.get('fields', [])]
    if not keys or not all(keys):
        raise ValueError(f'format {name!r} has no fields, or a field without a key')
    if spec.setdefault('body_field', 'outline') not in keys:
        raise ValueError(f"format {name!r}: body_field {spec['body_field']!r} is not one of its fields")
    return spec


def render_output_spec(fmt_spec: dict, *, slot: str, max_chars: int) -> str:
    lines = ['## 输出格式', '', fmt_spec['intro'], '']
    lines += [f"- `{f['key']}`：{f['instruction']}" for f in fmt_spec['fields']]
    lines += ['', fmt_spec['outro']]
    text = '\n'.join(lines) + '\n'
    return text.replace('<<PREMISE_HINT>>', PREMISE_HINT[slot]).replace('<<MAX_CHARS>>', str(max_chars))


REWRITE_MODE_LINE = {
    'waitlist': '这一篇进了候补：方向有可取之处，但还不够好。作者希望你按意见改写，改写稿会在这一轮重新参评。',
    'revise': '这一篇已经被选中，但作者要求按意见修改之后再批准。',
}


def render_rewrite(rewrite: dict, *, max_chars: int) -> list[str]:
    """The block that turns a slot brief into a rewrite request. It sits after the slot's
    task and before the output format, so the model still sees the premise shape it was
    working in, then QC's read of what it produced."""
    mode = rewrite.get('mode')
    if mode not in REWRITE_MODE_LINE:
        raise ValueError(f'unknown rewrite mode {mode!r}; expected one of {", ".join(REWRITE_MODE_LINE)}')
    out = ['## 这一篇是重写', '', REWRITE_MODE_LINE[mode], '']
    if rewrite.get('title'):
        out.append(f"- 原标题：{rewrite['title']}")
    if rewrite.get('score') is not None:
        out.append(f"- 作者打分：{rewrite['score']} / 10")
    out.append(f"- 作者意见：{rewrite.get('notes') or '（没有写意见）'}")
    out += ['', '你之前交的大纲：', '']
    out += [f'> {line}' if line.strip() else '>' for line in (rewrite.get('outline') or '').splitlines()]
    out += [
        '',
        '重写要求：',
        '',
        '- **以作者意见为准。** 意见要推翻的就推翻，不要为了保留原文而保留；意见肯定的部分可以留下。',
        f'- 仍然只写大纲，上限 **{max_chars} 字**（不含空白）。',
        '- 交一个完整的新版本，字段按下面的「输出格式」，不要只交改动的部分。',
        '',
    ]
    return out


def load_taste(domain: str = 'story', lang: str = TASTE_LANG) -> str:
    """The shared part of the taste profile followed by one domain, as the models read it."""
    parts = [TASTE_DIR / f'_shared.{lang}.md', TASTE_DIR / f'{domain}.{lang}.md']
    return '\n\n'.join(p.read_text(encoding='utf-8').strip() for p in parts)


def render(characters, scenes, guests, stories, *, taste: bool, slot: str,
           max_chars: int = DEFAULT_MAX_CHARS, fmt: dict | None = None, rewrite: dict | None = None) -> str:
    """One brief. `slot` is a key of SLOTS, or 'expansion'. `rewrite`, when given, turns it
    into a request to rewrite one earlier outline with QC's notes (see rewrite.py)."""
    # Not called `spec`: further down, `spec` is the slot's task from SLOTS.
    fmt_spec = fmt or load_format()
    out: list[str] = ['# QC Kindergarten 故事大纲任务', '', RULES.replace('<<MAX_CHARS>>', str(max_chars)), '## 角色', '']

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
    names = {c.slug: c.name for c in characters}
    for st in stories:
        out.append(f"- `{st['slug']}`（{st['kind']}）**{st['title']}** — {st['first']}")
        if st['knows']:
            who = '、'.join(f"{names.get(slug, slug)}（{KNOWLEDGE_ZH.get(level, level)}）" for slug, level in st['knows'])
            out.append(f'  - 知情者：{who}。其他人不知道。')
        if st['open_ending']:
            out.append('  - **刻意留白的结尾：不要续写、不要揭晓、不要解释，也不要让任何人去追查。**')
    out.append('')

    if taste:
        out += ['## 创作偏好', '',
                '以下是这个项目作者的创作偏好，来自对其历史决策的提炼。它描述作者会选什么，不是质量标准。', '',
                load_taste('story'), '']

    if slot == 'expansion':
        out += ['## 你的任务：扩展位', '', EXPANSION_BRIEF]
    else:
        spec = SLOTS[slot]
        out += [f"## 你的任务：{spec['zh']}", '', spec['brief'], '']

    # The hint used to list every slot's clause to every slot, so "接了哪篇的什么残留"
    # reached slots that were never meant to continue anything, and they did.
    if rewrite:
        out += render_rewrite(rewrite, max_chars=max_chars)
    out.append(render_output_spec(fmt_spec, slot=slot, max_chars=max_chars))
    return '\n'.join(out)


def build(*, taste: bool = True, slot: str = 'contradiction', max_chars: int = DEFAULT_MAX_CHARS,
          fmt: str | dict | None = None, rewrite: dict | None = None) -> str:
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
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError(f'max_chars must be a positive integer; got {max_chars!r}')
    fmt_spec = fmt if isinstance(fmt, dict) else load_format(fmt or DEFAULT_FORMAT)
    return render(characters, load_scenes(), load_guests(), load_stories(), taste=taste, slot=slot,
                  max_chars=max_chars, fmt=fmt_spec, rewrite=rewrite)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slot', default='contradiction',
                    help='consequence | contradiction | escalation | transposition | expansion')
    ap.add_argument('--no-taste', action='store_true', help='ablation arm: omit the taste profile')
    ap.add_argument('--max-chars', type=int, default=DEFAULT_MAX_CHARS, help='outline ceiling stated in the brief')
    ap.add_argument('--format', default=DEFAULT_FORMAT, help='output format, formats/<name>.json')
    ap.add_argument('--slots', action='store_true', help='list the slots and exit')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if args.slots:
        for name, spec in SLOTS.items():
            print(f"{name:15} {spec['zh']}  {spec['brief'].splitlines()[0]}")
        print(f"{'expansion':15} 扩展位  {EXPANSION_BRIEF.splitlines()[0]}")
        return 0

    text = build(taste=not args.no_taste, slot=args.slot, max_chars=args.max_chars, fmt=args.format)
    print(text)
    print(f'\n<!-- slot={args.slot} {len(text)} chars, sha256 {sha256(text)[:12]} -->', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
