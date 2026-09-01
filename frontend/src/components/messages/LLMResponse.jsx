import { memo } from "react";
import { Text, Paper } from "@mantine/core";
import { useThrottledValue } from "@mantine/hooks";
import MarkdownContent from "./MarkdownContent";

const LLMResponse = memo(({ event }) => {
  const throttledDelta = useThrottledValue(event.delta, 32);

  return (
    <Paper
      radius={16}
      py="sm"
      px="md"
      style={{
        width: "fit-content",
        maxWidth: "78%",
        borderRadius: 16,
        border: "1px solid rgba(111, 134, 133, 0.16)",
        background:
          "linear-gradient(180deg, rgba(252,253,253,0.98) 0%, rgba(246,249,248,0.94) 100%)",
        boxShadow: "0 8px 24px rgba(30, 49, 48, 0.05)",
        alignSelf: "flex-start",
      }}
    >
      <Text size="xs" fw={700} c="#667776" tt="uppercase" style={{ letterSpacing: "0.06em" }}>
        pcbGPT
      </Text>
      <MarkdownContent content={throttledDelta} />
    </Paper>
  );
});

export default LLMResponse;
