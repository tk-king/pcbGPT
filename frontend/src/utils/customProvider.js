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

export const normalizeCustomProvider = (raw) => {
  if (!raw || typeof raw !== "object") {
    return DEFAULT_CUSTOM_PROVIDER_SETTINGS;
  }
  return {
    providerName: raw.provider_name || raw.providerName || DEFAULT_CUSTOM_PROVIDER_SETTINGS.providerName,
    baseUrl: raw.base_url || raw.baseUrl || DEFAULT_CUSTOM_PROVIDER_SETTINGS.baseUrl,
    defaultModel: raw.default_model || raw.defaultModel || "",
    models: Array.isArray(raw.models) ? raw.models.map((model) => ({
      id: model.id,
      name: model.name || null,
      requestKwargs: model.request_kwargs || model.requestKwargs || {},
    })) : [],
    hasApiKey: Boolean(raw.has_api_key ?? raw.hasApiKey),
    apiKeyPreview: raw.api_key_preview || raw.apiKeyPreview || null,
    isDefault: Boolean(raw.is_default ?? raw.isDefault),
    source: raw.source || "database",
    updatedAt: raw.updated_at || raw.updatedAt || null,
  };
};

export const normalizeCustomProviders = (raw) => (
  Array.isArray(raw) ? raw.map(normalizeCustomProvider) : []
);
