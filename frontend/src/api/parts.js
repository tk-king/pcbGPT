import { apiUrl } from "./base.js";
import { requestJson } from "./http.js";

export const getPartIndexStatus = async () =>
  requestJson(apiUrl("/parts/index-status"), {
    fallbackError: "Failed to load part index status.",
  });

export const searchParts = async ({ query = "", page = 1, pageSize = 25 } = {}) => {
  const params = new URLSearchParams({
    query,
    page: String(page),
    page_size: String(pageSize),
  });
  return requestJson(apiUrl(`/parts/search?${params.toString()}`), {
    fallbackError: "Failed to load parts.",
  });
};

export const uploadPart = async ({ kicadSym, kicadMod, stepFile } = {}) => {
  const formData = new FormData();
  formData.append("kicad_sym", kicadSym);
  formData.append("kicad_mod", kicadMod);
  if (stepFile) {
    formData.append("step_file", stepFile);
  }
  return requestJson(apiUrl("/parts/upload"), {
    method: "POST",
    body: formData,
    fallbackError: "Failed to upload part.",
  });
};
