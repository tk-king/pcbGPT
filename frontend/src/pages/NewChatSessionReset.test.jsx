import { describe, it, expect, beforeEach } from "vitest";
import { renderUi as render, screen, waitFor } from "../test/ui.jsx";
import userEvent from "@testing-library/user-event";

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

describe("repro: new chat keeps old circuit", () => {
  beforeEach(() => {
    resetBackendMock();
    window.localStorage.setItem("pcbgpt_session_id", "sessOLD");
    backendMock.session = {
      session_id: "sessOLD",
      context: {
        generation_model_name: "gen-model-x",
        circuit: "OLD_CIRCUIT_CODE_FROM_ANOTHER_CHAT",
      },
      history: [
        { role: "user", content: "make me a circuit" },
        { role: "assistant", content: "done" },
      ],
    };
  });

  it("clears the circuit pane after new chat + non-circuit message", async () => {
    render(<App />);
    await waitFor(() => {
      expect(apiMocks.sessions.fetchSession).toHaveBeenCalledWith("sessOLD");
    });

    // Old chat shows the old circuit.
    expect(await screen.findByText(/OLD_CIRCUIT_CODE/)).toBeInTheDocument();

    // Click "New chat".
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /new chat/i }));

    // Circuit pane must be cleared immediately.
    await waitFor(() => {
      expect(screen.queryByText(/OLD_CIRCUIT_CODE/)).not.toBeInTheDocument();
    });

    // Send a plain non-circuit message.
    const input = screen.getByPlaceholderText(/ask a question or request a circuit/i);
    await user.type(input, "hello what can you do{Enter}");

    // REGRESSION: the message must carry the NEW session id, not the old one.
    const sent = backendMock.sentSocketMessages.at(-1);
    expect(sent.session_id).not.toBe("sessOLD");
    const newSessionId = sent.session_id;
    console.log("sent session_id:", newSessionId);

    emitSocketEvent({
      event: { type: "text", delta: "Hi! I can help with schematics." },
      context: {
        generation_model_name: "gen-model-x",
        validation_model_name: "val-model-x",
        validation_enabled: true,
        circuit: null,
        kicad_project_name: null,
        kicad_project_path: null,
        schematic_pdf_path: null,
        schematic_pdf_base64: null,
        kicad_errors: null,
        prompt_description: null,
        generation_model_name: "gen-model-x",
        validation_model_name: "val-model-x",
        validation_enabled: true,
        validation_session_id: null,
        validation_history: null,
        validation_has_run: false,
        sync_folder_path: null,
        sync_mode: null,
        sync_display_path: null,
        client_folder_name: null,
        imported_netlist: null,
        project_version: 0,
      },
      session_id: newSessionId,
    });
    emitSocketEvent({
      event: { type: "done" },
      context: {
        circuit: null,
        generation_model_name: "gen-model-x",
      },
      session_id: newSessionId,
    });

    await findTextContent("Hi! I can help with schematics.");

    // The old circuit must NOT reappear once the new session's (clean)
    // context is adopted from the server.
    expect(screen.queryByText(/OLD_CIRCUIT_CODE/)).not.toBeInTheDocument();
  });

  it("adopts the old session context when the server echoes it back", async () => {
    // Simulates the pre-fix behaviour: message sent with the OLD session id,
    // server replies with that session's context containing the circuit.
    render(<App />);
    await waitFor(() => {
      expect(apiMocks.sessions.fetchSession).toHaveBeenCalledWith("sessOLD");
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /new chat/i }));
    await waitFor(() => {
      expect(screen.queryByText(/OLD_CIRCUIT_CODE/)).not.toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/ask a question or request a circuit/i);
    await user.type(input, "hello{Enter}");
    const sent = backendMock.sentSocketMessages.at(-1);

    // Old-session reply must be ignored (session guard).
    emitSocketEvent({
      event: { type: "text", delta: "stale" },
      context: { circuit: "OLD_CIRCUIT_CODE" },
      session_id: "sessOLD",
    });

    // New-session reply is adopted.
    emitSocketEvent({
      event: { type: "done" },
      context: { circuit: null },
      session_id: sent.session_id,
    });

    await waitFor(() => {
      expect(screen.queryByText(/OLD_CIRCUIT_CODE/)).not.toBeInTheDocument();
    });
  });
});
