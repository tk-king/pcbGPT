export const normalizeToolArgs = (argsRaw) => {
  if (typeof argsRaw === "string") {
    try {
      return JSON.parse(argsRaw);
    } catch {
      return argsRaw;
    }
  }
  return argsRaw ?? {};
};

export const getToolResultStatus = (output) => {
  if (typeof output !== "string") {
    return "done";
  }

  const normalized = output.trim().toLowerCase();
  const failurePrefixes = [
    "tool execution failed:",
    "error executing circuit code:",
    "circuit code did not execute due to errors:",
    "error extracting circuit from code:",
    "circuit validation failed:",
    "validation failed:",
    "kicad-cli failed:",
    "kicad project/pdf generation failed:",
    "netlist conversion failed:",
    "agent run failed:",
    "failed:",
    "error:",
  ];

  return failurePrefixes.some((prefix) => normalized.startsWith(prefix))
    ? "failed"
    : "done";
};
