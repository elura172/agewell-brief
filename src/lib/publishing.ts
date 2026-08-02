import type { CollectionEntry } from "astro:content";

export type BriefEntry = CollectionEntry<"briefs">;

export function publishedBriefs(entries: BriefEntry[]): BriefEntry[] {
  return entries
    .filter((entry) => !entry.data.draft)
    .sort((a, b) => b.data.date.valueOf() - a.data.date.valueOf() || a.data.edition_rank - b.data.edition_rank);
}

export function withoutAffiliatePlacement(markdown: string): string {
  return markdown
    .replace(/^>\s*\*\*Affiliate disclosure:\*\*.*(?:\r?\n|$)/gim, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function plainTextExcerpt(markdown: string, limit = 220): string {
  const text = withoutAffiliatePlacement(markdown)
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^>\s?/gm, "")
    .replace(/[*_`~]/g, "")
    .replace(/\s+/g, " ")
    .trim();

  if (text.length <= limit) return text;
  const clipped = text.slice(0, limit + 1);
  return `${clipped.slice(0, Math.max(clipped.lastIndexOf(" "), limit - 30)).trim()}…`;
}

export function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}
