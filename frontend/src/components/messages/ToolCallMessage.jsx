import { memo, useState } from "react";
import {
  Text,
  Box,
  Collapse,
  Paper,
  Stack,
  Group,
  Badge,
  Loader,
  ThemeIcon,
  ActionIcon,
} from "@mantine/core";
import { IconChevronDown, IconChevronUp, IconTool } from "@tabler/icons-react";
import { baseMessageCardStyle } from "./sharedStyles";

const formatToolPayload = (value) => {
  if (value == null || value === "") {
    return "No data";
  }

  if (typeof value === "string") {
    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const isEmptyToolPayload = (value) => {
  if (value == null || value === "") {
    return true;
  }

  if (typeof value === "string") {
    return !value.trim();
  }

  if (Array.isArray(value)) {
    return value.length === 0;
  }

  if (typeof value === "object") {
    return Object.keys(value).length === 0;
  }

  return false;
};

const getToolStatus = (event) => {
  if (event.status === "cancelled") {
    return { label: "Stopped", color: "#8c6b46", tone: "rgba(191, 143, 76, 0.14)" };
  }

  if (event.status === "failed" || event.status === "error") {
    return { label: "Failed", color: "#8c5c5c", tone: "rgba(187, 107, 107, 0.12)" };
  }

  if (event.status === "done") {
    return { label: "Done", color: "#617170", tone: "rgba(111, 134, 133, 0.12)" };
  }

  return { label: "Running", color: "#617170", tone: "rgba(111, 134, 133, 0.12)" };
};

const SEARCH_COMPONENT_TOOL_NAMES = new Set([
  "search_component",
  "search_components",
  "tool_search_components",
  "component_search_agent",
]);

const DATASHEET_TOOL_NAMES = new Set([
  "obtain_needed_information",
]);

const getSearchComponentQuery = (event) => {
  if (!SEARCH_COMPONENT_TOOL_NAMES.has(event.name || "tool")) {
    return null;
  }

  const candidateKeys = ["query", "component", "input"];
  for (const key of candidateKeys) {
    if (typeof event.args?.[key] === "string" && event.args[key].trim()) {
      return event.args[key].trim();
    }
  }

  if (typeof event.args === "string" && event.args.trim()) {
    return event.args.trim();
  }

  return null;
};

const getDatasheetComponentText = (event) => {
  const toolName = event.name || "tool";
  if (!DATASHEET_TOOL_NAMES.has(toolName)) {
    return null;
  }

  const library =
    typeof event.args?.library === "string" ? event.args.library.trim() : "";
  const name =
    typeof event.args?.name === "string" ? event.args.name.trim() : "";

  if (library && name) {
    return `${library}:${name}`;
  }

  const candidateKeys = ["component", "part", "name", "query", "input"];
  for (const key of candidateKeys) {
    if (typeof event.args?.[key] === "string" && event.args[key].trim()) {
      return event.args[key].trim();
    }
  }

  if (typeof event.args === "string" && event.args.trim()) {
    return event.args.trim();
  }

  return null;
};

const getToolTitle = (event) => {
  const toolName = event.name || "tool";
  if (!SEARCH_COMPONENT_TOOL_NAMES.has(toolName)) {
    if (DATASHEET_TOOL_NAMES.has(toolName)) {
      return "Read Datasheet";
    }
    if (toolName === "write_circuit_code") {
      return "Generate Circuit";
    }
    return toolName;
  }
  return "Search component";
};

const getToolQueryText = (event) => {
  const searchQuery = getSearchComponentQuery(event);
  if (searchQuery) {
    return `Query: ${searchQuery}`;
  }

  const datasheetComponent = getDatasheetComponentText(event);
  if (datasheetComponent) {
    return `Part: ${datasheetComponent}`;
  }

  return null;
};

// Progress lines arrive as plain step descriptions; keep only the newest one.
const getProgressMessage = (event) =>
  typeof event.progressMessage === "string" ? event.progressMessage.trim() : "";

const getProgressHistory = (event) =>
  Array.isArray(event.progressHistory) ? event.progressHistory : [];


const ToolCallMessage = memo(({ event }) => {
  const [expanded, setExpanded] = useState(false);
  const parsed = event.args ?? {};
  const status = getToolStatus(event);
  const hasArguments = !isEmptyToolPayload(parsed);
  const hasOutput = event.output != null;
  const hasDetails = hasArguments || hasOutput;
  const toolTitle = getToolTitle(event);
  const toolQueryText = getToolQueryText(event);
  const isRunning = event.status === "running" || event.status == null;
  const progressMessage = getProgressMessage(event);
  const progressHistory = getProgressHistory(event);
  const hasProgressHistory = progressHistory.length > 0;
  const headerAlign = toolQueryText ? "flex-start" : "center";

  return (
    <Paper
      radius={16}
      p="md"
      style={{
        ...baseMessageCardStyle,
        alignSelf: "flex-start",
        width: "100%",
        maxWidth: "100%",
      }}
    >
      <Group justify="space-between" align={headerAlign} wrap="nowrap" gap="md">
        <Group align={headerAlign} wrap="nowrap" gap="sm">
          <ThemeIcon
            variant="light"
            radius="md"
            size="lg"
            color="gray"
            style={{
              backgroundColor: status.tone,
              color: "#475569",
            }}
          >
            <IconTool size={16} />
          </ThemeIcon>
          <Box
            style={{
              minWidth: 0,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            <Group gap="xs" align="center" wrap="wrap">
              <Text fw={700} size="sm" style={{ letterSpacing: "0.01em" }}>
                {toolTitle}
              </Text>
              <Badge variant="light" color={status.color} radius="md">
                {status.label}
              </Badge>
            </Group>
            {toolQueryText && (
              <Text size="xs" c="dimmed">
                {toolQueryText}
              </Text>
            )}
          </Box>
        </Group>

        {hasDetails && (
          <ActionIcon
            variant="subtle"
            color="gray"
            radius="md"
            aria-label={expanded ? "Collapse tool details" : "Expand tool details"}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
          </ActionIcon>
        )}
      </Group>

      {isRunning && progressMessage && (
        <Group
          gap="xs"
          mt="xs"
          wrap="nowrap"
          align="center"
          aria-live="polite"
        >
          <Loader size={12} type="dots" color="gray" />
          <Text size="xs" c="dimmed" style={{ flex: 1, minWidth: 0 }}>
            {progressMessage}
          </Text>
        </Group>
      )}

      <Collapse in={expanded && hasDetails}>
        <Stack gap="sm" mt="md">
          {hasProgressHistory && (
            <Box>
              <Text size="xs" fw={700} tt="uppercase" c="dimmed" mb={6}>
                Progress
              </Text>
              <Box
                component="pre"
                style={{
                  margin: 0,
                  padding: "0.875rem",
                  borderRadius: 8,
                  backgroundColor: "#f3f5f7",
                  color: "#243433",
                  border: "1px solid rgba(111, 134, 133, 0.14)",
                  fontFamily:
                    '"SFMono-Regular", "SF Mono", "Menlo", "Monaco", "Consolas", "Liberation Mono", monospace',
                  fontSize: 12,
                  lineHeight: 1.55,
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                  maxHeight: 200,
                  overflowY: "auto",
                }}
              >
                {(hasProgressHistory ? [...progressHistory] : []).join("\n")}
              </Box>
            </Box>
          )}

          {hasArguments && (
            <Box>
              <Text size="xs" fw={700} tt="uppercase" c="dimmed" mb={6}>
                Arguments
              </Text>
              <Box
                component="pre"
                style={{
                  margin: 0,
                  padding: "0.875rem",
                  borderRadius: 8,
                  backgroundColor: "#f3f5f7",
                  border: "1px solid rgba(111, 134, 133, 0.14)",
                  fontFamily:
                    '"SFMono-Regular", "SF Mono", "Menlo", "Monaco", "Consolas", "Liberation Mono", monospace',
                  fontSize: 13,
                  lineHeight: 1.55,
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                  overflowX: "auto",
                  maxHeight: hasOutput ? 240 : 320,
                }}
              >
                {formatToolPayload(parsed)}
              </Box>
            </Box>
          )}

          {hasOutput && (
            <Box>
              <Group justify="space-between" align="center" mb={6}>
                <Text size="xs" fw={700} tt="uppercase" c="dimmed">
                  Output
                </Text>
              </Group>
              <Box
                component="pre"
                style={{
                  margin: 0,
                  padding: "0.875rem",
                  borderRadius: 8,
                  backgroundColor: "#f3f5f7",
                  color: "#243433",
                  border: "1px solid rgba(111, 134, 133, 0.14)",
                  fontFamily:
                    '"SFMono-Regular", "SF Mono", "Menlo", "Monaco", "Consolas", "Liberation Mono", monospace',
                  fontSize: 13,
                  lineHeight: 1.55,
                  whiteSpace: "pre-wrap",
                  overflowWrap: "anywhere",
                  overflowX: "auto",
                  maxHeight: 320,
                }}
              >
                {formatToolPayload(event.output)}
              </Box>
            </Box>
          )}
        </Stack>
      </Collapse>
    </Paper>
  );
});

export default ToolCallMessage;
