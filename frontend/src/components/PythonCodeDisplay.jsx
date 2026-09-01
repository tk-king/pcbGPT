import { memo } from "react";
import {
  Box,
  Flex,
  Text,
} from "@mantine/core";
import SyntaxHighlighter from "react-syntax-highlighter";
import { a11yLight } from "react-syntax-highlighter/dist/esm/styles/hljs";

const PythonCodeDisplay = memo(({ circuit }) => {
  return (
    <Flex direction="column" w="100%" h="100%">
      <Box
        style={{
          flexGrow: 1,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          padding: 14,
          background:
            "linear-gradient(180deg, rgba(250,252,252,0.78) 0%, rgba(246,249,248,0.92) 100%)",
        }}
      >
        <Box
          style={{
            border: "1px solid rgba(111, 134, 133, 0.14)",
            borderRadius: 16,
            overflow: "hidden",
            backgroundColor: "rgba(255,255,255,0.7)",
            boxShadow: "0 10px 30px rgba(30, 49, 48, 0.05)",
            height: "100%",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <Box
            px="md"
            py="sm"
            style={{
              borderBottom: "1px solid rgba(111, 134, 133, 0.12)",
            }}
          >
            <Text size="xs" fw={700} tt="uppercase" c="#687877" style={{ letterSpacing: "0.07em" }}>
              Generated Circuit Code
            </Text>
          </Box>
          <Box style={{ flex: 1, overflow: "auto" }}>
            <SyntaxHighlighter
              w="100%"
              h="100%"
              wrapLines={true}
              wrapLongLines={true}
              language="python"
              style={a11yLight}
              customStyle={{
                margin: 0,
                backgroundColor: "#f8fafb",
                padding: "18px",
                fontSize: "12px",
                minHeight: "100%",
              }}
            >
              {circuit || "# Generated Python code will appear here."}
            </SyntaxHighlighter>
          </Box>
        </Box>
      </Box>
    </Flex>
  );
});

export default PythonCodeDisplay;
