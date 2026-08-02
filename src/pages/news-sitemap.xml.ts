import type { APIRoute } from "astro";
import { getCollection } from "astro:content";
import { escapeXml, publishedBriefs } from "../lib/publishing";

const TWO_DAYS_MS = 2 * 24 * 60 * 60 * 1000;

export const GET: APIRoute = async ({ site }) => {
  const now = Date.now();
  const entries = publishedBriefs(await getCollection("briefs"))
    .filter((entry) => now - entry.data.date.valueOf() <= TWO_DAYS_MS)
    .slice(0, 1000);
  const base = site ?? new URL("https://agewellbrief.com");

  const urls = entries.map((entry) => `
  <url>
    <loc>${escapeXml(new URL(`/brief/${entry.id}/`, base).href)}</loc>
    <news:news>
      <news:publication>
        <news:name>Agewell Brief</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>${entry.data.date.toISOString()}</news:publication_date>
      <news:title>${escapeXml(entry.data.title)}</news:title>
    </news:news>
    ${entry.data.image ? `<image:image>
      <image:loc>${escapeXml(new URL(entry.data.image, base).href)}</image:loc>
      <image:caption>${escapeXml(entry.data.image_alt ?? entry.data.title)}</image:caption>
    </image:image>` : ""}
  </url>`).join("");

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">${urls}
</urlset>\n`;

  return new Response(body, {
    headers: { "Content-Type": "application/xml; charset=utf-8" }
  });
};
