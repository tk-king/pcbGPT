import { Box, Button, Text, Textarea } from "@mantine/core";
import { IconChevronLeft } from "@tabler/icons-react";

// Dropdown panel for editing a single model's request kwargs.
const ModelSettingsView = ({
  activeModel,
  requestKwargsDraft,
  onRequestKwargsDraftChange,
  onSave,
  isSaving,
  error,
  onBack,
}) => (
  <Box px="xs" py={6}>
    <Button
      variant="subtle"
      size="compact-xs"
      leftSection={<IconChevronLeft size={14} />}
      onClick={onBack}
    >
      {activeModel?.name || activeModel?.id || "Model settings"}
    </Button>
    <Textarea
      mt="xs"
      label="Request kwargs"
      description="JSON merged into requests for this model. Use null to remove a global default."
      autosize
      minRows={7}
      maxRows={14}
      value={requestKwargsDraft}
      onChange={(event) => onRequestKwargsDraftChange(event.currentTarget.value)}
      styles={{ input: { fontFamily: "monospace", fontSize: 12 } }}
    />
    <Text mt={6} size="xs" c="#607070">
      Example: {`{"reasoning_effort":"high","temperature":1}`}
    </Text>
    {error ? (
      <Text mt={6} size="xs" c="red">{error}</Text>
    ) : null}
    <Button
      mt="xs"
      size="xs"
      fullWidth
      loading={isSaving}
      onClick={onSave}
    >
      Save model kwargs
    </Button>
  </Box>
);

export default ModelSettingsView;
