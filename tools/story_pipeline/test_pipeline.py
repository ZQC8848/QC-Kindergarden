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
import re
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

    def test_shortlist_without_qcs_view_is_refused(self):
        # A shortlisted idea comes back to be rewritten; without what works and what is
        # missing, the rewrite just regenerates the same flaw.
        with self.assertRaises(ValueError):
            store.decide(self.make(), 'shortlisted', now=NOW)

    def test_shortlist_retires_after_three_revisits_and_keeps_the_notes(self):
        c = store.decide(self.make(), 'shortlisted', notes='好在温馨，缺前置事件', now=NOW)
        for expected in (1, 2, 3):
            c = store.revisit(c, now=NOW)
            self.assertEqual((c.verdict, c.revisit_count), ('shortlisted', expected))
        c = store.revisit(c, now=NOW)
        self.assertEqual((c.verdict, c.reason), ('discarded', 'never_chosen'))
        self.assertEqual(c.notes, '好在温馨，缺前置事件')

    def test_only_shortlisted_candidates_can_be_revisited(self):
        with self.assertRaises(ValueError):
            store.revisit(self.make(), now=NOW)

    def test_retired_candidates_leave_the_pool(self):
        c = store.decide(self.make(), 'shortlisted', notes='n', now=NOW)
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


class StoryKnowledge(unittest.TestCase):
    def test_memory_holders_are_read_with_their_level(self):
        fm = (
            'title: T\ntimeline: 4\nmemories:\n'
            '  qc:\n    title: a\n    knowledge: inferred\n    summary: s\n'
            '  haide:\n    title: b\n    knowledge: secret\n'
            'teaser: x'
        )
        self.assertEqual(brief_mod._memory_holders(fm), [('qc', 'inferred'), ('haide', 'secret')])

    def test_a_story_without_memories_has_no_holders(self):
        self.assertEqual(brief_mod._memory_holders('title: T\ntype: extra'), [])

    def test_the_ferrari_secret_stays_with_three_people(self):
        # QC: "理论上幼儿园没那么多人知道法拉利的事情". The brief used to drop memories
        # entirely, and the round that followed argued the ticket in front of everyone.
        ferrari = next(st for st in brief_mod.load_stories() if st['slug'] == '2026-09-09-midnight-ferrari')
        self.assertEqual({slug for slug, _ in ferrari['knows']}, {'qc', 'haide', 'dianer'})


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

    def test_the_brief_carries_story_taste_but_not_image_rules(self):
        text = brief_mod.build(taste=True, slot='contradiction')
        self.assertIn('Start from characters; let theme emerge', text)      # story
        self.assertIn('Revise locally once the result is approved', text)   # shared
        self.assertNotIn('Identity must read before detail', text)          # image only

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

    def test_every_brief_lists_who_knows_and_the_adults_rule(self):
        text = brief_mod.build(taste=False, slot='contradiction')
        self.assertIn('其他人不知道', text)
        self.assertIn('秘密只属于知情的人', text)
        self.assertIn('除了 QC，所有角色都是孩子', text)

    def test_open_endings_are_marked_and_closed_to_the_consequence_slot(self):
        # Both of QC's deliberately unresolved stories were sequelled twice in one round.
        stories = brief_mod.load_stories()
        open_ones = {st['slug'] for st in stories if st['open_ending']}
        self.assertEqual(open_ones, {'2026-09-09-midnight-ferrari', '2026-09-09-kings-rank-night'})
        text = brief_mod.build(taste=False, slot='consequence')
        self.assertEqual(text.count('刻意留白的结尾：不要续写'), len(open_ones))
        self.assertIn('标了「刻意留白」的故事不能拿来接', text)

    def test_only_the_consequence_slot_is_told_to_continue_a_story(self):
        # "接了哪篇的什么残留" used to be shown to every slot, and non-sequel slots obeyed it.
        for slot in ('contradiction', 'escalation', 'transposition', 'expansion'):
            text = brief_mod.build(taste=False, slot=slot)
            self.assertNotIn('接了哪篇', text, slot)
            self.assertIn('这个位子不是续集，不要接任何已有故事', text, slot)
        self.assertIn('说明你接的是哪一篇的哪个残留', brief_mod.build(taste=False, slot='consequence'))

    def test_the_escalation_example_does_not_hand_out_a_target(self):
        # It used to ask what 艾莎's grudge book could be pushed to; 10 of 17 outlines used it.
        text = brief_mod.SLOTS['escalation']['brief']
        self.assertNotIn('艾莎的记仇本', text)
        self.assertIn('例子只说明形状', text)

    def test_dedup_field_does_not_reward_shrinking(self):
        # r01's `differs_from` was answered by being smaller and quieter than the good
        # stories, because that is the cheapest way to be different. The replacement asks
        # what earns the comparison instead.
        text = brief_mod.build(taste=False, slot='contradiction')
        self.assertIn('stands_beside', text)
        self.assertIn('不是"比它小"', text)
        self.assertNotIn('differs_from', text)


class TempStore(unittest.TestCase):
    """Points the store at a throwaway directory. CI never checks out ResearchAssets."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = store.CANDIDATES
        store.CANDIDATES = Path(self._tmp.name)

    def tearDown(self):
        store.CANDIDATES = self._saved
        self._tmp.cleanup()

    def make(self, **kw) -> store.Candidate:
        c = store.Candidate(
            id=kw.pop('id', store.new_id()), round=kw.pop('round', 'r-test'),
            slot=kw.pop('slot', 'contradiction'), model=kw.pop('model', 'codex'),
            taste_context=kw.pop('taste_context', 'off'), title=kw.pop('title', '原标题'),
            outline=kw.pop('outline', '原来的事。'), kind='memory', cast=['haide'], **kw,
        )
        store.write(c)
        return c


class OutputFormat(unittest.TestCase):
    def test_the_default_format_loads_and_names_its_body_field(self):
        spec = brief_mod.load_format()
        self.assertEqual(spec['body_field'], 'outline')
        self.assertIn('outline', [f['key'] for f in spec['fields']])
        self.assertEqual(len(spec['sha256']), 64)

    def test_an_unknown_format_is_refused(self):
        with self.assertRaises(ValueError):
            brief_mod.load_format('no-such-format')

    def test_the_default_ceiling_matches_the_store(self):
        self.assertEqual(brief_mod.DEFAULT_MAX_CHARS, store.MAX_OUTLINE_CHARS)

    def test_the_ceiling_reaches_both_places_the_brief_states_it(self):
        text = brief_mod.build(taste=False, slot='contradiction', max_chars=137)
        self.assertIn('大纲上限 **137 字**', text)
        self.assertIn('不超过 137 字', text)
        self.assertNotIn('<<MAX_CHARS>>', text)
        self.assertNotIn('大纲上限 **200 字**', text)

    def test_a_field_added_to_the_format_reaches_the_brief_and_the_candidate(self):
        # The point of the format file: a new field needs no code change anywhere.
        import run_round
        spec = json.loads(json.dumps(brief_mod.load_format()))
        spec['fields'].insert(-1, {'key': 'hook', 'instruction': '一句钩子。', 'show': 'note', 'label': '钩子'})
        self.assertIn('- `hook`：一句钩子。', brief_mod.build(taste=False, slot='contradiction', fmt=spec))
        raw = json.dumps({'title': 'T', 'outline': '事。', 'hook': '钩'}, ensure_ascii=False)
        c = run_round.to_candidate(raw, 'kimi', 'r-test', 'contradiction', 'on', spec=spec)
        self.assertEqual(c.extra, {'hook': '钩'})

    def test_candidates_record_the_format_and_ceiling_they_were_asked_for(self):
        import run_round
        c = run_round.to_candidate('{"title": "T", "outline": "事。"}', 'kimi', 'r-test', 'escalation', 'on',
                                   max_chars=150)
        self.assertEqual(c.max_chars, 150)
        self.assertTrue(c.format_version.startswith('default@'))

    def test_the_rewrite_block_carries_the_score_and_sits_before_the_format(self):
        text = brief_mod.build(taste=False, slot='contradiction', max_chars=180, rewrite={
            'mode': 'waitlist', 'title': '原标题', 'outline': '原来的事。', 'score': 5, 'notes': '缺前置事件'})
        self.assertIn('作者打分：5 / 10', text)
        self.assertIn('以作者意见为准', text)
        self.assertIn('缺前置事件', text)
        self.assertLess(text.index('这一篇是重写'), text.index('## 输出格式'))


class PerSlotCeiling(unittest.TestCase):
    def test_every_slot_gets_one_ceiling_inside_the_range(self):
        import random
        import run_round
        caps = run_round.draw_max_chars(['a', 'b', 'c'], 120, 300, random.Random(1))
        self.assertEqual(set(caps), {'a', 'b', 'c'})
        self.assertTrue(all(120 <= v <= 300 for v in caps.values()))

    def test_a_bad_range_is_refused(self):
        import random
        import run_round
        for lo, hi in ((300, 100), (0, 100), (100, store.MAX_PROSE_CHARS + 1)):
            with self.assertRaises(ValueError, msg=(lo, hi)):
                run_round.draw_max_chars(['a'], lo, hi, random.Random(1))

    def test_the_ceiling_is_per_candidate_when_recorded(self):
        c = store.Candidate(id='c-0005', round='r-test', slot='consequence', model='kimi',
                            taste_context='on', title='T', outline='一' * 250, max_chars=300)
        self.assertFalse(c.over_limit())
        self.assertEqual(c.ceiling(), 300)


class ScoresAndText(TempStore):
    def test_score_bands_map_to_destinations(self):
        f = store.verdict_for_score
        self.assertEqual(f(0, has_notes=True), 'discarded')
        self.assertEqual(f(3, has_notes=False), 'discarded')
        self.assertEqual(f(4, has_notes=True), 'shortlisted')
        self.assertEqual(f(7, has_notes=True), 'shortlisted')
        self.assertEqual(f(8, has_notes=False), 'selected')
        self.assertEqual(f(10, has_notes=True), 'selected_with_notes')
        for bad in (-1, 11, 5.5, True):
            with self.assertRaises(ValueError, msg=bad):
                f(bad, has_notes=False)

    def test_a_discard_with_only_a_note_is_accepted(self):
        # QC's feedback lives in the text box; the reason chips are shortcuts beside it.
        c = store.decide(self.make(), 'discarded', notes='像儿童动画', now=NOW)
        self.assertEqual((c.verdict, c.reason, c.notes), ('discarded', None, '像儿童动画'))

    def test_several_reasons_survive_and_the_first_stays_primary(self):
        c = store.decide(self.make(), 'discarded', reasons=['cringe', 'incoherent'],
                         notes='无聊 很尬 没有因果关系', score=2, now=NOW)
        back = store.read(c.path())
        self.assertEqual((back.reasons, back.reason, back.score), (['cringe', 'incoherent'], 'cringe', 2))

    def test_a_score_out_of_range_is_refused(self):
        with self.assertRaises(ValueError):
            store.decide(self.make(), 'selected', score=12, now=NOW)

    def test_a_file_from_before_multi_select_reads_its_reason_as_a_list(self):
        c = store.decide(self.make(), 'discarded', reason='bland', now=NOW)
        p = c.path()
        p.write_text(re.sub(r'^reasons: .*\n', '', p.read_text(encoding='utf-8'), flags=re.M),
                     encoding='utf-8', newline='\n')
        self.assertEqual(store.read(p).reasons, ['bland'])


class Rewrites(TempStore):
    def setUp(self):
        super().setUp()
        self.calls = []

    def fake_call(self, model, text, dry):
        self.calls.append((model, text))
        return json.dumps({'title': '重写', 'outline': '改过的事。', 'cast': ['haide'], 'kind': 'memory'},
                          ensure_ascii=False), None

    def rewrite(self, parent, mode, round_id):
        import rewrite
        import run_round
        return rewrite.run(parent, mode, round_id=round_id, call=self.fake_call,
                           to_candidate=run_round.to_candidate, now=NOW)

    def test_a_waitlist_rewrite_goes_to_the_same_model_with_qcs_notes(self):
        p = store.decide(self.make(), 'shortlisted', notes='好在温馨，缺前置事件', score=5, now=NOW)
        child, sha = self.rewrite(p, 'waitlist', 'r-next')
        model, text = self.calls[0]
        self.assertEqual(model, 'codex')
        self.assertIn('好在温馨，缺前置事件', text)
        self.assertIn('原来的事。', text)
        self.assertEqual((child.model, child.slot, child.parent, child.rewrite), ('codex', 'contradiction', p.id, 'waitlist'))
        self.assertEqual(len(sha), 64)
        back = store.find(p.id)
        self.assertEqual((back.rewritten_as, back.revisit_count, child.revisit_count), (child.id, 1, 1))

    def test_a_rewritten_parent_leaves_the_pool(self):
        p = store.decide(self.make(), 'shortlisted', notes='n', now=NOW)
        self.rewrite(p, 'waitlist', 'r-next')
        self.assertNotIn(p.id, [c.id for c in store.shortlist_pool()])

    def test_a_lineage_retires_after_three_rewrites(self):
        c = store.decide(self.make(), 'shortlisted', notes='n', now=NOW)
        for i in range(store.MAX_REVISITS):
            child, _ = self.rewrite(c, 'waitlist', f'r-{i}')
            c = store.decide(child, 'shortlisted', notes='还是差一点', score=5, now=NOW)
        child, sha = self.rewrite(c, 'waitlist', 'r-last')
        self.assertEqual((child, sha), (None, None))
        self.assertEqual(len(self.calls), store.MAX_REVISITS)
        back = store.find(c.id)
        self.assertEqual((back.verdict, back.reason), ('discarded', 'never_chosen'))

    def test_a_revise_rewrite_stays_in_its_round_and_spends_no_waitlist_budget(self):
        p = store.decide(self.make(round='2026-09-10-r01'), 'selected_with_notes', notes='把结尾收短', score=8, now=NOW)
        child, _ = self.rewrite(p, 'revise', p.round)
        self.assertEqual((child.round, child.rewrite, child.revisit_count), (p.round, 'revise', 0))
        self.assertEqual(store.find(p.id).revisit_count, 0)

    def test_qcs_ceiling_override_reaches_the_rewrite(self):
        p = store.decide(self.make(rewrite_max_chars=300), 'shortlisted', notes='上限提升到 300 字', now=NOW)
        child, _ = self.rewrite(p, 'waitlist', 'r-next')
        self.assertIn('不超过 300 字', self.calls[0][1])
        self.assertEqual(child.max_chars, 300)

    def test_a_model_failure_leaves_the_parent_untouched(self):
        import rewrite
        import run_round
        p = store.decide(self.make(), 'shortlisted', notes='n', now=NOW)
        with self.assertRaises(RuntimeError):
            rewrite.run(p, 'waitlist', round_id='r-next', call=lambda m, t, d: ('', 'Timeout'),
                        to_candidate=run_round.to_candidate, now=NOW)
        back = store.find(p.id)
        self.assertEqual((back.revisit_count, back.rewritten_as), (0, None))

    def test_rewrites_stay_out_of_baseline_stats(self):
        p = store.decide(self.make(round='2026-09-10-r01'), 'shortlisted', notes='n', now=NOW)
        child, _ = self.rewrite(p, 'revise', p.round)
        store.decide(child, 'selected', score=9, now=NOW)
        row = store.stats(p.round)['codex']
        self.assertEqual((row['shortlisted'], row['selected']), (1, 0))


class DryRound(TempStore):
    def test_a_dry_round_shares_one_ceiling_per_slot_and_rewrites_the_waitlist(self):
        import run_round
        parent = self.make(id='c-aaaa', round='2026-01-01-r01', slot='escalation', model='kimi')
        store.decide(parent, 'shortlisted', notes='缺前置事件', score=5, now=NOW)
        meta = run_round.run(dry=True, taste=False, min_chars=120, max_chars=180, seed=7, log=lambda s: None)
        cands = store.load_round(meta['round'])
        fresh = [c for c in cands if not c.rewrite]
        self.assertEqual(len(fresh), len(run_round.BASE_SLOTS) * len(run_round.MODEL_ORDER) + 1)
        for slot in run_round.BASE_SLOTS + ['expansion']:
            caps = {c.max_chars for c in fresh if c.slot == slot}
            self.assertEqual(len(caps), 1, slot)
            self.assertEqual(caps.pop(), meta['max_chars'][slot])
            self.assertTrue(120 <= meta['max_chars'][slot] <= 180)
        rewrites = [c for c in cands if c.rewrite == 'waitlist']
        self.assertEqual([(c.parent, c.model) for c in rewrites], [('c-aaaa', 'kimi')])
        self.assertEqual(store.find('c-aaaa').rewritten_as, rewrites[0].id)
        self.assertEqual(meta['waitlist_rewrites'][0]['parent'], 'c-aaaa')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    unittest.main(verbosity=2)
