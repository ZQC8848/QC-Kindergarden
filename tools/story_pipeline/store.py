#!/usr/bin/env python3
"""The candidate store: one markdown file per outline, plus the verdict state machine.

Deliberately files and not a database. Everything else in this project is greppable and
diffable in git, and the value of the discard pile is that someone can read it later —
a binary store would be the one opaque thing in the repo.

Candidates live in the private submodule because they carry QC's raw reasons for
rejecting stories about friends' fictional counterparts. Only selected, written stories
graduate to the public repo's stories/.

    ResearchAssets/story-candidates/<round-id>/
        c-a7f3.md
        round.json
"""
from __future__ import annotations

import json
import re
import secrets
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANDIDATES = ROOT / 'ResearchAssets' / 'story-candidates'

VERDICTS = ('pending', 'discarded', 'shortlisted', 'selected', 'selected_with_notes')
SELECTED = ('selected', 'selected_with_notes')

# Kept short on purpose: six coarse buckets QC can hit in one click. If most discards
# land in "就是不好笑" after a few rounds the set is too coarse and should be split —
# that is a decision to make from the distribution, not up front.
REASONS = {
    'off_character': '不像这个角色',
    'stale_joke': '梗太老',
    'too_mild': '太温和',
    'no_causality': '没有因果',
    'duplicate': '和已有故事重复',
    'not_funny': '就是不好笑',
    'never_chosen': '备选三次未选中',
}

MAX_REVISITS = 3


@dataclass
class Candidate:
    id: str
    round: str
    slot: str                      # baseline | expansion | seed
    model: str                     # never shown at review time
    taste_context: str             # on | off
    hook: str
    turn: str
    kind: str                      # memory | extra
    cast: list = field(default_factory=list)
    location: str = ''
    differs_from: str = ''
    new_elements: object = 'none'
    verdict: str = 'pending'
    reason: str | None = None
    notes: str | None = None
    revisit_count: int = 0
    decided_at: str | None = None
    parse_failed: bool = False
    raw: str = ''

    def path(self) -> Path:
        return CANDIDATES / self.round / f'{self.id}.md'


def new_id() -> str:
    """Short random id. Random rather than sequential so nothing about the ordering of a
    review queue leaks which model produced what."""
    return 'c-' + secrets.token_hex(2)


# --------------------------------------------------------------------------- io

_SCALAR = ('id', 'round', 'slot', 'model', 'taste_context', 'kind', 'location',
           'differs_from', 'verdict', 'reason', 'notes', 'decided_at')


def _yaml_scalar(v) -> str:
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    s = str(v)
    return json.dumps(s, ensure_ascii=False) if re.search(r'[:#\n"\']|^\s|\s$', s) else s


def write(c: Candidate) -> Path:
    p = c.path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ['---']
    for k in _SCALAR:
        lines.append(f'{k}: {_yaml_scalar(getattr(c, k))}')
    lines.append('cast: ' + json.dumps(c.cast, ensure_ascii=False))
    lines.append('new_elements: ' + json.dumps(c.new_elements, ensure_ascii=False))
    lines.append(f'revisit_count: {c.revisit_count}')
    lines.append(f'parse_failed: {"true" if c.parse_failed else "false"}')
    lines += ['---', '', f'**Hook**　{c.hook}', '', f'**Turn**　{c.turn}', '']
    if c.differs_from:
        lines += [f'**与已有故事的区别**　{c.differs_from}', '']
    if c.raw:
        lines += ['<details><summary>模型原始输出</summary>', '', '```', c.raw.strip(), '```', '', '</details>', '']
    p.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    return p


def read(path: Path) -> Candidate:
    md = path.read_text(encoding='utf-8')
    fm = re.match(r'^---\r?\n(.*?)\r?\n---', md, re.S)
    if not fm:
        raise ValueError(f'{path} has no frontmatter')
    data = {}
    for line in fm.group(1).splitlines():
        m = re.match(r'^(\w+):\s*(.*)$', line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v in ('null', ''):
            data[k] = None
        elif v in ('true', 'false'):
            data[k] = v == 'true'
        elif v.startswith(('[', '{', '"')):
            try:
                data[k] = json.loads(v)
            except json.JSONDecodeError:
                data[k] = v
        elif re.fullmatch(r'-?\d+', v):
            data[k] = int(v)
        else:
            data[k] = v
    body = md[fm.end():]
    data.setdefault('cast', [])
    data['hook'] = _field(body, 'Hook')
    data['turn'] = _field(body, 'Turn')
    data['raw'] = (re.search(r'```\n(.*?)\n```', body, re.S) or [None, ''])[1]
    known = {f for f in Candidate.__dataclass_fields__}
    return Candidate(**{k: v for k, v in data.items() if k in known})


def _field(body: str, label: str) -> str:
    m = re.search(rf'^\*\*{label}\*\*\s*(.+)$', body, re.M)
    return m.group(1).strip() if m else ''


def load_round(round_id: str) -> list[Candidate]:
    d = CANDIDATES / round_id
    return [read(p) for p in sorted(d.glob('c-*.md'))] if d.exists() else []


def load_all() -> list[Candidate]:
    out = []
    for d in sorted(CANDIDATES.glob('*/')):
        out += load_round(d.name)
    return out


# --------------------------------------------------------------------------- verdicts

def decide(c: Candidate, verdict: str, *, reason: str | None = None, notes: str | None = None, now: str) -> Candidate:
    """Apply a verdict, enforcing the two rules that make the archive worth keeping."""
    if verdict not in VERDICTS:
        raise ValueError(f'unknown verdict {verdict!r}; expected one of {VERDICTS}')
    # A discard without a reason is the failure mode the whole research pile exists to
    # avoid: six months later nobody can say why it was cut.
    if verdict == 'discarded' and not reason:
        raise ValueError('a discard must carry a reason; one of: ' + ', '.join(REASONS))
    if reason and reason not in REASONS:
        raise ValueError(f'unknown reason {reason!r}; expected one of {", ".join(REASONS)}')
    if verdict == 'selected_with_notes' and not notes:
        raise ValueError('selected_with_notes must carry the requested changes')
    c.verdict = verdict
    c.reason = reason
    c.notes = notes
    c.decided_at = now
    write(c)
    return c


def revisit(c: Candidate, *, now: str) -> Candidate:
    """Pull a shortlisted candidate back into a round.

    An unbounded shortlist becomes a landfill: it only grows, and by round ten every
    round is polluted with ideas that were never quite good enough. After MAX_REVISITS
    the candidate is retired into the research pile, and that retirement is itself a
    signal about which kinds of premise always fall just short.
    """
    if c.verdict != 'shortlisted':
        raise ValueError(f'{c.id} is {c.verdict}, not shortlisted')
    c.revisit_count += 1
    if c.revisit_count > MAX_REVISITS:
        return decide(c, 'discarded', reason='never_chosen', now=now)
    write(c)
    return c


def shortlist_pool() -> list[Candidate]:
    """Shortlisted candidates still eligible to be pulled, least-revisited first."""
    pool = [c for c in load_all() if c.verdict == 'shortlisted' and c.revisit_count <= MAX_REVISITS]
    return sorted(pool, key=lambda c: (c.revisit_count, c.id))


# --------------------------------------------------------------------------- round meta

def write_round_meta(round_id: str, meta: dict) -> Path:
    p = CANDIDATES / round_id / 'round.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return p


def stats(round_id: str) -> dict:
    """Per-model verdict distribution for one round. Read after review, never before —
    this is the number blind review exists to protect."""
    out: dict = {}
    for c in load_round(round_id):
        row = out.setdefault(c.model, {v: 0 for v in VERDICTS})
        row[c.verdict] += 1
    for model, row in out.items():
        total = sum(row.values()) or 1
        row['accept_rate'] = round((row['selected'] + row['selected_with_notes']) / total, 3)
    return out


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    rounds = sorted(d.name for d in CANDIDATES.glob('*/')) if CANDIDATES.exists() else []
    if not rounds:
        print('[store] no rounds yet')
        return 0
    for r in rounds:
        cs = load_round(r)
        counts = {v: sum(1 for c in cs if c.verdict == v) for v in VERDICTS}
        print(f'{r}: {len(cs)} candidates  ' + '  '.join(f'{k}={v}' for k, v in counts.items() if v))
    pool = shortlist_pool()
    print(f'\nshortlist pool: {len(pool)}' + (f" (revisits: {[c.revisit_count for c in pool]})" if pool else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
