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
    // The pipeline stopped emitting this line long ago; kept so older briefs
    // that still carry it are handled.
    .replace(/^>\s*\*\*Affiliate disclosure:\*\*.*(?:\r?\n|$)/gim, "")
    // Today's placement is an <aside class="resource-card"> block. Without this
    // the function was a no-op against every current brief, and the card only
    // stayed out of the feed because sanitize-html happened to drop <aside>.
    .replace(/<aside\b[^>]*class="[^"]*resource-card[^"]*"[\s\S]*?<\/aside>/gi, "")
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

// Hosts we earn commission from. Any link to one of these must be rel="sponsored",
// whether it is a third-party affiliate offer or our own program, so that editorial
// pages never pass ranking signals through a paid link.
const COMMERCIAL_HOSTS = ["hop.clickbank.net", "fullscript.com"];

export function isCommercialLink(href: string | undefined | null): boolean {
  if (!href) return false;
  try {
    const host = new URL(href).hostname.toLowerCase();
    return COMMERCIAL_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
  } catch {
    return false;
  }
}

/** Unlink commercial URLs in rendered HTML, keeping their anchor text.
 *
 * The syndicated copy carries no commission links: the programme cards are
 * stripped, and the link home is the route back to the offer. Prose links
 * slipped past that — the six programme explainers cite the storefront in their
 * Source line, and `marked` renders a bare <a> with no rel="sponsored", which
 * would then be republished on someone else's platform.
 */
export function stripCommercialLinks(html: string): string {
  return html.replace(
    /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi,
    (match, href: string, text: string) => (isCommercialLink(href) ? text : match)
  );
}

export function linkRel(href: string | undefined | null): string {
  return isCommercialLink(href) ? "sponsored noopener noreferrer" : "noopener noreferrer";
}

/** Curl the quotes in text that never passes through the Markdown renderer.
 *
 * Brief bodies get smart quotes from the Markdown pipeline, but frontmatter
 * strings (titles, deks, captions) are interpolated straight into the template,
 * so a generated headline like "Heart's" kept a typewriter apostrophe next to
 * body copy that is curly throughout.
 */
export function typographic(value: string | undefined | null): string {
  if (!value) return "";
  return value
    .replace(/(\w)'(\w)/g, "$1’$2") // contractions: don't, Heart's
    .replace(/'(?=\w)/g, "‘") // opening single
    .replace(/'/g, "’") // closing single / possessive plural
    .replace(/"(?=[^\s])/g, "“") // opening double
    .replace(/"/g, "”"); // closing double
}
