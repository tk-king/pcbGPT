import { Box, Flex } from "@mantine/core";

// Inline status pill shown under the last chat event while a turn is running.
const ActivityIndicator = ({ state }) => {
  if (!state) return null;

  const isActive = state.tone === "active";
  return (
    <Box pb="sm" pt="xs">
      <Flex
        align="center"
        gap="sm"
        className={isActive ? "chat-activity-shell chat-activity-shell-active" : "chat-activity-shell"}
      >
        <Box className="chat-activity-rail" />
        <Box className={isActive ? "chat-activity-pill chat-activity-pill-active" : "chat-activity-pill"}>
          <Box className={isActive ? "chat-activity-dot chat-activity-dot-active" : "chat-activity-dot"} />
          <span
            className={isActive ? "chat-activity-shimmer" : undefined}
            style={{
              color: isActive ? "#4d6665" : "#8a5a5a",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              fontWeight: 700,
              fontSize: 12,
              textAlign: "center",
            }}
          >
            {state.label}
          </span>
        </Box>
        <Box className="chat-activity-rail" />
      </Flex>
    </Box>
  );
};

export default ActivityIndicator;
