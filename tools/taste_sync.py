#!/usr/bin/env python3
"""Keep QC's taste profile in two languages, and say when one side falls behind.

The profile lives in .agents/skills/qc-taste/references/taste/, one pair of files per part:

    _shared.en.md      / _shared.zh.md       read together with every domain
    story.en.md        / story.zh.md         故事创作
    image.en.md        / image.zh.md         图片生成
    storyboard.en.md   / storyboard.zh.md    分镜头（尚未使用）
    video.en.md        / video.zh.md         视频生成（尚未使用）

Either language may be edited first. A script cannot translate a taste rule faithfully, so
this one does not try: it tracks which side changed and tells whoever is editing to bring the
other side in line. .agents/state/taste-sync.json holds the hash of both files as they were
the last time someone confirmed they say the same thing. From that:

    English changed, Chinese did not   -> the Chinese file is stale
    Chinese changed, English did not   -> the English file is stale
    both changed                       -> compare them, then stamp
    neither                            -> in sync

It also checks what a script can check: both files carry the same rule numbers in the same
order, the same number of headings at each level, and the same number of list items.

    python tools/taste_sync.py                  # report; exit 1 if anything is out of sync (CI)
    python tools/taste_sync.py stamp story      # confirm story.en.md and story.zh.md now match
    python tools/taste_sync.py stamp --all
    python tools/taste_sync.py hook             # Claude Code PostToolUse hook; event on stdin

Codex has no hooks, so the qc-taste skill tells every agent to run the report after editing,
and CI runs it on every push.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASTE_DIR = ROOT / '.agents' / 'skills' / 'qc-taste' / 'references' / 'taste'
STATE = ROOT / '.agents' / 'state' / 'taste-sync.json'
LANGS = ('en', 'zh')
LANG_NAME = {'en': 'English', 'zh': 'Chinese'}

# Display order on the review site. `_shared` is not a domain: every domain is read with it.
PARTS = {
    'story': {
        'zh': '故事创作', 'en': 'Story creation',
        'used_by': {'zh': '故事流水线发给模型的 brief（英文版，连同共通部分）',
                    'en': 'The story pipeline brief sent to the models (English, with the shared part)'},
    },
    'image': {
        'zh': '图片生成', 'en': 'Image generation',
        'used_by': {'zh': '角色形象与插图工作（qc-taste 配合 story-illustrator）',
                    'en': 'Character art and illustrations (qc-taste with story-illustrator)'},
    },
    'storyboard': {
        'zh': '分镜头', 'en': 'Storyboards',
        'used_by': {'zh': '尚未使用', 'en': 'Not in use yet'},
    },
    'video': {
        'zh': '视频生成', 'en': 'Video generation',
        'used_by': {'zh': '尚未使用', 'en': 'Not in use yet'},
    },
    '_shared': {
        'zh': '共通', 'en': 'Shared',
        'used_by': {'zh': '四个领域都和它一起读', 'en': 'Read together with every domain'},
    },
}

STATE_TEXT = {
    'synced': ('in sync', '中英已同步'),
    'zh_stale': ('the Chinese file is behind the English one', '中文版落后于英文版'),
    'en_stale': ('the English file is behind the Chinese one', '英文版落后于中文版'),
    'both_changed': ('both files changed since they were last confirmed to match', '中英两版都改过，还没确认一致'),
    'unstamped': ('never confirmed as in sync', '还没有确认过同步'),
    'missing': ('a language file is missing', '缺少某个语言的文件'),
}

RULE_RE = re.compile(r'^#{2,6}\s+(\d+[a-z]?)\.\s', re.M)
HEADING_RE = re.compile(r'^(#{1,6})\s', re.M)
ITEM_RE = re.compile(r'^\s*[-*]\s+\S', re.M)


def path(part: str, lang: str) -> Path:
    return TASTE_DIR / f'{part}.{lang}.md'


def rel(p: Path) -> str:
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def read(part: str, lang: str) -> str | None:
    p = path(part, lang)
    return p.read_text(encoding='utf-8') if p.exists() else None


def normalize(text: str) -> str:
    # Trailing spaces are a Markdown line break, not content; line endings are not content either.
    return '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').split('\n')).strip()


def digest(text: str) -> str:
    return hashlib.sha256(normalize(text).encode('utf-8')).hexdigest()


def skeleton(text: str) -> dict:
    levels: dict[int, int] = {}
    for m in HEADING_RE.finditer(text):
        levels[len(m.group(1))] = levels.get(len(m.group(1)), 0) + 1
    return {'rules': RULE_RE.findall(text), 'headings': levels, 'items': len(ITEM_RE.findall(text))}


def structure_problems(en: str, zh: str) -> list[str]:
    a, b = skeleton(en), skeleton(zh)
    out = []
    if a['rules'] != b['rules']:
        only_en = [r for r in a['rules'] if r not in b['rules']]
        only_zh = [r for r in b['rules'] if r not in a['rules']]
        if only_en:
            out.append('rule numbers only in English: ' + ', '.join(only_en))
        if only_zh:
            out.append('rule numbers only in Chinese: ' + ', '.join(only_zh))
        if not only_en and not only_zh:
            out.append('the rules are in a different order')
    for level in sorted(set(a['headings']) | set(b['headings'])):
        if a['headings'].get(level, 0) != b['headings'].get(level, 0):
            out.append(f"{'#' * level} headings: English {a['headings'].get(level, 0)}, "
                       f"Chinese {b['headings'].get(level, 0)}")
    if a['items'] != b['items']:
        out.append(f"list items: English {a['items']}, Chinese {b['items']}")
    return out


def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    parts = data.get('parts') if isinstance(data, dict) else None
    return parts if isinstance(parts, dict) else {}


def save_state(parts: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({'version': 1, 'parts': dict(sorted(parts.items()))}, ensure_ascii=False, indent=2) + '\n',
                     encoding='utf-8', newline='\n')


def status(part: str, stamps: dict | None = None) -> dict:
    stamps = load_state() if stamps is None else stamps
    texts = {lang: read(part, lang) for lang in LANGS}
    result = {'part': part, 'files': {lang: rel(path(part, lang)) for lang in LANGS},
              'stamped': None, 'problems': [], 'missing': []}
    result['missing'] = [lang for lang in LANGS if texts[lang] is None]
    if result['missing']:
        result['state'] = 'missing'
        return result
    result['problems'] = structure_problems(texts['en'], texts['zh'])
    stamp = stamps.get(part)
    if not stamp:
        result['state'] = 'unstamped'
        return result
    result['stamped'] = stamp.get('stamped')
    changed = {lang: digest(texts[lang]) != stamp.get(lang) for lang in LANGS}
    if not any(changed.values()):
        result['state'] = 'synced'
    elif all(changed.values()):
        result['state'] = 'both_changed'
    else:
        result['state'] = 'zh_stale' if changed['en'] else 'en_stale'
    return result


def in_sync(st: dict) -> bool:
    return st['state'] == 'synced' and not st['problems']


def overview() -> dict:
    """Everything the review site shows: both texts of every part, with its sync state."""
    stamps = load_state()
    parts = []
    for key, meta in PARTS.items():
        st = status(key, stamps)
        parts.append({
            **st,
            'key': key,
            'title': {'zh': meta['zh'], 'en': meta['en']},
            'used_by': meta['used_by'],
            'shared': key == '_shared',
            'state_text': {'en': STATE_TEXT[st['state']][0], 'zh': STATE_TEXT[st['state']][1]},
            'texts': {lang: read(key, lang) for lang in LANGS},
        })
    return {'parts': parts}


def cmd_report() -> int:
    stamps = load_state()
    bad = 0
    for key in PARTS:
        st = status(key, stamps)
        ok = in_sync(st)
        bad += not ok
        print(f"{'ok ' if ok else 'OUT'}  {key:11} {STATE_TEXT[st['state']][0]}")
        for problem in st['problems']:
            print(f'     structure: {problem}')
        for lang in st['missing']:
            print(f"     missing: {st['files'][lang]}")
    if bad:
        print(f'\n[taste-sync] {bad} part(s) out of sync. Bring the stale file in line with the edited one '
              '(translate only what changed; keep rule numbers, sections and QC\'s quoted words), '
              'then run: python tools/taste_sync.py stamp <part>')
        return 1
    print('\n[taste-sync] every part is in sync in both languages')
    return 0


def cmd_stamp(parts: list[str]) -> int:
    if parts == ['--all']:
        parts = list(PARTS)
    if not parts:
        print('usage: python tools/taste_sync.py stamp <part> [<part> ...] | --all')
        return 2
    unknown = [p for p in parts if p not in PARTS]
    if unknown:
        print(f"[taste-sync] unknown part(s): {', '.join(unknown)}; expected {', '.join(PARTS)}")
        return 2
    stamps = load_state()
    today = dt.date.today().isoformat()
    for part in parts:
        st = status(part, stamps)
        if st['missing']:
            print(f"[taste-sync] {part}: not stamped, missing {', '.join(st['files'][l] for l in st['missing'])}")
            return 1
        if st['problems']:
            print(f'[taste-sync] {part}: not stamped, the two files differ in structure:')
            for problem in st['problems']:
                print(f'  - {problem}')
            return 1
        stamps[part] = {'en': digest(read(part, 'en')), 'zh': digest(read(part, 'zh')), 'stamped': today}
    save_state(stamps)
    print(f"[taste-sync] stamped {', '.join(parts)}")
    return 0


def part_of(file_path: str) -> tuple[str, str] | None:
    if not file_path:
        return None
    try:
        resolved = Path(file_path).resolve()
    except OSError:
        return None
    if os.path.normcase(str(resolved.parent)) != os.path.normcase(str(TASTE_DIR.resolve())):
        return None
    m = re.fullmatch(r'(.+)\.(en|zh)\.md', resolved.name)
    if not m or m.group(1) not in PARTS:
        return None
    return m.group(1), m.group(2)


def hook_message(part: str, lang: str, st: dict) -> dict | None:
    if in_sync(st):
        return None
    lines = [f"A taste profile file changed: {st['files'][lang]}."]
    if st['state'] in ('zh_stale', 'en_stale'):
        stale = 'zh' if st['state'] == 'zh_stale' else 'en'
        lines.append(
            f"Its {LANG_NAME[stale]} counterpart, {st['files'][stale]}, is now stale. Before finishing this task, "
            'bring it in line: translate only what changed, keep rule numbers, section order and list items '
            "parallel, and keep QC's quoted words verbatim in both files. These are instructions, so accuracy "
            'comes before style.')
    elif st['state'] == 'both_changed':
        lines.append('Both language files have changed since they were last confirmed to match. If this edit was '
                     'the translation step, read the two files side by side and confirm they say the same thing.')
    elif st['state'] == 'unstamped':
        lines.append('This part has never been confirmed as in sync. Compare the two files.')
    elif st['state'] == 'missing':
        missing = ', '.join(st['files'][l] for l in st['missing'])
        lines.append(f'A language file is missing ({missing}); create it as a faithful translation of the other.')
    if st['problems']:
        lines.append('Structure check failed: ' + '; '.join(st['problems']) + '.')
    lines.append(f'When both files say the same thing and the structure matches, run: python tools/taste_sync.py stamp {part}')
    lines.append("Translating never changes a rule. A rule change goes through the qc-taste update protocol and needs QC's approval.")
    summary = STATE_TEXT[st['state']][1] + ('，结构不一致' if st['problems'] else '')
    return {
        'systemMessage': f"taste 中英同步：{PARTS[part]['zh']} · {summary}",
        'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': '\n'.join(lines)},
    }


def cmd_hook() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 - a hook must never break the tool call it follows
        return 0
    file_path = ((event.get('tool_input') or {}).get('file_path')
                 or (event.get('tool_response') or {}).get('filePath') or '')
    hit = part_of(str(file_path))
    if not hit:
        return 0
    message = hook_message(hit[0], hit[1], status(hit[0]))
    if message:
        sys.stdout.write(json.dumps(message, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:  # noqa: BLE001
            pass
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ('check', 'status', 'report'):
        return cmd_report()
    if args[0] == 'stamp':
        return cmd_stamp(args[1:])
    if args[0] == 'hook':
        return cmd_hook()
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
