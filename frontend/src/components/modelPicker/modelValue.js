// Helpers for the "provider.model" composite values used by custom providers.

export const parseCustomProviderModelValue = (value) => {
  const cleaned = String(value || "").trim();
  if (!cleaned) {
    return null;
  }
  const separatorIndex = cleaned.indexOf(".");
  if (separatorIndex <= 0 || separatorIndex >= cleaned.length - 1) {
    return null;
  }
  const providerName = cleaned.slice(0, separatorIndex).trim().toLowerCase();
  const modelName = cleaned.slice(separatorIndex + 1).trim();
  if (!providerName || !modelName) {
    return null;
  }
  return { providerName, modelName };
};

export const buildCustomProviderModelValue = (providerName, modelName) => {
  const provider = String(providerName || "").trim().toLowerCase();
  const model = String(modelName || "").trim();
  return provider && model ? `${provider}.${model}` : "";
};

export const formatUpdatedAt = (value) => {
  if (!value) return "not synced yet";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "sync time unavailable";
  return `synced ${timestamp.toLocaleString()}`;
};

export const getModelLabel = (providers, value) => {
  const parsed = parseCustomProviderModelValue(value);
  if (!parsed) {
    return value || "Select model";
  }
  const provider = (providers || []).find(
    (entry) => entry.providerName === parsed.providerName,
  );
  const model = (provider?.models || []).find((entry) => entry.id === parsed.modelName);
  if (!provider) {
    return `${parsed.providerName} / ${parsed.modelName}`;
  }
  return `${provider.providerName} / ${model?.name || model?.id || parsed.modelName}`;
};
