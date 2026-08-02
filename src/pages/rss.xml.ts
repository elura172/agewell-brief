import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import { marked } from "marked";
import sanitizeHtml from "sanitize-html";
import { plainTextExcerpt, publishedBriefs, withoutAffiliatePlacement } from "../lib/publishing";

export async function GET(context: { site?: URL }) {
  const entries = publishedBriefs(await getCollection("briefs"));
  const site = context.site ?? new URL("https://agewellbrief.com");

  return rss({
    title: "Agewell Brief",
    description: "Clear, source-linked health and longevity reporting for staying capable and curious.",
    site,
    xmlns: { atom: "http://www.w3.org/2005/Atom" },
    customData:
      '<language>en-ca</language>' +
      `<atom:link href="${new URL("/rss.xml", site).href}" rel="self" type="application/rss+xml" />`,
    items: entries.map((entry) => {
      const feedMarkdown = withoutAffiliatePlacement(entry.body ?? "");
      const rendered = marked.parse(feedMarkdown, { async: false }) as string;
      const content = sanitizeHtml(rendered, {
        allowedTags: sanitizeHtml.defaults.allowedTags.concat(["img", "small"]),
        allowedAttributes: {
          a: ["href", "title", "rel"],
          img: ["src", "alt", "title", "width", "height"],
          small: ["class"]
        },
        allowedSchemes: ["http", "https", "mailto"]
      });

      return {
        title: entry.data.title,
        link: `/brief/${entry.id}/`,
        pubDate: entry.data.date,
        description: plainTextExcerpt(feedMarkdown),
        content,
        categories: [entry.data.category, entry.data.content_type === "lead" ? "Deep Read" : "Signal"],
        source: { title: entry.data.source_name, url: entry.data.source_url }
      };
    })
  });
}
