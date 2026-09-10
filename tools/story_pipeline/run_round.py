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

STUB = json.dumps(
    [
        {
            'hook': '（dry run）某人在某处干了一件蠢事。',
            'turn': '（dry run）另一个人早就知道，只是没说。',
            'kind': 'memory',
            'cast': ['haide'],
            'location': 'Courtyard',
            'differs_from': '与 2026-09-09-seven-day-bite 相近，但起因不同。',
            'new_elements': 'none',
        }
    ],
    ensure_ascii=False,
)


def next_round_id(today: str) -> str:
    existing = sorted(d.name for d in store.CANDIDATES.glob(f'{today}-r*')) if store.CANDIDATES.exists() else []
    return f'{today}-r{len(existing) + 1:02d}'


def round_index() -> int:
    """How many rounds have run, used to rotate which model takes the expansion slot."""
    return len(list(store.CANDIDATES.glob('*-r*'))) if store.CANDIDATES.exists() else 0


def call(model: str, text: str, dry: bool) -> tuple[str, str | None]:
    """Returns (raw output, error). A failure costs one outline, never the round."""
    if dry:
        return STUB, None
    try:
        return ADAPTERS[model].generate(text), None
    except Exception as exc:  # noqa: BLE001 - one model failing must not stop the others
        return '', f'{type(exc).__name__}: {exc}'


def to_candidate(raw: str, model: str, round_id: str, slot: str, taste: str, fallback_combo: dict) -> store.Candidate:
    outlines = parse_outlines(raw)
    if not outlines:
        return store.Candidate(
            id=store.new_id(), round=round_id, slot=slot, model=model, taste_context=taste,
            hook='(unparsed)', turn='', kind='memory', cast=fallback_combo['cast'],
            location=fallback_combo['location'], parse_failed=True, raw=raw,
        )
    o = outlines[0]
    return store.Candidate(
        id=store.new_id(), round=round_id, slot=slot, model=model, taste_context=taste,
        hook=str(o.get('hook', '')).strip(),
        turn=str(o.get('turn', '')).strip(),
        kind='extra' if o.get('kind') == 'extra' else 'memory',
        cast=o.get('cast') or fallback_combo['cast'],
        location=str(o.get('location') or fallback_combo['location']),
        differs_from=str(o.get('differs_from', '')).strip(),
        new_elements=o.get('new_elements', 'none'),
        raw=raw,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='stub models; writes a real round')
    ap.add_argument('--no-taste', action='store_true', help='ablation arm: brief without the taste profile')
    ap.add_argument('--models', default=','.join(MODEL_ORDER))
    ap.add_argument('--combos', type=int, default=3)
    ap.add_argument('--no-expansion', action='store_true')
    ap.add_argument('--seed-text', default=None, help="QC's own idea; sent to every model")
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    models = [m.strip() for m in args.models.split(',') if m.strip()]
    unknown = [m for m in models if m not in ADAPTERS]
    if unknown:
        sys.exit(f'[round] unknown model(s): {", ".join(unknown)}')

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
    seed = abs(hash(round_id)) % (2**31)

    # One brief per combo; every model gets that combo's brief unchanged.
    _, combos = brief_mod.build(taste=not args.no_taste, n=args.combos, seed=seed)
    briefs = []
    for combo in combos:
        text, _ = brief_mod.build(taste=not args.no_taste, combos=[combo])
        briefs.append(text)

    jobs = []   # (model, slot, brief text, combo)
    for combo, text in zip(combos, briefs):
        for m in models:
            jobs.append((m, 'baseline', text, combo))

    expansion_model = None
    if not args.no_expansion:
        expansion_model = MODEL_ORDER[round_index() % len(MODEL_ORDER)]
        if expansion_model not in models:
            expansion_model = models[0]
        exp_text, exp_combos = brief_mod.build(taste=not args.no_taste, expansion=True, seed=seed + 1)
        jobs.append((expansion_model, 'expansion', exp_text, exp_combos[0]))

    if args.seed_text:
        seed_text, seed_combos = brief_mod.build(taste=not args.no_taste, n=1, seed=seed + 2)
        seed_text += f'\n## QC 的种子\n\n请基于下面这个想法写大纲，扩写它而不是替换它：\n\n{args.seed_text}\n'
        for m in models:
            jobs.append((m, 'seed', seed_text, seed_combos[0]))

    print(f'[round] {round_id}  taste={taste}  {len(jobs)} calls '
          f'({len(models)} models x {len(combos)} combos'
          + (f' + expansion:{expansion_model}' if expansion_model else '')
          + (f' + seed x{len(models)}' if args.seed_text else '') + ')')

    # HTTP models run in parallel; the CLIs each start an agent loop and are slow, so
    # they are capped rather than fanned out.
    results = []
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(call, m, text, args.dry_run): (m, slot, combo) for m, slot, text, combo in jobs}
        for fut in futures.as_completed(futs):
            m, slot, combo = futs[fut]
            raw, err = fut.result()
            results.append((m, slot, combo, raw, err))
            print(f'  {"FAIL" if err else "ok  "} {m:9} {slot:9} {combo["location"]:18} {err or ""}')

    written, failed, unparsed = [], 0, 0
    for m, slot, combo, raw, err in results:
        if err:
            failed += 1
            continue
        c = to_candidate(raw, m, round_id, slot, taste, combo)
        unparsed += int(c.parse_failed)
        store.write(c)
        written.append(c)

    meta = {
        'round': round_id,
        'created': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'dry_run': args.dry_run,
        'taste_context': taste,
        'models': models,
        'expansion_model': expansion_model,
        'seeded': bool(args.seed_text),
        'combos': combos,
        # The identical-input claim, made checkable rather than asserted.
        'brief_sha256': {c['location']: brief_mod.sha256(t) for c, t in zip(combos, briefs)},
        'calls': len(jobs),
        'written': len(written),
        'failed': failed,
        'parse_failed': unparsed,
    }
    store.write_round_meta(round_id, meta)

    print(f'\n[round] wrote {len(written)} candidates to '
          f'{(store.CANDIDATES / round_id).relative_to(brief_mod.ROOT).as_posix()}')
    if failed:
        print(f'[round] {failed} call(s) failed')
    if unparsed:
        print(f'[round] {unparsed} response(s) could not be parsed; kept raw and flagged')
    print('[round] all candidates are `pending`. Review is the next step.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
