import rss from "@astrojs/rss";
import { getCollection } from "astro:content";
import { marked } from "marked";
import sanitizeHtml from "sanitize-html";
import { imageFigureHtml, isCommercialLink, mediaRssData, plainTextExcerpt, publishedBriefs, withoutAffiliatePlacement } from "../lib/publishing";

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
      const canonical = new URL(`/brief/${entry.id}/`, site).href;
      // This feed is built to be syndicated — Substack imports it directly. A
      // syndicated copy on a high-authority domain outranks a young one, so every
      // item has to point home. It is also the only route back to the program
      // cards, which withoutAffiliatePlacement strips from the feed on purpose.
      const backlink =
        `<p><em>Originally published on ` +
        `<a href="${canonical}">Agewell Brief</a>. ` +
        `<a href="${canonical}">Read the original</a> for the full sources and the ` +
        `field guide for this topic.</em></p>`;
      const rendered =
        imageFigureHtml(entry.data, site) +
        (marked.parse(feedMarkdown, { async: false }) as string) +
        backlink;
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
        // <source> means "where this was first reported". The six programme
        // explainers cite our own storefront, and naming a shop as the reporting
        // source in a syndicated feed is not a claim worth making.
        ...(isCommercialLink(entry.data.source_url)
          ? {}
          : { source: { title: entry.data.source_name, url: entry.data.source_url } }),
        customData: mediaRssData(entry.data, site)
      };
    })
  });
}
