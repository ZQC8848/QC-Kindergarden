/**
 * Sanity checks on the built dist/, run at the end of `npm run verify`.
 *
 * Why this exists: the site deploys with `vercel build --prebuilt`, so the dist that goes
 * live is built on whoever runs the deploy, while CI builds its own copy on Linux and
 * throws it away. CI can therefore be green while the uploaded dist is wrong — that is
 * exactly how every story page shipped its title twice. These checks run against the
 * artefact itself, so they hold wherever it was built.
 *
 * Run: node scripts/check-build.mjs   (or npm run verify)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const site = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const dist = path.join(site, 'dist');

const problems = [];
const note = (page, message) => problems.push(`${page}: ${message}`);

function htmlFiles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    return e.isDirectory() ? htmlFiles(full) : e.name.endsWith('.html') ? [full] : [];
  });
}

if (!fs.existsSync(dist)) {
  console.error('[check-build] dist/ not found; run `npm run build` first');
  process.exit(1);
}

const pages = htmlFiles(dist);
const assetRefs = new Set();

for (const file of pages) {
  const rel = '/' + path.relative(dist, file).replace(/\\/g, '/');
  const html = fs.readFileSync(file, 'utf8');

  // The root index.html is a meta-refresh stub to /zh/ and has no content of its own.
  const isRedirectStub = /<meta[^>]+http-equiv=["']?refresh/i.test(html);
  if (isRedirectStub) continue;

  // One H1 per page. The story pages had two: the layout renders the title from
  // frontmatter, and a CRLF-only parser bug left the body's own `# title` in place.
  const h1s = html.match(/<h1[\s>]/g)?.length ?? 0;
  if (h1s !== 1) note(rel, `expected exactly one <h1>, found ${h1s}`);

  const title = html.match(/<title>([^<]*)<\/title>/)?.[1]?.trim();
  if (!title) note(rel, 'no <title>');
  if (!/<meta name="description" content="[^"]+"/.test(html)) note(rel, 'no meta description');
  if (!/<link rel="canonical" href="https?:\/\//.test(html)) note(rel, 'no absolute canonical');
  if (!/<meta property="og:title"/.test(html)) note(rel, 'no og:title');

  // Share-card images must be absolute and must actually exist in dist, or the card
  // unfurls blank in Discord with no error anywhere.
  const og = html.match(/<meta property="og:image" content="([^"]+)"/)?.[1];
  if (og) {
    if (!/^https?:\/\//.test(og)) note(rel, `og:image is not absolute: ${og}`);
    else assetRefs.add(new URL(og).pathname);
  } else if (rel !== '/404.html') {
    note(rel, 'no og:image');
  }
}

for (const ref of assetRefs) {
  if (!fs.existsSync(path.join(dist, ref))) problems.push(`og:image ${ref} is not in dist/`);
}

for (const required of ['sitemap.xml', 'robots.txt', '404.html']) {
  if (!fs.existsSync(path.join(dist, required))) problems.push(`dist/${required} is missing`);
}

if (problems.length) {
  console.error(`[check-build] ${problems.length} problem(s) in dist/:`);
  for (const p of problems.slice(0, 40)) console.error(`  ${p}`);
  if (problems.length > 40) console.error(`  … +${problems.length - 40}`);
  process.exit(1);
}
console.log(`[check-build] ${pages.length} pages OK`);
