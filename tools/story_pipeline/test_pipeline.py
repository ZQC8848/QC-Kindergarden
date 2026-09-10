#!/usr/bin/env python3
"""Tests for the parts of the pipeline that can be wrong silently.

Two areas earn tests. The outline parser reads whatever four different models chose to
emit, and a tolerant parser that quietly returns nothing looks exactly like a model that
had nothing to say. The verdict state machine enforces the two rules the archive depends
on — every discard carries a reason, and the shortlist decays — and both are easy to
regress into a no-op.

Run:  python tools/story_pipeline/test_pipeline.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import brief as brief_mod
import store
from adapters import parse_outlines

NOW = '2026-09-09T21:00:00-07:00'


class ParseOutlines(unittest.TestCase):
    def test_plain_array(self):
        out = parse_outlines('[{"hook": "a"}, {"hook": "b"}]')
        self.assertEqual([o['hook'] for o in out], ['a', 'b'])

    def test_fenced_json(self):
        self.assertEqual(parse_outlines('```json\n[{"hook": "a"}]\n```')[0]['hook'], 'a')

    def test_chatty_preamble_and_epilogue(self):
        # An agent CLI will not always obey "output nothing else"; this is the case that
        # would otherwise lose a whole call.
        text = '好的，这是三条大纲：\n\n[{"hook": "a"}]\n\n需要我展开哪一条？'
        self.assertEqual(parse_outlines(text)[0]['hook'], 'a')

    def test_json_object_wrapper(self):
        # response_format=json_object cannot return a bare array, so the models wrap it.
        self.assertEqual(parse_outlines('{"outlines": [{"hook": "a"}]}')[0]['hook'], 'a')

    def test_single_object_not_wrapped(self):
        self.assertEqual(parse_outlines('{"hook": "a", "turn": "b"}')[0]['turn'], 'b')

    def test_unparseable_returns_empty_rather_than_raising(self):
        self.assertEqual(parse_outlines('I could not complete this request.'), [])
        self.assertEqual(parse_outlines(''), [])
        self.assertEqual(parse_outlines('[{"hook": broken'), [])

    def test_drops_non_objects_inside_the_array(self):
        self.assertEqual(len(parse_outlines('[{"hook": "a"}, "oops", null]')), 1)


class Verdicts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = store.CANDIDATES
        store.CANDIDATES = Path(self._tmp.name)

    def tearDown(self):
        store.CANDIDATES = self._saved
        self._tmp.cleanup()

    def make(self, **kw) -> store.Candidate:
        c = store.Candidate(
            id=kw.pop('id', store.new_id()), round='r-test', slot='baseline', model='kimi',
            taste_context='on', hook='h', turn='t', kind='memory', cast=['haide'],
            location='Courtyard', **kw,
        )
        store.write(c)
        return c

    def test_discard_without_a_reason_is_refused(self):
        # The whole point of keeping rejects is knowing why they were rejected.
        with self.assertRaises(ValueError):
            store.decide(self.make(), 'discarded', now=NOW)

    def test_discard_with_an_unknown_reason_is_refused(self):
        with self.assertRaises(ValueError):
            store.decide(self.make(), 'discarded', reason='vibes', now=NOW)

    def test_the_two_buckets_round_r01_forced_are_distinct(self):
        # 太日常 means the premise never left reality; 寡淡 means it did and still had no
        # flavour. Round r01 produced both complaints and the original set had neither.
        self.assertIn('too_everyday', store.REASONS)
        self.assertIn('bland', store.REASONS)
        self.assertNotEqual(store.REASONS['too_everyday'], store.REASONS['bland'])

    def test_discard_with_a_known_reason_is_recorded(self):
        c = store.decide(self.make(), 'discarded', reason='stale_joke', now=NOW)
        self.assertEqual((c.verdict, c.reason, c.decided_at), ('discarded', 'stale_joke', NOW))

    def test_selected_with_notes_requires_the_notes(self):
        with self.assertRaises(ValueError):
            store.decide(self.make(), 'selected_with_notes', now=NOW)
        c = store.decide(self.make(), 'selected_with_notes', notes='把结尾收短', now=NOW)
        self.assertEqual(c.notes, '把结尾收短')

    def test_unknown_verdict_is_refused(self):
        with self.assertRaises(ValueError):
            store.decide(self.make(), 'maybe', now=NOW)

    def test_shortlist_retires_after_three_revisits(self):
        c = store.decide(self.make(), 'shortlisted', now=NOW)
        for expected in (1, 2, 3):
            c = store.revisit(c, now=NOW)
            self.assertEqual((c.verdict, c.revisit_count), ('shortlisted', expected))
        c = store.revisit(c, now=NOW)
        self.assertEqual((c.verdict, c.reason), ('discarded', 'never_chosen'))

    def test_only_shortlisted_candidates_can_be_revisited(self):
        with self.assertRaises(ValueError):
            store.revisit(self.make(), now=NOW)

    def test_retired_candidates_leave_the_pool(self):
        c = store.decide(self.make(), 'shortlisted', now=NOW)
        self.assertEqual(len(store.shortlist_pool()), 1)
        for _ in range(4):
            c = store.revisit(c, now=NOW)
        self.assertEqual(store.shortlist_pool(), [])


class RoundTrip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = store.CANDIDATES
        store.CANDIDATES = Path(self._tmp.name)

    def tearDown(self):
        store.CANDIDATES = self._saved
        self._tmp.cleanup()

    def test_a_candidate_survives_write_then_read(self):
        c = store.Candidate(
            id='c-abcd', round='r-test', slot='expansion', model='codex', taste_context='off',
            hook='一句 "带引号" 的 hook', turn='转折', kind='extra', cast=['haide', 'mimi'],
            location='ArtClassRoom', differs_from='和 X 的区别',
            new_elements=[{'guest': 'Mimi 的姐姐', 'why': '需要一个成年人'}],
            verdict='shortlisted', revisit_count=2, raw='[{"hook": "x"}]',
        )
        store.write(c)
        back = store.read(c.path())
        for f in ('id', 'slot', 'model', 'taste_context', 'hook', 'turn', 'kind', 'cast',
                  'location', 'differs_from', 'new_elements', 'verdict', 'revisit_count'):
            self.assertEqual(getattr(back, f), getattr(c, f), f)

    def test_stats_counts_by_model_and_computes_accept_rate(self):
        for i, (model, verdict, reason) in enumerate([
            ('kimi', 'selected', None),
            ('kimi', 'selected_with_notes', None),
            ('kimi', 'discarded', 'not_funny'),
            ('kimi', 'discarded', 'bland'),
            ('codex', 'discarded', 'stale_joke'),
        ]):
            c = store.Candidate(
                id=f'c-{i:04d}', round='r-test', slot='baseline', model=model,
                taste_context='on', hook='h', turn='t', kind='memory',
            )
            store.write(c)
            store.decide(c, verdict, reason=reason, notes='n' if verdict == 'selected_with_notes' else None, now=NOW)
        s = store.stats('r-test')
        self.assertEqual(s['kimi']['accept_rate'], 0.5)
        self.assertEqual(s['codex']['accept_rate'], 0.0)
        self.assertEqual(s['kimi']['discarded'], 2)


class Brief(unittest.TestCase):
    def test_all_twelve_characters_are_in_the_brief(self):
        text, _ = brief_mod.build(taste=False, seed=1)
        for slug, _folder in brief_mod.load_roster():
            self.assertIn(f'slug `{slug}`', text)

    def test_guests_are_listed_because_reuse_is_encouraged(self):
        # A model cannot reuse a guest it was never shown.
        text, _ = brief_mod.build(taste=False, seed=1)
        self.assertIn('可复用的客串角色', text)
        self.assertIn('Mimi 的姐姐', text)

    def test_existing_stories_are_listed_for_dedup(self):
        text, _ = brief_mod.build(taste=False, seed=1)
        self.assertIn('2026-09-08-four-witches', text)

    def test_the_floor_plan_is_not_offered_as_a_location(self):
        text, _ = brief_mod.build(taste=False, seed=1)
        self.assertNotIn('Kindergarten-Map', text)

    def test_taste_flag_actually_changes_the_brief(self):
        with_taste, _ = brief_mod.build(taste=True, seed=1)
        without, _ = brief_mod.build(taste=False, seed=1)
        self.assertIn('创作偏好', with_taste)
        self.assertNotIn('创作偏好', without)
        self.assertNotEqual(brief_mod.sha256(with_taste), brief_mod.sha256(without))

    def test_same_seed_gives_the_same_brief(self):
        # round.json records a sha256 per combo to back the "all four models got the same
        # bytes" claim; that is only meaningful if the build is deterministic.
        a, _ = brief_mod.build(taste=True, seed=7)
        b, _ = brief_mod.build(taste=True, seed=7)
        self.assertEqual(brief_mod.sha256(a), brief_mod.sha256(b))

    def test_expansion_prompt_asks_for_one_outline_and_one_combo(self):
        text, combos = brief_mod.build(taste=False, expansion=True, seed=1)
        self.assertEqual(len(combos), 1)
        self.assertIn('必须引入一个临时客串角色或一个新场景', text)

    def test_baseline_prompt_never_mentions_the_new_element_permission(self):
        # The structural half of the fix: the discouraging language must not reach the
        # twelve baseline calls, or it suppresses them too.
        text, _ = brief_mod.build(taste=False, expansion=False, seed=1)
        self.assertNotIn('必须引入一个临时客串角色', text)
        self.assertIn('`new_elements`', text)  # still a neutral field to fill


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    unittest.main(verbosity=2)
