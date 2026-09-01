import { apiUrl } from "./base.js";
import { requestJson, postJson } from "./http.js";

export const checkKicadPaths = async () =>
  requestJson(apiUrl("/system/kicad-check"), {
    fallbackError: "Could not read KiCad configuration.",
  });

export const configureKicadPaths = async ({ symbolPath, footprintPath, modelPath }) =>
  postJson(
    apiUrl("/system/kicad-configure"),
    {
      symbol_path: symbolPath,
      footprint_path: footprintPath,
      model_path: modelPath,
    },
    { fallbackError: "Could not save KiCad configuration." },
  );

export const setEmbeddingModel = async (embeddingModel) =>
  postJson(
    apiUrl("/parts/embedding-model"),
    { embedding_model: embeddingModel },
    { fallbackError: "Could not save the embedding model." },
  );

export const startReindex = async ({ symbolPath, footprintPath, modelPath, embeddingModel }) =>
  postJson(
    apiUrl("/parts/reindex"),
    {
      symbol_path: symbolPath,
      footprint_path: footprintPath,
      model_path: modelPath,
      embedding_model: embeddingModel,
    },
    { fallbackError: "KiCad part reindex failed." },
  );

export const getReindexJob = async (jobId) =>
  requestJson(apiUrl(`/parts/reindex/${jobId}`), {
    fallbackError: "Could not read reindex progress.",
  });

// Polls a reindex job until it leaves the queued/running state.
export const pollReindexJob = async (job, onProgress, pollIntervalMs = 800) => {
  let current = job;
  onProgress?.(current);
  while (current.status === "queued" || current.status === "running") {
    await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    current = await getReindexJob(current.job_id);
    onProgress?.(current);
  }
  if (current.status === "failed") {
    throw new Error(current.error || "KiCad part reindex failed.");
  }
  return current;
};
