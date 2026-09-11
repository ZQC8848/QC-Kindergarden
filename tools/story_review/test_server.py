#!/usr/bin/env python3
"""Tests for the review site's server and its translator. No network beyond localhost, no
real models, no Google calls, no ResearchAssets checkout: every test works on a temporary
candidate directory with a fake translation backend.

    python tools/story_review/test_server.py
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tools' / 'story_pipeline'))
sys.path.insert(0, str(HERE))

import run_round  # noqa: E402
import server  # noqa: E402
import store  # noqa: E402
import taste_sync  # noqa: E402
import translate as translate_mod  # noqa: E402

NOW ='2026-09-10T12:00:00+08:00'
ROUND = '2026-09-10-r01'
MODELS = tuple(run_round.ADAPTERS)


class FakeGoogle:
    """Stands in for google_translate: wraps each text so tests can see what was sent."""

    def __init__(self, fail: bool = False):
        self.calls: list[list[str]] = []
        self.fail = fail

    def __call__(self, texts, *, key, source='zh-CN', target='en'):
        if self.fail:
            raise translate_mod.TranslateError('Google Translate returned 403: API key not valid')
        self.calls.append(list(texts))
        return [f'EN[{t}]' for t in texts]


def fake_translator(backend=None, key='test-key', cache_path=None):
    return translate_mod.Translator(cache_path=cache_path, key_source=lambda: key,
                                    names={'陆姚': 'Luyao', '牧师': 'Mushi'}, backend=backend or FakeGoogle())


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved_dir = store.CANDIDATES
        self._saved_call = run_round.call
        store.CANDIDATES = Path(self._tmp.name)
        self.google = FakeGoogle()
        # Background work runs inline, so every effect is visible when the call returns.
        self.review = server.Review(dry=True, start_thread=lambda fn: fn(), translator=fake_translator(self.google))

    def tearDown(self):
        run_round.call = self._saved_call
        store.CANDIDATES = self._saved_dir
        self._tmp.cleanup()

    def make(self, **kw) -> store.Candidate:
        c = store.Candidate(
            id=kw.pop('id', store.new_id()), round=kw.pop('round', ROUND),
            slot=kw.pop('slot', 'contradiction'), model=kw.pop('model', 'kimi'),
            taste_context=kw.pop('taste_context', 'on'), title=kw.pop('title', '标题'),
            outline=kw.pop('outline', '一件事。'), kind='memory', cast=['haide'], **kw,
        )
        store.write(c)
        return c

    def refused(self, fn, payload, status: int) -> server.ApiError:
        with self.assertRaises(server.ApiError) as ctx:
            fn(payload)
        self.assertEqual(ctx.exception.status, status, ctx.exception.message)
        return ctx.exception

    def stub_model(self, calls: list, outline: str = '改过的事。'):
        def call(model, text, dry):
            calls.append((model, text))
            return json.dumps({'title': '改过', 'outline': outline, 'cast': ['haide']}, ensure_ascii=False), None
        run_round.call = call


class Blind(Base):
    def test_state_never_names_a_model(self):
        for m in MODELS:
            self.make(model=m, raw=f'raw output from {m}')
        st = self.review.state()
        self.assertEqual(len(st['candidates']), len(MODELS))
        for c in st['candidates']:
            for hidden in ('model', 'raw', 'taste_context'):
                self.assertNotIn(hidden, c)
        text = json.dumps([st['candidates'], st['job'], st['rewrites'], st['rounds']], ensure_ascii=False).lower()
        for m in MODELS:
            self.assertNotIn(m, text)

    def test_per_model_numbers_wait_for_the_whole_round(self):
        a, b = self.make(model='kimi'), self.make(model='codex')
        with self.assertRaises(server.ApiError) as ctx:
            self.review.stats(ROUND)
        self.assertEqual(ctx.exception.status, 409)
        store.decide(a, 'selected', score=8, now=NOW)
        store.decide(b, 'discarded', notes='寡淡', score=2, now=NOW)
        self.assertEqual(set(self.review.stats(ROUND)['models']), {'kimi', 'codex'})

    def test_logs_and_rewrite_errors_are_scrubbed(self):
        self.review.log('  ok   kimi      escalation     120/200 字  标题')
        self.review.log('[round] 17 calls (4 models x 4 slots + expansion:DeepSeek)')
        text = '\n'.join(self.review.job['log']).lower()
        for m in MODELS:
            self.assertNotIn(m, text)
        self.assertNotIn('claude', server.scrub('RuntimeError: claude could not rewrite c-1234: Timeout'))
        # Ordinary words that merely contain a model name stay as they are.
        self.assertEqual(server.scrub('kimino'), 'kimino')


class Verdicts(Base):
    def test_the_score_picks_the_destination(self):
        for score, notes, want in ((2, '无聊', 'discarded'), (5, '缺前置', 'shortlisted'), (8, '', 'selected')):
            c = self.make()
            self.assertEqual(self.review.verdict({'id': c.id, 'score': score, 'notes': notes})['verdict'], want)
            back = store.find(c.id)
            self.assertEqual((back.verdict, back.score), (want, score))

    def test_a_discard_or_a_shortlist_must_say_why_in_words(self):
        c = self.make()
        self.refused(self.review.verdict, {'id': c.id, 'score': 1, 'reasons': ['bland']}, 400)
        self.refused(self.review.verdict, {'id': c.id, 'score': 5, 'notes': '   '}, 400)
        self.assertEqual(store.find(c.id).verdict, 'pending')

    def test_a_discard_keeps_every_reason_ticked(self):
        c = self.make()
        self.review.verdict({'id': c.id, 'score': 0, 'notes': '很尬', 'reasons': ['cringe', 'incoherent']})
        back = store.find(c.id)
        self.assertEqual((back.reasons, back.reason), (['cringe', 'incoherent'], 'cringe'))

    def test_reasons_the_system_writes_are_not_offered(self):
        c = self.make()
        self.refused(self.review.verdict, {'id': c.id, 'score': 0, 'notes': 'x', 'reasons': ['never_chosen']}, 400)
        offered = self.review.state()['reasons']
        for key in server.SYSTEM_REASONS:
            self.assertNotIn(key, offered)
        self.assertIn('bland', offered)

    def test_bad_input_is_refused(self):
        c = self.make()
        self.refused(self.review.verdict, {'id': '../../etc', 'score': 1, 'notes': 'x'}, 400)
        self.refused(self.review.verdict, {'id': c.id, 'notes': 'x'}, 400)
        self.refused(self.review.verdict, {'id': c.id, 'score': 11, 'notes': 'x'}, 400)
        self.refused(self.review.verdict, {'id': c.id, 'score': True, 'notes': 'x'}, 400)
        self.refused(self.review.verdict, {'id': 'c-ffff', 'score': 1, 'notes': 'x'}, 404)
        self.review.verdict({'id': c.id, 'score': 8})
        self.refused(self.review.verdict, {'id': c.id, 'score': 2, 'notes': 'x'}, 409)

    def test_every_error_has_an_english_message(self):
        err = self.refused(self.review.verdict, {'id': 'nope', 'score': 1}, 400)
        self.assertEqual((err.text('zh'), err.text('en')), ('无效的故事 id', 'Invalid story id'))

    def test_selected_with_notes_is_rewritten_at_once_by_the_same_model(self):
        calls: list = []
        self.stub_model(calls)
        c = self.make(model='deepseek')
        out = self.review.verdict({'id': c.id, 'score': 9, 'notes': '结尾收短', 'max_chars': 150})
        self.assertEqual(out['verdict'], 'selected_with_notes')
        self.assertEqual(len(calls), 1)
        model, brief = calls[0]
        self.assertEqual(model, 'deepseek')
        self.assertIn('结尾收短', brief)
        self.assertIn('不超过 150 字', brief)
        parent = store.find(c.id)
        child = store.find(parent.rewritten_as)
        self.assertEqual((child.round, child.rewrite, child.parent, child.verdict, child.max_chars),
                         (ROUND, 'revise', c.id, 'pending', 150))
        self.assertEqual(parent.rewrite_max_chars, 150)
        self.assertEqual(self.review.rewrites[c.id]['state'], 'done')

    def test_a_failed_rewrite_is_reported_without_the_model_and_can_be_retried(self):
        run_round.call = lambda model, text, dry: ('', f'{model} timed out after 900s')
        c = self.make(model='claude')
        self.review.verdict({'id': c.id, 'score': 8, 'notes': '改一下'})
        job = self.review.rewrites[c.id]
        self.assertEqual(job['state'], 'failed')
        self.assertNotIn('claude', job['error'].lower())
        self.assertIsNone(store.find(c.id).rewritten_as)
        run_round.call = self._saved_call   # the dry-run stub
        self.review.retry_rewrite({'id': c.id})
        self.assertEqual(self.review.rewrites[c.id]['state'], 'done')
        self.assertTrue(store.find(c.id).rewritten_as)

    def test_the_rewrite_ceiling_is_only_for_an_open_shortlist(self):
        c = self.make()
        self.refused(self.review.ceiling, {'id': c.id, 'max_chars': 300}, 409)
        store.decide(c, 'shortlisted', notes='n', now=NOW)
        self.review.ceiling({'id': c.id, 'max_chars': 300})
        self.assertEqual(store.find(c.id).rewrite_max_chars, 300)
        self.review.ceiling({'id': c.id, 'max_chars': None})
        self.assertIsNone(store.find(c.id).rewrite_max_chars)
        self.refused(self.review.ceiling, {'id': c.id, 'max_chars': 0}, 400)
        self.refused(self.review.ceiling, {'id': c.id, 'max_chars': store.MAX_PROSE_CHARS + 1}, 400)


class Generate(Base):
    def test_generation_waits_for_review_and_for_rewrites(self):
        c = self.make()
        self.refused(self.review.generate, {'min_chars': 100, 'max_chars': 200}, 409)
        st = self.review.state()
        self.assertFalse(st['can_generate'])
        self.assertEqual(set(st['generate_blocked']), {'zh', 'en'})
        store.decide(c, 'selected', score=8, now=NOW)
        self.review.rewrites['c-0000'] = {'state': 'running'}
        self.refused(self.review.generate, {'min_chars': 100, 'max_chars': 200}, 409)
        del self.review.rewrites['c-0000']
        self.refused(self.review.generate, {'min_chars': 300, 'max_chars': 100}, 400)
        self.refused(self.review.generate, {'min_chars': 100, 'max_chars': store.MAX_PROSE_CHARS + 1}, 400)
        self.assertTrue(self.review.state()['can_generate'])

    def test_a_round_brings_the_waitlist_back_to_its_own_model(self):
        p = self.make(id='c-abcd', round='2026-01-01-r01', slot='escalation', model='codex')
        store.decide(p, 'shortlisted', notes='缺前置事件', score=5, now=NOW)
        self.review.ceiling({'id': 'c-abcd', 'max_chars': 260})
        self.review.generate({'min_chars': 120, 'max_chars': 160})
        job = self.review.job
        self.assertIsNone(job['error'])
        self.assertFalse(job['running'])
        cands = store.load_round(job['round'])
        rewrites = [c for c in cands if c.rewrite == 'waitlist']
        self.assertEqual([(c.parent, c.model, c.max_chars) for c in rewrites], [('c-abcd', 'codex', 260)])
        fresh = [c for c in cands if not c.rewrite]
        self.assertTrue(fresh)
        self.assertTrue(all(120 <= c.max_chars <= 160 for c in fresh))
        log = '\n'.join(job['log']).lower()
        for m in MODELS:
            self.assertNotIn(m, log)


class Translation(unittest.TestCase):
    def test_names_are_fenced_and_come_back_as_the_website_spells_them(self):
        sent = translate_mod.protect('陆姚和牧师<吵架>&\n第二行', {'陆姚': 'Luyao', '牧师': 'Mushi'})
        self.assertIn('<span translate="no">Luyao</span>', sent)
        self.assertIn('<span translate="no">Mushi</span>', sent)
        self.assertIn('&lt;吵架&gt;&amp;', sent)
        self.assertNotIn('\n', sent)
        self.assertEqual(translate_mod.restore(sent), 'Luyao和Mushi<吵架>&\n第二行')

    def test_restore_undoes_what_google_does_to_markup(self):
        google = '<span translate="no">Luyao</span> said &quot;fine&quot; <br /> Next line &amp; more'
        self.assertEqual(translate_mod.restore(google), 'Luyao said "fine"\nNext line & more')

    def test_no_stray_space_is_left_after_a_name(self):
        google = ('<span translate="no">Luyao</span> &#39;s cap; <span translate="no">Ruanruan</span> , '
                  'then <span translate="no">Luyao</span> . <span translate="no">Mushi</span> said')
        self.assertEqual(translate_mod.restore(google), "Luyao's cap; Ruanruan, then Luyao. Mushi said")

    def test_a_cache_from_another_version_is_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'translations.json'
            fake_translator(cache_path=path).translate(['你好'])
            data = json.loads(path.read_text(encoding='utf-8'))
            data['version'] = translate_mod.CACHE_VERSION - 1
            path.write_text(json.dumps(data), encoding='utf-8')
            google = FakeGoogle()
            fake_translator(google, cache_path=path).translate(['你好'])
            self.assertEqual(len(google.calls), 1)

    def test_only_chinese_is_sent_and_each_text_once(self):
        google = FakeGoogle()
        tr = fake_translator(google)
        out = tr.translate(['hello', '你好', '你好', '陆姚来了'])
        self.assertEqual(out['hello'], 'hello')
        self.assertEqual(out['你好'], 'EN[你好]')
        self.assertEqual(out['陆姚来了'], 'EN[Luyao来了]')
        self.assertEqual(google.calls, [['你好', '<span translate="no">Luyao</span>来了']])
        tr.translate(['你好', '陆姚来了'])
        self.assertEqual(len(google.calls), 1)

    def test_the_cache_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'nested' / 'translations.json'
            fake_translator(cache_path=path).translate(['你好'])
            again = fake_translator(FakeGoogle(fail=True), cache_path=path)
            self.assertEqual(again.translate(['你好']), {'你好': 'EN[你好]'})
            # The cache is keyed by hashes, never by the source text itself.
            entries = json.loads(path.read_text(encoding='utf-8'))['entries']
            self.assertTrue(entries)
            self.assertTrue(all(len(k) == 64 and all(ch in '0123456789abcdef' for ch in k) for k in entries))

    def test_batches_stay_under_googles_limits(self):
        self.assertEqual(len(translate_mod.batches(['字'] * 250)), 3)
        self.assertEqual(len(translate_mod.batches(['字' * 3000, '字' * 3000])), 2)
        google = FakeGoogle()
        fake_translator(google).translate([f'第{i}条' for i in range(230)])
        self.assertTrue(all(len(call) <= translate_mod.MAX_SEGMENTS for call in google.calls))
        self.assertEqual(sum(len(call) for call in google.calls), 230)

    def test_no_key_means_no_call(self):
        google = FakeGoogle()
        tr = fake_translator(google, key=None)
        self.assertFalse(tr.available())
        self.assertEqual(tr.translate(['no chinese here']), {'no chinese here': 'no chinese here'})
        with self.assertRaises(translate_mod.MissingKey):
            tr.translate(['你好'])
        self.assertEqual(google.calls, [])


class TranslateEndpoint(Base):
    def test_translate_returns_english_and_validates_input(self):
        self.assertEqual(self.review.translate({'texts': ['你好', 'ok']})['translations'], {'你好': 'EN[你好]', 'ok': 'ok'})
        self.refused(self.review.translate, {'texts': '你好'}, 400)
        self.refused(self.review.translate, {'texts': ['你好', 3]}, 400)
        self.refused(self.review.translate, {'texts': ['字'] * (server.MAX_TRANSLATE_TEXTS + 1)}, 413)

    def test_a_missing_key_or_a_google_error_is_explained(self):
        self.review.translator = fake_translator(key=None)
        err = self.refused(self.review.translate, {'texts': ['你好']}, 503)
        self.assertIn(translate_mod.KEY_NAME, err.text('en'))
        self.assertFalse(self.review.state()['translate']['available'])
        self.review.translator = fake_translator(FakeGoogle(fail=True))
        self.refused(self.review.translate, {'texts': ['你好']}, 502)

    def test_state_carries_the_english_vocabulary(self):
        st = self.review.state()
        self.assertEqual(set(st['reasons_en']), set(st['reasons']))
        self.assertEqual(set(st['all_reasons_en']), set(store.REASONS))
        self.assertEqual(set(st['slots_en']), set(st['slots']))
        self.assertEqual(set(st['scenes_en']), set(st['scenes']))
        for ch in st['characters'].values():
            self.assertTrue(ch['name_en'])
        labels = {f['key']: f.get('label_en') for f in st['format']['fields'] if f['show'] == 'note'}
        self.assertTrue(all(labels.values()), labels)
        self.assertTrue(st['translate']['available'])


class TastePage(Base):
    def test_every_part_arrives_in_both_languages(self):
        parts = self.review.taste()['parts']
        self.assertEqual([p['key'] for p in parts], ['story', 'image', 'storyboard', 'video', '_shared'])
        for p in parts:
            self.assertTrue(p['texts']['en'] and p['texts']['zh'], p['key'])
            self.assertIn(p['state'], taste_sync.STATE_TEXT)
            self.assertEqual(set(p['title']), {'zh', 'en'})


class Http(Base):
    def setUp(self):
        super().setUp()
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        self.port = self.httpd.server_address[1]
        self.httpd.RequestHandlerClass = server.make_handler(self.review, self.port)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers={'Host': f'127.0.0.1:{self.port}', **(headers or {})})
            res = conn.getresponse()
            return res.status, res.getheader('Content-Type') or '', res.read()
        finally:
            conn.close()

    def test_the_page_and_its_script_are_served_with_the_right_types(self):
        status, ctype, body = self.request('GET', '/')
        self.assertEqual((status, ctype.split(';')[0]), (200, 'text/html'))
        self.assertIn('/static/app.js', body.decode('utf-8'))
        status, ctype, _ = self.request('GET', '/static/app.js')
        self.assertEqual((status, ctype.split(';')[0]), (200, 'text/javascript'))

    def test_state_is_served_as_json(self):
        self.make()
        status, _, body = self.request('GET', '/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)['candidates']), 1)

    def test_the_key_never_reaches_the_page(self):
        self.review.translator = fake_translator(key='AIzaSECRET-never-in-a-response')
        _, _, state = self.request('GET', '/api/state')
        _, _, translated = self.request('POST', '/api/translate', json.dumps({'texts': ['你好']}),
                                        {'Content-Type': 'application/json'})
        for body in (state, translated):
            self.assertNotIn(b'AIzaSECRET', body)

    def test_the_taste_page_data_is_served(self):
        status, ctype, body = self.request('GET', '/api/taste')
        self.assertEqual((status, ctype.split(';')[0]), (200, 'application/json'))
        self.assertEqual(len(json.loads(body)['parts']), len(taste_sync.PARTS))

    def test_a_foreign_host_is_refused(self):
        self.assertEqual(self.request('GET', '/api/state', headers={'Host': 'evil.example'})[0], 403)

    def test_only_same_origin_json_can_write(self):
        c = self.make()
        payload = json.dumps({'id': c.id, 'score': 1, 'notes': 'x'})
        json_type = {'Content-Type': 'application/json'}
        self.assertEqual(self.request('POST', '/api/verdict', payload, {**json_type, 'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.request('POST', '/api/verdict', payload, {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(store.find(c.id).verdict, 'pending')
        status, _, body = self.request('POST', '/api/verdict', payload, json_type)
        self.assertEqual(status, 200, body)
        self.assertEqual(store.find(c.id).verdict, 'discarded')

    def test_errors_follow_the_page_language(self):
        bad = json.dumps({'id': 'nope', 'score': 1})
        _, _, en = self.request('POST', '/api/verdict', bad, {'Content-Type': 'application/json', 'X-Lang': 'en'})
        _, _, zh = self.request('POST', '/api/verdict', bad, {'Content-Type': 'application/json'})
        self.assertEqual(json.loads(en)['error'], 'Invalid story id')
        self.assertEqual(json.loads(zh)['error'], '无效的故事 id')

    def test_nothing_outside_the_allowed_files_is_served(self):
        for path in ('/avatar/../server.py', '/avatar/..%2Fserver.png', '/fonts/../../package.json',
                     '/static/../server.py', '/static/test_server.py', '/static/translate.py', '/site/../server.py'):
            self.assertEqual(self.request('GET', path)[0], 404, path)


if __name__ == '__main__':
    unittest.main(verbosity=1)
