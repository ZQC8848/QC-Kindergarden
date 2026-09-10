#!/usr/bin/env python3
"""Push a round's stories to Discord for reading. One story, one post.

    python tools/story_pipeline/publish.py --dry-run     # print, send nothing
    python tools/story_pipeline/publish.py               # send the latest round
    python tools/story_pipeline/publish.py --round 2026-09-09-r02 --all

Webhook, not a bot. That is a deliberate downgrade: an incoming webhook can only write,
so verdicts cannot come back as emoji reactions. Reading happens in Discord, judging
happens in the terminal with review.py. The trade is one surface less to build and
maintain against having to carry the id across.

Blind review still holds: nothing posted here names the model. `slot` is posted because
it says what the story was asked to be, which is part of reading it fairly; `model` is
not, and neither is `taste_context`.

Discord's limits shape the layout: 2000 characters per message, 4096 per embed
description, 1024 per embed field. So each story is a metadata embed followed by its
prose split across as many plain messages as it needs, cut on paragraph boundaries.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import store
from adapters import load_env

CONTENT_LIMIT = 1900      # 2000, with room for the continuation marker
FIELD_LIMIT = 1000        # 1024
THROTTLE = 1.2            # seconds between posts; webhooks rate-limit around 5 per 2s

KIND_COLOR = {'memory': 0x2C4A88, 'extra': 0xD39A34}
SLOT_LABEL = {
    'consequence': '后果位',
    'contradiction': '矛盾位',
    'escalation': '放大位',
    'transposition': '移植位',
    'expansion': '扩展位',
}


def webhook_url() -> str:
    url = load_env().get('DISCORD_REVIEW_WEBHOOK_URL')
    if not url:
        sys.exit('[publish] DISCORD_REVIEW_WEBHOOK_URL not set '
                 '(environment, repo-root .env, or ResearchAssets/config/story-pipeline.env)')
    return url


def post(url: str, payload: dict, dry: bool) -> None:
    if dry:
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:2500])
        print('-' * 60)
        return
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        # Cloudflare rejects urllib's default "Python-urllib/3.x" with a bare 403. The
        # sibling discord-notify script never hit this because `requests` sends its own
        # agent string. Discord asks API clients to identify themselves anyway.
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'QCKindergarten-StoryPipeline (https://github.com/ZQC8848/QC-Kindergarten, 0.1)',
        },
        method='POST',
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60):
                return
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 3:
                # Discord tells us how long to wait; obey it rather than guessing.
                retry = 2.0
                try:
                    retry = float(json.loads(exc.read().decode()).get('retry_after', 2.0))
                except Exception:  # noqa: BLE001 - the body is best-effort
                    pass
                time.sleep(retry + 0.5)
                continue
            raise
    raise RuntimeError('rate limited four times in a row')


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + '…'


def chunks(text: str, limit: int = CONTENT_LIMIT) -> list[str]:
    """Split prose on blank lines, then on single lines, never mid-sentence if avoidable."""
    out: list[str] = []
    buf = ''
    for para in text.split('\n\n'):
        piece = para.strip('\n')
        if len(piece) > limit:
            # A single paragraph over the limit: fall back to line-by-line, then hard cut.
            for line in piece.split('\n'):
                while len(line) > limit:
                    out.append((buf + '\n\n' + line[:limit]).strip() if buf else line[:limit])
                    buf, line = '', line[limit:]
                if len(buf) + len(line) + 2 > limit:
                    out.append(buf.strip())
                    buf = line
                else:
                    buf = f'{buf}\n{line}' if buf else line
            continue
        if len(buf) + len(piece) + 2 > limit:
            out.append(buf.strip())
            buf = piece
        else:
            buf = f'{buf}\n\n{piece}' if buf else piece
    if buf.strip():
        out.append(buf.strip())
    return out


def embed_for(c: store.Candidate) -> dict:
    fields = [
        {'name': '类型', 'value': '记忆事件' if c.kind == 'memory' else '番外', 'inline': True},
        {'name': '地点', 'value': c.location or '—', 'inline': True},
        {'name': '长度', 'value': f'{c.words()} 字', 'inline': True},
    ]
    if c.cast:
        fields.append({'name': '出场', 'value': clip('、'.join(c.cast), FIELD_LIMIT), 'inline': False})
    if c.premise_line:
        fields.append({'name': '前提', 'value': clip(c.premise_line, FIELD_LIMIT), 'inline': False})
    if c.stands_beside:
        near = f'`{c.nearest}`　' if c.nearest else ''
        fields.append({'name': '比照', 'value': clip(near + c.stands_beside, FIELD_LIMIT), 'inline': False})
    if c.residue:
        fields.append({'name': '残留', 'value': clip(c.residue, FIELD_LIMIT), 'inline': False})
    if c.new_elements not in ('none', None, [], ''):
        value = c.new_elements if isinstance(c.new_elements, str) else json.dumps(c.new_elements, ensure_ascii=False)
        fields.append({'name': '新元素', 'value': clip(str(value), FIELD_LIMIT), 'inline': False})
    return {
        'title': f'「{c.title}」' if c.title else c.id,
        'color': KIND_COLOR.get(c.kind, 0x6E7B8B),
        'fields': fields,
        'footer': {'text': f'{c.id} · {SLOT_LABEL.get(c.slot, c.slot)} · {c.round}'},
    }


def publish(c: store.Candidate, url: str, dry: bool) -> int:
    """One candidate, one message. Returns messages sent.

    An outline of at most 200 characters fits in the embed's description, so a candidate
    no longer needs the follow-up messages that full prose required.
    """
    embed = embed_for(c)
    embed['description'] = clip(c.outline or '（无大纲）', 4000)
    post(url, {'embeds': [embed]}, dry)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--round', default=None)
    ap.add_argument('--all', action='store_true', help='include already-sent and already-decided candidates')
    ap.add_argument('--only', help='publish just this candidate id')
    ap.add_argument('--dry-run', action='store_true', help='print the payloads, send nothing')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    rounds = sorted(d.name for d in store.CANDIDATES.glob('*-r*')) if store.CANDIDATES.exists() else []
    round_id = args.round or (rounds[-1] if rounds else None)
    if not round_id:
        sys.exit('[publish] no rounds yet')

    cands = store.load_round(round_id)
    if args.only:
        cands = [c for c in cands if c.id == args.only]
    elif not args.all:
        # Unsent and unjudged. A round arrives in stages — the slow models trail the fast
        # ones by many minutes — so this can be run repeatedly and only posts what is new.
        cands = [c for c in cands if c.verdict == 'pending' and not c.published_at]
    if not cands:
        print('[publish] nothing to send')
        return 0

    url = '' if args.dry_run else webhook_url()
    print(f'[publish] {round_id}: {len(cands)} stor{"y" if len(cands) == 1 else "ies"}'
          + (' (dry run)' if args.dry_run else ''))

    # The header introduces the round and carries the verdict commands, so it belongs at
    # the top once. A round is now published in stages as the slow models land, and
    # without this flag every follow-up run repeated it.
    meta_path = store.CANDIDATES / round_id / 'round.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
    header = (
        f'## 新一轮故事 · `{round_id}`\n'
        f'{len(cands)} 篇，作者匿名。读完在终端裁决：\n'
        '```\npython tools/story_pipeline/review.py <id> select\n'
        'python tools/story_pipeline/review.py <id> discard --reason too_everyday\n'
        'python tools/story_pipeline/review.py <id> shortlist\n'
        'python tools/story_pipeline/review.py <id> revise --notes "..."\n```'
    )
    total = 0
    if not meta.get('header_posted'):
        post(url, {'content': header}, args.dry_run)
        total = 1
        if not args.dry_run and meta:
            meta['header_posted'] = True
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n'
            )

    for c in cands:
        if not args.dry_run:
            time.sleep(THROTTLE)
        total += publish(c, url, args.dry_run)
        if not args.dry_run:
            store.mark_published(c, now=dt.datetime.now().astimezone().isoformat(timespec='seconds'))
        print(f'  sent {c.id}  {c.words()} 字  「{c.title}」')

    print(f'[publish] {total} message(s) '
          + ('rendered' if args.dry_run else 'posted'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
