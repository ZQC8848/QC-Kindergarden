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
    def test_object_with_a_nested_array(self):
        # The trap: `cast` is an array inside the object. Looking for the outermost
        # [...] first parsed ["haide"] and reported every story as unparseable.
        out = parse_outlines('{"title":"T","cast":["haide"],"story":"S"}')
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['title'], 'T')

    def test_plain_array(self):
        out = parse_outlines('[{"title": "a"}, {"title": "b"}]')
        self.assertEqual([o['title'] for o in out], ['a', 'b'])

    def test_fenced_json(self):
        self.assertEqual(parse_outlines('```json\n{"title":"T","cast":["a"]}\n```')[0]['title'], 'T')

    def test_chatty_preamble_and_epilogue(self):
        # An agent CLI will not always obey "output nothing else".
        text = '好的，这是故事：\n\n{"title":"T","cast":["a"]}\n\n需要我改哪里？'
        self.assertEqual(parse_outlines(text)[0]['title'], 'T')

    def test_codex_prints_its_own_chrome(self):
        text = 'codex\n{"title":"T","cast":["a"]}\ntokens used\n5,541'
        self.assertEqual(parse_outlines(text)[0]['title'], 'T')

    def test_json_object_wrapper(self):
        # response_format=json_object cannot return a bare array, so models wrap it.
        self.assertEqual(parse_outlines('{"stories":[{"title":"A","cast":["x"]}]}')[0]['title'], 'A')

    def test_unparseable_returns_empty_rather_than_raising(self):
        self.assertEqual(parse_outlines('I could not complete this request.'), [])
        self.assertEqual(parse_outlines(''), [])
        self.assertEqual(parse_outlines('{"title": broken'), [])


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
            taste_context='on', title='T', outline='大纲。', kind='memory', cast=['haide'],
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
            id='c-abcd', round='r-test', slot='transposition', model='codex', taste_context='off',
            title='一个 "带引号" 的标题', premise_line='移植进了法庭片', kind='extra',
            cast=['haide', 'mimi'], location='ArtClassRoom',
            nearest='2026-09-08-four-witches', stands_beside='它把移植当成了证词而不是造型',
            residue='从此开庭前要先摇铃',
            new_elements=[{'guest': 'Mimi 的姐姐', 'why': '需要一个成年人'}],
            outline='开庭。全体起立，没有人起立。',
            verdict='shortlisted', revisit_count=2,
        )
        store.write(c)
        back = store.read(c.path())
        for f in ('id', 'slot', 'model', 'taste_context', 'title', 'premise_line', 'kind',
                  'cast', 'location', 'nearest', 'stands_beside', 'residue', 'new_elements',
                  'outline', 'verdict', 'revisit_count'):
            self.assertEqual(getattr(back, f), getattr(c, f), f)

    def test_the_outline_survives_intact(self):
        # Losing a line of it to the frontmatter parser would be invisible until someone
        # opened the file, so the round trip is pinned.
        body = '第一句，带 --- 这样的破折号。\n\n第二句。'
        c = store.Candidate(id='c-0001', round='r-test', slot='consequence', model='kimi',
                            taste_context='on', title='T', outline=body)
        store.write(c)
        self.assertEqual(store.read(c.path()).outline, body)

    def test_length_is_counted_ignoring_whitespace(self):
        c = store.Candidate(id='c-0002', round='r-test', slot='consequence', model='kimi',
                            taste_context='on', title='T', outline='一二三\n\n四五')
        self.assertEqual(c.words(), 5)

    def test_the_outline_ceiling_is_flagged_not_enforced(self):
        # The cap is a review signal, not a hard reject: an outline a few characters over
        # that is otherwise excellent should still reach QC, marked.
        ok = store.Candidate(id='c-0003', round='r-test', slot='consequence', model='kimi',
                             taste_context='on', title='T', outline='一' * store.MAX_OUTLINE_CHARS)
        over = store.Candidate(id='c-0004', round='r-test', slot='consequence', model='kimi',
                               taste_context='on', title='T', outline='一' * (store.MAX_OUTLINE_CHARS + 1))
        self.assertFalse(ok.over_limit())
        self.assertTrue(over.over_limit())

    def test_the_two_ceilings_are_separate(self):
        # 200 is what a generated outline may run to; 2286 is what a finished story may
        # run to. Collapsing them would quietly let 2000-character outlines back in.
        self.assertEqual(store.MAX_OUTLINE_CHARS, 200)
        self.assertEqual(store.MAX_PROSE_CHARS, 2286)
        self.assertLess(store.MAX_OUTLINE_CHARS, store.MAX_PROSE_CHARS)

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
                taste_context='on', title='T', outline='大纲。', kind='memory',
            )
            store.write(c)
            store.decide(c, verdict, reason=reason, notes='n' if verdict == 'selected_with_notes' else None, now=NOW)
        s = store.stats('r-test')
        self.assertEqual(s['kimi']['accept_rate'], 0.5)
        self.assertEqual(s['codex']['accept_rate'], 0.0)
        self.assertEqual(s['kimi']['discarded'], 2)


class ToCandidate(unittest.TestCase):
    def test_valid_json_with_no_outline_is_flagged(self):
        # Worse than unparseable: it lands as an empty candidate that looks real. Kimi
        # returned exactly this once — a title, a truncated premise, and nothing else.
        import run_round
        raw = '{"title": "陆姚不炸的那几天", "premise_line": "放大既有事实", "kind": "memory"}'
        c = run_round.to_candidate(raw, 'kimi', 'r-test', 'escalation', 'on')
        self.assertTrue(c.parse_failed)
        self.assertEqual(c.title, '陆姚不炸的那几天')
        self.assertEqual(c.raw, raw)

    def test_a_complete_response_is_not_flagged(self):
        import run_round
        raw = '{"title": "T", "outline": "发生了一件事。", "cast": ["haide"], "kind": "memory"}'
        c = run_round.to_candidate(raw, 'kimi', 'r-test', 'escalation', 'on')
        self.assertFalse(c.parse_failed)
        self.assertEqual(c.outline, '发生了一件事。')


class Brief(unittest.TestCase):
    def test_all_twelve_characters_are_in_the_brief(self):
        text = brief_mod.build(taste=False, slot='contradiction')
        for slug, _folder in brief_mod.load_roster():
            self.assertIn(f'slug `{slug}`', text)

    def test_guests_are_listed_because_reuse_is_encouraged(self):
        # A model cannot reuse a guest it was never shown.
        text = brief_mod.build(taste=False, slot='contradiction')
        self.assertIn('可复用的客串角色', text)
        self.assertIn('Mimi 的姐姐', text)

    def test_existing_stories_are_listed(self):
        self.assertIn('2026-09-08-four-witches', brief_mod.build(taste=False, slot='consequence'))

    def test_the_floor_plan_is_not_offered_as_a_location(self):
        self.assertNotIn('Kindergarten-Map', brief_mod.build(taste=False, slot='contradiction'))

    def test_taste_flag_actually_changes_the_brief(self):
        with_taste = brief_mod.build(taste=True, slot='contradiction')
        without = brief_mod.build(taste=False, slot='contradiction')
        self.assertIn('创作偏好', with_taste)
        self.assertNotIn('创作偏好', without)
        self.assertNotEqual(brief_mod.sha256(with_taste), brief_mod.sha256(without))

    def test_the_build_is_deterministic(self):
        # round.json records a sha256 per slot to back the "all models got the same bytes"
        # claim; that is only meaningful if the build is reproducible.
        a = brief_mod.build(taste=True, slot='escalation')
        b = brief_mod.build(taste=True, slot='escalation')
        self.assertEqual(brief_mod.sha256(a), brief_mod.sha256(b))

    def test_every_slot_produces_a_distinct_brief(self):
        seen = {brief_mod.sha256(brief_mod.build(taste=False, slot=s)) for s in brief_mod.SLOTS}
        self.assertEqual(len(seen), len(brief_mod.SLOTS))

    def test_an_unknown_slot_is_refused(self):
        with self.assertRaises(ValueError):
            brief_mod.build(slot='vibes')

    def test_the_four_slots_are_the_shapes_qc_has_accepted(self):
        # Each slot is reverse-engineered from an accepted story, and each brief names it.
        for slot, story in (('consequence', '七天追咬'), ('contradiction', '变成狗'),
                            ('escalation', '法拉利'), ('transposition', '四大魔女')):
            self.assertIn(story, brief_mod.SLOTS[slot]['brief'], slot)

    def test_baseline_prompts_never_mention_the_new_element_permission(self):
        # The structural half of the fix: the discouraging language must not reach the
        # ordinary slots, or it suppresses them too.
        for slot in brief_mod.SLOTS:
            self.assertNotIn('必须引入一个临时客串角色', brief_mod.build(taste=False, slot=slot), slot)
        self.assertIn('必须引入一个临时客串角色', brief_mod.build(taste=False, slot='expansion'))

    def test_outlines_are_requested_not_prose(self):
        text = brief_mod.build(taste=False, slot='contradiction')
        self.assertIn('这一步只写大纲，不写正文', text)
        self.assertIn('`outline`', text)
        self.assertIn(str(store.MAX_OUTLINE_CHARS), text)

    def test_dedup_field_does_not_reward_shrinking(self):
        # r01's `differs_from` was answered by being smaller and quieter than the good
        # stories, because that is the cheapest way to be different. The replacement asks
        # what earns the comparison instead.
        text = brief_mod.build(taste=False, slot='contradiction')
        self.assertIn('stands_beside', text)
        self.assertIn('不是"比它小"', text)
        self.assertNotIn('differs_from', text)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    unittest.main(verbosity=2)
