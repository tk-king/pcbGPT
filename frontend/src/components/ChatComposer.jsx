import { Alert, Box, Button, Flex, Text, Textarea } from "@mantine/core";
import { IconAlertTriangle, IconPlayerStop, IconSend } from "@tabler/icons-react";

const ChatComposer = ({
  chatboxInput,
  onInputChange,
  onSend,
  onStop,
  isTurnPending,
  isConnected,
  isSetupComplete,
  setupIssues,
  onOpenSettings,
  onOpenParts,
}) => {
  const isComposerDisabled = isTurnPending || !isConnected || !isSetupComplete;
  const handleOpenSetup = () => {
    if (setupIssues.some((issue) => issue.target === "settings")) {
      onOpenSettings();
      return;
    }
    onOpenParts();
  };

  return (
    <Box
      px="md"
      py="sm"
      style={{
        borderTop: "1px solid rgba(111, 134, 133, 0.14)",
        background:
          "linear-gradient(180deg, rgba(248,250,249,0.92) 0%, rgba(243,247,246,0.96) 100%)",
      }}
    >
      {setupIssues.length > 0 && (
        <Alert
          mb="sm"
          color="yellow"
          icon={<IconAlertTriangle size={16} />}
          styles={{
            root: {
              backgroundColor: "rgba(255, 248, 224, 0.9)",
              borderColor: "rgba(207, 166, 61, 0.28)",
            },
          }}
        >
          <Flex direction="column" gap={6}>
            <Text size="sm" fw={700} c="#5f4b13">System setup required</Text>
            {setupIssues.map((issue) => (
              <Text key={issue.key} size="xs" c="#6a5b20">
                {issue.label}
              </Text>
            ))}
            <Flex gap="xs" wrap="wrap" mt={2}>
              <Button size="xs" variant="light" color="yellow" onClick={handleOpenSetup}>
                Open settings
              </Button>
            </Flex>
          </Flex>
        </Alert>
      )}
      <Flex w="100%" gap="sm" align="center">
        <Textarea
          w="100%"
          autosize
          minRows={2}
          maxRows={8}
          placeholder={
            isComposerDisabled
              ? (!isSetupComplete ? "Complete system setup before starting…" : "Wait for the current turn to finish…")
              : "Ask a question or request a circuit…"
          }
          value={chatboxInput}
          onChange={(event) => onInputChange(event.target.value)}
          disabled={isComposerDisabled}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          styles={{
            input: {
              backgroundColor: "rgba(255,255,255,0.86)",
              borderColor: "rgba(111, 134, 133, 0.18)",
              borderRadius: 12,
            },
          }}
        />
        {isTurnPending ? (
          <Button
            size="md"
            radius="md"
            color="red"
            variant="light"
            onClick={onStop}
            disabled={!isConnected}
            aria-label="Stop generation"
          >
            <IconPlayerStop size={16} />
          </Button>
        ) : (
          <Button
            size="md"
            radius="md"
            onClick={onSend}
            disabled={isComposerDisabled}
            aria-label="Send message"
          >
            <IconSend size={16} />
          </Button>
        )}
      </Flex>
    </Box>
  );
};

export default ChatComposer;
