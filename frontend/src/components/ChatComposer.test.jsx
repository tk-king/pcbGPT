import { describe, it, expect, vi } from "vitest";
import { renderUi as render, screen } from "../test/ui.jsx";
import userEvent from "@testing-library/user-event";
import ChatComposer from "./ChatComposer.jsx";

const baseProps = {
  chatboxInput: "",
  onInputChange: vi.fn(),
  onSend: vi.fn(),
  onStop: vi.fn(),
  isTurnPending: false,
  isConnected: true,
  isSetupComplete: true,
  setupIssues: [],
  onOpenSettings: vi.fn(),
  onOpenParts: vi.fn(),
};

describe("ChatComposer", () => {
  it("sends the message on Enter and clears nothing itself", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatComposer {...baseProps} onSend={onSend} />);

    const input = screen.getByPlaceholderText(/ask a question/i);
    await user.type(input, "Hello{Enter}");

    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("does not send on Shift+Enter", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatComposer {...baseProps} onSend={onSend} />);

    await user.type(screen.getByPlaceholderText(/ask a question/i), "line{Shift>}{Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("shows the stop button and disables the composer during a pending turn", () => {
    render(<ChatComposer {...baseProps} isTurnPending />);

    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stop/i })).toBeEnabled();
    expect(screen.getByPlaceholderText(/wait for the current turn/i)).toBeDisabled();
  });

  it("disables the send button when setup is incomplete", () => {
    render(
      <ChatComposer
        {...baseProps}
        isSetupComplete={false}
        setupIssues={[
          { key: "generation", label: "Choose a generation model.", target: "settings" },
          { key: "parts-empty", label: "Index KiCad parts before starting a chat.", target: "parts" },
        ]}
      />,
    );

    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
    expect(screen.getByText("System setup required")).toBeInTheDocument();
    expect(screen.getByText(/choose a generation model/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/complete system setup/i)).toBeDisabled();
  });

  it("disables everything while offline", () => {
    render(<ChatComposer {...baseProps} isConnected={false} />);
    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });

  it("routes the open-settings action by issue target", async () => {
    const user = userEvent.setup();
    const onOpenSettings = vi.fn();
    const onOpenParts = vi.fn();
    render(
      <ChatComposer
        {...baseProps}
        isSetupComplete={false}
        onOpenSettings={onOpenSettings}
        onOpenParts={onOpenParts}
        setupIssues={[
          { key: "generation", label: "Choose a generation model.", target: "settings" },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /open settings/i }));
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
    expect(onOpenParts).not.toHaveBeenCalled();
  });
});
