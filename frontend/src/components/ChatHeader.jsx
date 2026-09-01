import { Box, Flex, Text, Title, ActionIcon } from "@mantine/core";
import { IconSettings } from "@tabler/icons-react";

const getMaxTokens = (metrics) => {
  if (!metrics) return 0;
  if (typeof metrics.usage?.max_total_tokens === "number") {
    return metrics.usage.max_total_tokens;
  }
  return 0;
};

const ChatHeader = ({
  systemSettings,
  metrics,
  onOpenSettings,
}) => {
  const maxTokens = getMaxTokens(metrics);

  return (
    <Box
      px="md"
      py="sm"
      className="chat-header"
      style={{
        borderBottom: "1px solid rgba(111, 134, 133, 0.14)",
        background:
          "linear-gradient(180deg, rgba(249,251,250,0.94) 0%, rgba(244,248,247,0.88) 100%)",
      }}
    >
      <Box className="chat-header-top">
        <Box className="chat-brand">
          <Box>
            <Flex align="center" gap="sm">
              <Box
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 12,
                  background: "linear-gradient(135deg, rgba(127,178,177,0.28) 0%, rgba(65,119,118,0.18) 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  border: "1px solid rgba(111, 134, 133, 0.18)",
                }}
              >
                <img src="/logo_no_background.png" alt="pcbGPT Logo" width={24} height={24} />
              </Box>
              <Title order={5}>pcbGPT</Title>
            </Flex>
            <Box mt={4}>
              <Text size="xs" c="#667776">Generation Model: {systemSettings.generationModel || "Not configured"}</Text>
              <Text size="xs" c="#667776">Validation Model: {systemSettings.validationModel || "Not configured"}</Text>
              <Text size="xs" c="#667776">Validation: {systemSettings.validationEnabled ? "On" : "Off"}</Text>
            </Box>
          </Box>
        </Box>
        <Flex direction="column" align="flex-end" gap={6}>
          <Flex gap="xs">
            <ActionIcon
              variant="subtle"
              color="gray"
              radius="md"
              size="lg"
              onClick={onOpenSettings}
              aria-label="Open settings"
            >
              <IconSettings size={18} />
            </ActionIcon>
          </Flex>
          {metrics && (
            <Flex className="chat-status" gap="xs" wrap="wrap">
              <Text size="xs" c="#667776">Max Tokens: {maxTokens.toLocaleString()}</Text>
            </Flex>
          )}
        </Flex>
      </Box>
    </Box>
  );
};

export default ChatHeader;
