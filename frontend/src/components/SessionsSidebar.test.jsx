import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent } from "@testing-library/react";
import { renderUi as render, screen } from "../test/ui.jsx";
import userEvent from "@testing-library/user-event";

// Mock the context hook so the sidebar can be tested in isolation.
const usePcbGPTContext = vi.hoisted(() => vi.fn());
vi.mock("../hooks/usePcbGPTContext.js", () => ({ default: usePcbGPTContext }));

import SessionsSidebar from "./SessionsSidebar.jsx";

const sessions = [
  { session_id: "s1", title: "LED matrix driver" },
  { session_id: "s2", title: "" },
];

function renderSidebar(props = {}) {
  const handlers = {
    sessions,
    sessionId: "s1",
    selectSession: vi.fn(),
    createNewSession: vi.fn(),
    renameSession: vi.fn(async () => true),
    deleteSession: vi.fn(async () => true),
    ...props,
  };
  usePcbGPTContext.mockReturnValue(handlers);
  render(<SessionsSidebar />);
  return handlers;
}

// Hovers the first session's row and opens its "…" menu.
function openSessionMenu() {
  fireEvent.mouseOver(screen.getByRole("button", { name: "LED matrix driver" }));
  const trigger = screen.getByRole("button", {
    name: /session options for led matrix driver/i,
  });
  fireEvent.click(trigger);
  return trigger;
}

describe("SessionsSidebar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists all sessions with fallback titles", () => {
    renderSidebar();
    expect(screen.getByRole("button", { name: "LED matrix driver" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Untitled chat" })).toBeInTheDocument();
  });

  it("shows an empty state without sessions", () => {
    renderSidebar({ sessions: [] });
    expect(screen.getByText(/no sessions yet/i)).toBeInTheDocument();
  });

  it("selects a session on click", async () => {
    const user = userEvent.setup();
    const handlers = renderSidebar();

    await user.click(screen.getByRole("button", { name: "Untitled chat" }));
    expect(handlers.selectSession).toHaveBeenCalledWith("s2");
  });

  it("creates a new session from the header button", async () => {
    const user = userEvent.setup();
    const handlers = renderSidebar();

    await user.click(screen.getByRole("button", { name: /new chat/i }));
    expect(handlers.createNewSession).toHaveBeenCalledTimes(1);
  });

  it("renames a session via the context menu", async () => {
    const user = userEvent.setup();
    const handlers = renderSidebar();

    // Hover the row to reveal the "…" menu (pointer-events are restored
    // via React state), then open it.
    fireEvent.mouseOver(screen.getByRole("button", { name: "LED matrix driver" }));
    // Hover the row to reveal the "…" menu (pointer-events are restored
    // via React state), then open it.
    openSessionMenu();
    await user.click(await screen.findByText("Rename"));


    const input = screen.getByDisplayValue("LED matrix driver");
    await user.clear(input);
    await user.type(input, "Renamed chat{Enter}");

    expect(handlers.renameSession).toHaveBeenCalledWith("s1", "Renamed chat");
    expect(input).not.toBeInTheDocument(); // editing finished
  });

  it("deletes a session after confirmation", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const handlers = renderSidebar();

    openSessionMenu();
    await user.click(await screen.findByText("Delete"));

    expect(handlers.deleteSession).toHaveBeenCalledWith("s1");
    window.confirm.mockRestore();
  });

  it("keeps the session when delete is not confirmed", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const handlers = renderSidebar();

    openSessionMenu();
    await user.click(await screen.findByText("Delete"));

    expect(handlers.deleteSession).not.toHaveBeenCalled();
    window.confirm.mockRestore();
  });
});
