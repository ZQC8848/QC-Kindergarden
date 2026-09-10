/**
 * An endpoint rather than a file in public/ so the sitemap URL is derived from `site` in
 * astro.config.mjs. The domain is still the Vercel default and will change; this way it
 * only has to change in one place.
 */
import type { APIRoute } from 'astro';

export const GET: APIRoute = ({ site }) =>
  new Response(`User-agent: *\nAllow: /\n\nSitemap: ${new URL('/sitemap.xml', site).href}\n`, {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
