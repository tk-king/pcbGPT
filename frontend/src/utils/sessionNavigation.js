// Centralises session id <-> URL/localStorage handling.

const SESSION_STORAGE_KEY = "pcbgpt_session_id";
const GENERATE_PREFIX = "/generate/";

export const readInitialSessionId = () => {
  const path = window.location.pathname || "/";
  if (path.startsWith(GENERATE_PREFIX)) {
    return path.replace(GENERATE_PREFIX, "").trim() || null;
  }
  if (path === GENERATE_PREFIX.slice(0, -1)) {
    return null;
  }
  return window.localStorage.getItem(SESSION_STORAGE_KEY);
};

export const persistSessionId = (sessionId) => {
  window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
};

export const clearPersistedSessionId = () => {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
};

export const replaceUrlForSession = (sessionId) => {
  window.history.replaceState({}, "", `${GENERATE_PREFIX}${sessionId}`);
};

export const createSessionId = () => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
};
