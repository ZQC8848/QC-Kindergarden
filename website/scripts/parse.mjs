/**
 * The parsing half of the content sync: turning a bible or a story's markdown into the
 * structures the site reads. Pulled out of sync-content.mjs so it can be tested without
 * touching the filesystem — these parsers depend on conventions in hand-written markdown
 * (heading names, the catchphrase line, the illustration marker), and a convention that
 * quietly stops matching loses a field with no error anywhere.
 *
 * See scripts/parse.test.mjs. Everything here is pure; the fs work stays in sync-content.mjs.
 */
import { marked } from 'marked';
import { characters, descriptionOrder, nameToSlug } from '../src/data/characters.config.mjs';

marked.setOptions({ gfm: true, breaks: false });

const knownSlugs = new Set(characters.map((c) => c.slug));

/** A name as written in a bible or a story's frontmatter → the character's slug, or null. */
export function resolveSlug(value) {
  const raw = String(value).trim();
  return knownSlugs.has(raw) ? raw : (nameToSlug[raw] ?? nameToSlug[raw.toLowerCase()] ?? null);
}

/**
 * A story's `memories:` frontmatter → [slug, fields] pairs, dropping unknown names.
 * Both languages read the same shape, so they share this.
 */
export function memoryEntries(raw) {
  return Object.entries(raw ?? {}).flatMap(([name, value]) => {
    const slug = resolveSlug(name);
    if (!slug || !value || typeof value !== 'object') return [];
    return [
      [
        slug,
        {
          title: String(value.title ?? ''),
          knowledge: String(value.knowledge ?? 'witnessed'),
          summary: String(value.summary ?? ''),
          impact: value.impact ? String(value.impact) : null,
        },
      ],
    ];
  });
}

export const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Highest `vN` among `files` matching `<prefix><N>.png`, or null. */
export function latestVersionOf(files, prefix, suffixRe = '(\\d+)\\.png') {
  const hits = files
    .map((f) => ({ f, m: f.match(new RegExp(`^${escapeRe(prefix)}${suffixRe}$`)) }))
    .filter((x) => x.m)
    .sort((a, b) => Number(b.m[1]) - Number(a.m[1]));
  return hits.length ? hits[0].f : null;
}

/** Highest version of each panel among `<stem>-p<panel>-v<version>.png`, ordered by panel. */
export function latestIllustrationsOf(files, stem) {
  const pattern = new RegExp(`^${escapeRe(stem)}-p(\\d+)-v(\\d+)\\.png$`);
  const latestByPanel = new Map();
  for (const file of files) {
    const match = file.match(pattern);
    if (!match) continue;
    const panel = Number(match[1]);
    const version = Number(match[2]);
    const current = latestByPanel.get(panel);
    if (!current || version > current.version) latestByPanel.set(panel, { panel, version, file });
  }
  return [...latestByPanel.values()].sort((a, b) => a.panel - b.panel);
}

/**
 * Drop the story's own `# 标题` line; the page renders the title from frontmatter instead.
 *
 * Deliberately line-based rather than one regex. The regex this replaced was
 * `/^\s*# .+\n/`, and in a JS regex `.` excludes every line terminator — `\r` included —
 * so on a CRLF checkout `.+` stopped short of `\r`, the whole pattern failed, and all
 * twelve story pages shipped their title twice. See parse.test.mjs.
 *
 * Joining with `\n` also normalises the body's line endings, so the generated JSON — and
 * therefore the built HTML — is the same whether the checkout is CRLF or LF.
 */
export function stripLeadingH1(content) {
  const lines = content.split(/\r?\n/);
  let i = 0;
  while (i < lines.length && lines[i].trim() === '') i++;
  if (i < lines.length && /^#\s+\S/.test(lines[i])) lines.splice(0, i + 1);
  return lines.join('\n');
}

/** Story body → alternating prose and illustration blocks, split on `<!-- illustration:N|caption -->`. */
export function parseStoryContent(body) {
  const blocks = [];
  const marker = /<!--\s*illustration:(\d+)\s*\|\s*(.*?)\s*-->/g;
  let cursor = 0;
  for (const match of body.matchAll(marker)) {
    const markdown = body.slice(cursor, match.index).trim();
    if (markdown) blocks.push({ type: 'html', html: marked.parse(markdown) });
    blocks.push({ type: 'illustration', panel: Number(match[1]), title: match[2].trim() });
    cursor = match.index + match[0].length;
  }
  const markdown = body.slice(cursor).trim();
  if (markdown) blocks.push({ type: 'html', html: marked.parse(markdown) });
  return blocks;
}

/** First line of real prose, used as the card excerpt and the meta description. */
export function excerptOf(body) {
  return body
    .split(/\r?\n/)
    .map((l) => l.trim())
    .find(
      (l) => l && !l.startsWith('#') && !l.startsWith('---') && !l.startsWith('**') && !l.startsWith('<!--'),
    );
}

// English bibles (性格设定.en.md) use these headings; they map onto the Chinese canonical
// section names so descriptionOrder / relations / phrases resolve for both languages.
// Keep this table in sync with .agents/skills/translate-en/SKILL.md.
// tools/audit_en.py reads it straight out of this file.
export const SECTION_ALIASES = {
  Basics: '基本信息',
  'Core personality': '性格核心',
  'Personality in the design': '外形里的性格线索',
  Habits: '行为习惯',
  'Expressions and moods': '表情与情绪',
  'Likes / dislikes': '喜欢 / 讨厌',
  'Strengths and growth': '优点与课题',
  'Meaning of the props': '道具的意义',
  Relationships: '和其他人的相处',
};

export const canonTitle = (t) => SECTION_ALIASES[t] ?? t;
const isExtra = (s) => s.canon.startsWith('额外设定') || /^Extra(\s[^:：]+)?[:：]/.test(s.title);
const extraLabel = (s) =>
  s.title
    .replace(/^额外设定[一二三四五六七八九十]?[:：]?\s*/, '')
    .replace(/^Extra(\s[^:：]+)?[:：]\s*/, '') || s.title;

/** **Haide** → a link to that character's page, from any /<lang>/characters/<slug>/ page. */
export function linkNames(html) {
  return html.replace(/<strong>([^<]+)<\/strong>/g, (m, name) => {
    const slug = resolveSlug(name);
    return slug ? `<a class="name-link" data-slug="${slug}" href="../${slug}/">${name}</a>` : m;
  });
}

/** A 性格设定.md (either language) → the structure a character page renders. */
export function parseBible(md) {
  const lines = md.split(/\r?\n/);
  const titleLine = lines.find((l) => l.startsWith('# ')) ?? '';
  const tagline = (md.match(/^> (?:一句话|One line)[:：]\s*(.+)$/m)?.[1] ?? '').trim();

  const sections = [];
  let cur = null;
  for (const line of lines) {
    if (line.startsWith('## ')) {
      const title = line.slice(3).trim();
      cur = { title, canon: canonTitle(title), lines: [] };
      sections.push(cur);
    } else if (cur) cur.lines.push(line);
  }
  const bySection = (canon) => sections.find((s) => s.canon === canon);

  const basic = {};
  const basicSec = bySection('基本信息');
  if (basicSec) {
    for (const l of basicSec.lines) {
      const m = l.match(/^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|$/);
      if (m && !['项目', 'Item', 'Field'].includes(m[1]) && !/^-+$/.test(m[1])) basic[m[1]] = m[2];
    }
  }

  const habits = bySection('行为习惯');
  const phraseLine = habits?.lines.find((l) => l.includes('口头禅') || /catchphrase/i.test(l));
  // Chinese catchphrases stay short by nature; English ones need more room to stay quotable.
  const phrases = phraseLine
    ? [...phraseLine.matchAll(/"([^"]+)"/g)]
        .map((m) => m[1])
        .filter((p) => p.length <= (/[一-鿿]/.test(p) ? 24 : 60))
    : [];

  const toHtml = (s) => marked.parse(s.lines.join('\n').trim());

  const description = descriptionOrder
    .map((t) => bySection(t))
    .filter(Boolean)
    .map((s) => ({ title: s.title, html: toHtml(s) }));

  const extras = sections.filter(isExtra).map((s) => ({ title: extraLabel(s), html: toHtml(s) }));

  const relSec = bySection('和其他人的相处');
  const relations = relSec
    ? relSec.lines
        .filter((l) => l.startsWith('- '))
        .map((l) => {
          const html = linkNames(marked.parseInline(l.slice(2).trim()));
          const targets = [...l.matchAll(/\*\*([^*]+)\*\*/g)].map((m) => resolveSlug(m[1])).filter(Boolean);
          return { html, targets: [...new Set(targets)] };
        })
    : [];

  return {
    title: titleLine.replace(/^#\s*/, ''),
    tagline,
    mbti: (basic['MBTI'] ?? '').split(/[（(]/)[0].trim(),
    mbtiLabel: basic['MBTI'] ?? '',
    basic,
    phrases,
    description,
    extras,
    relations,
  };
}
