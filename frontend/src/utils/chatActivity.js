// Maps tool activity to a readable status label for the chat activity pill.

const SEARCH_COMPONENT_TOOL_NAMES = new Set([
  "search_component",
  "search_components",
  "tool_search_components",
  "component_search_agent",
]);

const DATASHEET_TOOL_NAMES = new Set([
  "obtain_needed_information",
]);

const getReadableToolName = (toolName) => {
  if (SEARCH_COMPONENT_TOOL_NAMES.has(toolName)) {
    return "Searching components";
  }
  if (DATASHEET_TOOL_NAMES.has(toolName)) {
    return "Reading datasheet";
  }
  if (toolName === "write_circuit_code") {
    return "Generating circuit";
  }
  if (!toolName) {
    return "Running tool";
  }
  return toolName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
};

export const getActivityState = (events, isConnected, isTurnPending) => {
  if (!isConnected) {
    return { tone: "offline", label: "Reconnecting" };
  }
  const runningTools = (events || []).filter(
    (event) => event?.type === "tool" && event?.status === "running",
  );
  if (runningTools.length > 0) {
    const activeTool = runningTools[runningTools.length - 1];
    return { tone: "active", label: getReadableToolName(activeTool?.name) };
  }
  if (isTurnPending) {
    return { tone: "active", label: "Thinking" };
  }
  return null;
};
