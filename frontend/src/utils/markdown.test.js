import { test, expect } from "vitest";

import { normalizeMarkdownWhitespace, renderMarkdownHtml } from "./markdown.js";

test("preserves Markdown block boundaries and renders GFM tables", () => {
  const markdown = [
    "| Pin | Function |",
    "| ---: | --- |",
    "| 1 | Common anode for all emitters |",
    "| 2 | 950 nm cathode, emitter 1 |",
  ].join("\n");

  const normalized = normalizeMarkdownWhitespace(markdown);
  const html = renderMarkdownHtml(normalized);

  expect(normalized).toBe(markdown);
  expect(html).toMatch(/<table>/);
  expect(html).toMatch(/<th align="right">Pin<\/th>/);
  expect(html).toMatch(/<td align="right">1<\/td>/);
});

test("keeps list items on separate lines", () => {
  const markdown = [
    "Spectrum grouping:",
    "",
    "- **Red, 670 nm:** pins 4 and 6",
    "- **Infrared, 810 nm:** pins 3 and 7",
    "- **Near-infrared, 950 nm:** pins 2 and 8",
  ].join("\n");

  const normalized = normalizeMarkdownWhitespace(markdown);
  const html = renderMarkdownHtml(normalized);

  expect(normalized).toBe(markdown);
  expect(html).toMatch(/<ul>/);
  expect((html.match(/<li>/g) || []).length).toBe(3);
});
