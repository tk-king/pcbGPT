import React from "react";
import {
  fetchSettings,
  saveCustomProviderRequest,
  saveModelRequestKwargsRequest,
  refreshProviderModelsRequest,
  updateProviderRequest,
  deleteProviderRequest,
  saveSystemSettings,
} from "../api/settings.js";
import { normalizeCustomProvider, normalizeCustomProviders } from "../utils/customProvider";

const DEFAULT_SYSTEM_SETTINGS = {
  generationModel: null,
  validationModel: null,
  validationEnabled: false,
};
const DEFAULT_CUSTOM_PROVIDER_SETTINGS = {
  providerName: "",
  baseUrl: "",
  defaultModel: "",
  models: [],
  hasApiKey: false,
  apiKeyPreview: null,
  isDefault: false,
  source: "default",
  updatedAt: null,
};

const useSettings = () => {
  const [providers, setProviders] = React.useState([]);
  const [systemSettings, setSystemSettings] = React.useState(DEFAULT_SYSTEM_SETTINGS);
  const [settingsHydrated, setSettingsHydrated] = React.useState(false);
  const [customProviderSettings, setCustomProviderSettings] = React.useState(DEFAULT_CUSTOM_PROVIDER_SETTINGS);
  const [customProviders, setCustomProviders] = React.useState([]);
  const settingsDirtyRef = React.useRef(false);
  const settingsHydratedRef = React.useRef(false);

  React.useEffect(() => {
    let cancelled = false;
    const loadSettings = async () => {
      try {
        const data = await fetchSettings();
        if (cancelled) return;
        setProviders(Array.isArray(data.providers) ? data.providers.map(normalizeCustomProvider) : []);
        if (!settingsDirtyRef.current) {
          setSystemSettings({
            generationModel: data.generation_model || DEFAULT_SYSTEM_SETTINGS.generationModel,
            validationModel: data.validation_model || DEFAULT_SYSTEM_SETTINGS.validationModel,
            validationEnabled: Boolean(data.validation_enabled),
          });
        }
        setSettingsHydrated(true);
        setCustomProviderSettings(normalizeCustomProvider(data.custom_provider));
        setCustomProviders(normalizeCustomProviders(data.custom_providers));
      } catch {
        // Keep local defaults when the backend is still starting.
      }
    };
    loadSettings();
    return () => { cancelled = true; };
  }, []);

  const persistSystemSettings = React.useCallback((nextSettings) => {
    saveSystemSettings(nextSettings).catch(() => {
      // Keep the local UI responsive; backend extraction also persists on send.
    });
  }, []);

  const updateSystemSetting = React.useCallback((key, value) => {
    settingsDirtyRef.current = true;
    setSystemSettings((prev) => {
      const next = { ...prev, [key]: value };
      persistSystemSettings(next);
      return next;
    });
  }, [persistSystemSettings]);

  const saveCustomProvider = React.useCallback(async ({
    providerName,
    baseUrl,
    apiKey,
    modelName,
  }) => {
    const data = await saveCustomProviderRequest({ providerName, baseUrl, apiKey, modelName });
    const normalizedProvider = normalizeCustomProvider(data.custom_provider);
    setCustomProviderSettings(normalizedProvider);
    setCustomProviders(normalizeCustomProviders(data.custom_providers));
    setProviders(Array.isArray(data.providers) ? data.providers.map(normalizeCustomProvider) : []);
    return {
      customProvider: normalizedProvider,
      modelValue: data.model_value,
    };
  }, []);

  const applyProviderResponse = React.useCallback((data) => {
    const normalizedProvider = normalizeCustomProvider(data.custom_provider);
    if (normalizedProvider.isDefault) {
      setCustomProviderSettings(normalizedProvider);
    }
    setCustomProviders(normalizeCustomProviders(data.custom_providers));
    setProviders(Array.isArray(data.providers) ? data.providers.map(normalizeCustomProvider) : []);
    return normalizedProvider;
  }, []);

  const refreshProviderModels = React.useCallback(async (providerName) =>
    applyProviderResponse(
      await refreshProviderModelsRequest(providerName),
    ), [applyProviderResponse]);

  const updateProvider = React.useCallback(async ({ providerName, baseUrl, apiKey }) =>
    applyProviderResponse(
      await updateProviderRequest({ providerName, baseUrl, apiKey }),
    ), [applyProviderResponse]);

  const deleteProvider = React.useCallback(async (providerName) => {
    const data = await deleteProviderRequest(providerName);
    setProviders(Array.isArray(data.providers) ? data.providers.map(normalizeCustomProvider) : []);
    setCustomProviders(normalizeCustomProviders(data.custom_providers));
    setCustomProviderSettings(normalizeCustomProvider(data.custom_provider));
    // Drop local model selections pointing at the deleted provider.
    const prefix = `${String(providerName || "").trim().toLowerCase()}.`;
    setSystemSettings((prev) => {
      const next = { ...prev };
      if (String(prev.generationModel || "").startsWith(prefix)) next.generationModel = null;
      if (String(prev.validationModel || "").startsWith(prefix)) next.validationModel = null;
      return next;
    });
    return data;
  }, []);

  const saveModelRequestKwargs = React.useCallback(async ({
    providerName,
    modelId,
    requestKwargs,
  }) =>
    applyProviderResponse(
      await saveModelRequestKwargsRequest({ providerName, modelId, requestKwargs }),
    ), [applyProviderResponse]);

  React.useEffect(() => {
    settingsHydratedRef.current = settingsHydrated;
  }, [settingsHydrated]);

  const hydrateSettingsFromContext = React.useCallback((context) => {
    if (settingsHydratedRef.current || !context) return;
    const generationModel = context?.generation_model_name;
    const validationModel = context?.validation_model_name;
    const validationEnabled = context?.validation_enabled;
    if (!generationModel && !validationModel && typeof validationEnabled !== "boolean") return;

    setSystemSettings((prev) => {
      if (settingsHydratedRef.current) return prev;
      const next = {
        generationModel: generationModel || prev.generationModel,
        validationModel: validationModel || prev.validationModel,
        validationEnabled: typeof validationEnabled === "boolean"
          ? validationEnabled
          : prev.validationEnabled,
      };
      if (
        next.generationModel === prev.generationModel &&
        next.validationModel === prev.validationModel &&
        next.validationEnabled === prev.validationEnabled
      ) {
        return prev;
      }
      return next;
    });
  }, []);

  return {
    providers,
    systemSettings,
    settingsHydrated,
    customProviderSettings,
    customProviders,
    settingsDirtyRef,
    updateSystemSetting,
    saveCustomProvider,
    refreshProviderModels,
    updateProvider,
    deleteProvider,
    saveModelRequestKwargs,
    hydrateSettingsFromContext,
  };
};

export default useSettings;
