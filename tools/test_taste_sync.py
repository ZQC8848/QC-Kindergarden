#!/usr/bin/env python3
"""Tests for tools/taste_sync.py. Each test works on a temporary copy of the taste directory,
so nothing in the repository is modified.

    python tools/test_taste_sync.py
"""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import taste_sync  # noqa: E402

REAL_DIR = taste_sync.TASTE_DIR


class Sandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._saved = (taste_sync.ROOT, taste_sync.TASTE_DIR, taste_sync.STATE)
        taste_sync.ROOT = base
        taste_sync.TASTE_DIR = base / 'taste'
        taste_sync.STATE = base / 'state' / 'taste-sync.json'
        shutil.copytree(REAL_DIR, taste_sync.TASTE_DIR)
        code, _ = self.quiet(taste_sync.cmd_stamp, ['--all'])
        self.assertEqual(code, 0)

    def tearDown(self):
        taste_sync.ROOT, taste_sync.TASTE_DIR, taste_sync.STATE = self._saved
        self._tmp.cleanup()

    @staticmethod
    def quiet(fn, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = fn(*args)
        return code, buf.getvalue()

    @staticmethod
    def edit(part, lang, old, new):
        p = taste_sync.path(part, lang)
        text = p.read_text(encoding='utf-8')
        assert old in text, (part, lang, old)
        p.write_text(text.replace(old, new, 1), encoding='utf-8', newline='\n')

    def state(self, part):
        return taste_sync.status(part)['state']


class States(Sandbox):
    def test_a_fresh_stamp_is_in_sync_everywhere(self):
        for part in taste_sync.PARTS:
            self.assertTrue(taste_sync.in_sync(taste_sync.status(part)), part)
        self.assertEqual(self.quiet(taste_sync.cmd_report)[0], 0)

    def test_editing_english_leaves_chinese_stale_until_both_are_stamped(self):
        self.edit('story', 'en', 'Write the shortest version that lands.', 'Write the shortest version that works.')
        self.assertEqual(self.state('story'), 'zh_stale')
        self.assertEqual(self.state('image'), 'synced')
        self.assertEqual(self.quiet(taste_sync.cmd_report)[0], 1)
        self.edit('story', 'zh', '写能成立的最短版本。', '写能成立的、最短的版本。')
        self.assertEqual(self.state('story'), 'both_changed')
        self.assertEqual(self.quiet(taste_sync.cmd_stamp, ['story'])[0], 0)
        self.assertEqual(self.state('story'), 'synced')

    def test_editing_chinese_leaves_english_stale(self):
        self.edit('image', 'zh', '先认出是谁，再看细节', '先认出是谁，然后再看细节')
        self.assertEqual(self.state('image'), 'en_stale')

    def test_line_endings_and_trailing_spaces_are_not_changes(self):
        p = taste_sync.path('_shared', 'en')
        text = p.read_text(encoding='utf-8')
        p.write_bytes(text.replace('\n', '   \r\n').encode('utf-8'))
        self.assertEqual(self.state('_shared'), 'synced')

    def test_a_missing_language_is_reported(self):
        taste_sync.path('video', 'zh').unlink()
        st = taste_sync.status('video')
        self.assertEqual((st['state'], st['missing']), ('missing', ['zh']))
        self.assertEqual(self.quiet(taste_sync.cmd_stamp, ['video'])[0], 1)


class Structure(Sandbox):
    def test_a_rule_in_one_language_only_blocks_the_stamp(self):
        self.edit('story', 'en', '## Story negative boundaries', '### 11. A new rule\n\nText.\n\n## Story negative boundaries')
        st = taste_sync.status('story')
        self.assertTrue(any('11' in p for p in st['problems']), st['problems'])
        before = taste_sync.STATE.read_text(encoding='utf-8')
        code, out = self.quiet(taste_sync.cmd_stamp, ['story'])
        self.assertEqual(code, 1)
        self.assertIn('structure', out)
        self.assertEqual(taste_sync.STATE.read_text(encoding='utf-8'), before)

    def test_a_dropped_list_item_is_noticed(self):
        self.edit('_shared', 'zh', '- 不要把制作流程上的偏好误当成创作 taste。\n', '')
        self.assertTrue(any('list items' in p for p in taste_sync.status('_shared')['problems']))

    def test_the_repository_files_match_in_structure(self):
        taste_sync.TASTE_DIR = REAL_DIR
        for part in taste_sync.PARTS:
            self.assertEqual(taste_sync.status(part)['problems'], [], part)


class Hook(Sandbox):
    def run_hook(self, file_path):
        event = {'tool_name': 'Edit', 'tool_input': {'file_path': str(file_path)}}
        saved = sys.stdin
        sys.stdin = io.StringIO(json.dumps(event))
        try:
            code, out = self.quiet(taste_sync.cmd_hook)
        finally:
            sys.stdin = saved
        self.assertEqual(code, 0)
        return json.loads(out) if out.strip() else None

    def test_only_taste_files_are_recognised(self):
        self.assertEqual(taste_sync.part_of(str(taste_sync.path('story', 'zh'))), ('story', 'zh'))
        self.assertIsNone(taste_sync.part_of(str(taste_sync.TASTE_DIR / 'notes.en.md')))
        self.assertIsNone(taste_sync.part_of(str(taste_sync.ROOT / 'stories' / 'story.en.md')))
        self.assertIsNone(taste_sync.part_of(''))

    def test_the_hook_stays_quiet_for_other_files_and_in_sync_pairs(self):
        self.assertIsNone(self.run_hook(taste_sync.ROOT / 'README.md'))
        self.assertIsNone(self.run_hook(taste_sync.path('story', 'en')))

    def test_the_hook_names_the_stale_file_and_the_stamp_command(self):
        self.edit('story', 'en', 'Keep it short', 'Keep it very short')
        out = self.run_hook(taste_sync.path('story', 'en'))
        context = out['hookSpecificOutput']['additionalContext']
        self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'PostToolUse')
        self.assertIn('story.zh.md', context)
        self.assertIn('python tools/taste_sync.py stamp story', context)
        self.assertIn('中文版落后于英文版', out['systemMessage'])

    def test_a_malformed_event_is_ignored(self):
        saved = sys.stdin
        sys.stdin = io.StringIO('not json')
        try:
            self.assertEqual(self.quiet(taste_sync.cmd_hook), (0, ''))
        finally:
            sys.stdin = saved


if __name__ == '__main__':
    unittest.main(verbosity=1)
