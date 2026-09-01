import { Text, Box, Button, Menu, TextInput, PasswordInput } from "@mantine/core";
import { IconChevronLeft } from "@tabler/icons-react";

const CustomProviderForm = ({
  providerNameInput,
  baseUrlInput,
  apiKeyInput,
  customProvider,
  customProviderError,
  onProviderNameChange,
  onBaseUrlChange,
  onApiKeyChange,
  onBack,
  onSubmit,
  isSaving,
  canApply,
}) => {
  const savedProviderMatchesInput = (
    String(customProvider?.providerName || "").trim().toLowerCase() ===
    String(providerNameInput || "").trim().toLowerCase()
  );

  return (
    <Box className="chat-custom-provider-panel">
      <Menu.Item onClick={onBack} leftSection={<IconChevronLeft size={14} />}>
        Custom Provider
      </Menu.Item>
      <Menu.Divider />
      <Box px="xs" py={6}>
        <TextInput
          label="Provider name"
          placeholder="openrouter"
          size="xs"
          value={providerNameInput}
          onChange={(event) => onProviderNameChange(event.currentTarget.value)}
        />
        <TextInput
          mt="xs"
          label="Base URL"
          placeholder="https://openrouter.ai/api/v1"
          size="xs"
          value={baseUrlInput}
          onChange={(event) => onBaseUrlChange(event.currentTarget.value)}
        />
        <PasswordInput
          mt="xs"
          label="API Key"
          placeholder={customProvider?.hasApiKey && savedProviderMatchesInput
            ? `Configured ${customProvider.apiKeyPreview || ""}`
            : "sk-..."}
          size="xs"
          value={apiKeyInput}
          onChange={(event) => onApiKeyChange(event.currentTarget.value)}
        />
        {customProvider?.hasApiKey && savedProviderMatchesInput && (
          <Text mt={4} size="xs" c="#607070">
            API key configured {customProvider.apiKeyPreview || ""}
          </Text>
        )}
        {customProviderError && (
          <Text mt={6} size="xs" c="red">
            {customProviderError}
          </Text>
        )}
        <Button
          mt="xs"
          size="xs"
          fullWidth
          loading={isSaving}
          disabled={!canApply}
          onClick={onSubmit}
        >
          Save and use provider
        </Button>
      </Box>
    </Box>
  );
};

export default CustomProviderForm;
