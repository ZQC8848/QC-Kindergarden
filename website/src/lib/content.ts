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
  focus: { card?: string; avatar?: string } | null;
  name: { zh: string; en: string };
  mbti: string;
  hasPoster: boolean;
  hasExpressions: boolean;
  hasTurnaround: boolean;
  zh: Bible;
  en: Bible | null;
}
export type StoryKind = 'memory' | 'extra';
export interface StoryMemory {
  character: string;
  title: string;
  knowledge: 'witnessed' | 'heard' | 'inferred' | 'partial' | 'secret';
  summary: string;
  impact: string | null;
}
export type StoryContentBlock =
  | { type: 'html'; html: string }
  | { type: 'illustration'; panel: number; title: string };
export interface Story {
  slug: string;
  title: string;
  cast: string[];
  location: string | null;
  locations: string[];
  date: string;
  source: string | null;
  kind: StoryKind;
  timeline: number | null;
  framing: string | null;
  memories: StoryMemory[];
  hasCover: boolean;
  illustrations: number[];
  excerpt: string;
  content: StoryContentBlock[];
}

export const characters = charactersJson as Character[];
export const stories = storiesJson as Story[];
export const bySlug = Object.fromEntries(characters.map((c) => [c.slug, c]));

type Img = { default: ImageMetadata };
const posters = import.meta.glob<Img>('/src/assets/characters/*/poster.png', { eager: true });
const expressions = import.meta.glob<Img>('/src/assets/characters/*/expressions.png', { eager: true });
const turnarounds = import.meta.glob<Img>('/src/assets/characters/*/turnaround.png', { eager: true });
const storyImages = import.meta.glob<Img>('/src/assets/stories/*.png', { eager: true });
const scenes = import.meta.glob<Img>('/src/assets/scenes/*.png', { eager: true });
const group = import.meta.glob<Img>('/src/assets/group-photo.png', { eager: true });

export const posterOf = (slug: string) => posters[`/src/assets/characters/${slug}/poster.png`]?.default;
export const expressionsOf = (slug: string) => expressions[`/src/assets/characters/${slug}/expressions.png`]?.default;
export const turnaroundOf = (slug: string) => turnarounds[`/src/assets/characters/${slug}/turnaround.png`]?.default;
export const coverOf = (slug: string) => storyImages[`/src/assets/stories/${slug}.png`]?.default;
export const illustrationOf = (slug: string, panel: number) => storyImages[`/src/assets/stories/${slug}-p${panel}.png`]?.default;
export const leadImageOf = (story: Story) => coverOf(story.slug) ?? story.illustrations.map((panel) => illustrationOf(story.slug, panel)).find(Boolean);
export const sceneOf = (file: string) => scenes[`/src/assets/scenes/${file}.png`]?.default;
export const groupPhoto = group['/src/assets/group-photo.png']?.default;
export const groupLayers = composition.layers as { character: string; x: number; y: number; depth: number; scale: number; spot?: { x: number; y: number } }[];
export interface Scene {
  file: string;
  slug: string;
  zh: string;
  en: string;
}
export const sceneMeta = sceneList as Scene[];
export const sceneBySlug: Record<string, Scene> = Object.fromEntries(sceneMeta.map((sc) => [sc.slug, sc]));
export const sceneByFile: Record<string, Scene> = Object.fromEntries(sceneMeta.map((sc) => [sc.file, sc]));
/** Scenes that get their own page (everything but the floor plan). */
export const places = sceneMeta.filter((sc) => sc.file !== 'Kindergarten-Map');
export const placeName = (sc: Scene, lang: 'zh' | 'en') => (lang === 'en' ? sc.en : sc.zh);
/** Stories set (fully or partly) in a scene: memory events first in world order, then extras. */
export const storiesAt = (file: string) =>
  stories
    .filter((st) => st.locations.includes(file))
    .sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'memory' ? -1 : 1;
      return (a.timeline ?? 999) - (b.timeline ?? 999);
    });

/** The bible to render for a language, plus whether we fell back to Chinese. */
export function bibleFor(c: Character, lang: Lang): { bible: Bible; fallback: boolean } {
  if (lang === 'en' && c.en) return { bible: c.en, fallback: false };
  return { bible: c.zh, fallback: lang === 'en' };
}

export const nameOf = (c: Character, lang: Lang) => (lang === 'en' ? c.name.en : c.name.zh);

/** object-position for a cropped poster (see `focus` in characters.config.mjs). */
export function focusOf(c: Pick<Character, 'focus'>, use: 'card' | 'avatar'): string {
  return c.focus?.[use] ?? (use === 'card' ? '50% 50%' : '50% 15%');
}

/** WCAG relative luminance of a #rrggbb colour. */
function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const ch = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * ch((n >> 16) & 255) + 0.7152 * ch((n >> 8) & 255) + 0.0722 * ch(n & 255);
}

function contrast(a: string, b: string): number {
  const la = luminance(a), lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Text colour to put ON a solid accent background: cream on dark accents, deep brown on light ones. */
export function onAccent(hex: string): string {
  const cream = '#fffaf6', dark = '#1f1613';
  return contrast(hex, cream) >= contrast(hex, dark) ? cream : dark;
}

/** Darken an accent enough for text on the peach page (DESIGN.md: 用作文字时必须加深). */
export function inkOf(hex: string, amount = 0.32): string {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const d = (v: number) => Math.round(v * (1 - amount));
  return `#${[d(r), d(g), d(b)].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
}
