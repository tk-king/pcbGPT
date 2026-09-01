import React from "react";
import { Box, Button, Group, Menu, Text } from "@mantine/core";
import { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
import CustomProviderForm from "../CustomProviderForm.jsx";
import ProviderModelsView from "./ProviderModelsView.jsx";
import ModelSettingsView from "./ModelSettingsView.jsx";
import {
  getModelLabel,
  parseCustomProviderModelValue,
} from "./modelValue.js";

// Dropdown picker for choosing a model across all configured providers.
// Also handles adding a custom provider and per-model request kwargs.
const ModelPicker = ({
  label,
  value,
  providers,
  onChange,
  disabled,
  customProvider,
  onSaveCustomProvider,
  onRefreshProviderModels,
  onSaveModelRequestKwargs,
  styles,
}) => {
  const [opened, setOpened] = React.useState(false);
  const [view, setView] = React.useState("root");
  const [activeProviderName, setActiveProviderName] = React.useState("");
  const [modelSearch, setModelSearch] = React.useState("");
  const [providerNameInput, setProviderNameInput] = React.useState("");
  const [baseUrlInput, setBaseUrlInput] = React.useState("");
  const [apiKeyInput, setApiKeyInput] = React.useState("");
  const [customProviderError, setCustomProviderError] = React.useState("");
  const [isSavingCustomProvider, setIsSavingCustomProvider] = React.useState(false);
  const [activeModelId, setActiveModelId] = React.useState("");
  const [requestKwargsDraft, setRequestKwargsDraft] = React.useState("{}");
  const [modelSettingsError, setModelSettingsError] = React.useState("");
  const [isSavingModelSettings, setIsSavingModelSettings] = React.useState(false);
  const [isRefreshingModels, setIsRefreshingModels] = React.useState(false);
  const autoRefreshAttemptedRef = React.useRef(new Set());

  const selectedLabel = getModelLabel(providers, value);
  const canApplyCustomProvider = Boolean(
    String(providerNameInput || "").trim() &&
    String(baseUrlInput || "").trim() &&
    !isSavingCustomProvider &&
    onSaveCustomProvider
  );
  const activeProvider = (providers || []).find((provider) => provider.providerName === activeProviderName) || null;
  const activeModel = (activeProvider?.models || []).find((model) => model.id === activeModelId) || null;
  const filteredModels = (activeProvider?.models || []).filter((model) => {
    const needle = modelSearch.trim().toLowerCase();
    if (!needle) {
      return true;
    }
    return String(model.name || "").toLowerCase().includes(needle)
      || String(model.id || "").toLowerCase().includes(needle);
  });

  React.useEffect(() => {
    const parsed = parseCustomProviderModelValue(value);
    if (parsed) {
      setActiveProviderName(parsed.providerName);
    } else if (customProvider) {
      setActiveProviderName(customProvider.providerName || "");
    }
  }, [customProvider, value]);

  const resetCustomProviderForm = React.useCallback(() => {
    setProviderNameInput("");
    setBaseUrlInput("");
    setApiKeyInput("");
    setCustomProviderError("");
  }, []);

  const closeMenu = React.useCallback(() => {
    setOpened(false);
    setView("root");
    setModelSearch("");
    setCustomProviderError("");
  }, []);

  const selectModel = React.useCallback((modelValue) => {
    onChange(modelValue);
    closeMenu();
  }, [closeMenu, onChange]);

  const applyCustomProvider = React.useCallback(async () => {
    if (!canApplyCustomProvider) {
      return;
    }
    setIsSavingCustomProvider(true);
    setCustomProviderError("");
    try {
      const result = await onSaveCustomProvider({
        providerName: providerNameInput,
        baseUrl: baseUrlInput,
        apiKey: apiKeyInput,
        modelName: null,
      });
      setApiKeyInput("");
      setActiveProviderName(providerNameInput.trim().toLowerCase());
      selectModel(result?.modelValue || "");
    } catch (error) {
      setCustomProviderError(error?.message || "Could not save provider settings.");
    } finally {
      setIsSavingCustomProvider(false);
    }
  }, [
    apiKeyInput,
    baseUrlInput,
    canApplyCustomProvider,
    onSaveCustomProvider,
    providerNameInput,
    selectModel,
  ]);

  const openModelSettings = React.useCallback((model) => {
    setActiveModelId(model.id);
    setRequestKwargsDraft(JSON.stringify(model.requestKwargs || {}, null, 2));
    setModelSettingsError("");
    setView("model-settings");
  }, []);

  const refreshModels = React.useCallback(async (providerName = activeProviderName) => {
    if (!providerName || !onRefreshProviderModels) return;
    setIsRefreshingModels(true);
    setModelSettingsError("");
    try {
      await onRefreshProviderModels(providerName);
    } catch (error) {
      setModelSettingsError(error?.message || "Could not refresh provider models.");
    } finally {
      setIsRefreshingModels(false);
    }
  }, [activeProviderName, onRefreshProviderModels]);

  React.useEffect(() => {
    if (
      !opened
      || view !== "provider-models"
      || !activeProviderName
      || !onRefreshProviderModels
      || autoRefreshAttemptedRef.current.has(activeProviderName)
    ) {
      return;
    }
    autoRefreshAttemptedRef.current.add(activeProviderName);
    void refreshModels(activeProviderName);
  }, [activeProviderName, onRefreshProviderModels, opened, refreshModels, view]);

  const saveModelSettings = React.useCallback(async () => {
    if (!activeProviderName || !activeModelId || !onSaveModelRequestKwargs) return;
    let requestKwargs;
    try {
      requestKwargs = JSON.parse(requestKwargsDraft || "{}");
      if (!requestKwargs || typeof requestKwargs !== "object" || Array.isArray(requestKwargs)) {
        throw new Error("Request kwargs must be a JSON object.");
      }
    } catch (error) {
      setModelSettingsError(error?.message || "Request kwargs must be valid JSON.");
      return;
    }
    setIsSavingModelSettings(true);
    setModelSettingsError("");
    try {
      await onSaveModelRequestKwargs({
        providerName: activeProviderName,
        modelId: activeModelId,
        requestKwargs,
      });
      setView("provider-models");
    } catch (error) {
      setModelSettingsError(error?.message || "Could not save model request kwargs.");
    } finally {
      setIsSavingModelSettings(false);
    }
  }, [
    activeModelId,
    activeProviderName,
    onSaveModelRequestKwargs,
    requestKwargsDraft,
  ]);

  return (
    <Box className="chat-model-picker">
      <Text component="label" className="chat-model-picker-label" style={styles?.label}>
        {label}
      </Text>
      <Menu
        opened={opened}
        onChange={(nextOpened) => {
          setOpened(nextOpened);
          if (!nextOpened) {
            setView("root");
          }
        }}
        width={view === "custom-provider" || view === "model-settings" ? 360 : 240}
        position="bottom-start"
        withinPortal
        closeOnItemClick={false}
        middlewares={{ flip: true, shift: true, size: true }}
        styles={{
          dropdown: {
            maxWidth: "calc(100vw - 16px)",
            maxHeight: "calc(100dvh - 16px)",
            overflowY: "auto",
            overscrollBehavior: "contain",
          },
        }}
      >
        <Menu.Target>
          <Button
            className={parseCustomProviderModelValue(value)
              ? "chat-model-picker-button chat-model-picker-button-custom-provider"
              : "chat-model-picker-button"}
            variant="default"
            size="xs"
            fullWidth
            disabled={disabled}
            rightSection={<IconChevronDown size={14} />}
            title={selectedLabel}
          >
            <Text span truncate={parseCustomProviderModelValue(value) ? undefined : "end"}>
              {selectedLabel}
            </Text>
          </Button>
        </Menu.Target>
        <Menu.Dropdown className="chat-model-picker-dropdown">
          {view === "root" ? (
            <>
              {(!providers || providers.length === 0) && (
                <Box px="xs" py="sm">
                  <Text size="xs" c="#607070">No providers saved yet.</Text>
                </Box>
              )}
              {(providers || []).map((provider) => (
                <Menu.Item
                  key={provider.providerName}
                  onClick={() => {
                    setActiveProviderName(provider.providerName);
                    setModelSearch("");
                    setView("provider-models");
                  }}
                  rightSection={<IconChevronRight size={14} />}
                >
                  {provider.providerName}
                </Menu.Item>
              ))}
              <Menu.Item
                onClick={() => {
                  resetCustomProviderForm();
                  setView("custom-provider");
                }}
                rightSection={<IconChevronRight size={14} />}
              >
                Custom Provider
              </Menu.Item>
            </>
          ) : view === "provider-models" ? (
            <ProviderModelsView
              activeProvider={activeProvider}
              modelSearch={modelSearch}
              onModelSearchChange={setModelSearch}
              filteredModels={filteredModels}
              selectedValue={value}
              onSelectModel={selectModel}
              onOpenModelSettings={openModelSettings}
              canConfigureModels={Boolean(onSaveModelRequestKwargs)}
              isRefreshingModels={isRefreshingModels}
              onRefresh={() => void refreshModels()}
              error={modelSettingsError}
              onBack={() => setView("root")}
            />
          ) : view === "model-settings" ? (
            <ModelSettingsView
              activeModel={activeModel}
              requestKwargsDraft={requestKwargsDraft}
              onRequestKwargsDraftChange={setRequestKwargsDraft}
              onSave={saveModelSettings}
              isSaving={isSavingModelSettings}
              error={modelSettingsError}
              onBack={() => {
                setModelSettingsError("");
                setView("provider-models");
              }}
            />
          ) : (
            <CustomProviderForm
              providerNameInput={providerNameInput}
              baseUrlInput={baseUrlInput}
              apiKeyInput={apiKeyInput}
              customProvider={customProvider}
              customProviderError={customProviderError}
              onProviderNameChange={setProviderNameInput}
              onBaseUrlChange={setBaseUrlInput}
              onApiKeyChange={setApiKeyInput}
              onBack={() => setView("root")}
              onSubmit={applyCustomProvider}
              isSaving={isSavingCustomProvider}
              canApply={canApplyCustomProvider}
            />
          )}
        </Menu.Dropdown>
      </Menu>
    </Box>
  );
};

export default ModelPicker;
