import { micromark } from "micromark";
import { gfm, gfmHtml } from "micromark-extension-gfm";
import { math, mathHtml } from "micromark-extension-math";

export const normalizeMathDelimiters = (content) =>
  (content ?? "")
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_, expr) => `$$\n${expr.trim()}\n$$`)
    .replace(/\\\(((?:.|\n)*?)\\\)/g, (_, expr) => `$${expr.trim()}$`);

export const normalizeTextBlock = (block) =>
  block.replace(/\n{3,}/g, "\n\n");

export const normalizeMarkdownWhitespace = (content) => {
  const normalized = normalizeMathDelimiters(content);
  const segments = normalized.split(/(```[\s\S]*?```)/g);

  return segments
    .map((segment) =>
      segment.startsWith("```") && segment.endsWith("```")
        ? segment
        : normalizeTextBlock(segment),
    )
    .join("");
};

export const renderMarkdownHtml = (content) =>
  micromark(content, {
    extensions: [gfm(), math()],
    htmlExtensions: [gfmHtml(), mathHtml()],
  });
