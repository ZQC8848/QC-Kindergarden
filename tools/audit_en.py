#!/usr/bin/env python3
"""English coverage audit for the QC Kindergarten site.

Run from the repository root:  python tools/audit_en.py [--dist]

Checks (no dependencies beyond Python 3):
  1. every character folder has 性格设定.en.md whose headings cover every Chinese section
  2. every story has <slug>.en.md with the same memory keys and illustration markers
  3. website/src/i18n.ts has the same keys under zh and en
  4. with --dist (or when website/dist/en exists): no built /en/ page contains CJK text

Exit code 1 when anything is missing.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAR_DIR = ROOT / 'character reference'
STORIES = ROOT / 'stories'
I18N = ROOT / 'website' / 'src' / 'i18n.ts'
DIST_EN = ROOT / 'website' / 'dist' / 'en'
ALIAS_SRC = ROOT / 'website' / 'scripts' / 'parse.mjs'

CJK = re.compile(r'[㐀-䶿一-鿿　-〿＀-￯]+')
ALLOWED_CJK = {'中文'}  # language switch label on English pages


def load_aliases():
    """Read SECTION_ALIASES from the sync script so the audit cannot drift from it."""
    text = ALIAS_SRC.read_text(encoding='utf-8')
    block = re.search(r'const SECTION_ALIASES = \{(.*?)\};', text, re.S)
    aliases = {}
    if block:
        # Prettier drops the quotes around keys that do not need them (`Basics:` next to
        # `'Core personality':`), so accept a key either way.
        for m in re.finditer(r"(?:'([^']+)'|([A-Za-z_$][\w$]*))\s*:\s*'([^']+)'", block.group(1)):
            aliases[m.group(1) or m.group(2)] = m.group(3)
    if not aliases:
        # Same failure mode as the i18n check: the table moved from sync-content.mjs to
        # parse.mjs once already, and an empty table turns every English bible into a
        # false positive instead of an error.
        sys.exit(f'[setup] no SECTION_ALIASES found in {ALIAS_SRC.relative_to(ROOT)}; the parser needs updating')
    return aliases


def headings(md):
    return [l[3:].strip() for l in md.splitlines() if l.startswith('## ')]


def canon(title, aliases):
    if title in aliases:
        return aliases[title]
    if title.startswith('额外设定') or re.match(r'^Extra(\s[^:：]+)?[:：]', title):
        return '额外设定'
    if title.startswith('事件档案') or title.startswith('Archive'):
        return '事件档案'
    return title


def frontmatter(md):
    """Minimal YAML subset: top-level `key: value` and `memories:` → two-space-indented keys."""
    m = re.match(r'^---\r?\n(.*?)\r?\n---', md, re.S)
    data, memories = {}, {}
    if not m:
        return data, memories
    in_mem = False
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if not line.startswith(' '):
            in_mem = False
            key, _, val = line.partition(':')
            data[key.strip()] = val.strip()
            if key.strip() == 'memories':
                in_mem = True
        elif in_mem and re.match(r'^  \S', line):
            memories[line.strip().rstrip(':')] = True
    return data, memories


def markers(md):
    return [int(n) for n in re.findall(r'<!--\s*illustration:(\d+)\s*\|', md)]


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        for k, v in attrs:
            if k in ('alt', 'title', 'aria-label', 'placeholder') and v:
                self.parts.append(v)

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def main():
    # Windows consoles default to a legacy code page; the report contains Chinese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    aliases = load_aliases()
    problems = []

    # 1. bibles
    for folder in sorted(p for p in CHAR_DIR.iterdir() if p.is_dir() and not p.name.startswith('_') and p.name != '_guests'):
        zh = folder / '性格设定.md'
        en = folder / '性格设定.en.md'
        if not zh.exists():
            continue
        if not en.exists():
            problems.append(f'[bible] {folder.name}: missing 性格设定.en.md')
            continue
        zh_sections = [canon(h, aliases) for h in headings(zh.read_text(encoding='utf-8'))]
        en_sections = [canon(h, aliases) for h in headings(en.read_text(encoding='utf-8'))]
        for sec in zh_sections:
            # 事件档案 is a markdown-only pointer block: it renders nowhere on the site, so
            # the English bibles do not carry it. This one line is why zh and en section
            # counts are allowed to differ. Convention documented in stories/README.md.
            if sec == '事件档案':
                continue
            if zh_sections.count(sec) > en_sections.count(sec):
                problems.append(f'[bible] {folder.name}: English file lacks section "{sec}"')
        for h in headings(en.read_text(encoding='utf-8')):
            if canon(h, aliases) == h and h not in aliases.values():
                problems.append(f'[bible] {folder.name}: heading "{h}" is not in the alias table')
        en_text = en.read_text(encoding='utf-8')
        if not re.search(r'^> One line[:：]', en_text, re.M):
            problems.append(f'[bible] {folder.name}: missing "> One line:" tagline')
        if not re.search(r'catchphrase', en_text, re.I):
            problems.append(f'[bible] {folder.name}: no "Catchphrases:" line under Habits')

    # 2. stories
    for zh in sorted(STORIES.glob('*.md')):
        if zh.name == 'README.md' or zh.name.endswith('.en.md'):
            continue
        en = zh.with_name(zh.stem + '.en.md')
        zh_md = zh.read_text(encoding='utf-8')
        if not en.exists():
            problems.append(f'[story] {zh.stem}: missing {en.name}')
            continue
        en_md = en.read_text(encoding='utf-8')
        zh_data, zh_mem = frontmatter(zh_md)
        en_data, en_mem = frontmatter(en_md)
        if not en_data.get('title'):
            problems.append(f'[story] {zh.stem}: English frontmatter has no title')
        if zh_data.get('type') == 'extra' and zh_data.get('framing') and not en_data.get('framing'):
            problems.append(f'[story] {zh.stem}: English frontmatter has no framing (extra story)')
        for k in zh_mem:
            if k not in en_mem:
                problems.append(f'[story] {zh.stem}: memory "{k}" not translated')
        if markers(zh_md) != markers(en_md):
            problems.append(f'[story] {zh.stem}: illustration markers differ (zh {markers(zh_md)} vs en {markers(en_md)})')

    # 3. i18n keys
    src = I18N.read_text(encoding='utf-8')
    # `const zh = {` and `const en: Dict = {`, each closed by a `}` in column 0.
    dicts = dict(re.findall(r'^const (zh|en)(?:\s*:\s*[\w<>\[\] ]+)? = \{(.*?)^\}', src, re.S | re.M))
    keys = {lang: set(re.findall(r'^  (\w+):', body, re.M)) for lang, body in dicts.items()}
    if len(keys) != 2 or not all(keys.values()):
        # Never pass quietly: this check silently stopped matching once already, when the
        # two dictionaries moved out of a wrapper object.
        problems.append('[i18n] could not read the zh and en dictionaries from i18n.ts; the parser needs updating')
    else:
        for k in sorted(keys['zh'] - keys['en']):
            problems.append(f'[i18n] key "{k}" exists in zh but not in en')
        for k in sorted(keys['en'] - keys['zh']):
            problems.append(f'[i18n] key "{k}" exists in en but not in zh')

    # 4. built pages
    if DIST_EN.exists():
        for page in sorted(DIST_EN.rglob('*.html')):
            parser = TextOnly()
            parser.feed(page.read_text(encoding='utf-8', errors='ignore'))
            found = []
            for part in parser.parts:
                for run in CJK.findall(part):
                    if run not in ALLOWED_CJK and run not in found:
                        found.append(run)
            if found:
                rel = page.relative_to(ROOT / 'website' / 'dist')
                sample = ' | '.join(found[:6])
                more = f' … +{len(found) - 6}' if len(found) > 6 else ''
                problems.append(f'[page] /{rel.as_posix()}: Chinese text remains: {sample}{more}')
    elif '--dist' in sys.argv:
        problems.append('[page] website/dist/en not found; run `npx astro build` in website/ first')

    if problems:
        print('\n'.join(problems))
        print(f'\n{len(problems)} issue(s).')
        return 1
    print('English coverage complete.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
