#!/usr/bin/env python3
"""Run one generation round.

    python tools/story_pipeline/run_round.py --dry-run     # stub models, proves the loop
    python tools/story_pipeline/run_round.py               # live
    python tools/story_pipeline/run_round.py --no-taste    # ablation arm
    python tools/story_pipeline/run_round.py --models kimi,deepseek

Shape of a round (design doc, §一):

    12 baseline  = 4 models x 3 combos x 1 outline
     1 expansion = the new-elements slot, one model, rotating by round
     4 seed      = optional, same seed to all four models

One call per (model, combo), each asking for a single outline. Batching three outlines
into one call would lose all three to one timeout, and models nudge a batch's members
apart from each other, which narrows the range of any single one.

The invariant this file protects: for a given combo, all four models receive identical
bytes. Per-combo sha256 goes into round.json so that claim can be checked later rather
than trusted.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief as brief_mod
import store
from adapters import ADAPTERS, parse_outlines

MODEL_ORDER = ['claude', 'codex', 'kimi', 'deepseek']
BASE_SLOTS = ['consequence', 'contradiction', 'escalation', 'transposition']

STUB_STORY = {
    'title': '（dry run）某人做了一件不可能的事',
    'premise_line': '（dry run）用了某人的某条矛盾。',
    'kind': 'memory',
    'cast': ['haide'],
    'location': 'Courtyard',
    'nearest': '2026-09-09-seven-day-bite',
    'stands_beside': '（dry run）它带来了那一篇没有的东西。',
    'residue': '（dry run）从此某样东西再也没有变回去。',
    'new_elements': 'none',
    'story': '（dry run）这里本该是一篇完整的短篇故事。',
}
STUB = json.dumps(STUB_STORY, ensure_ascii=False)


def next_round_id(today: str) -> str:
    existing = sorted(d.name for d in store.CANDIDATES.glob(f'{today}-r*')) if store.CANDIDATES.exists() else []
    return f'{today}-r{len(existing) + 1:02d}'


def round_index() -> int:
    """How many rounds have run, used to rotate which model takes the expansion slot."""
    return len(list(store.CANDIDATES.glob('*-r*'))) if store.CANDIDATES.exists() else 0


def call(model: str, text: str, dry: bool) -> tuple[str, str | None]:
    """Returns (raw output, error). A failure costs one story, never the round."""
    if dry:
        return STUB, None
    try:
        return ADAPTERS[model].generate(text), None
    except Exception as exc:  # noqa: BLE001 - one model failing must not stop the others
        return '', f'{type(exc).__name__}: {exc}'


def to_candidate(raw: str, model: str, round_id: str, slot: str, taste: str) -> store.Candidate:
    outlines = parse_outlines(raw)
    base = dict(id=store.new_id(), round=round_id, slot=slot, model=model, taste_context=taste)
    if not outlines:
        return store.Candidate(**base, title='(unparsed)', parse_failed=True, raw=raw)
    o = outlines[0]
    return store.Candidate(
        **base,
        title=str(o.get('title', '')).strip(),
        premise_line=str(o.get('premise_line', '')).strip(),
        kind='extra' if o.get('kind') == 'extra' else 'memory',
        cast=o.get('cast') or [],
        location=str(o.get('location') or ''),
        nearest=str(o.get('nearest', '')).strip(),
        stands_beside=str(o.get('stands_beside', '')).strip(),
        residue=str(o.get('residue', '')).strip(),
        new_elements=o.get('new_elements', 'none'),
        story=str(o.get('story', '')).strip(),
        raw=raw,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='stub models; writes a real round')
    ap.add_argument('--no-taste', action='store_true', help='ablation arm: brief without the taste profile')
    ap.add_argument('--models', default=','.join(MODEL_ORDER))
    ap.add_argument('--slots', default=','.join(BASE_SLOTS), help='which premise slots to run')
    ap.add_argument('--no-expansion', action='store_true')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    models = [m.strip() for m in args.models.split(',') if m.strip()]
    unknown = [m for m in models if m not in ADAPTERS]
    if unknown:
        sys.exit(f'[round] unknown model(s): {", ".join(unknown)}')
    slots = [s.strip() for s in args.slots.split(',') if s.strip()]
    bad = [s for s in slots if s not in BASE_SLOTS]
    if bad:
        sys.exit(f'[round] unknown slot(s): {", ".join(bad)}; expected {", ".join(BASE_SLOTS)}')

    if not args.dry_run:
        blocked = [(m, ADAPTERS[m].available()[1]) for m in models if not ADAPTERS[m].available()[0]]
        if blocked:
            print('[round] these models are not usable right now:')
            for m, why in blocked:
                print(f'  {m}: {why}')
            sys.exit('[round] fix the above, or pass --models with only the usable ones, or --dry-run')

    today = dt.date.today().isoformat()
    round_id = next_round_id(today)
    taste = 'off' if args.no_taste else 'on'

    # One brief per slot; every model gets that slot's brief unchanged. The premise shape
    # is the controlled variable now — not a cast and a room.
    briefs = {slot: brief_mod.build(taste=not args.no_taste, slot=slot) for slot in slots}

    jobs = [(m, slot, briefs[slot]) for slot in slots for m in models]

    expansion_model = None
    if not args.no_expansion:
        expansion_model = MODEL_ORDER[round_index() % len(MODEL_ORDER)]
        if expansion_model not in models:
            expansion_model = models[0]
        briefs['expansion'] = brief_mod.build(taste=not args.no_taste, slot='expansion')
        jobs.append((expansion_model, 'expansion', briefs['expansion']))

    print(f'[round] {round_id}  taste={taste}  {len(jobs)} calls '
          f'({len(models)} models x {len(slots)} slots'
          + (f' + expansion:{expansion_model}' if expansion_model else '') + ')')
    print('[round] full short stories; allow up to half an hour. Candidates are written as they arrive.', flush=True)

    written, failed, unparsed = [], 0, 0
    # One worker per job: almost all of the elapsed time is spent waiting on a model, and
    # capping at four meant a single slow CLI call blocked three other models behind it.
    with futures.ThreadPoolExecutor(max_workers=min(len(jobs), 8)) as pool:
        futs = {pool.submit(call, m, text, args.dry_run): (m, slot) for m, slot, text in jobs}
        for fut in futures.as_completed(futs):
            m, slot = futs[fut]
            raw, err = fut.result()
            if err:
                failed += 1
                print(f'  FAIL {m:9} {slot:14} {err}')
                continue
            # Written as it arrives, not after the round. A long round used to show no
            # progress at all and would have lost every finished story to one interrupt.
            c = to_candidate(raw, m, round_id, slot, taste)
            unparsed += int(c.parse_failed)
            store.write(c)
            written.append(c)
            over = '  ⚠ 超出上限' if c.words() > store.MAX_STORY_CHARS else ''
            print(f'  ok   {m:9} {slot:14} {c.words()} 字{over}  {c.title}', flush=True)

    meta = {
        'round': round_id,
        'created': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'dry_run': args.dry_run,
        'taste_context': taste,
        'models': models,
        'slots': slots,
        'expansion_model': expansion_model,
        # The identical-input claim, made checkable rather than asserted.
        'brief_sha256': {slot: brief_mod.sha256(text) for slot, text in briefs.items()},
        'calls': len(jobs),
        'written': len(written),
        'failed': failed,
        'parse_failed': unparsed,
        'median_length': sorted(c.words() for c in written)[len(written) // 2] if written else 0,
    }
    store.write_round_meta(round_id, meta)

    print(f'\n[round] wrote {len(written)} stories to '
          f'{(store.CANDIDATES / round_id).relative_to(brief_mod.ROOT).as_posix()}')
    if failed:
        print(f'[round] {failed} call(s) failed')
    if unparsed:
        print(f'[round] {unparsed} response(s) could not be parsed; kept raw and flagged')
    print('[round] all candidates are `pending`. Review is the next step.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
