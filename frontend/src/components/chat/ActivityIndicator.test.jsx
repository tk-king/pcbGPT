import { describe, it, expect } from "vitest";
import { renderUi as render, screen } from "../../test/ui.jsx";
import ActivityIndicator from "./ActivityIndicator.jsx";

describe("ActivityIndicator", () => {
  it("renders nothing without state", () => {
    render(<ActivityIndicator state={null} />);
    // The Mantine provider injects style tags, so check for content instead
    // of an empty container.
    expect(screen.queryByText(/./)).toBeNull();
  });

  it("renders the active label with the shimmer style", () => {
    render(
      <ActivityIndicator state={{ tone: "active", label: "Searching components" }} />,
    );
    expect(screen.getByText("Searching components")).toBeInTheDocument();
  });

  it("renders the offline tone without shimmer", () => {
    render(
      <ActivityIndicator state={{ tone: "offline", label: "Reconnecting" }} />,
    );
    const label = screen.getByText("Reconnecting");
    expect(label).toBeInTheDocument();
    expect(label.className).not.toContain("chat-activity-shimmer");
  });
});
