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
import { characters, scenes } from '../src/data/characters.config.mjs';
import { CharactersSchema, StoriesSchema } from '../src/data/schema.ts';
import {
  excerptOf,
  latestIllustrationsOf,
  latestVersionOf,
  memoryEntries,
  parseBible,
  parseStoryContent,
  resolveSlug,
} from './parse.mjs';

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

/** fs wrapper around latestVersionOf. */
function latestVersion(dir, prefix, suffixRe) {
  if (!fs.existsSync(dir)) return null;
  const file = latestVersionOf(fs.readdirSync(dir), prefix, suffixRe);
  return file ? path.join(dir, file) : null;
}

/** fs wrapper around latestIllustrationsOf. */
function latestIllustrations(dir, stem) {
  if (!fs.existsSync(dir)) return [];
  return latestIllustrationsOf(fs.readdirSync(dir), stem).map((i) => ({ ...i, src: path.join(dir, i.file) }));
}

/** Check generated data against src/data/schema.ts and stop the build on the first bad record. */
function validate(schema, value, what, labelOf) {
  const result = schema.safeParse(value);
  if (result.success) return result.data;
  console.error(`[sync] ${what} failed validation:`);
  for (const issue of result.error.issues.slice(0, 20)) {
    const [index, ...rest] = issue.path;
    const where = labelOf && typeof index === 'number' ? labelOf(index) : String(index ?? '');
    console.error(`  ${[where, ...rest].filter((p) => p !== '').join('.')}: ${issue.message}`);
  }
  process.exit(1);
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
validate(CharactersSchema, charOut, 'characters.json', (i) => charOut[i]?.slug ?? `#${i}`);
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
    const memories = memoryEntries(data.memories).map(([character, m]) => ({ character, ...m }));
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
      const enMemories = Object.fromEntries(
        memoryEntries(twin.data.memories).map(([slug, m]) => [
          slug,
          { title: m.title, summary: m.summary, impact: m.impact },
        ]),
      );
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
        if (!known)
          console.warn(`[sync] ${f}: unknown location "${l}" (not in characters.config.mjs scenes)`);
        return known;
      });
    storyOut.push({
      slug: stem,
      title: data.title ?? stem,
      cast,
      locations,
      date:
        data.date instanceof Date
          ? data.date.toISOString().slice(0, 10)
          : String(data.date ?? '').slice(0, 10),
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
validate(StoriesSchema, storyOut, 'stories.json', (i) => storyOut[i]?.slug ?? `#${i}`);
fs.writeFileSync(path.join(outData, 'stories.json'), JSON.stringify(storyOut, null, 2));
console.log(`[sync] ${storyOut.length} stories`);

// ---- scenes + group photo ---------------------------------------------------

let nScenes = 0;
for (const s of scenes) {
  if (copyIfNewer(path.join(SCENES, `${s.file}.png`), path.join(outAssets, 'scenes', `${s.file}.png`)))
    nScenes++;
}
console.log(`[sync] ${nScenes} scenes`);
copyIfNewer(
  path.join(site, 'group-photo', 'group-photo-final-v1.png'),
  path.join(outAssets, 'group-photo.png'),
);
console.log('[sync] done');
