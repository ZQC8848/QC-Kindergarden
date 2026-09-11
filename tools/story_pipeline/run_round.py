#!/usr/bin/env python3
"""Run one generation round.

    python tools/story_pipeline/run_round.py --dry-run                 # stub models, proves the loop
    python tools/story_pipeline/run_round.py                           # live
    python tools/story_pipeline/run_round.py --min-chars 120 --max-chars 300
    python tools/story_pipeline/run_round.py --no-taste                # ablation arm
    python tools/story_pipeline/run_round.py --models kimi,deepseek
    python tools/story_pipeline/run_round.py --format default          # formats/<name>.json

Shape of a round:

    16 baseline  = 4 models x 4 premise slots x 1 outline
     1 expansion = the new-elements slot, one model, rotating by round
     N waitlist  = every shortlisted candidate still in the pool, rewritten by its own model

One call per (model, slot), each asking for a single outline. Batching several outlines
into one call would lose all of them to one timeout, and models nudge a batch's members
apart from each other, which narrows the range of any single one.

The invariant this file protects: for a given slot, all four models receive identical
bytes. That is why the outline ceiling is drawn once per slot rather than once per story,
and why each slot's sha256 goes into round.json, so the claim can be checked later rather
than trusted. Waitlist rewrites sit outside that comparison by construction, since each
rewrite brief is unique to one story, and they are recorded separately.
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import datetime as dt
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief as brief_mod
import rewrite as rewrite_mod
import store
from adapters import ADAPTERS, parse_outlines

MODEL_ORDER = ['claude', 'codex', 'kimi', 'deepseek']
BASE_SLOTS = ['consequence', 'contradiction', 'escalation', 'transposition']

# Candidate attributes a format field lands in directly. Anything else the format asks for
# is kept in Candidate.extra, so adding a field to the format never needs a change here.
KNOWN_FIELDS = ('title', 'premise_line', 'kind', 'cast', 'location', 'nearest',
                'stands_beside', 'residue', 'new_elements', 'outline')

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
    'outline': '（dry run）这里本该是一条不超过上限的大纲。',
}
STUB = json.dumps(STUB_STORY, ensure_ascii=False)


def next_round_id(today: str) -> str:
    existing = sorted(d.name for d in store.CANDIDATES.glob(f'{today}-r*')) if store.CANDIDATES.exists() else []
    return f'{today}-r{len(existing) + 1:02d}'


def round_index() -> int:
    """How many rounds have run, used to rotate which model takes the expansion slot."""
    return len(list(store.CANDIDATES.glob('*-r*'))) if store.CANDIDATES.exists() else 0


def latest_round() -> str | None:
    rounds = sorted(d.name for d in store.CANDIDATES.glob('*-r*')) if store.CANDIDATES.exists() else []
    return rounds[-1] if rounds else None


def pending_in(round_id: str | None) -> int:
    return sum(1 for c in store.load_round(round_id) if c.verdict == 'pending') if round_id else 0


def _display(path: Path) -> str:
    try:
        return path.relative_to(brief_mod.ROOT).as_posix()
    except ValueError:
        return str(path)


def call(model: str, text: str, dry: bool) -> tuple[str, str | None]:
    """Returns (raw output, error). A failure costs one story, never the round."""
    if dry:
        return STUB, None
    try:
        return ADAPTERS[model].generate(text), None
    except Exception as exc:  # noqa: BLE001 - one model failing must not stop the others
        return '', f'{type(exc).__name__}: {exc}'


def to_candidate(raw: str, model: str, round_id: str, slot: str, taste: str, *,
                 spec: dict | None = None, max_chars: int | None = None) -> store.Candidate:
    """Map one model reply onto a Candidate, using the output format to find its fields."""
    spec = spec or brief_mod.load_format()
    body_key = spec.get('body_field', 'outline')
    body_keys = [body_key] + [k for k in spec.get('body_aliases', []) if k != body_key]
    base = dict(id=store.new_id(), round=round_id, slot=slot, model=model, taste_context=taste,
                max_chars=max_chars, format_version=f"{spec.get('name', 'default')}@{spec.get('version', '?')}")
    outlines = parse_outlines(raw)
    if not outlines:
        return store.Candidate(**base, title='(unparsed)', parse_failed=True, raw=raw)
    o = outlines[0]
    # Valid JSON that is missing the field the whole exercise is about is worse than
    # unparseable output: it lands as an empty candidate and looks like a real one.
    # Kimi did exactly this once, returning a title and nothing else.
    body = next((str(o[k]).strip() for k in body_keys if str(o.get(k) or '').strip()), '')
    if not body:
        return store.Candidate(**base, title=str(o.get('title', '')).strip() or '(no outline)',
                               parse_failed=True, raw=raw)
    extra = {f['key']: o[f['key']] for f in spec.get('fields', [])
             if f['key'] in o and f['key'] not in KNOWN_FIELDS and f['key'] != body_key}
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
        outline=body,
        extra=extra,
        raw=raw,
    )


def draw_max_chars(slots: list[str], lo: int, hi: int, rng: random.Random) -> dict:
    """One outline ceiling per slot, shared by every model on that slot.

    QC asked for length to vary inside a range (2026-09-10). Drawing per story would hand
    the four models on one slot different ceilings, and a model could then look better
    only because it drew more room. Drawing per slot keeps the identical-brief invariant
    and still varies length across the round."""
    if isinstance(lo, bool) or isinstance(hi, bool) or not isinstance(lo, int) or not isinstance(hi, int):
        raise ValueError(f'the ceiling range must be two integers; got {lo!r}..{hi!r}')
    if not 1 <= lo <= hi <= store.MAX_PROSE_CHARS:
        raise ValueError(f'the ceiling range must satisfy 1 <= min <= max <= {store.MAX_PROSE_CHARS}; got {lo}..{hi}')
    return {slot: rng.randint(lo, hi) for slot in slots}


def run(*, models: list[str] | None = None, slots: list[str] | None = None, expansion: bool = True,
        taste: bool = True, dry: bool = False, min_chars: int = store.MAX_OUTLINE_CHARS,
        max_chars: int = store.MAX_OUTLINE_CHARS, fmt: str = brief_mod.DEFAULT_FORMAT,
        waitlist: bool = True, seed: int | None = None, log=print) -> dict:
    """Run one round and return its round.json.

    Raises ValueError for bad arguments and RuntimeError when a model the baseline needs
    cannot be used. Past that point failures are per story, never per round."""
    models = list(models or MODEL_ORDER)
    slots = list(slots or BASE_SLOTS)
    unknown = [m for m in models if m not in ADAPTERS]
    if unknown:
        raise ValueError(f'unknown model(s): {", ".join(unknown)}')
    bad = [s for s in slots if s not in BASE_SLOTS]
    if bad:
        raise ValueError(f'unknown slot(s): {", ".join(bad)}; expected {", ".join(BASE_SLOTS)}')

    spec = brief_mod.load_format(fmt)
    all_slots = slots + (['expansion'] if expansion else [])
    caps = draw_max_chars(all_slots, min_chars, max_chars, random.Random(seed))

    if not dry:
        blocked = [(m, ADAPTERS[m].available()[1]) for m in models if not ADAPTERS[m].available()[0]]
        if blocked:
            raise RuntimeError('these models are not usable right now: '
                               + '; '.join(f'{m}: {why}' for m, why in blocked)
                               + '. Pass models with only the usable ones, or dry_run.')

    round_id = next_round_id(dt.date.today().isoformat())
    taste_s = 'on' if taste else 'off'

    # One brief per slot; every model on that slot gets it unchanged.
    briefs = {slot: brief_mod.build(taste=taste, slot=slot, max_chars=caps[slot], fmt=spec) for slot in slots}
    jobs: list[tuple] = [('base', m, slot) for slot in slots for m in models]

    expansion_model = None
    if expansion:
        expansion_model = MODEL_ORDER[round_index() % len(MODEL_ORDER)]
        if expansion_model not in models:
            expansion_model = models[0]
        briefs['expansion'] = brief_mod.build(taste=taste, slot='expansion', max_chars=caps['expansion'], fmt=spec)
        jobs.append(('base', expansion_model, 'expansion'))

    # Every shortlisted candidate comes back, to the model that wrote it (QC, 2026-09-10).
    skipped = []
    for parent in (store.shortlist_pool() if waitlist else []):
        usable = parent.model in ADAPTERS and (dry or ADAPTERS[parent.model].available()[0])
        if not usable:
            skipped.append(parent.id)
            continue
        jobs.append(('rewrite', parent.model, parent))

    base_n = sum(1 for j in jobs if j[0] == 'base')
    rewrite_n = len(jobs) - base_n
    log(f'[round] {round_id}  taste={taste_s}  format={spec["name"]}@{spec["version"]}  {base_n} calls '
        f'({len(models)} models x {len(slots)} slots'
        + (f' + expansion:{expansion_model}' if expansion_model else '') + ')'
        + (f' + {rewrite_n} waitlist rewrite(s)' if rewrite_n else ''))
    log('[round] outline ceiling per slot: ' + '  '.join(f'{s}={caps[s]}' for s in all_slots))
    if skipped:
        log(f'[round] waitlist left for next round, model unavailable: {", ".join(skipped)}')

    def work(job):
        kind, model, target = job
        if kind == 'base':
            return call(model, briefs[target], dry)
        return rewrite_mod.run(target, 'waitlist', round_id=round_id, call=call,
                               to_candidate=to_candidate, dry=dry, fmt=spec)

    written, rewritten, retired, rewrite_meta = [], [], [], []
    failed = unparsed = 0
    # One worker per job: almost all of the elapsed time is spent waiting on a model, and
    # capping at four meant a single slow CLI call blocked three other models behind it.
    with futures.ThreadPoolExecutor(max_workers=max(1, min(len(jobs), 8))) as pool:
        futs = {pool.submit(work, job): job for job in jobs}
        for fut in futures.as_completed(futs):
            kind, model, target = futs[fut]
            if kind == 'base':
                raw, err = fut.result()
                if err:
                    failed += 1
                    log(f'  FAIL {model:9} {target:14} {err}')
                    continue
                # Written as it arrives, not after the round. A long round used to show no
                # progress at all and would have lost every finished story to one interrupt.
                c = to_candidate(raw, model, round_id, target, taste_s, spec=spec, max_chars=caps[target])
                unparsed += int(c.parse_failed)
                store.write(c)
                written.append(c)
                over = f'  ⚠ 超出 {c.ceiling()} 字上限' if c.over_limit() else ''
                log(f'  ok   {model:9} {target:14} {c.words()}/{c.ceiling()} 字{over}  {c.title}')
                continue
            try:
                child, sha = fut.result()
            except Exception as exc:  # noqa: BLE001 - a failed rewrite leaves its parent in the pool
                failed += 1
                log(f'  FAIL {model:9} rewrite of {target.id}: {exc}')
                continue
            if child is None:
                retired.append(target.id)
                log(f'  retired {target.id}: rewritten {store.MAX_REVISITS} times without being chosen')
                continue
            unparsed += int(child.parse_failed)
            rewritten.append(child)
            rewrite_meta.append({'id': child.id, 'parent': target.id, 'mode': 'waitlist', 'brief_sha256': sha,
                                 'max_chars': child.max_chars, 'revisit_count': child.revisit_count})
            log(f'  ok   {model:9} rewrite {target.id} -> {child.id}  '
                f'{child.words()}/{child.ceiling()} 字  {child.title}')

    lengths = sorted(c.words() for c in written)
    meta = {
        'round': round_id,
        'created': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'dry_run': dry,
        'taste_context': taste_s,
        'models': models,
        'slots': slots,
        'expansion_model': expansion_model,
        'format': {'name': spec['name'], 'version': spec['version'], 'sha256': spec['sha256']},
        'max_chars_range': [min_chars, max_chars],
        'max_chars': caps,
        'seed': seed,
        # The identical-input claim, made checkable rather than asserted.
        'brief_sha256': {slot: brief_mod.sha256(text) for slot, text in briefs.items()},
        'calls': base_n,
        'written': len(written),
        'failed': failed,
        'parse_failed': unparsed,
        'median_length': lengths[len(lengths) // 2] if lengths else 0,
        'waitlist_rewrites': rewrite_meta,
        'waitlist_retired': retired,
        'waitlist_skipped': skipped,
    }
    store.write_round_meta(round_id, meta)

    log(f'[round] wrote {len(written)} stories'
        + (f' and {len(rewritten)} rewrite(s)' if rewritten else '')
        + f' to {_display(store.CANDIDATES / round_id)}')
    if failed:
        log(f'[round] {failed} call(s) failed')
    if unparsed:
        log(f'[round] {unparsed} response(s) could not be parsed; kept raw and flagged')
    log('[round] all candidates are `pending`. Review is the next step.')
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='stub models; writes a real round')
    ap.add_argument('--no-taste', action='store_true', help='ablation arm: brief without the taste profile')
    ap.add_argument('--models', default=','.join(MODEL_ORDER))
    ap.add_argument('--slots', default=','.join(BASE_SLOTS), help='which premise slots to run')
    ap.add_argument('--no-expansion', action='store_true')
    ap.add_argument('--min-chars', type=int, default=store.MAX_OUTLINE_CHARS,
                    help='lower bound of the outline ceiling drawn per slot')
    ap.add_argument('--max-chars', type=int, default=store.MAX_OUTLINE_CHARS,
                    help='upper bound of the outline ceiling drawn per slot')
    ap.add_argument('--format', default=brief_mod.DEFAULT_FORMAT, help='output format, formats/<name>.json')
    ap.add_argument('--no-waitlist', action='store_true', help='do not rewrite shortlisted candidates this round')
    ap.add_argument('--seed', type=int, default=None, help='fix the ceiling draw; the drawn values are recorded either way')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    prev = latest_round()
    left = pending_in(prev)
    if left:
        print(f'[round] note: {left} candidate(s) in {prev} are still pending. Any of them you shortlist '
              'later will only come back in the round after this one.')
    try:
        run(models=[m.strip() for m in args.models.split(',') if m.strip()],
            slots=[s.strip() for s in args.slots.split(',') if s.strip()],
            expansion=not args.no_expansion, taste=not args.no_taste, dry=args.dry_run,
            min_chars=args.min_chars, max_chars=args.max_chars, fmt=args.format,
            waitlist=not args.no_waitlist, seed=args.seed,
            log=lambda line: print(line, flush=True))
    except (ValueError, RuntimeError) as exc:
        sys.exit(f'[round] {exc}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
