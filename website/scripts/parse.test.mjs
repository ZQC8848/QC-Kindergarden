/**
 * Tests for the markdown conventions the site depends on.
 *
 * These parsers read hand-written files, so a convention that quietly stops matching
 * (a renamed heading, a different quote character, a reworded catchphrase line) drops a
 * field with no error anywhere: the page just renders empty. Each test below pins one
 * of those conventions.
 *
 * Run: npm test
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  canonTitle,
  excerptOf,
  latestIllustrationsOf,
  latestVersionOf,
  linkNames,
  memoryEntries,
  parseBible,
  parseStoryContent,
  resolveSlug,
} from './parse.mjs';

describe('resolveSlug', () => {
  it('accepts a slug, a Chinese name and an English name', () => {
    assert.equal(resolveSlug('haide'), 'haide');
    assert.equal(resolveSlug('艾莎'), 'aisha');
    assert.equal(resolveSlug('Fufu'), 'fufu');
  });

  it('is case-insensitive and trims', () => {
    assert.equal(resolveSlug('  HAIDE '), 'haide');
    assert.equal(resolveSlug('mimi'), 'mimi');
  });

  it('returns null for someone who is not in the cast', () => {
    assert.equal(resolveSlug('园长'), null);
    assert.equal(resolveSlug(''), null);
  });
});

describe('memoryEntries', () => {
  it('reads one memory and defaults knowledge to witnessed', () => {
    const out = memoryEntries({ haide: { title: 'T', summary: 'S' } });
    assert.deepEqual(out, [['haide', { title: 'T', knowledge: 'witnessed', summary: 'S', impact: null }]]);
  });

  it('keys by slug no matter how the name is written', () => {
    const out = memoryEntries({ 艾莎: { title: 'T', summary: 'S', impact: 'I' } });
    assert.equal(out[0][0], 'aisha');
    assert.equal(out[0][1].impact, 'I');
  });

  it('drops names that are not in the cast, rather than inventing a character', () => {
    assert.deepEqual(memoryEntries({ 门卫: { title: 'T' } }), []);
    assert.deepEqual(memoryEntries(undefined), []);
  });
});

describe('parseStoryContent', () => {
  it('returns one prose block when there is no illustration', () => {
    const blocks = parseStoryContent('第一段。\n\n第二段。');
    assert.equal(blocks.length, 1);
    assert.equal(blocks[0].type, 'html');
    assert.match(blocks[0].html, /第一段/);
  });

  it('splits prose around a marker and keeps the caption', () => {
    const blocks = parseStoryContent('前面。\n\n<!-- illustration:2|一句说明 -->\n\n后面。');
    assert.deepEqual(
      blocks.map((b) => b.type),
      ['html', 'illustration', 'html'],
    );
    assert.equal(blocks[1].panel, 2);
    assert.equal(blocks[1].title, '一句说明');
  });

  it('handles a marker with no prose before it', () => {
    const blocks = parseStoryContent('<!-- illustration:1|开场 -->\n\n正文。');
    assert.deepEqual(
      blocks.map((b) => b.type),
      ['illustration', 'html'],
    );
  });
});

describe('excerptOf', () => {
  it('skips headings, frontmatter rules, bold lines and comments', () => {
    const body = '# 标题\n\n---\n\n**加粗的引子**\n\n<!-- illustration:1|x -->\n\n真正的第一句。';
    assert.equal(excerptOf(body), '真正的第一句。');
  });
});

describe('latestVersionOf', () => {
  const files = ['a_v1.png', 'a_v2.png', 'a_v10.png', 'b_v3.png', 'a_v2-4k.png', 'notes.md'];

  it('compares versions as numbers, so v10 beats v9', () => {
    assert.equal(latestVersionOf(files, 'a_v'), 'a_v10.png');
  });

  it('ignores other stems and the 4k master', () => {
    assert.equal(latestVersionOf(files, 'b_v'), 'b_v3.png');
  });

  it('returns null when nothing matches', () => {
    assert.equal(latestVersionOf(files, 'c_v'), null);
    assert.equal(latestVersionOf([], 'a_v'), null);
  });

  it('escapes regex characters in the prefix', () => {
    assert.equal(latestVersionOf(['a.b_v1.png', 'axb_v2.png'], 'a.b_v'), 'a.b_v1.png');
  });
});

describe('latestIllustrationsOf', () => {
  it('keeps the highest version of each panel, ordered by panel', () => {
    const files = ['s-p2-v1.png', 's-p1-v1.png', 's-p1-v3.png', 's-p1-v2.png', 'other-p1-v9.png'];
    assert.deepEqual(
      latestIllustrationsOf(files, 's').map((i) => i.file),
      ['s-p1-v3.png', 's-p2-v1.png'],
    );
  });
});

describe('linkNames', () => {
  it('turns a bolded cast name into a relative link', () => {
    assert.equal(
      linkNames('和 <strong>Mimi</strong> 一起'),
      '和 <a class="name-link" data-slug="mimi" href="../mimi/">Mimi</a> 一起',
    );
  });

  it('leaves bold text alone when it is not a character', () => {
    assert.equal(linkNames('<strong>注意</strong>'), '<strong>注意</strong>');
  });
});

describe('canonTitle', () => {
  it('maps an English heading onto its Chinese canonical name', () => {
    assert.equal(canonTitle('Basics'), '基本信息');
    assert.equal(canonTitle('Relationships'), '和其他人的相处');
  });

  it('leaves an unknown heading as-is', () => {
    assert.equal(canonTitle('基本信息'), '基本信息');
    assert.equal(canonTitle('随便写的'), '随便写的');
  });
});

const BIBLE = `# 测试角色（ENTP）性格设定

> 一句话：用来测试的一句话。

## 基本信息

| 项目 | 内容 |
|---|---|
| 名字 | 测试 |
| MBTI | ENTP（辩论家 / 测试型） |

## 性格核心

**E（外向）**：精力过剩。

## 行为习惯

- 口头禅："短句一。""短句二。""这一句特别特别特别特别特别特别特别特别特别长，不该被当成口头禅收进去。"

## 和其他人的相处

- 和 **Mimi** 是搭档，也常找 **艾莎** 麻烦。
- 一条没有点名任何人的关系。

## 额外设定：一条真正的补充设定

内容。

## 事件档案

以下事件的完整叙述在故事集。

## 道具的意义

道具说明。
`;

describe('parseBible', () => {
  const b = parseBible(BIBLE);

  it('reads the tagline and the basic-info table', () => {
    assert.equal(b.tagline, '用来测试的一句话。');
    assert.equal(b.basic['名字'], '测试');
    assert.equal(b.mbti, 'ENTP');
    assert.equal(b.mbtiLabel, 'ENTP（辩论家 / 测试型）');
  });

  it('takes catchphrases from the 口头禅 line and drops over-long ones', () => {
    assert.deepEqual(b.phrases, ['短句一。', '短句二。']);
  });

  it('orders description sections by descriptionOrder and excludes relations', () => {
    // 和其他人的相处 is rendered as its own section, so it must not appear here as well
    const titles = b.description.map((s) => s.title);
    assert.deepEqual(titles, ['性格核心', '行为习惯', '道具的意义']);
  });

  it('counts 额外设定 as an extra and 事件档案 as not one', () => {
    assert.deepEqual(
      b.extras.map((s) => s.title),
      ['一条真正的补充设定'],
    );
  });

  it('links every cast name in a relationship line and keeps lines that name nobody', () => {
    assert.equal(b.relations.length, 2);
    assert.deepEqual(b.relations[0].targets, ['mimi', 'aisha']);
    assert.deepEqual(b.relations[1].targets, []);
    assert.match(b.relations[0].html, /href="\.\.\/mimi\/"/);
  });

  it('reads an English bible through the alias table', () => {
    const en = parseBible(
      '# Test\n\n> One line: a tagline.\n\n## Basics\n\n| Item | Value |\n|---|---|\n| MBTI | ENTP |\n\n## Relationships\n\n- With **Mimi**.\n',
    );
    assert.equal(en.tagline, 'a tagline.');
    assert.equal(en.mbti, 'ENTP');
    assert.deepEqual(en.relations[0].targets, ['mimi']);
  });

  it('survives a bible with no sections at all', () => {
    const empty = parseBible('# Nothing here\n');
    assert.deepEqual(empty.description, []);
    assert.deepEqual(empty.relations, []);
    assert.deepEqual(empty.phrases, []);
  });
});
