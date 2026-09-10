#!/usr/bin/env python3
"""Blind review from the terminal — the stand-in for the Discord bot.

    python tools/story_pipeline/review.py                          # list pending, blind
    python tools/story_pipeline/review.py --show c-a7f3            # read the whole story
    python tools/story_pipeline/review.py c-a7f3 discard --reason stale_joke
    python tools/story_pipeline/review.py c-a7f3 shortlist --notes "好在哪，缺什么"
    python tools/story_pipeline/review.py c-a7f3 select
    python tools/story_pipeline/review.py c-a7f3 revise --notes "把结尾收短"
    python tools/story_pipeline/review.py --stats                   # after review only

Blind means blind: nothing this tool prints reveals which model wrote a candidate, and
--stats refuses to run while anything in the round is still pending. Knowing the author
mid-review is what turns a preference into a habit and quietly ruins both the choosing
and the per-model numbers.

Build the Discord bot only once a few rounds have proved the outlines are worth the
trouble of one.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import store

VERDICT_ALIASES = {
    'discard': 'discarded',
    'shortlist': 'shortlisted',
    'select': 'selected',
    'revise': 'selected_with_notes',
}


def latest_round() -> str | None:
    rounds = sorted(d.name for d in store.CANDIDATES.glob('*-r*')) if store.CANDIDATES.exists() else []
    return rounds[-1] if rounds else None


def find(cid: str) -> store.Candidate:
    for c in store.load_all():
        if c.id == cid:
            return c
    sys.exit(f'[review] no candidate {cid!r}')


def show(c: store.Candidate, *, blind: bool = True, full: bool = False) -> None:
    over = ' ⚠超上限' if c.over_limit() else ''
    print(f'\n{c.id}  「{c.title}」  [{c.kind}] {c.location or "-"}  {c.words()} 字{over}')
    if not blind:
        print(f'  model: {c.model}  taste: {c.taste_context}  slot: {c.slot}')
    if c.parse_failed:
        print('  !! 模型输出无法解析；原始内容在文件里')
    if c.premise_line:
        print(f'  前提  {c.premise_line}')
    if c.cast:
        print(f'  出场  {", ".join(c.cast)}')
    if c.stands_beside:
        print(f'  比照  {c.nearest} — {c.stands_beside}')
    if c.residue:
        print(f'  残留  {c.residue}')
    if c.new_elements not in ('none', None, [], ''):
        print(f'  新元素 {c.new_elements}')
    if c.outline:
        print()
        for line in c.outline.splitlines():
            print(f'  {line}')
    if c.verdict != 'pending':
        tail = f' ({store.REASONS.get(c.reason, c.reason)})' if c.reason else ''
        print(f'  -> {c.verdict}{tail}' + (f'  notes: {c.notes}' if c.notes else ''))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('id', nargs='?', help='candidate id')
    ap.add_argument('verdict', nargs='?', choices=list(VERDICT_ALIASES), help='discard | shortlist | select | revise')
    ap.add_argument('--reason', choices=list(store.REASONS), help='required for discard')
    ap.add_argument('--notes', help='required for revise')
    ap.add_argument('--round', default=None)
    ap.add_argument('--show', metavar='ID')
    ap.add_argument('--all', action='store_true', help='include already-decided candidates')
    ap.add_argument('--stats', action='store_true', help='reveal per-model results (review must be complete)')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    round_id = args.round or latest_round()
    if not round_id:
        print('[review] no rounds yet — run run_round.py first')
        return 0

    if args.show:
        show(find(args.show), blind=True, full=True)
        return 0

    if args.stats:
        pending = [c for c in store.load_round(round_id) if c.verdict == 'pending']
        if pending:
            print(f'[review] {len(pending)} candidate(s) still pending in {round_id}.')
            print('  Per-model results stay hidden until the round is fully judged —'
                  ' seeing them early is what blind review is for.')
            return 1
        print(f'{round_id}\n')
        print(f'{"model":10} {"sel":>4} {"rev":>4} {"short":>6} {"disc":>5} {"accept":>7}')
        for model, row in sorted(store.stats(round_id).items()):
            print(f'{model:10} {row["selected"]:>4} {row["selected_with_notes"]:>4} '
                  f'{row["shortlisted"]:>6} {row["discarded"]:>5} {row["accept_rate"]:>7.0%}')
        reasons: dict[str, int] = {}
        for c in store.load_round(round_id):
            if c.reason:
                reasons[c.reason] = reasons.get(c.reason, 0) + 1
        if reasons:
            print('\ndiscard reasons:')
            for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
                print(f'  {v:>3}  {store.REASONS[k]}')
        return 0

    if not args.id:
        cands = store.load_round(round_id)
        pending = [c for c in cands if c.verdict == 'pending' or args.all]
        print(f'{round_id}: {len(pending)} of {len(cands)} to review')
        for c in pending:
            show(c, blind=True)
        if pending:
            print('\nverdicts:  discard --reason X  |  shortlist  |  select  |  revise --notes "..."')
            print('reasons:   ' + '  '.join(f'{k}={v}' for k, v in store.REASONS.items() if k not in ('never_chosen', 'generation_failed')))
        return 0

    if not args.verdict:
        sys.exit('[review] give a verdict: discard | shortlist | select | revise')
    c = find(args.id)
    now = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    try:
        c = store.decide(c, VERDICT_ALIASES[args.verdict], reason=args.reason, notes=args.notes, now=now)
    except ValueError as exc:
        sys.exit(f'[review] {exc}')
    show(c, blind=True)
    left = sum(1 for x in store.load_round(c.round) if x.verdict == 'pending')
    print(f'\n{left} left in {c.round}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
