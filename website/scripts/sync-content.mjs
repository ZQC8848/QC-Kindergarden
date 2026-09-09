// Build-time content sync. Runs before `astro dev` / `astro build`.
//
// Reads the single source of truth outside website/ (DESIGN.md: 网站不手抄):
//   ../character reference/<folder>/性格设定.md        → src/data/characters.json
//   ../character reference/<folder>/*.png              → src/assets/characters/<slug>/
//   ../stories/*.md + ../stories/assets/*.png          → src/data/stories.json + src/assets/stories/
//   ../Scene Reference/*.png                           → src/assets/scenes/
//   ./group-photo/group-photo-final-v1.png             → src/assets/group-photo.png
//
// Images are copied (not moved) only when the source is newer, so Astro's image
// pipeline can optimise them from inside src/assets.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import matter from 'gray-matter';
import { marked } from 'marked';
import { characters, descriptionOrder, nameToSlug, scenes } from '../src/data/characters.config.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const site = path.resolve(here, '..');
const repo = path.resolve(site, '..');
const CH = path.join(repo, 'character reference');
const STORIES = path.join(repo, 'stories');
const SCENES = path.join(repo, 'Scene Reference');

const outData = path.join(site, 'src', 'data');
const outAssets = path.join(site, 'src', 'assets');
fs.mkdirSync(outData, { recursive: true });

marked.setOptions({ gfm: true, breaks: false });

function copyIfNewer(src, dst) {
  if (!fs.existsSync(src)) return false;
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  if (fs.existsSync(dst) && fs.statSync(dst).mtimeMs >= fs.statSync(src).mtimeMs) return true;
  fs.copyFileSync(src, dst);
  return true;
}

function latestVersion(dir, prefix, suffixRe) {
  if (!fs.existsSync(dir)) return null;
  const hits = fs
    .readdirSync(dir)
    .map((f) => ({ f, m: f.match(new RegExp(`^${escapeRe(prefix)}${suffixRe}$`)) }))
    .filter((x) => x.m)
    .sort((a, b) => Number(b.m[1]) - Number(a.m[1]));
  return hits.length ? path.join(dir, hits[0].f) : null;
}
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function latestIllustrations(dir, stem) {
  if (!fs.existsSync(dir)) return [];
  const pattern = new RegExp(`^${escapeRe(stem)}-p(\\d+)-v(\\d+)\\.png$`);
  const latestByPanel = new Map();
  for (const file of fs.readdirSync(dir)) {
    const match = file.match(pattern);
    if (!match) continue;
    const panel = Number(match[1]);
    const version = Number(match[2]);
    const current = latestByPanel.get(panel);
    if (!current || version > current.version) {
      latestByPanel.set(panel, { panel, version, src: path.join(dir, file) });
    }
  }
  return [...latestByPanel.values()].sort((a, b) => a.panel - b.panel);
}

function parseStoryContent(body) {
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

function excerptOf(body) {
  return body
    .split(/\r?\n/)
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith('#') && !l.startsWith('---') && !l.startsWith('**') && !l.startsWith('<!--'));
}

const knownSlugs = new Set(characters.map((c) => c.slug));
function resolveSlug(value) {
  const raw = String(value).trim();
  return knownSlugs.has(raw) ? raw : nameToSlug[raw] ?? nameToSlug[raw.toLowerCase()] ?? null;
}

// ---- bible parsing ----------------------------------------------------------

function linkNames(html) {
  // **haide** → <a href="../haide/">haide</a> (relative link works from any /<lang>/characters/<slug>/ page)
  return html.replace(/<strong>([^<]+)<\/strong>/g, (m, name) => {
    const slug = nameToSlug[name.trim()] ?? nameToSlug[name.trim().toLowerCase()];
    return slug ? `<a class="name-link" data-slug="${slug}" href="../${slug}/">${name}</a>` : m;
  });
}

// English bibles (性格设定.en.md) use these headings; they map onto the Chinese canonical
// section names so descriptionOrder / relations / phrases resolve for both languages.
// Keep this table in sync with .agents/skills/translate-en/SKILL.md.
const SECTION_ALIASES = {
  'Basics': '基本信息',
  'Core personality': '性格核心',
  'Personality in the design': '外形里的性格线索',
  'Habits': '行为习惯',
  'Expressions and moods': '表情与情绪',
  'Likes / dislikes': '喜欢 / 讨厌',
  'Strengths and growth': '优点与课题',
  'Meaning of the props': '道具的意义',
  'Relationships': '和其他人的相处',
};
const canonTitle = (t) => SECTION_ALIASES[t] ?? t;
const isExtra = (s) => s.canon.startsWith('额外设定') || /^Extra(\s[^:：]+)?[:：]/.test(s.title);
const extraLabel = (s) =>
  s.title.replace(/^额外设定[一二三四五六七八九十]?[:：]?\s*/, '').replace(/^Extra(\s[^:：]+)?[:：]\s*/, '') || s.title;

function parseBible(md) {
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
    ? [...phraseLine.matchAll(/"([^"]+)"/g)].map((m) => m[1]).filter((p) => p.length <= (/[\u4e00-\u9fff]/.test(p) ? 24 : 60))
    : [];

  const toHtml = (s) => marked.parse(s.lines.join('\n').trim());

  const description = descriptionOrder
    .map((t) => bySection(t))
    .filter(Boolean)
    .map((s) => ({ title: s.title, html: toHtml(s) }));

  const extras = sections
    .filter(isExtra)
    .map((s) => ({ title: extraLabel(s), html: toHtml(s) }));

  const relSec = bySection('和其他人的相处');
  const relations = relSec
    ? relSec.lines
        .filter((l) => l.startsWith('- '))
        .map((l) => {
          const html = linkNames(marked.parseInline(l.slice(2).trim()));
          const targets = [...l.matchAll(/\*\*([^*]+)\*\*/g)]
            .map((m) => nameToSlug[m[1].trim()] ?? nameToSlug[m[1].trim().toLowerCase()])
            .filter(Boolean);
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

// ---- characters -------------------------------------------------------------

const charOut = [];
for (const c of characters) {
  const dir = path.join(CH, c.folder);
  const zhPath = path.join(dir, '性格设定.md');
  const enPath = path.join(dir, '性格设定.en.md');
  if (!fs.existsSync(zhPath)) {
    console.warn(`[sync] missing bible: ${zhPath}`);
    continue;
  }
  const zh = parseBible(fs.readFileSync(zhPath, 'utf8'));
  const en = fs.existsSync(enPath) ? parseBible(fs.readFileSync(enPath, 'utf8')) : null;

  const assetDir = path.join(outAssets, 'characters', c.slug);
  const poster = copyIfNewer(path.join(dir, `${c.folder}.png`), path.join(assetDir, 'poster.png'));
  const expr = latestVersion(path.join(dir, 'expressions'), `${c.folder}_expressions_v`, '(\\d+)\\.png');
  const turn = latestVersion(path.join(dir, 'turnaround'), `${c.folder}_turnaround_v`, '(\\d+)\\.png');
  if (expr) copyIfNewer(expr, path.join(assetDir, 'expressions.png'));
  if (turn) copyIfNewer(turn, path.join(assetDir, 'turnaround.png'));

  charOut.push({
    slug: c.slug,
    folder: c.folder,
    accent: c.accent,
    hoverCell: c.hoverCell,
    focus: c.focus ?? null,
    name: { zh: zh.basic['名字'] ?? c.folder.split('-')[0], en: c.en.name },
    translated: Boolean(en),
    mbti: zh.mbti,
    hasPoster: poster,
    hasExpressions: Boolean(expr),
    hasTurnaround: Boolean(turn),
    zh,
    en,
  });
}
fs.writeFileSync(path.join(outData, 'characters.json'), JSON.stringify(charOut, null, 2));
console.log(`[sync] ${charOut.length} characters`);

// ---- stories ----------------------------------------------------------------

const storyOut = [];
if (fs.existsSync(STORIES)) {
  for (const f of fs.readdirSync(STORIES)) {
    if (!f.endsWith('.md') || f === 'README.md' || f.endsWith('.en.md')) continue;
    const stem = f.replace(/\.md$/, '');
    const raw = fs.readFileSync(path.join(STORIES, f), 'utf8');
    const { data, content } = matter(raw);
    // strip the first H1 (title is rendered from frontmatter)
    const body = content.replace(/^\s*# .+\n/, '');
    const cast = (data.cast ?? []).map(resolveSlug).filter(Boolean);
    const memories = Object.entries(data.memories ?? {})
      .map(([name, value]) => {
        const character = resolveSlug(name);
        const memory = value && typeof value === 'object' ? value : {};
        return character
          ? {
              character,
              title: String(memory.title ?? ''),
              knowledge: String(memory.knowledge ?? 'witnessed'),
              summary: String(memory.summary ?? ''),
              impact: memory.impact ? String(memory.impact) : null,
            }
          : null;
      })
      .filter(Boolean);
    const storyAssets = path.join(STORIES, 'assets');
    const cover = latestVersion(storyAssets, `${stem}-v`, '(\\d+)\\.png');
    const illustrations = latestIllustrations(storyAssets, stem);
    if (cover) copyIfNewer(cover, path.join(outAssets, 'stories', `${stem}.png`));
    for (const illustration of illustrations) {
      copyIfNewer(illustration.src, path.join(outAssets, 'stories', `${stem}-p${illustration.panel}.png`));
    }
    const excerpt = excerptOf(body);
    // Optional English twin: stories/<stem>.en.md with the same frontmatter shape
    // (title, framing, memories.<slug>.{title,summary,impact}) and a translated body
    // that keeps the <!-- illustration:N|caption --> markers.
    const enPath = path.join(STORIES, `${stem}.en.md`);
    let en = null;
    if (fs.existsSync(enPath)) {
      const twin = matter(fs.readFileSync(enPath, 'utf8'));
      const enBody = twin.content.replace(/^\s*# .+\n/, '');
      const enMemories = {};
      for (const [name, value] of Object.entries(twin.data.memories ?? {})) {
        const slug = resolveSlug(name);
        if (!slug || !value || typeof value !== 'object') continue;
        enMemories[slug] = {
          title: String(value.title ?? ''),
          summary: String(value.summary ?? ''),
          impact: value.impact ? String(value.impact) : null,
        };
      }
      en = {
        title: String(twin.data.title ?? data.title ?? stem),
        framing: twin.data.framing ? String(twin.data.framing) : null,
        excerpt: excerptOf(enBody) ?? '',
        content: parseStoryContent(enBody),
        memories: enMemories,
      };
    }
    // `location` may be one scene or a list of scenes; unknown names are dropped with a warning.
    const rawLoc = data.location;
    const locations = (Array.isArray(rawLoc) ? rawLoc : rawLoc ? [rawLoc] : [])
      .map((l) => String(l).trim())
      .filter(Boolean)
      .filter((l) => {
        const known = scenes.some((sc) => sc.file === l);
        if (!known) console.warn(`[sync] ${f}: unknown location "${l}" (not in characters.config.mjs scenes)`);
        return known;
      });
    storyOut.push({
      slug: stem,
      title: data.title ?? stem,
      cast,
      location: locations[0] ?? null,
      locations,
      date: data.date instanceof Date ? data.date.toISOString().slice(0, 10) : String(data.date ?? '').slice(0, 10),
      source: data.source ?? null,
      kind: data.type === 'extra' ? 'extra' : 'memory',
      timeline: Number.isFinite(Number(data.timeline)) ? Number(data.timeline) : null,
      framing: data.framing ? String(data.framing) : null,
      memories,
      hasCover: Boolean(cover),
      illustrations: illustrations.map(({ panel }) => panel),
      excerpt: excerpt ?? '',
      content: parseStoryContent(body),
      en,
    });
  }
}
storyOut.sort((a, b) => {
  if (a.date !== b.date) return a.date < b.date ? 1 : -1;
  return (b.timeline ?? -1) - (a.timeline ?? -1);
});
fs.writeFileSync(path.join(outData, 'stories.json'), JSON.stringify(storyOut, null, 2));
console.log(`[sync] ${storyOut.length} stories`);

// ---- scenes + group photo ---------------------------------------------------

let nScenes = 0;
for (const s of scenes) {
  if (copyIfNewer(path.join(SCENES, `${s.file}.png`), path.join(outAssets, 'scenes', `${s.file}.png`))) nScenes++;
}
console.log(`[sync] ${nScenes} scenes`);
copyIfNewer(path.join(site, 'group-photo', 'group-photo-final-v1.png'), path.join(outAssets, 'group-photo.png'));
console.log('[sync] done');
