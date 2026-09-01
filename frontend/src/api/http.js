// Small fetch wrapper used by every API module.
// Keeps error extraction consistent across endpoints.

const extractErrorMessage = async (response, fallback) => {
  let message = fallback;
  try {
    const data = await response.json();
    message = data?.detail || data?.message || message;
  } catch {
    try {
      const text = await response.text();
      message = text || message;
    } catch {
      // keep fallback
    }
  }
  return message;
};

export const requestJson = async (path, { fallbackError = "Request failed.", ...options } = {}) => {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    throw new Error(error?.message || "Network error.");
  }

  if (!response.ok) {
    throw new Error(await extractErrorMessage(response, fallbackError));
  }
  return response.json();
};

export const postJson = (path, payload, options = {}) =>
  requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    ...options,
  });

export const patchJson = (path, payload, options = {}) =>
  requestJson(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    ...options,
  });
