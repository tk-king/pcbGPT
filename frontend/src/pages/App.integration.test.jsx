import { describe, it, expect, beforeEach } from "vitest";
import { renderUi as render, screen, waitFor, within } from "../test/ui.jsx";
import userEvent from "@testing-library/user-event";

// Import the backend mock FIRST so vi.mock registrations apply to
// everything imported afterwards (App pulls in the api layer).
import {
  backendMock,
  apiMocks,
  emitSocketEvent,
  resetBackendMock,
} from "../test/backendMock.js";

import App from "../App.jsx";

const findTextContent = async (text) => {
  const matches = await screen.findAllByText(
    (_, element) => element?.textContent === text,
  );
  return matches;
};

async function renderApp({ sessionId = "sess123" } = {}) {
  if (sessionId) {
    window.localStorage.setItem("pcbgpt_session_id", sessionId);
  }
  render(<App />);
  if (sessionId) {
    // Wait for the socket to be up and the initial session to be hydrated.
    await waitFor(() => {
      expect(apiMocks.sessions.fetchSession).toHaveBeenCalledWith(sessionId);
    });
    return;
  }
  await waitFor(() => {
    expect(apiMocks.parts.getPartIndexStatus).toHaveBeenCalled();
  });
}

describe("App (backend mocked)", () => {
  beforeEach(() => {
    resetBackendMock();
  });

  it("renders the shell with sidebar, chat and output panes", async () => {
    await renderApp();

    expect(screen.getByText("Sessions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new chat/i })).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/ask a question or request a circuit/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Python Code" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Schematic PDF" })).toBeInTheDocument();
  });

  it("hydrates the last session from the backend on connect", async () => {
    await renderApp();

    expect(apiMocks.settings.fetchSettings).toHaveBeenCalled();
    expect(apiMocks.parts.getPartIndexStatus).toHaveBeenCalled();
    expect(apiMocks.sessions.fetchSession).toHaveBeenCalledWith("sess123");
  });

  it("stays empty until the first message when no session is stored", async () => {
    await renderApp({ sessionId: null });

    await waitFor(() => {
      expect(apiMocks.parts.getPartIndexStatus).toHaveBeenCalled();
    });
    expect(apiMocks.sessions.fetchSession).not.toHaveBeenCalled();
  });

  it("sends the composed message over the websocket with system settings", async () => {
    const user = userEvent.setup();
    await renderApp();

    const input = screen.getByPlaceholderText(/ask a question or request a circuit/i);
    await user.type(input, "Hello circuit{Enter}");

    expect(backendMock.sentSocketMessages).toEqual([
      {
        input: "Hello circuit",
        session_id: "sess123",
        system_settings: {
          generation_model: "gen-model-x",
          validation_model: "val-model-x",
          validation_enabled: true,
        },
      },
    ]);

    // The user message shows up immediately and the input is cleared.
    expect(await screen.findByText("Hello circuit")).toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("streams assistant deltas into a single message and finalises the turn", async () => {
    const user = userEvent.setup();
    await renderApp();

    await user.type(
      screen.getByPlaceholderText(/ask a question or request a circuit/i),
      "Draw an LED blinker{Enter}",
    );

    emitSocketEvent({
      event: { type: "text", delta: "Here is " },
      session_id: "sess123",
    });
    emitSocketEvent({
      event: { type: "text", delta: "your circuit." },
      session_id: "sess123",
    });

    await findTextContent("Here is your circuit.");

    // While streaming, the activity indicator is shown; after completion
    // the turn settles and the session is adopted from the server.
    emitSocketEvent({
      event: { type: "response.completed" },
      session_id: "sess123",
      context: { generation_model_name: "gen-model-x" },
    });
    await waitFor(() => {
      expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument();
    });
  });

  it("cancels a running turn via the stop button", async () => {
    const user = userEvent.setup();
    await renderApp();

    await user.type(
      screen.getByPlaceholderText(/ask a question or request a circuit/i),
      "Long running task{Enter}",
    );

    const stop = await screen.findByRole("button", { name: /stop/i });
    await user.click(stop);

    expect(backendMock.sentSocketMessages.at(-1)).toEqual({
      action: "cancel",
      session_id: "sess123",
    });
  });

  it("accumulates token usage reported by the backend", async () => {
    await renderApp();

    emitSocketEvent({
      event: {
        type: "metrics",
        metrics: {
          usage: {
            requests: 2,
            input_tokens: 10,
            output_tokens: 5,
            total_tokens: 15,
            max_total_tokens: 4096,
          },
        },
      },
      session_id: "sess123",
    });

    const expected = (4096).toLocaleString();
    expect(await screen.findByText(new RegExp(`max tokens:\\s*${expected}`, "i"))).toBeInTheDocument();
  });

  it("lists sessions pushed by the backend and switches between them", async () => {
    const user = userEvent.setup();
    await renderApp();

    emitSocketEvent({
      event: {
        type: "sessions",
        sessions: [
          { session_id: "sess123", title: "LED driver" },
          { session_id: "sess999", title: "Boost converter" },
        ],
      },
    });

    const sidebarButton = await screen.findByRole("button", {
      name: "Boost converter",
    });
    await user.click(sidebarButton);

    expect(apiMocks.sessions.fetchSession).toHaveBeenCalledWith("sess999");
  });

  it("shows tool activity while a tool runs and its result afterwards", async () => {
    const user = userEvent.setup();
    await renderApp();

    await user.type(
      screen.getByPlaceholderText(/ask a question or request a circuit/i),
      "Find a resistor{Enter}",
    );

    emitSocketEvent({
      event: {
        type: "tool_call",
        id: "tool_1",
        name: "search_component",
        args: { query: "resistor" },
      },
      session_id: "sess123",
    });

    expect(await screen.findByText("Searching components")).toBeInTheDocument();

    emitSocketEvent({
      event: {
        type: "tool_result",
        id: "tool_1",
        name: "search_component",
        result: { components: [] },
      },
      session_id: "sess123",
    });

    await waitFor(() => {
      expect(screen.queryByText("Searching components")).not.toBeInTheDocument();
    });
  }, 15000);

it("replays a hydrated conversation history into the chat", async () => {
    backendMock.session = {
      session_id: "sess123",
      context: { generation_model_name: "gen-model-x" },
      history: [
        { role: "user", content: "Design an LED blinker" },
        {
          role: "assistant",
          tool_calls: [
            {
              id: "call_1",
              function: {
                name: "search_component",
                arguments: JSON.stringify({ query: "LED" }),
              },
            },
          ],
        },
        { role: "tool", tool_call_id: "call_1", content: "Found 3 matching components." },
        { role: "assistant", content: "Here is your LED blinker." },
      ],
    };

    await renderApp();

    // User message and final assistant answer are replayed.
    expect(await screen.findByText("Design an LED blinker")).toBeInTheDocument();
    await findTextContent("Here is your LED blinker.");

    // The historical tool call renders as a completed tool card.
    expect(screen.getByText("Search component")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("Query: LED")).toBeInTheDocument();
  });

  it("renders the session's generated python code in the output pane", async () => {
    backendMock.session = {
      session_id: "sess123",
      context: {
        generation_model_name: "gen-model-x",
        circuit: "led = LED(pin=1)\nled.on()",
        kicad_project_path: "/tmp/proj.kicad_pro",
      },
      history: [],
    };

    await renderApp();

    // The code view is the default right pane.
    expect(screen.getByText("Generated Circuit Code")).toBeInTheDocument();
    await waitFor(() => {
      expect(document.body.textContent).toContain("led.on()");
    });

    // With a circuit present, the netlist download becomes available.
    expect(screen.getByRole("link", { name: /netlist/i })).toHaveAttribute(
      "href",
      expect.stringContaining("/download/netlist/sess123"),
    );
  });

  it("renders the session's schematic pdf and the placeholder without one", async () => {
    backendMock.session = {
      session_id: "sess123",
      context: {
        generation_model_name: "gen-model-x",
        // The backend ships the PDF inline as base64 (kicad-cli export).
        schematic_pdf_base64: "JVBERi0xLjQKJcTl8uXrp/Og0MTGCg==",
      },
      history: [],
    };

    const user = userEvent.setup();
    await renderApp();

    await user.click(screen.getByRole("radio", { name: "Schematic PDF" }));
    const frame = await screen.findByTitle("Schematic PDF");
    expect(frame).toHaveAttribute(
      "src",
      "data:application/pdf;base64,JVBERi0xLjQKJcTl8uXrp/Og0MTGCg==",
    );

    // Switching to a session without a schematic swaps in the placeholder.
    emitSocketEvent({
      event: {
        type: "sessions",
        sessions: [
          { session_id: "sess123", title: "LED driver" },
          { session_id: "sess999", title: "Boost converter" },
        ],
      },
    });
    backendMock.session = {
      session_id: "sess999",
      context: { generation_model_name: "gen-model-x" },
      history: [],
    };

    await user.click(await screen.findByRole("button", { name: "Boost converter" }));
    expect(apiMocks.sessions.fetchSession).toHaveBeenCalledWith("sess999");
    expect(
      await screen.findByText("No schematic PDF available yet."),
    ).toBeInTheDocument();
  });

  it("opens the settings modal and lists parts served by the backend", async () => {
    const user = userEvent.setup();
    await renderApp();

    await user.click(screen.getByRole("button", { name: /open settings/i }));

    // Switch to the Parts tab inside the modal.
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("tab", { name: /parts/i }));

    // The mocked /parts/search payload renders in the list.
    // The name appears in the list item and in the details panel.
    expect((await within(dialog).findAllByText("R_10k")).length).toBeGreaterThan(0);
    expect(apiMocks.parts.searchParts).toHaveBeenCalled();

    // Index counters come from the mocked index-status endpoint.
    expect(within(dialog).getByText(/symbols:\s*42/i)).toBeInTheDocument();
  });
});
