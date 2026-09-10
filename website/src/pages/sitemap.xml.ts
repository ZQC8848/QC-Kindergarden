/**
 * Hand-rolled sitemap rather than @astrojs/sitemap.
 *
 * The site's pages all come from the same three lists the rest of the build reads, so
 * enumerating them here costs a dozen lines and no dependency — the same reason schema.ts
 * uses `astro/zod` instead of adding zod.
 *
 * Every URL carries its other-language twin as an xhtml:link, which is what search engines
 * read to pair /zh/ and /en/ instead of treating them as duplicates.
 */
import type { APIRoute } from 'astro';
import { characters, places, stories } from '../lib/content';
import { langs } from '../i18n';

/** Paths without the language prefix; `trailingSlash: 'always'` in astro.config.mjs. */
const paths = [
  '/',
  ...characters.map((c) => `/characters/${c.slug}/`),
  ...stories.map((st) => `/stories/${st.slug}/`),
  ...places.map((sc) => `/places/${sc.slug}/`),
];

const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');

export const GET: APIRoute = ({ site }) => {
  const abs = (p: string) => escape(new URL(p, site).href);
  const entries = langs.flatMap((lang) =>
    paths.map((p) => {
      const alternates = langs
        .map((l) => `    <xhtml:link rel="alternate" hreflang="${l}" href="${abs(`/${l}${p}`)}"/>`)
        .join('\n');
      return `  <url>\n    <loc>${abs(`/${lang}${p}`)}</loc>\n${alternates}\n  </url>`;
    }),
  );
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${entries.join('\n')}
</urlset>
`;
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
