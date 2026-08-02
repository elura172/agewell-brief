import { defineConfig } from "astro/config";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  integrations: [
    mdx(),
    sitemap({
      customSitemaps: ["https://agewellbrief.com/news-sitemap.xml"]
    })
  ],
  site: "https://agewellbrief.com",
  output: "static"
});
