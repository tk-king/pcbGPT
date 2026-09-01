import React from "react";
import {
  Box,
  Button,
  Group,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import {
  IconCheck,
  IconChevronDown,
  IconChevronRight,
} from "@tabler/icons-react";

const ProviderSettingsItem = ({ provider, onUpdateProvider, onDeleteProvider }) => {
  const [expanded, setExpanded] = React.useState(false);
  const [baseUrl, setBaseUrl] = React.useState(provider.baseUrl || "");
  const [apiKey, setApiKey] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");

  // Re-sync the fields when the provider list is refreshed from the backend.
  React.useEffect(() => {
    setBaseUrl(provider.baseUrl || "");
  }, [provider.baseUrl]);

  React.useEffect(() => {
    setApiKey("");
    setError("");
    setNotice("");
    setConfirmDelete(false);
  }, [provider.providerName]);

  const trimmedBaseUrl = String(baseUrl || "").trim();
  const hasChanges =
    trimmedBaseUrl !== String(provider.baseUrl || "") ||
    String(apiKey || "").trim() !== "";

  const canSave = Boolean(
    trimmedBaseUrl &&
    hasChanges &&
    !isSaving &&
    typeof onUpdateProvider === "function"
  );

  const handleSave = async () => {
    if (!canSave) return;
    setIsSaving(true);
    setError("");
    setNotice("");
    try {
      await onUpdateProvider({
        providerName: provider.providerName,
        baseUrl: trimmedBaseUrl,
        apiKey: String(apiKey || "").trim() || null,
      });
      setApiKey("");
      setNotice("Provider settings saved.");
    } catch (saveError) {
      setError(saveError?.message || "Could not save provider settings.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (typeof onDeleteProvider !== "function" || isDeleting) return;
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    setIsDeleting(true);
    setError("");
    try {
      await onDeleteProvider(provider.providerName);
      // The parent removes the item from the list; nothing else to do here.
    } catch (deleteError) {
      setError(deleteError?.message || "Could not delete the provider.");
      setConfirmDelete(false);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Box
      style={{
        borderRadius: 12,
        border: "1px solid rgba(111, 134, 133, 0.16)",
        background: expanded
          ? "rgba(250, 252, 251, 0.98)"
          : "rgba(252, 253, 253, 0.98)",
        overflow: "hidden",
      }}
    >
      <UnstyledButton
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
        aria-label={`${expanded ? "Collapse" : "Expand"} settings for ${provider.providerName}`}
        style={{ display: "block", width: "100%", padding: "0.625rem 0.75rem" }}
      >
        <Group justify="space-between" align="center" wrap="nowrap" gap="sm">
          <Group gap="xs" align="center" wrap="nowrap" style={{ minWidth: 0 }}>
            <Text fw={700} size="sm" truncate>
              {provider.providerName}
            </Text>
          </Group>
          <Group gap="xs" wrap="nowrap">
            <Text size="xs" c="#607070">
              {(provider.models || []).length} models
            </Text>
            {expanded ? (
              <IconChevronDown size={14} style={{ color: "#607070" }} />
            ) : (
              <IconChevronRight size={14} style={{ color: "#607070" }} />
            )}
          </Group>
        </Group>
      </UnstyledButton>

      {expanded && (
        <Box px="0.75rem" pb="0.75rem" pt="xs">
          <Stack gap="xs">
            <TextInput
              size="xs"
              label="Base URL"
              value={baseUrl}
              placeholder="https://openrouter.ai/api/v1"
              onChange={(event) => setBaseUrl(event.currentTarget.value)}
            />

            <PasswordInput
              size="xs"
              label="API Key"
              value={apiKey}
              onChange={(event) => setApiKey(event.currentTarget.value)}
              placeholder={
                provider.hasApiKey
                  ? `Configured ${provider.apiKeyPreview || ""} — enter a new key to replace it`
                  : "sk-..."
              }
            />
            {provider.hasApiKey && !apiKey && (
              <Text size="xs" c="#607070">
                API key configured {provider.apiKeyPreview || ""}
              </Text>
            )}

            {error && (
              <Text size="xs" c="red">
                {error}
              </Text>
            )}
            {notice && (
              <Group gap={4} wrap="nowrap">
                <IconCheck size={14} color="teal" />
                <Text size="xs" c="teal">
                  {notice}
                </Text>
              </Group>
            )}

            <Button
              size="xs"
              fullWidth
              loading={isSaving}
              disabled={!canSave}
              onClick={handleSave}
            >
              Save provider settings
            </Button>

            {typeof onDeleteProvider === "function" && (
              <Button
                size="xs"
                fullWidth
                variant={confirmDelete ? "filled" : "light"}
                color="red"
                loading={isDeleting}
                onClick={handleDelete}
              >
                {confirmDelete ? "Click again to confirm delete" : "Delete provider"}
              </Button>
            )}
          </Stack>
        </Box>
      )}
    </Box>
  );
};

const AddProviderPanel = ({ onSaveCustomProvider }) => {
  const [providerName, setProviderName] = React.useState("");
  const [baseUrl, setBaseUrl] = React.useState("");
  const [apiKey, setApiKey] = React.useState("");
  const [isSaving, setIsSaving] = React.useState(false);
  const [error, setError] = React.useState("");

  const trimmedName = String(providerName || "").trim().toLowerCase();
  const trimmedBaseUrl = String(baseUrl || "").trim();
  const canSave = Boolean(
    trimmedName &&
    trimmedBaseUrl &&
    !isSaving &&
    typeof onSaveCustomProvider === "function"
  );

  const handleSave = async () => {
    if (!canSave) return;
    setIsSaving(true);
    setError("");
    try {
      await onSaveCustomProvider({
        providerName: trimmedName,
        baseUrl: trimmedBaseUrl,
        apiKey: String(apiKey || "").trim() || null,
      });
      setProviderName("");
      setBaseUrl("");
      setApiKey("");
    } catch (saveError) {
      setError(saveError?.message || "Could not save the provider.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Box
      px="0.75rem"
      pb="0.75rem"
      pt="xs"
      style={{
        borderRadius: 12,
        border: "1px solid rgba(111, 134, 133, 0.16)",
        background: "rgba(250, 252, 251, 0.98)",
      }}
    >
      <Stack gap="xs">
        <TextInput
          size="xs"
          label="Provider name"
          value={providerName}
          placeholder="openrouter"
          onChange={(event) => setProviderName(event.currentTarget.value)}
        />
        <TextInput
          size="xs"
          label="Base URL"
          value={baseUrl}
          placeholder="https://openrouter.ai/api/v1"
          onChange={(event) => setBaseUrl(event.currentTarget.value)}
        />
        <PasswordInput
          size="xs"
          label="API Key"
          value={apiKey}
          onChange={(event) => setApiKey(event.currentTarget.value)}
          placeholder="sk-..."
        />
        {error && (
          <Text size="xs" c="red">
            {error}
          </Text>
        )}
        <Button
          size="xs"
          fullWidth
          loading={isSaving}
          disabled={!canSave}
          onClick={handleSave}
        >
          Save and use provider
        </Button>
      </Stack>
    </Box>
  );
};

const ProviderSettingsSection = ({
  providers = [],
  onUpdateProvider = null,
  onDeleteProvider = null,
  onSaveCustomProvider = null,
}) => {
  const canAddProvider = typeof onSaveCustomProvider === "function";

  return (
    <Box
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "0.75rem 0.125rem 1rem",
      }}
    >
      {(!providers || providers.length === 0) && (
        <Text size="sm" c="#607070" mb="sm">
          No providers configured yet.
        </Text>
      )}
      <Stack gap="sm">
        {(providers || []).map((provider) => (
          <ProviderSettingsItem
            key={provider.providerName}
            provider={provider}
            onUpdateProvider={onUpdateProvider}
            onDeleteProvider={onDeleteProvider}
          />
        ))}

        {canAddProvider && (
          <Box>
            <Text
              fw={700}
              size="sm"
              c="#607070"
              mt="xs"
              mb={4}
            >
              Create new provider
            </Text>
            <AddProviderPanel onSaveCustomProvider={onSaveCustomProvider} />
          </Box>
        )}
      </Stack>
    </Box>
  );
};

export default ProviderSettingsSection;
