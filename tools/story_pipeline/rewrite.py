#!/usr/bin/env python3
"""Rewrite a candidate with QC's notes, sent back to the model that wrote it.

Two triggers, one mechanism:

- waitlist: a shortlisted candidate comes back in the *next* round. run_round.py pulls
  every one still in the pool and calls this for each.
- revise: a candidate selected with notes is rewritten *immediately*. The review site
  calls this in the background the moment QC submits, and the rewrite lands in the same
  round for QC to approve.

The rewrite goes to the same model on purpose. What a rewrite tests is whether this author
can fix what QC pointed at; handing it to another model would make it a new candidate
wearing an old id.

Rewrites stay out of per-model baseline statistics (store.stats). That comparison rests on
every model on a slot receiving an identical brief, and a rewrite brief is by construction
unique to one story.

    python tools/story_pipeline/rewrite.py c-a7f3                 # revise now, same round
    python tools/story_pipeline/rewrite.py c-a7f3 --dry-run       # stub model
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief as brief_mod
import store

MODES = ('waitlist', 'revise')


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def ceiling_for(parent: store.Candidate) -> int:
    """QC's override for this story wins, then the ceiling it was written under, then the default."""
    return parent.rewrite_max_chars or parent.max_chars or store.MAX_OUTLINE_CHARS


def rewrite_request(parent: store.Candidate, mode: str) -> dict:
    return {
        'mode': mode,
        'title': parent.title,
        'outline': parent.outline,
        'score': parent.score,
        'notes': parent.notes or '',
    }


def build_brief(parent: store.Candidate, mode: str, *, fmt=brief_mod.DEFAULT_FORMAT) -> tuple[str, int, dict]:
    """The slot brief the parent was written under, at its rewrite ceiling, plus QC's notes."""
    spec = fmt if isinstance(fmt, dict) else brief_mod.load_format(fmt)
    ceiling = ceiling_for(parent)
    text = brief_mod.build(taste=parent.taste_context != 'off', slot=parent.slot, max_chars=ceiling,
                           fmt=spec, rewrite=rewrite_request(parent, mode))
    return text, ceiling, spec


def run(parent: store.Candidate, mode: str, *, round_id: str, call, to_candidate,
        dry: bool = False, fmt=brief_mod.DEFAULT_FORMAT, now: str | None = None):
    """Rewrite `parent` once.

    Returns (child, brief_sha256), or (None, None) when a waitlist lineage has already been
    rewritten MAX_REVISITS times and is retired instead. `call` and `to_candidate` come from
    run_round.py; they are passed in so this module never imports it.

    The parent is left alone until the model has answered: a timeout raises before anything
    is written, so a shortlisted parent stays in the pool, uncounted, and comes back next round.
    """
    if mode not in MODES:
        raise ValueError(f'unknown rewrite mode {mode!r}; expected one of {", ".join(MODES)}')
    now = now or now_iso()
    if mode == 'waitlist' and parent.revisit_count >= store.MAX_REVISITS:
        store.revisit(parent, now=now)   # passes MAX_REVISITS, so this retires it as never_chosen
        return None, None

    text, ceiling, spec = build_brief(parent, mode, fmt=fmt)
    raw, err = call(parent.model, text, dry)
    if err:
        raise RuntimeError(f'{parent.model} could not rewrite {parent.id}: {err}')

    child = to_candidate(raw, parent.model, round_id, parent.slot, parent.taste_context,
                         spec=spec, max_chars=ceiling)
    child.parent = parent.id
    child.rewrite = mode
    if mode == 'waitlist':
        # The lineage shares one budget: a rewrite inherits the count, so shortlisting it
        # again cannot restart the clock.
        parent = store.revisit(parent, now=now)
    child.revisit_count = parent.revisit_count
    store.write(child)
    store.link_rewrite(parent, child)
    return child, brief_mod.sha256(text)


def main() -> int:
    import run_round   # imported here: run_round imports this module at the top

    ap = argparse.ArgumentParser(description='Rewrite one candidate with QC notes, using the model that wrote it.')
    ap.add_argument('id')
    ap.add_argument('--mode', choices=MODES, default='revise')
    ap.add_argument('--dry-run', action='store_true', help='stub model')
    ap.add_argument('--format', default=brief_mod.DEFAULT_FORMAT, help='output format, formats/<name>.json')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parent = store.find(args.id)
    if not parent:
        sys.exit(f'[rewrite] no candidate {args.id!r}')
    round_id = parent.round if args.mode == 'revise' else (run_round.latest_round() or parent.round)
    try:
        child, _sha = run(parent, args.mode, round_id=round_id, call=run_round.call,
                          to_candidate=run_round.to_candidate, dry=args.dry_run, fmt=args.format)
    except (ValueError, RuntimeError) as exc:
        sys.exit(f'[rewrite] {exc}')
    if child is None:
        print(f'[rewrite] {parent.id} had used up its rewrites and was retired')
        return 0
    print(f'[rewrite] {parent.id} -> {child.id} in {child.round}  {child.words()}/{child.ceiling()} 字  {child.title}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
