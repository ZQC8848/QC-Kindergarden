#!/usr/bin/env python3
"""Local review site for story candidates: read a round, score it, send each story on.

    python tools/story_review/server.py                # live: the real candidates, real models
    python tools/story_review/server.py --dry-run      # a throwaway copy of the candidates, stub models
    python tools/story_review/server.py --port 4388 --no-open

Local only by design. It binds to 127.0.0.1, writes into the private ResearchAssets
submodule, and has nothing to do with the Vercel site.

What it guarantees, and where:

- Blind review. Nothing sent to the browser names a model (blind()); per-model numbers are
  served only once a round has nothing pending (Review.stats). review.py enforces the same
  rule in the terminal.
- One set of rules. Verdicts go through store.decide, rewrites through rewrite.run, rounds
  through run_round.run. The site adds one rule of its own, from QC: a discard or a
  shortlist must say why in the text box.
- The score decides the destination (store.SCORE_BANDS). Selected with notes is rewritten
  at once by the same model and lands in the same round for approval. Shortlisted stories
  are rewritten only when the next round is generated.
- Generation waits for review. Generating is refused while any story is pending or a
  rewrite is still running, because the next round's waitlist is only final then.
- A dry run never touches the real archive. Without --candidates it works on a copy.
- The Google key stays here. English mode posts text to /api/translate and this server
  calls Google (translate.py), so the key never reaches the page.
"""
from __future__ import annotations

import argparse
import atexit
import datetime as dt
import json
import queue
import re
import shutil
import sys
import tempfile
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PIPELINE = ROOT / 'tools' / 'story_pipeline'
WEBSITE = ROOT / 'website'
STATIC = HERE / 'static'
sys.path.insert(0, str(PIPELINE))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools'))

import adapters  # noqa: E402
import brief as brief_mod  # noqa: E402
import rewrite as rewrite_mod  # noqa: E402
import run_round  # noqa: E402
import store  # noqa: E402
import taste_sync  # noqa: E402
import translate as translate_mod  # noqa: E402

# Blind review covers the logs too. run_round prints lines like
# `ok   kimi      escalation     180/200 字  标题`, and a rewrite that times out says which
# model timed out; either one names a story's author. Every line the page or this terminal
# shows goes through scrub(). The candidate files and round.json keep the real names.
MODEL_NAME_RE = re.compile(
    r'(?<![A-Za-z])(' + '|'.join(sorted(map(re.escape, run_round.ADAPTERS), key=len, reverse=True)) + r')(?![A-Za-z])',
    re.IGNORECASE,
)


def scrub(text: str) -> str:
    return MODEL_NAME_RE.sub('[model]', text)


ID_RE = re.compile(r'^c-[0-9a-f]{4,16}$')
SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{0,40}$')
ROUND_RE = re.compile(r'^[\w.-]{1,64}$')

# Reasons the system writes. They are never QC's judgement, so they are not offered as chips.
SYSTEM_REASONS = {'never_chosen', 'generation_failed', 'superseded'}

# The only candidate fields the browser ever receives. `model`, `taste_context` and `raw`
# are left out on purpose: the first is what blind review hides, the second is the hidden
# arm of the ablation, and the third can quote a model's own chatter.
PUBLIC_FIELDS = (
    'id', 'round', 'slot', 'kind', 'title', 'outline', 'cast', 'location', 'nearest',
    'premise_line', 'stands_beside', 'residue', 'new_elements', 'extra',
    'verdict', 'reason', 'reasons', 'notes', 'score', 'decided_at',
    'parent', 'rewrite', 'rewritten_as', 'revisit_count', 'max_chars', 'rewrite_max_chars',
    'parse_failed', 'format_version',
)

# Set explicitly: on Windows, mimetypes reads the registry, which can map .js to text/plain,
# and browsers refuse to run a module script served that way.
CONTENT_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
}

# Posters are a few hundred KB each and the page shows them on every card; everything else,
# the page itself included, is re-read on each request so edits show up on reload.
ASSET_CACHE = 'max-age=3600'

# English labels for the page's fixed vocabulary. These are written, not machine-translated:
# they are few, they never change per story, and they should read the same every time.
SLOTS_EN = {
    'consequence': 'Consequence',
    'contradiction': 'Contradiction',
    'escalation': 'Escalation',
    'transposition': 'Transposition',
    'expansion': 'Expansion',
}
REASONS_EN = {
    'too_everyday': 'Too everyday: the premise never leaves real life',
    'bland': 'Bland: a premise, but no flavour',
    'cringe': 'Cringe: tries hard for the laugh and misses',
    'incoherent': "Doesn't add up: motive or logic breaks",
    'not_funny': 'Just not funny',
    'off_character': "Doesn't sound like the character",
    'stale_joke': 'Stale joke',
    'duplicate': 'Repeats an existing story',
    'too_long': "Over the length cap, and can't carry it",
    'never_chosen': 'Shortlisted three times, never chosen',
    'superseded': 'Generated before a rule change; round voided',
    'breaks_canon': 'Breaks canon (the world, or who knows what)',
    'forced_sequel': 'Forces a sequel onto a deliberately open ending',
    'generation_failed': 'Model output missing (system record, not a verdict)',
}

# Translations of private candidates stay in the private submodule, outside git.
TRANSLATE_CACHE = ROOT / 'ResearchAssets' / '.cache' / 'story-review-translations.json'
MAX_TRANSLATE_TEXTS = 400
MAX_TRANSLATE_CHARS = 100_000


class ApiError(Exception):
    """An error the page shows to QC, in both of the page's languages."""

    def __init__(self, status: int, message: str, message_en: str | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.message_en = message_en or message

    def text(self, lang: str) -> str:
        return self.message_en if lang == 'en' else self.message


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def blind(c: store.Candidate) -> dict:
    d = {k: getattr(c, k) for k in PUBLIC_FIELDS}
    d['words'] = c.words()
    d['ceiling'] = c.ceiling()
    d['over_limit'] = c.over_limit()
    return d


def load_characters() -> dict:
    """Names, accents and avatar crops, from the website's synced data when it exists."""
    out: dict = {}
    synced = WEBSITE / 'src' / 'data' / 'characters.json'
    rows = []
    if synced.exists():
        try:
            rows = json.loads(synced.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            rows = []
    if rows:
        for r in rows:
            name = r.get('name') or {}
            focus = (r.get('focus') or {}).get('avatar') or '50% 15%'
            zh = name.get('zh') or r['slug']
            out[r['slug']] = {'name': zh, 'name_en': name.get('en') or zh,
                              'accent': r.get('accent') or '#9a807a', 'focus': focus}
    else:
        text = brief_mod.CONFIG.read_text(encoding='utf-8')
        for slug, folder, accent in re.findall(r"slug:\s*'([^']+)',\s*folder:\s*'([^']+)',\s*accent:\s*'([^']+)'", text):
            name = folder.split('-')[0]
            out[slug] = {'name': name, 'name_en': name, 'accent': accent, 'focus': '50% 15%'}
    for slug, d in out.items():
        d['avatar'] = (WEBSITE / 'src' / 'assets' / 'characters' / slug / 'poster.png').exists()
    return out


def load_story_titles_en() -> dict:
    """English titles of published stories, from the website's synced data, keyed by slug."""
    path = WEBSITE / 'src' / 'data' / 'stories.json'
    try:
        rows = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(rows, dict):
        rows = rows.get('stories') or list(rows.values())
    out = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        # sync-content.mjs writes the English version of a story under `en`.
        slug, english = r.get('slug'), r.get('en')
        en = english.get('title') if isinstance(english, dict) else None
        if isinstance(slug, str) and isinstance(en, str) and en.strip():
            out[slug] = en.strip()
    return out


def make_sandbox() -> Path:
    """A throwaway copy of the candidates, so a dry run can generate, judge and rewrite freely."""
    target = Path(tempfile.mkdtemp(prefix='story-review-sandbox-')) / 'story-candidates'
    if store.CANDIDATES.exists():
        shutil.copytree(store.CANDIDATES, target)
    else:
        target.mkdir(parents=True)
    return target


class Review:
    """Everything the site can do, without the HTTP. Tests drive this class directly."""

    def __init__(self, *, dry: bool, start_thread=None, translator=None):
        self.dry = dry
        self.lock = threading.RLock()
        self.job = {'running': False, 'kind': None, 'started': None, 'finished': None,
                    'round': None, 'error': None, 'log': deque(maxlen=300)}
        self.rewrites: dict[str, dict] = {}
        self.listeners: list[queue.Queue] = []
        self._start_thread = start_thread or (lambda fn: threading.Thread(target=fn, daemon=True).start())
        self.characters = load_characters()
        self.translator = translator or translate_mod.Translator(
            cache_path=TRANSLATE_CACHE if (TRANSLATE_CACHE.parents[1] / 'config').is_dir() else None,
            key_source=lambda: adapters.load_env().get(translate_mod.KEY_NAME),
            names={d['name']: d['name_en'] for d in self.characters.values()},
        )

    # ------------------------------------------------------------------ events

    def emit(self, event: str, data) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        for q in list(self.listeners):
            try:
                q.put_nowait((event, payload))
            except queue.Full:
                pass

    def log(self, line: str) -> None:
        line = scrub(line)
        self.job['log'].append(line)
        print(line, flush=True)
        self.emit('log', line)
        # A round logs each story the moment it is written, so refresh the page now instead
        # of waiting for the file watcher's next pass.
        self.emit('changed', {})

    def signature(self) -> tuple:
        base = store.CANDIDATES
        # The taste files are watched too, so the taste page follows an edit made anywhere.
        paths = list(base.glob('*/*')) if base.exists() else []
        paths += list(taste_sync.TASTE_DIR.glob('*.md')) + [taste_sync.STATE]
        sig = []
        for p in paths:
            if p.suffix not in ('.md', '.json'):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            sig.append((str(p), st.st_mtime_ns, st.st_size))
        return tuple(sorted(sig))

    def watch(self, interval: float = 1.5) -> None:
        """Tell the page when candidate files change, whoever changed them."""
        last = self.signature()
        while True:
            time.sleep(interval)
            current = self.signature()
            if current != last:
                last = current
                self.emit('changed', {})

    # ------------------------------------------------------------------ reading

    def rounds(self, cands: list) -> list[dict]:
        by_round: dict = {}
        for c in cands:
            by_round.setdefault(c.round, []).append(c)
        out = []
        for rid in sorted(by_round):
            cs = by_round[rid]
            meta = {}
            meta_path = store.CANDIDATES / rid / 'round.json'
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    meta = {}
            pending = sum(1 for c in cs if c.verdict == 'pending')
            fmt = meta.get('format') or {}
            out.append({
                'id': rid,
                'created': meta.get('created'),
                'dry_run': bool(meta.get('dry_run')),
                'total': len(cs),
                'pending': pending,
                'complete': pending == 0,
                'format': f"{fmt['name']}@{fmt['version']}" if fmt.get('name') else None,
                'max_chars_range': meta.get('max_chars_range'),
            })
        return out

    def generate_block(self, cands: list) -> tuple[str, str] | None:
        """Why generating is refused right now, in Chinese and English; None when it is allowed."""
        if self.job['running']:
            return '上一轮还在生成', 'the previous round is still generating'
        running = sum(1 for r in self.rewrites.values() if r.get('state') == 'running')
        if running:
            return f'还有 {running} 篇正在按意见重写', f'{running} rewrite(s) with notes still running'
        pending = sum(1 for c in cands if c.verdict == 'pending')
        if pending:
            return f'还有 {pending} 篇没有裁决', f'{pending} {"story" if pending == 1 else "stories"} still unjudged'
        return None

    def state(self) -> dict:
        with self.lock:
            cands = store.load_all()
            rewrites = {k: dict(v) for k, v in self.rewrites.items()}
            job = {k: (list(v) if k == 'log' else v) for k, v in self.job.items()}
            block = self.generate_block(cands)
        spec = brief_mod.load_format()
        scenes = brief_mod.load_scenes()
        slots = {k: v['zh'] for k, v in brief_mod.SLOTS.items()}
        slots['expansion'] = '扩展位'
        offered = [k for k in store.REASONS if k not in SYSTEM_REASONS]
        return {
            'mode': 'dry-run' if self.dry else 'live',
            'store': _display(store.CANDIDATES),
            'bands': [list(b) for b in store.SCORE_BANDS],
            'score_range': [store.SCORE_MIN, store.SCORE_MAX],
            'max_prose_chars': store.MAX_PROSE_CHARS,
            'default_max_chars': store.MAX_OUTLINE_CHARS,
            'max_revisits': store.MAX_REVISITS,
            'reasons': {k: store.REASONS[k] for k in offered},
            'reasons_en': {k: REASONS_EN.get(k, store.REASONS[k]) for k in offered},
            'all_reasons': dict(store.REASONS),
            'all_reasons_en': {k: REASONS_EN.get(k, v) for k, v in store.REASONS.items()},
            'slots': slots,
            'slots_en': {k: SLOTS_EN.get(k, k) for k in slots},
            'scenes': {s.file: s.zh for s in scenes},
            'scenes_en': {s.file: s.en for s in scenes},
            'stories': {s['slug']: s['title'] for s in brief_mod.load_stories()},
            'stories_en': load_story_titles_en(),
            'format': {
                'name': spec['name'],
                'version': spec['version'],
                'fields': [{'key': f['key'], 'label': f.get('label'), 'label_en': f.get('label_en'),
                            'show': f.get('show', 'note')} for f in spec['fields']],
            },
            'characters': self.characters,
            'translate': {'available': self.translator.available()},
            'rounds': self.rounds(cands),
            'candidates': [blind(c) for c in cands],
            'job': job,
            'rewrites': rewrites,
            'can_generate': block is None,
            'generate_blocked': {'zh': block[0], 'en': block[1]} if block else None,
        }

    def taste(self) -> dict:
        """QC's taste profile for the taste page: every part in both languages, with its sync state.
        Read-only; rule changes go through the qc-taste update protocol."""
        return taste_sync.overview()

    def stats(self, round_id: str) -> dict:
        if not isinstance(round_id, str) or not ROUND_RE.match(round_id):
            raise ApiError(400, '无效的轮次', 'Invalid round')
        cands = store.load_round(round_id)
        if not cands:
            raise ApiError(404, f'没有 {round_id} 这一轮', f'No round {round_id}')
        pending = sum(1 for c in cands if c.verdict == 'pending')
        if pending:
            raise ApiError(409, f'这一轮还有 {pending} 篇没裁，裁完才揭晓各模型的表现',
                           f'{pending} still unjudged in this round; model results are revealed once it is complete')
        reasons: dict = {}
        for c in cands:
            if c.rewrite:
                continue
            for r in (c.reasons or ([c.reason] if c.reason else [])):
                reasons[r] = reasons.get(r, 0) + 1
        return {
            'round': round_id,
            'models': store.stats(round_id),
            'reasons': [{'key': k, 'label': store.REASONS.get(k, k), 'label_en': REASONS_EN.get(k, store.REASONS.get(k, k)),
                         'count': v} for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])],
            'rewrites': sum(1 for c in cands if c.rewrite),
        }

    # ------------------------------------------------------------------ writing

    @staticmethod
    def _id(payload: dict) -> str:
        cid = payload.get('id')
        if not isinstance(cid, str) or not ID_RE.match(cid):
            raise ApiError(400, '无效的故事 id', 'Invalid story id')
        return cid

    @staticmethod
    def _ceiling(value) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= store.MAX_PROSE_CHARS:
            raise ApiError(400, f'字数上限要在 1 到 {store.MAX_PROSE_CHARS} 之间',
                           f'The cap must be between 1 and {store.MAX_PROSE_CHARS}')
        return value

    def verdict(self, payload: dict) -> dict:
        cid = self._id(payload)
        score = payload.get('score')
        if isinstance(score, bool) or not isinstance(score, int):
            raise ApiError(400, '请先拖动滑条打分', 'Score it first')
        notes = payload.get('notes') or ''
        if not isinstance(notes, str):
            raise ApiError(400, '批注格式不对', 'Notes must be text')
        notes = notes.strip()
        reasons = payload.get('reasons') or []
        if not isinstance(reasons, list) or any(r not in store.REASONS or r in SYSTEM_REASONS for r in reasons):
            raise ApiError(400, '理由标签不对', 'Unknown discard reason')
        try:
            verdict = store.verdict_for_score(score, has_notes=bool(notes))
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        # QC's emphasis (2026-09-10): the text box is the feedback. A discard or a shortlist
        # that says nothing in words is refused here even when a reason chip is ticked.
        if verdict == 'discarded' and not notes:
            raise ApiError(400, '丢弃要写一句为什么', 'Say why it goes')
        if verdict == 'shortlisted' and not notes:
            raise ApiError(400, '候补要写清楚好在哪、缺什么', 'Say what works and what is missing')
        ceiling = payload.get('max_chars')
        if verdict == 'selected_with_notes' and ceiling is not None:
            ceiling = self._ceiling(ceiling)
        with self.lock:
            c = store.find(cid)
            if c is None:
                raise ApiError(404, f'找不到 {cid}', f'No story {cid}')
            if c.verdict != 'pending':
                raise ApiError(409, '这篇已经裁过了', 'This story has already been judged')
            try:
                c = store.decide(c, verdict, reasons=reasons if verdict == 'discarded' else [],
                                 notes=notes or None, score=score, now=now_iso())
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            if verdict == 'selected_with_notes':
                if ceiling is not None:
                    c.rewrite_max_chars = ceiling
                    store.write(c)
                self.start_rewrite(c)
        self.emit('changed', {'id': cid})
        return {'ok': True, 'verdict': verdict, 'candidate': blind(c)}

    def ceiling(self, payload: dict) -> dict:
        cid = self._id(payload)
        value = payload.get('max_chars')
        value = None if value is None else self._ceiling(value)
        with self.lock:
            if self.job['running']:
                raise ApiError(409, '正在生成新一轮，候补的上限等这一轮结束再改',
                               'A round is generating; change shortlist caps once it finishes')
            c = store.find(cid)
            if c is None:
                raise ApiError(404, f'找不到 {cid}', f'No story {cid}')
            if c.verdict != 'shortlisted' or c.rewritten_as:
                raise ApiError(409, '只有还没被重写的候补可以改上限', 'Only a shortlisted story not yet rewritten has a rewrite cap')
            c.rewrite_max_chars = value
            store.write(c)
        self.emit('changed', {'id': cid})
        return {'ok': True, 'candidate': blind(c)}

    def start_rewrite(self, parent: store.Candidate) -> None:
        pid = parent.id
        with self.lock:
            if self.rewrites.get(pid, {}).get('state') == 'running':
                return
            self.rewrites[pid] = {'state': 'running', 'child': None, 'error': None,
                                  'started': now_iso(), 'finished': None}
        self.emit('changed', {'id': pid})

        def work():
            try:
                child, _sha = rewrite_mod.run(parent, 'revise', round_id=parent.round, call=run_round.call,
                                              to_candidate=run_round.to_candidate, dry=self.dry)
                with self.lock:
                    self.rewrites[pid].update(state='done', child=child.id, finished=now_iso())
                print(f'[review] rewrote {pid} -> {child.id}', flush=True)
            except Exception as exc:  # noqa: BLE001 - reported on the card, with a retry button
                with self.lock:
                    self.rewrites[pid].update(state='failed', error=scrub(f'{type(exc).__name__}: {exc}'),
                                              finished=now_iso())
                print(scrub(f'[review] rewrite of {pid} failed: {exc}'), flush=True)
            self.emit('changed', {'id': pid})

        self._start_thread(work)

    def retry_rewrite(self, payload: dict) -> dict:
        cid = self._id(payload)
        with self.lock:
            c = store.find(cid)
            if c is None:
                raise ApiError(404, f'找不到 {cid}', f'No story {cid}')
            if c.verdict != 'selected_with_notes' or c.rewritten_as:
                raise ApiError(409, '这篇不需要重写', 'This story does not need a rewrite')
            self.start_rewrite(c)
        return {'ok': True}

    def generate(self, payload: dict) -> dict:
        lo, hi = payload.get('min_chars'), payload.get('max_chars')
        if (isinstance(lo, bool) or isinstance(hi, bool) or not isinstance(lo, int) or not isinstance(hi, int)
                or not 1 <= lo <= hi <= store.MAX_PROSE_CHARS):
            raise ApiError(400, f'字数范围要满足 1 ≤ 最小 ≤ 最大 ≤ {store.MAX_PROSE_CHARS}',
                           f'The range needs 1 ≤ lowest ≤ highest ≤ {store.MAX_PROSE_CHARS}')
        with self.lock:
            block = self.generate_block(store.load_all())
            if block:
                raise ApiError(409, f'现在不能生成：{block[0]}', f'Cannot generate yet: {block[1]}')
            self.job.update(running=True, kind='generate', started=now_iso(), finished=None, round=None, error=None)
            self.job['log'].clear()
        self.emit('job', {'running': True})

        def work():
            try:
                meta = run_round.run(dry=self.dry, min_chars=lo, max_chars=hi, log=self.log)
                self.job['round'] = meta['round']
            except Exception as exc:  # noqa: BLE001 - shown in the page's job log
                self.job['error'] = f'{type(exc).__name__}: {exc}'
                self.log(f'[round] {self.job["error"]}')
            finally:
                with self.lock:
                    self.job.update(running=False, finished=now_iso())
                self.emit('job', {'running': False})
                self.emit('changed', {})

        self._start_thread(work)
        return {'ok': True}

    def translate(self, payload: dict) -> dict:
        texts = payload.get('texts')
        if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
            raise ApiError(400, '要翻译的内容格式不对', 'texts must be a list of strings')
        if len(texts) > MAX_TRANSLATE_TEXTS or sum(map(len, texts)) > MAX_TRANSLATE_CHARS:
            raise ApiError(413, '一次要翻译的内容太多', 'Too much text in one request')
        try:
            out = self.translator.translate(texts)
        except translate_mod.MissingKey as exc:
            raise ApiError(503, f'没有配置 Google 翻译 key（{translate_mod.KEY_NAME}）',
                           f'No Google Translate key configured ({translate_mod.KEY_NAME})') from exc
        except translate_mod.TranslateError as exc:
            raise ApiError(502, f'翻译失败：{exc}', f'Translation failed: {exc}') from exc
        return {'ok': True, 'translations': out}


def make_handler(review: Review, port: int):
    allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    post_routes = {
        '/api/verdict': review.verdict,
        '/api/ceiling': review.ceiling,
        '/api/generate': review.generate,
        '/api/retry-rewrite': review.retry_rewrite,
        '/api/translate': review.translate,
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = 'StoryReview/1'

        def log_message(self, fmt, *args):  # keep the terminal for the round log
            pass

        def _lang(self) -> str:
            return 'en' if (self.headers.get('X-Lang') or '').lower() == 'en' else 'zh'

        def _send(self, status: int, body: bytes, ctype: str, cache: str = 'no-store') -> None:
            self.send_response(status)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', cache)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

        def _error(self, exc: ApiError) -> None:
            self._json(exc.status, {'ok': False, 'error': exc.text(self._lang())})

        def _missing(self) -> None:
            self._send(404, b'not found', 'text/plain; charset=utf-8')

        def _file(self, path: Path, cache: str = 'no-store') -> None:
            ctype = CONTENT_TYPES.get(path.suffix)
            if not ctype or not path.is_file():
                return self._missing()
            self._send(200, path.read_bytes(), ctype, cache)

        def _host_ok(self) -> bool:
            # Refuses DNS-rebinding: a page on another domain that resolves to 127.0.0.1
            # still sends its own Host header.
            if self.headers.get('Host') in allowed_hosts:
                return True
            self._send(403, b'host not allowed', 'text/plain; charset=utf-8')
            return False

        def do_GET(self):
            if not self._host_ok():
                return
            url = urlparse(self.path)
            path = url.path
            try:
                if path == '/':
                    return self._file(STATIC / 'index.html')
                if path in ('/static/app.js', '/static/app.css'):
                    return self._file(STATIC / path.rsplit('/', 1)[1])
                if path == '/site/global.css':
                    return self._file(WEBSITE / 'src' / 'styles' / 'global.css')
                if path == '/favicon.ico':
                    return self._file(WEBSITE / 'public' / 'favicon.ico', ASSET_CACHE)
                if path.startswith('/fonts/'):
                    name = path[len('/fonts/'):]
                    if re.fullmatch(r'[\w.-]+\.woff2', name):
                        return self._file(WEBSITE / 'public' / 'fonts' / name, ASSET_CACHE)
                    return self._missing()
                if path.startswith('/avatar/') and path.endswith('.png'):
                    slug = path[len('/avatar/'):-len('.png')]
                    if SLUG_RE.match(slug):
                        return self._file(WEBSITE / 'src' / 'assets' / 'characters' / slug / 'poster.png', ASSET_CACHE)
                    return self._missing()
                if path == '/api/state':
                    return self._json(200, review.state())
                if path == '/api/taste':
                    return self._json(200, review.taste())
                if path == '/api/stats':
                    return self._json(200, review.stats((parse_qs(url.query).get('round') or [''])[0]))
                if path == '/api/events':
                    return self._events()
                return self._missing()
            except ApiError as exc:
                self._error(exc)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as exc:  # noqa: BLE001
                self._json(500, {'ok': False, 'error': f'{type(exc).__name__}: {exc}'})

        def do_POST(self):
            if not self._host_ok():
                return
            # A cross-site page can make the browser send a simple POST, but it cannot set
            # this content type without a preflight, and its Origin would not match.
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc not in allowed_hosts:
                return self._json(403, {'ok': False, 'error': 'cross-origin request refused'})
            if (self.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json':
                return self._json(415, {'ok': False, 'error': 'expected application/json'})
            try:
                length = int(self.headers.get('Content-Length') or 0)
                if length > 1_000_000:
                    raise ApiError(413, '请求太大', 'Request too large')
                raw = self.rfile.read(length) if length else b'{}'
                try:
                    payload = json.loads(raw.decode('utf-8') or '{}')
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ApiError(400, '请求不是合法的 JSON', 'Request is not valid JSON') from exc
                if not isinstance(payload, dict):
                    raise ApiError(400, '请求格式不对', 'Malformed request')
                handler = post_routes.get(urlparse(self.path).path)
                if handler is None:
                    raise ApiError(404, 'not found')
                self._json(200, handler(payload))
            except ApiError as exc:
                self._error(exc)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            except Exception as exc:  # noqa: BLE001
                self._json(500, {'ok': False, 'error': f'{type(exc).__name__}: {exc}'})

        def _events(self):
            q: queue.Queue = queue.Queue(maxsize=500)
            review.listeners.append(q)
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(b'retry: 2000\n\n')
                self.wfile.flush()
                while True:
                    try:
                        event, data = q.get(timeout=15)
                        self.wfile.write(f'event: {event}\ndata: {data}\n\n'.encode('utf-8'))
                    except queue.Empty:
                        self.wfile.write(b': ping\n\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            finally:
                if q in review.listeners:
                    review.listeners.remove(q)

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description='Local review site for QC Kindergarten story candidates.')
    ap.add_argument('--port', type=int, default=4388)
    ap.add_argument('--dry-run', action='store_true',
                    help='stub models, and work on a throwaway copy of the candidates')
    ap.add_argument('--candidates', help='use this candidate directory instead of ResearchAssets/story-candidates')
    ap.add_argument('--no-open', action='store_true', help='do not open a browser')
    args = ap.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    if args.candidates:
        store.CANDIDATES = Path(args.candidates).resolve()
    elif args.dry_run:
        store.CANDIDATES = make_sandbox()
        # The copy is throwaway by definition. A normal stop (Ctrl+C) removes it; a killed
        # process leaves it in the system temp directory, which is harmless.
        atexit.register(shutil.rmtree, store.CANDIDATES.parent, ignore_errors=True)

    review = Review(dry=args.dry_run)
    threading.Thread(target=review.watch, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(review, args.port))
    server.daemon_threads = True

    url = f'http://127.0.0.1:{args.port}/'
    mode = 'DRY RUN (stub models)' if args.dry_run else 'LIVE (generating calls the real models)'
    english = ('Google Translate ready' if review.translator.available()
               else f'no {translate_mod.KEY_NAME}; English mode shows untranslated story text')
    print(f'[review] {mode}')
    print(f'[review] candidates: {store.CANDIDATES}')
    print(f'[review] English mode: {english}')
    print(f'[review] {url}   Ctrl+C to stop', flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[review] stopped')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
