import { describe, it, expect } from "vitest";
import { getActivityState } from "./chatActivity.js";

describe("getActivityState", () => {
  it("reports reconnecting when the socket is down", () => {
    expect(getActivityState([], false, true)).toEqual({
      tone: "offline",
      label: "Reconnecting",
    });
  });

  it("shows nothing when idle and connected", () => {
    expect(getActivityState([], true, false)).toBeNull();
  });

  it("falls back to Thinking while the turn is pending", () => {
    expect(getActivityState([], true, true)).toEqual({
      tone: "active",
      label: "Thinking",
    });
  });

  it("labels running search tools", () => {
    const events = [
      { type: "tool", name: "search_component", status: "running" },
    ];
    expect(getActivityState(events, true, false)).toEqual({
      tone: "active",
      label: "Searching components",
    });
  });

  it("labels datasheet tools", () => {
    const events = [
      { type: "tool", name: "obtain_needed_information", status: "running" },
    ];
    expect(getActivityState(events, true, true)).toEqual({
      tone: "active",
      label: "Reading datasheet",
    });
  });

  it("uses the latest running tool", () => {
    const events = [
      { type: "tool", name: "search_component", status: "done" },
      { type: "tool", name: "write_circuit_code", status: "running" },
    ];
    expect(getActivityState(events, true, false)).toEqual({
      tone: "active",
      label: "Generating circuit",
    });
  });

  it("title-cases unknown tool names", () => {
    const events = [{ type: "tool", name: "some_new_tool", status: "running" }];
    expect(getActivityState(events, true, false)).toEqual({
      tone: "active",
      label: "Some New Tool",
    });
  });
});
