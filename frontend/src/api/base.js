const trimTrailingSlash = (value) => value.replace(/\/+$/, "");

const readConfiguredBaseUrl = () => {
  const raw = import.meta.env.VITE_API_BASE_URL;
  if (typeof raw !== "string") {
    return "";
  }
  const trimmed = raw.trim();
  return trimmed ? trimTrailingSlash(trimmed) : "";
};

const configuredBaseUrl = readConfiguredBaseUrl();

export const apiUrl = (path) => {
  if (!path.startsWith("/")) {
    throw new Error(`API path must start with '/': ${path}`);
  }
  return configuredBaseUrl ? `${configuredBaseUrl}${path}` : path;
};

export const websocketUrl = (path) => {
  if (!path.startsWith("/")) {
    throw new Error(`WebSocket path must start with '/': ${path}`);
  }

  if (configuredBaseUrl) {
    const url = new URL(configuredBaseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = path;
    url.search = "";
    url.hash = "";
    return url.toString();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
};
