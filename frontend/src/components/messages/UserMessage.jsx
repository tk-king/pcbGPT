import { memo } from "react";
import { Box, Text, Paper } from "@mantine/core";

const UserMessage = memo(({ event }) => (
  <Box style={{ width: "100%", display: "flex", justifyContent: "flex-end" }}>
    <Paper
      radius={16}
      py="sm"
      px="md"
      style={{
        width: "fit-content",
        maxWidth: "78%",
        borderRadius: 16,
        border: "1px solid rgba(101, 137, 136, 0.22)",
        background:
          "linear-gradient(180deg, rgba(234,243,243,0.96) 0%, rgba(223,236,236,0.92) 100%)",
        textAlign: "left",
      }}
    >
      <Text size="xs" fw={700} c="#5d7070" tt="uppercase" style={{ letterSpacing: "0.06em" }}>
        You
      </Text>
      <Text c="#203131">{event.content}</Text>
    </Paper>
  </Box>
));

export default UserMessage;
