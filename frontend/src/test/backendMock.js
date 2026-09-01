import { vi } from "vitest";

// Shared, mutable state for the mocked backend. Accessible from tests via
// `backendMock` (imported below) and from inside vi.mock factories through
// the hoisted handle.
const backendMockHandle = vi.hoisted(() => ({
  // Messages captured by the fake WebSocket ("client -> server").
  sentSocketMessages: [],
  // Live fake socket instances ("server -> client" is driven by pushing
  // messages through `.handleMessage` on an instance).
  socketInstances: [],
  // Fixture data each mocked endpoint resolves with. Tests can override.
  settings: {
    providers: [],
    generation_model: "gen-model-x",
    validation_model: "val-model-x",
    validation_enabled: true,
    custom_provider: null,
    custom_providers: [],
  },
  partIndexStatus: {
    embedding_model: "embed-model-x",
    component_count: 42,
    footprint_count: 120,
  },
  partsPage: {
    results: [
      {
        key: "Device:R_10k",
        name: "R_10k",
        library: "Device",
        description: "10 kOhm resistor",
        footprints: [],
        pins: [],
      },
    ],
    total: 1,
    page: 1,
    page_size: 25,
  },
  session: {
    session_id: "sess123",
    context: { generation_model_name: "gen-model-x" },
    history: [],
  },
}));

vi.mock("../api/websocket.js", () => ({
  default: class MockWebSocketService {
    constructor(url) {
      this.url = url;
      this.handleMessage = null;
      this.handleOpen = null;
      backendMockHandle.socketInstances.push(this);
    }

    connect() {
      setTimeout(() => this.handleOpen?.(), 0);
    }

    onMessage(callback) {
      this.handleMessage = callback;
    }

    onOpen(callback) {
      this.handleOpen = callback;
    }

    onClose() {}

    onError() {}

    sendMessage(message) {
      backendMockHandle.sentSocketMessages.push(message);
    }

    close() {}

    getCurrentThreadId() {
      return null;
    }
  },
}));

vi.mock("../api/settings.js", () => ({
  fetchSettings: vi.fn(async () => backendMockHandle.settings),
  saveSystemSettings: vi.fn(async () => ({})),
  saveCustomProviderRequest: vi.fn(async () => ({
    custom_provider: null,
    custom_providers: [],
    providers: [],
    model_value: "",
  })),
  refreshProviderModelsRequest: vi.fn(async () => ({
    custom_provider: null,
    custom_providers: [],
    providers: [],
  })),
  saveModelRequestKwargsRequest: vi.fn(async () => ({
    custom_provider: null,
    custom_providers: [],
    providers: [],
  })),
}));

vi.mock("../api/parts.js", () => ({
  getPartIndexStatus: vi.fn(async () => backendMockHandle.partIndexStatus),
  searchParts: vi.fn(async () => backendMockHandle.partsPage),
  uploadPart: vi.fn(async () => ({ message: "uploaded", components: [] })),
}));

vi.mock("../api/kicad.js", () => ({
  checkKicadPaths: vi.fn(async () => ({
    symbol_path: "/kicad/sym",
    footprint_path: "/kicad/fp",
    model_path: "/kicad/3d",
  })),
  configureKicadPaths: vi.fn(async () => ({
    kicad_symbol_valid: true,
    kicad_footprint_valid: true,
    kicad_model_valid: true,
  })),
  setEmbeddingModel: vi.fn(async () => ({})),
  startReindex: vi.fn(async () => ({ job_id: "job1", status: "done", result: {} })),
  getReindexJob: vi.fn(async () => ({ status: "done" })),
  pollReindexJob: vi.fn(async () => ({ status: "done", result: {} })),
}));

vi.mock("../api/sessions.js", () => ({
  fetchSession: vi.fn(async () => backendMockHandle.session),
  deleteSessionRequest: vi.fn(async () => ({ sessions: [] })),
  renameSessionRequest: vi.fn(async () => ({ sessions: [] })),
}));

vi.mock("../api/sync.js", () => ({
  importProject: vi.fn(async () => ({ context: {} })),
  reimportProject: vi.fn(async () => ({ context: {} })),
  downloadProjectZip: vi.fn(async () => new ArrayBuffer(0)),
}));

// Exported separately because vitest does not allow
// `export const ... = vi.hoisted(...)`.
export const backendMock = backendMockHandle;

import * as settingsApi from "../api/settings.js";
import * as partsApi from "../api/parts.js";
import * as kicadApi from "../api/kicad.js";
import * as sessionsApi from "../api/sessions.js";
import * as syncApi from "../api/sync.js";

// Convenience handles so tests can assert on individual endpoints.
export const apiMocks = {
  settings: settingsApi,
  parts: partsApi,
  kicad: kicadApi,
  sessions: sessionsApi,
  sync: syncApi,
};

// Pushes a chat-stream event to the app through the fake WebSocket.
export const emitSocketEvent = (payload) => {
  const instance = backendMockHandle.socketInstances.at(-1);
  if (!instance?.handleMessage) {
    throw new Error("No connected mock WebSocket instance.");
  }
  instance.handleMessage(payload);
};

export const resetBackendMock = () => {
  backendMockHandle.sentSocketMessages.length = 0;
  backendMockHandle.socketInstances.length = 0;
  backendMockHandle.settings = {
    providers: [],
    generation_model: "gen-model-x",
    validation_model: "val-model-x",
    validation_enabled: true,
    custom_provider: null,
    custom_providers: [],
  };
  backendMockHandle.partIndexStatus = {
    embedding_model: "embed-model-x",
    component_count: 42,
    footprint_count: 120,
  };
  Object.values(apiMocks).forEach((module) => {
    Object.values(module).forEach((value) => {
      if (typeof value === "function" && "mockClear" in value) {
        value.mockClear();
      }
    });
  });
};
