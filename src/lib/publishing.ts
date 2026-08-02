import type { CollectionEntry } from "astro:content";

export type BriefEntry = CollectionEntry<"briefs">;

type ImageData = BriefEntry["data"];

export function topicSlug(value: string): string {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

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

export function imageFigureHtml(data: ImageData, base = new URL("https://agewellbrief.com")): string {
  if (!data.image) return "";
  const imageUrl = new URL(data.image, base).href;
  const alt = escapeXml(data.image_alt ?? "Illustrative photograph for this Agewell Brief article");
  const photographer = escapeXml(data.image_photographer ?? "Photo contributor");
  const photographerCredit = data.image_photographer_url
    ? `<a href="${escapeXml(data.image_photographer_url)}" rel="noopener noreferrer">${photographer}</a>`
    : photographer;
  const provider = escapeXml(data.image_provider ?? "Pexels");
  const sourceCredit = data.image_source_url
    ? ` on <a href="${escapeXml(data.image_source_url)}" rel="noopener noreferrer">${provider}</a>`
    : ` via ${provider}`;
  return `<figure class="editorial-image"><img src="${escapeXml(imageUrl)}" alt="${alt}" width="${data.image_width}" height="${data.image_height}" loading="lazy"><figcaption>Illustrative photo by ${photographerCredit}${sourceCredit}</figcaption></figure>`;
}

export function mediaRssData(data: ImageData, base = new URL("https://agewellbrief.com")): string {
  if (!data.image) return "";
  const imageUrl = new URL(data.image, base).href;
  return `<media:content url="${escapeXml(imageUrl)}" medium="image" width="${data.image_width}" height="${data.image_height}"><media:description type="plain">${escapeXml(data.image_alt ?? "Illustrative Agewell Brief photograph")}</media:description><media:credit role="photographer">${escapeXml(data.image_photographer ?? "Photo contributor")}</media:credit></media:content>`;
}
