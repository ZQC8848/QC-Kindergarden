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

# Rewritten after round r01, where QC's own words were 尴尬 / 莫名其妙 / 寡淡 / 太日常
# and only one of the six original buckets ("就是不好笑") matched anything they said.
# The first two entries carry the defect T019 exists to name, and they are separate on
# purpose: 太日常 means the premise never left reality, 寡淡 means it did and still had
# no flavour. One round was enough to show the first set was guesswork.
REASONS = {
    'too_everyday': '太日常，前提没有超出现实',
    'bland': '寡淡，有前提但没味道',
    'cringe': '尴尬，笑点用力但没接住',
    'incoherent': '莫名其妙，动机或逻辑读不通',
    'not_funny': '就是不好笑',
    'off_character': '不像这个角色',
    'stale_joke': '梗太老',
    'duplicate': '和已有故事重复',
    'too_long': '超出长度上限，撑不住这个篇幅',
    'never_chosen': '备选三次未选中',   # written by the shortlist decay, not by QC
    'superseded': '在规则变更前生成，整轮作废',
}

MAX_REVISITS = 3

# Two different ceilings, deliberately separate.
#
# The pipeline generates outlines, and an outline is capped hard at 200 non-whitespace
# characters: r02 asked for full prose and the round came back at 817-4895 characters,
# which was both unreadable at review scale and the wrong unit of work.
#
# The prose ceiling is what a *finished* story may run to once it is drafted elsewhere -
# the longest accepted story (《幼儿园四大魔女》, 2086) plus 200. It is recorded here
# because taste rule T021 refers to it, not because this module enforces it.
MAX_OUTLINE_CHARS = 200
MAX_PROSE_CHARS = 2286

# Written when a round is cut because the rules it was produced under have since changed,
# rather than because each story failed on its own. Keeping these apart matters: they are
# not evidence about what QC dislikes, and mining them as such would poison the profile.



@dataclass
class Candidate:
    """One generated candidate: a premise and the outline of what happens.

    The outline body lives in the markdown, everything sortable lives in the frontmatter.
    Prose is not generated here — the pipeline picks premises, and the chosen ones get
    drafted separately, so what has to be judged at this stage is whether the premise is
    worth writing at all.
    """
    id: str
    round: str
    slot: str                      # consequence | contradiction | escalation | transposition | expansion
    model: str                     # never shown at review time
    taste_context: str             # on | off
    title: str = ''
    premise_line: str = ''         # what the model did with its slot
    kind: str = 'memory'           # memory | extra
    cast: list = field(default_factory=list)
    location: str = ''
    nearest: str = ''              # the existing story this one is closest in kind to
    stands_beside: str = ''        # why it earns its place next to that one
    residue: str = ''              # what this story leaves permanently changed
    new_elements: object = 'none'
    outline: str = ''              # what happens, at most MAX_OUTLINE_CHARS
    verdict: str = 'pending'
    reason: str | None = None
    notes: str | None = None
    revisit_count: int = 0
    decided_at: str | None = None
    parse_failed: bool = False
    raw: str = ''

    def path(self) -> Path:
        return CANDIDATES / self.round / f'{self.id}.md'

    def words(self) -> int:
        """Rough length. CJK has no spaces, so count characters and ignore whitespace."""
        return len(re.sub(r'\s+', '', self.outline))

    def over_limit(self) -> bool:
        return self.words() > MAX_OUTLINE_CHARS


def new_id() -> str:
    """Short random id. Random rather than sequential so nothing about the ordering of a
    review queue leaks which model produced what."""
    return 'c-' + secrets.token_hex(2)


# --------------------------------------------------------------------------- io

_SCALAR = ('id', 'round', 'slot', 'model', 'taste_context', 'title', 'kind', 'location',
           'nearest', 'verdict', 'reason', 'notes', 'decided_at')


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
    lines += ['---', '']
    for label, value in (('Premise', c.premise_line), ('Stands beside', c.stands_beside), ('Residue', c.residue)):
        if value:
            lines += [f'**{label}**　{value}', '']
    lines += ['---', '', c.outline.strip(), '']
    if c.parse_failed and c.raw:
        lines += ['<details><summary>无法解析的模型原始输出</summary>', '', '```', c.raw.strip()[:20000], '```', '', '</details>', '']
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
    data['premise_line'] = _field(body, 'Premise')
    data['stands_beside'] = _field(body, 'Stands beside')
    data['residue'] = _field(body, 'Residue')
    # The prose is everything after the horizontal rule that closes the metadata block.
    parts = re.split(r'^---\s*$', body, flags=re.M)
    data['outline'] = parts[-1].split('<details>')[0].strip() if len(parts) > 1 else ''
    data['raw'] = (re.search(r'```\n(.*?)\n```', body, re.S) or [None, ''])[1]
    known = {f for f in Candidate.__dataclass_fields__}
    return Candidate(**{k: v for k, v in data.items() if k in known})


def _field(body: str, label: str) -> str:
    m = re.search(rf'^\*\*{re.escape(label)}\*\*\s*(.+)$', body, re.M)
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
