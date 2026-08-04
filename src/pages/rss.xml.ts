import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import { marked } from "marked";
import sanitizeHtml from "sanitize-html";
import { imageFigureHtml, mediaRssData, plainTextExcerpt, publishedBriefs, withoutAffiliatePlacement } from "../lib/publishing";

export async function GET(context: { site?: URL }) {
  const entries = publishedBriefs(await getCollection("briefs"));
  const site = context.site ?? new URL("https://agewellbrief.com");

  return rss({
    title: "Agewell Brief · Biophysics & Cellular Longevity",
    description: "Source-led biophysics, Exclusion Zone transport, and functional longevity intelligence—translated daily from preprints and original research with zero medical condescension.",
    site,
    xmlns: {
      atom: "http://www.w3.org/2005/Atom",
      media: "http://search.yahoo.com/mrss/"
    },
    customData:
      '<language>en-ca</language>' +
      '<managingEditor>elura172@proton.me (Elura · Agewell Brief)</managingEditor>' +
      `<atom:link href="${new URL("/rss.xml", site).href}" rel="self" type="application/rss+xml" />`,
    items: entries.map((entry) => {
      const feedMarkdown = withoutAffiliatePlacement(entry.body ?? "");
      const rendered = imageFigureHtml(entry.data, site) + (marked.parse(feedMarkdown, { async: false }) as string);
      const content = sanitizeHtml(rendered, {
        allowedTags: sanitizeHtml.defaults.allowedTags.concat(["figure", "figcaption", "img", "small"]),
        allowedAttributes: {
          a: ["href", "title", "rel"],
          figure: ["class"],
          img: ["src", "alt", "title", "width", "height", "loading"],
          small: ["class"]
        },
        allowedSchemes: ["http", "https", "mailto"]
      });

      return {
        title: entry.data.title,
        link: `/brief/${entry.id}/`,
        pubDate: entry.data.date,
        description: plainTextExcerpt(feedMarkdown),
        author: "Elura · Agewell Brief Editorial Desk",
        content,
        categories: [entry.data.category, entry.data.content_type === "lead" ? "Deep Read" : "Signal"],
        source: { title: entry.data.source_name, url: entry.data.source_url },
        customData: mediaRssData(entry.data, site)
      };
    })
  });
}
