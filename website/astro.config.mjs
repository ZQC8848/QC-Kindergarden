import { defineConfig } from 'astro/config';

export default defineConfig({
  // Vercel default domain for now; change when a domain is bought (DESIGN.md 未定).
  site: 'https://qc-kindergarten.vercel.app',
  trailingSlash: 'always',
  i18n: {
    defaultLocale: 'zh',
    locales: ['zh', 'en'],
    routing: {
      prefixDefaultLocale: true,
      redirectToDefaultLocale: true,
    },
  },
  build: {
    inlineStylesheets: 'auto',
  },
});
