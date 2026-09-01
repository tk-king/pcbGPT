import { apiUrl } from "./base.js";
import { postJson } from "./http.js";

const importPayload = ({ sessionId, archiveBase64, folderName, folderPath }) => ({
  session_id: sessionId,
  archive_b64: archiveBase64,
  folder_path: folderPath,
  folder_name: folderName,
});

// Returns { session_id, context }
export const importProject = async (payload) =>
  postJson(apiUrl("/sync/import"), importPayload(payload), {
    fallbackError: "Project import failed.",
  });

export const reimportProject = async (payload) =>
  postJson(apiUrl("/sync/reimport"), importPayload(payload), {
    fallbackError: "Project re-import failed.",
  });

export const downloadProjectZip = async ({ sessionId }) => {
  let response;
  try {
    response = await fetch(apiUrl(`/download/project/${sessionId}`));
  } catch (error) {
    throw new Error(error?.message || "Network error.");
  }
  if (!response.ok) {
    throw new Error(await response.text() || response.statusText);
  }
  return response.arrayBuffer();
};
