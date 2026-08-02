import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const briefs = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./content/posts" }),
  schema: z.object({
    title: z.string(),
    date: z.coerce.date(),
    draft: z.boolean().default(true),
    category: z.string().default("general wellness"),
    content_type: z.enum(["lead", "signal"]).default("signal"),
    edition_rank: z.number().int().positive().default(99),
    edition_id: z.string().optional(),
    source_url: z.string().url(),
    source_title: z.string(),
    source_name: z.string().default("Original source")
  })
});

export const collections = { briefs };
