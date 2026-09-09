import type { ImageMetadata } from 'astro';
import charactersJson from '../data/characters.json';
import storiesJson from '../data/stories.json';
import composition from '../../group-photo/composition.json';
import { scenes as sceneList } from '../data/characters.config.mjs';
import type { Lang } from '../i18n';

export interface Section {
  title: string;
  html: string;
}
export interface Relation {
  html: string;
  targets: string[];
}
export interface Bible {
  title: string;
  tagline: string;
  mbti: string;
  mbtiLabel: string;
  basic: Record<string, string>;
  phrases: string[];
  description: Section[];
  extras: Section[];
  relations: Relation[];
}
export interface Character {
  slug: string;
  folder: string;
  accent: string;
  hoverCell: number;
  name: { zh: string; en: string };
  mbti: string;
  hasPoster: boolean;
  hasExpressions: boolean;
  hasTurnaround: boolean;
  zh: Bible;
  en: Bible | null;
}
export interface Story {
  slug: string;
  title: string;
  cast: string[];
  location: string | null;
  date: string;
  source: string | null;
  hasCover: boolean;
  excerpt: string;
  html: string;
}

export const characters = charactersJson as Character[];
export const stories = storiesJson as Story[];
export const bySlug = Object.fromEntries(characters.map((c) => [c.slug, c]));

type Img = { default: ImageMetadata };
const posters = import.meta.glob<Img>('/src/assets/characters/*/poster.png', { eager: true });
const expressions = import.meta.glob<Img>('/src/assets/characters/*/expressions.png', { eager: true });
const turnarounds = import.meta.glob<Img>('/src/assets/characters/*/turnaround.png', { eager: true });
const covers = import.meta.glob<Img>('/src/assets/stories/*.png', { eager: true });
const scenes = import.meta.glob<Img>('/src/assets/scenes/*.png', { eager: true });
const group = import.meta.glob<Img>('/src/assets/group-photo.png', { eager: true });

export const posterOf = (slug: string) => posters[`/src/assets/characters/${slug}/poster.png`]?.default;
export const expressionsOf = (slug: string) => expressions[`/src/assets/characters/${slug}/expressions.png`]?.default;
export const turnaroundOf = (slug: string) => turnarounds[`/src/assets/characters/${slug}/turnaround.png`]?.default;
export const coverOf = (slug: string) => covers[`/src/assets/stories/${slug}.png`]?.default;
export const sceneOf = (file: string) => scenes[`/src/assets/scenes/${file}.png`]?.default;
export const groupPhoto = group['/src/assets/group-photo.png']?.default;
export const groupLayers = composition.layers as { character: string; x: number; y: number; depth: number; scale: number }[];
export const sceneMeta = sceneList as { file: string; zh: string; en: string }[];

/** The bible to render for a language, plus whether we fell back to Chinese. */
export function bibleFor(c: Character, lang: Lang): { bible: Bible; fallback: boolean } {
  if (lang === 'en' && c.en) return { bible: c.en, fallback: false };
  return { bible: c.zh, fallback: lang === 'en' };
}

export const nameOf = (c: Character, lang: Lang) => (lang === 'en' ? c.name.en : c.name.zh);

/** Darken an accent enough for text on the peach page (DESIGN.md: 用作文字时必须加深). */
export function inkOf(hex: string, amount = 0.32): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const d = (v: number) => Math.round(v * (1 - amount));
  return `#${[d(r), d(g), d(b)].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}
