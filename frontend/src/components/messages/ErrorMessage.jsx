import { memo } from "react";
import { Text, Paper } from "@mantine/core";

const ErrorMessage = memo(({ message }) => (
  <Paper
    radius={16}
    py="sm"
    px="md"
    style={{
      width: "fit-content",
      maxWidth: "78%",
      borderRadius: 16,
      border: "1px solid rgba(187, 107, 107, 0.28)",
      background:
        "linear-gradient(180deg, rgba(254,245,245,0.98) 0%, rgba(252,236,236,0.94) 100%)",
      boxShadow: "0 8px 24px rgba(120, 47, 47, 0.06)",
      alignSelf: "flex-start",
    }}
  >
    <Text size="xs" fw={700} c="#8c5c5c" tt="uppercase" style={{ letterSpacing: "0.06em" }}>
      Error
    </Text>
    <Text c="#5f2f2f">{message || "Request failed."}</Text>
  </Paper>
));

export default ErrorMessage;
