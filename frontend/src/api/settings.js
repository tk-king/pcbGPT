import { apiUrl } from "./base.js";
import { patchJson, requestJson, postJson } from "./http.js";

export const fetchSettings = async () =>
  requestJson(apiUrl("/settings"), {
    fallbackError: "Could not load settings.",
  });

export const saveSystemSettings = async ({ generationModel, validationModel, validationEnabled }) =>
  postJson(
    apiUrl("/settings/system"),
    {
      generation_model: generationModel,
      validation_model: validationModel,
      validation_enabled: validationEnabled,
    },
    { fallbackError: "Could not save system settings." },
  );

export const saveCustomProviderRequest = async ({ providerName, baseUrl, apiKey, modelName }) =>
  postJson(
    apiUrl("/settings/custom-provider"),
    {
      provider_name: providerName,
      base_url: baseUrl,
      api_key: apiKey || null,
      model_name: modelName,
    },
    { fallbackError: "Could not save provider settings." },
  );

export const updateProviderRequest = async ({ providerName, baseUrl, apiKey }) =>
  patchJson(
    apiUrl(`/settings/providers/${encodeURIComponent(providerName)}`),
    {
      base_url: baseUrl || null,
      api_key: apiKey || null,
    },
    { fallbackError: "Could not save provider settings." },
  );

export const deleteProviderRequest = async (providerName) =>
  requestJson(apiUrl(`/settings/providers/${encodeURIComponent(providerName)}`), {
    method: "DELETE",
    fallbackError: "Could not delete the provider.",
  });

export const refreshProviderModelsRequest = async (providerName) =>
  postJson(apiUrl(`/settings/providers/${encodeURIComponent(providerName)}/refresh`), undefined, {
    headers: { "Content-Type": "application/json" },
    body: null,
    fallbackError: "Could not refresh provider models.",
  });

export const saveModelRequestKwargsRequest = async ({ providerName, modelId, requestKwargs }) =>
  postJson(
    apiUrl("/settings/model-request-kwargs"),
    {
      provider_name: providerName,
      model_id: modelId,
      request_kwargs: requestKwargs,
    },
    { fallbackError: "Could not save model request kwargs." },
  );
