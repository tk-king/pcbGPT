import { apiUrl } from "./base.js";
import { requestJson, patchJson } from "./http.js";

export const fetchSession = async (sessionId) =>
  requestJson(apiUrl(`/sessions/${sessionId}`), {
    fallbackError: "Could not load session.",
  });

export const deleteSessionRequest = async (sessionId) =>
  requestJson(apiUrl(`/sessions/${sessionId}`), {
    method: "DELETE",
    fallbackError: "Could not delete session.",
  });

export const renameSessionRequest = async (sessionId, title) =>
  patchJson(
    apiUrl(`/sessions/${sessionId}/title`),
    { title },
    { fallbackError: "Could not rename session." },
  );
