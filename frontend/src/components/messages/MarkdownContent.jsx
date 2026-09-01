import { memo, useMemo } from "react";
import { Box } from "@mantine/core";
import SyntaxHighlighter from "react-syntax-highlighter";
import { a11yLight } from "react-syntax-highlighter/dist/esm/styles/hljs";
import { normalizeMarkdownWhitespace, renderMarkdownHtml } from "../../utils/markdown";

const MarkdownContent = memo(({ content }) => {
  const segments = useMemo(() => {
    const normalizedContent = normalizeMarkdownWhitespace(content);
    return normalizedContent.split(/(```[\s\S]*?```)/g).filter(Boolean);
  }, [content]);

  return (
    <Box
      className="chat-markdown"
      style={{
        fontSize: 14,
        lineHeight: 1.6,
        overflowWrap: "anywhere",
      }}
    >
      {segments.map((segment, index) => {
        if (segment.startsWith("```") && segment.endsWith("```")) {
          const code = segment
            .replace(/^```[^\n]*\n?/, "")
            .replace(/\n?```$/, "");

          return (
            <SyntaxHighlighter
              key={`code-${index}`}
              language="python"
              wrapLines={true}
              wrapLongLines={true}
              style={a11yLight}
              customStyle={{
                margin: "0 0 0.75rem 0",
                padding: "0.75rem",
                borderRadius: 8,
                display: "inline-block",
                maxWidth: "100%",
                backgroundColor: "#f3f5f7",
                fontSize: "13px",
                lineHeight: 1.5,
              }}
              codeTagProps={{
                style: {
                  fontFamily:
                    '"SFMono-Regular", "SF Mono", "Menlo", "Monaco", "Consolas", "Liberation Mono", monospace',
                },
              }}
            >
              {code}
            </SyntaxHighlighter>
          );
        }

        return (
          <Box
            key={`md-${index}`}
            dangerouslySetInnerHTML={{ __html: renderMarkdownHtml(segment) }}
          />
        );
      })}
    </Box>
  );
});

export default MarkdownContent;
