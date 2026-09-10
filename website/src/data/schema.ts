/**
 * The shape of the JSON that `scripts/sync-content.mjs` writes and the site reads.
 *
 * This file is the single source of truth for that shape. The sync script imports the
 * schemas and validates before writing (Node runs .ts directly via type stripping);
 * `src/lib/content.ts` imports only the inferred types, so nothing here reaches the
 * browser bundle. Before, the shape was written once in the sync script and again as
 * hand-kept interfaces, and the two drifted until `astro check` failed.
 *
 * zod comes from `astro/zod`, which Astro already ships, so this adds no dependency.
 */
import { z } from 'astro/zod';

export const SectionSchema = z.object({
  title: z.string(),
  html: z.string(),
});

export const RelationSchema = z.object({
  html: z.string(),
  /** slugs of the characters named in this line */
  targets: z.array(z.string()),
});

export const BibleSchema = z.object({
  title: z.string(),
  tagline: z.string(),
  mbti: z.string(),
  mbtiLabel: z.string(),
  basic: z.record(z.string(), z.string()),
  phrases: z.array(z.string()),
  description: z.array(SectionSchema),
  extras: z.array(SectionSchema),
  relations: z.array(RelationSchema),
});

export const CharacterSchema = z.object({
  slug: z.string(),
  folder: z.string(),
  accent: z.string().regex(/^#[0-9a-fA-F]{6}$/, 'accent must be #rrggbb'),
  hoverCell: z.number().int().min(0).max(8),
  /** object-position overrides for cropped posters */
  focus: z.object({ card: z.string().optional(), avatar: z.string().optional() }).nullable(),
  name: z.object({ zh: z.string(), en: z.string() }),
  /** true when 性格设定.en.md exists */
  translated: z.boolean(),
  mbti: z.string(),
  hasPoster: z.boolean(),
  hasExpressions: z.boolean(),
  hasTurnaround: z.boolean(),
  zh: BibleSchema,
  en: BibleSchema.nullable(),
});

/** How much a character knows about the event they carry a memory of. Not exported: the
 * values reach the rest of the site through `Knowledge` and the i18n `knowledge` labels. */
const KNOWLEDGE = ['witnessed', 'heard', 'inferred', 'partial', 'secret'] as const;

export const StoryMemorySchema = z.object({
  character: z.string(),
  title: z.string(),
  knowledge: z.enum(KNOWLEDGE),
  summary: z.string(),
  impact: z.string().nullable(),
});

export const StoryContentBlockSchema = z.union([
  z.object({ type: z.literal('html'), html: z.string() }),
  z.object({ type: z.literal('illustration'), panel: z.number().int(), title: z.string() }),
]);

export const StoryMemoryTextSchema = z.object({
  title: z.string(),
  summary: z.string(),
  impact: z.string().nullable(),
});

export const StoryEnSchema = z.object({
  title: z.string(),
  framing: z.string().nullable(),
  excerpt: z.string(),
  content: z.array(StoryContentBlockSchema),
  memories: z.record(z.string(), StoryMemoryTextSchema),
});

export const StorySchema = z.object({
  slug: z.string(),
  title: z.string(),
  /** every character the story is about, used for filtering */
  cast: z.array(z.string()),
  /** scene files this story happens in; the first one is the primary */
  locations: z.array(z.string()),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'date must be YYYY-MM-DD'),
  source: z.string().nullable(),
  kind: z.enum(['memory', 'extra']),
  /** in-world order; extras may omit it */
  timeline: z.number().nullable(),
  framing: z.string().nullable(),
  /** only the characters who actually carry this memory */
  memories: z.array(StoryMemorySchema),
  hasCover: z.boolean(),
  illustrations: z.array(z.number().int()),
  excerpt: z.string(),
  content: z.array(StoryContentBlockSchema),
  en: StoryEnSchema.nullable(),
});

export const CharactersSchema = z.array(CharacterSchema);
export const StoriesSchema = z.array(StorySchema);

export type Section = z.infer<typeof SectionSchema>;
export type Relation = z.infer<typeof RelationSchema>;
export type Bible = z.infer<typeof BibleSchema>;
export type Character = z.infer<typeof CharacterSchema>;
export type StoryMemory = z.infer<typeof StoryMemorySchema>;
export type StoryMemoryText = z.infer<typeof StoryMemoryTextSchema>;
export type StoryContentBlock = z.infer<typeof StoryContentBlockSchema>;
export type StoryEn = z.infer<typeof StoryEnSchema>;
export type Story = z.infer<typeof StorySchema>;
export type StoryKind = Story['kind'];
export type Knowledge = StoryMemory['knowledge'];
