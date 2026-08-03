import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const briefs = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./content/posts" }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    updated: z.coerce.date().optional(),
    draft: z.boolean().default(true),
    category: z.string().default("general wellness"),
    content_type: z.enum(["lead", "signal", "evergreen", "editorial"]).default("signal"),
    edition_rank: z.number().int().positive().default(99),
    edition_id: z.string().optional(),
    source_url: z.string().url(),
    source_title: z.string(),
    source_name: z.string().default("Original source"),
    frontier_vectors: z.array(z.string()).default([]),
    evidence_position: z.enum(["established", "emerging", "contested", "historical", "speculative"]).default("emerging"),
    author: z.string().default("Agewell Brief Editorial Desk"),
    image_id: z.number().int().positive().optional(),
    image_provider: z.enum(["Pexels", "Pixabay"]).default("Pexels"),
    image_provider_id: z.string().optional(),
    image: z.string().refine((value) => value.startsWith("/") || URL.canParse(value), "Expected a local or absolute image URL").optional(),
    image_alt: z.string().optional(),
    image_caption: z.string().optional(),
    image_width: z.number().int().positive().default(1200),
    image_height: z.number().int().positive().default(627),
    image_photographer: z.string().optional(),
    image_photographer_url: z.string().url().optional(),
    image_source_url: z.string().url().optional(),
    image_review_status: z.enum(["pending", "metadata-approved", "human-reviewed", "vision-approved"]).default("pending"),
    image_avg_color: z.string().regex(/^#[0-9a-fA-F]{6}$/).default("#cad4cf"),
    autoresearch_antecedents: z.array(z.object({
      scientist: z.string(),
      year: z.union([z.string(), z.number()]).transform((v) => String(v)),
      discovery: z.string()
    })).optional().default([]),
    ancestral_insight: z.string().optional()
  })
});

export const collections = { briefs };
