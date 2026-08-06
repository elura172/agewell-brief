import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";

// Hosts we earn commission from. Markdown body links are authored as plain
// [text](url) and render with no rel at all, so mark them here rather than
// relying on every author remembering. Keep in sync with COMMERCIAL_HOSTS in
// src/lib/publishing.ts, which covers links built in templates.
const COMMERCIAL_HOSTS = ["hop.clickbank.net", "fullscript.com"];

function isCommercial(href) {
  if (typeof href !== "string") return false;
  try {
    const host = new URL(href).hostname.toLowerCase();
    return COMMERCIAL_HOSTS.some((h) => host === h || host.endsWith(`.${h}`));
  } catch {
    return false;
  }
}

function rehypeSponsorCommercialLinks() {
  return (tree) => {
    const walk = (node) => {
      if (node.type === "element" && node.tagName === "a" && isCommercial(node.properties?.href)) {
        const existing = node.properties.rel;
        const rel = new Set(
          Array.isArray(existing) ? existing : String(existing ?? "").split(/\s+/).filter(Boolean)
        );
        rel.add("sponsored");
        rel.add("noopener");
        rel.add("noreferrer");
        node.properties.rel = [...rel];
      }
      for (const child of node.children ?? []) walk(child);
    };
    walk(tree);
  };
}

export default defineConfig({
  integrations: [
    mdx(),
    sitemap({
      customSitemaps: ["https://agewellbrief.com/news-sitemap.xml"]
    })
  ],
  markdown: {
    rehypePlugins: [rehypeSponsorCommercialLinks]
  },
  site: "https://agewellbrief.com",
  output: "static"
});
