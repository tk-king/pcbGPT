import { describe, it, expect } from "vitest";
import { renderUi as render, screen } from "../../test/ui.jsx";
import DownloadButton from "./DownloadButton.jsx";

describe("DownloadButton", () => {
  it("renders an enabled link when a href is given", () => {
    render(<DownloadButton href="/download/netlist/s1">Netlist</DownloadButton>);
    const link = screen.getByRole("link", { name: /netlist/i });
    expect(link).toHaveAttribute("href", "/download/netlist/s1");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).not.toBeDisabled();
  });

  it("is disabled without a href", () => {
    render(<DownloadButton>Netlist</DownloadButton>);
    const el = screen.getByText("Netlist").closest("a");
    expect(el).toHaveAttribute("disabled");
  });
});
