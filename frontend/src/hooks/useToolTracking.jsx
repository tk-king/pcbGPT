import React from "react";
import { normalizeToolArgs, getToolResultStatus } from "../utils/toolEvents";

const MAX_TOOL_PROGRESS_ENTRIES = 8;
const useToolTracking = (setEvents) => {
  const toolEventIndexRef = React.useRef(new Map());
  const toolRunningSinceRef = React.useRef(new Map());
  const toolCompletionTimerRef = React.useRef(new Map());
  const anonymousToolIdsRef = React.useRef(new Map());
  const anonymousToolCounterRef = React.useRef(0);

  const resetToolTracking = React.useCallback(() => {
    toolEventIndexRef.current = new Map();
    toolRunningSinceRef.current = new Map();
    toolCompletionTimerRef.current.forEach((timer) => window.clearTimeout(timer));
    toolCompletionTimerRef.current.clear();
    anonymousToolIdsRef.current = new Map();
    anonymousToolCounterRef.current = 0;
  }, []);

  const createAnonymousToolId = React.useCallback((toolName) => {
    anonymousToolCounterRef.current += 1;
    return `anon:${toolName || "tool"}:${anonymousToolCounterRef.current}`;
  }, []);

  const enqueueAnonymousToolId = React.useCallback((toolName, toolId) => {
    const key = toolName || "tool";
    const queue = anonymousToolIdsRef.current.get(key) || [];
    anonymousToolIdsRef.current.set(key, [...queue, toolId]);
  }, []);

  const consumeAnonymousToolId = React.useCallback((toolName) => {
    const key = toolName || "tool";
    const queue = anonymousToolIdsRef.current.get(key) || [];
    if (queue.length === 0) return null;
    const [toolId, ...rest] = queue;
    if (rest.length > 0) {
      anonymousToolIdsRef.current.set(key, rest);
    } else {
      anonymousToolIdsRef.current.delete(key);
    }
    return toolId;
  }, []);

  const indexToolEvents = React.useCallback((eventList) => {
    const nextIndex = new Map();
    (eventList || []).forEach((event, index) => {
      if (event?.type === "tool" && event?.id) {
        nextIndex.set(event.id, index);
      }
    });
    toolEventIndexRef.current = nextIndex;
  }, []);

  const findLatestRunningToolIndexByName = React.useCallback((eventList, toolName) => {
    if (!toolName) return -1;
    for (let index = (eventList?.length || 0) - 1; index >= 0; index -= 1) {
      const event = eventList[index];
      if (event?.type === "tool" && event?.name === toolName && event?.status === "running") {
        return index;
      }
    }
    return -1;
  }, []);

  const clearToolCompletionTimer = React.useCallback((toolKey) => {
    const timer = toolCompletionTimerRef.current.get(toolKey);
    if (timer) {
      window.clearTimeout(timer);
      toolCompletionTimerRef.current.delete(toolKey);
    }
  }, []);

  const finalizeToolResult = React.useCallback((toolId, event) => {
    setEvents((prevEvents) => {
      const updated = [...prevEvents];
      const nextStatus = getToolResultStatus(event.output);
      const existingIndex = toolId
        ? toolEventIndexRef.current.get(toolId)
        : findLatestRunningToolIndexByName(updated, event.name || "tool");

      if (Number.isInteger(existingIndex) && existingIndex >= 0 && updated[existingIndex]?.type === "tool") {
        updated[existingIndex] = {
          ...updated[existingIndex],
          id: updated[existingIndex].id || toolId,
          name: updated[existingIndex].name || event.name || "tool",
          output: event.output,
          status: nextStatus,
        };
        if (toolId) {
          toolEventIndexRef.current.set(toolId, existingIndex);
        }
        return updated;
      }

      const fallback = {
        type: "tool",
        id: toolId,
        name: event.name || "tool",
        args: {},
        output: event.output,
        status: nextStatus,
      };
      updated.push(fallback);
      if (toolId) {
        toolEventIndexRef.current.set(toolId, updated.length - 1);
      }
      return updated;
    });
  }, [findLatestRunningToolIndexByName, setEvents]);

  const markRunningToolsCancelled = React.useCallback(() => {
    setEvents((prevEvents) => prevEvents.map((event) => {
      if (event?.type === "tool" && event?.status === "running") {
        return { ...event, status: "cancelled" };
      }
      return event;
    }));
    toolRunningSinceRef.current.clear();
    toolCompletionTimerRef.current.forEach((timer) => window.clearTimeout(timer));
    toolCompletionTimerRef.current.clear();
  }, [setEvents]);

  const ensureRunningToolEvent = React.useCallback((toolId, name, args = {}) => {
    setEvents((prevEvents) => {
      const updated = [...prevEvents];
      const existingIndex = toolId
        ? toolEventIndexRef.current.get(toolId)
        : findLatestRunningToolIndexByName(updated, name || "tool");

      const existingEvent =
        Number.isInteger(existingIndex) && existingIndex >= 0
          ? updated[existingIndex]
          : null;

      if (existingEvent) {
        updated[existingIndex] = {
          ...existingEvent,
          type: "tool",
          id: existingEvent.id || toolId,
          name: existingEvent.name || name || "tool",
          args: existingEvent.args ?? args,
          output: null,
          status: "running",
        };
        if (toolId) {
          toolEventIndexRef.current.set(toolId, existingIndex);
        }
        return updated;
      }

      const runningEvent = {
        type: "tool",
        id: toolId,
        name: name || "tool",
        args,
        output: null,
        status: "running",
      };
      updated.push(runningEvent);
      if (toolId) {
        toolEventIndexRef.current.set(toolId, updated.length - 1);
      }
      return updated;
    });
  }, [findLatestRunningToolIndexByName, setEvents]);

  const appendToolProgress = React.useCallback(
    (toolId, toolName, message) => {
      if (!message) return;
      setEvents((prevEvents) => {
        const updated = [...prevEvents];
        const existingIndex = toolId
          ? toolEventIndexRef.current.get(toolId)
          : findLatestRunningToolIndexByName(updated, toolName || "tool");
        if (
          !Number.isInteger(existingIndex) ||
          existingIndex < 0 ||
          updated[existingIndex]?.type !== "tool"
        ) {
          return updated;
        }
        const target = updated[existingIndex];
        updated[existingIndex] = {
          ...target,
          progressMessage: message,
          progressHistory: [
            ...(target.progressHistory || []),
            message,
          ].slice(-MAX_TOOL_PROGRESS_ENTRIES),
        };
        return updated;
      });
    },
    [findLatestRunningToolIndexByName, setEvents],
  );

  const mapHistoryToEvents = React.useCallback((history) => {
    const result = [];
    const toolCallIdToName = {};
    const toolCallIdToIndex = {};
    const anonymousToolIds = [];
    let pendingAssistantContent = null;
    let pendingToolCallIds = null;
    let histIdCounter = 0;
    const nextHistId = () => { histIdCounter += 1; return `hist_${histIdCounter}`; };

    const flushPendingAssistant = () => {
      if (pendingAssistantContent) {
        result.push({ type: "text", delta: pendingAssistantContent, id: nextHistId() });
        pendingAssistantContent = null;
        pendingToolCallIds = null;
      }
    };

    for (const item of history || []) {
      if (item.role === "user") {
        flushPendingAssistant();
        result.push({ type: "user", content: item.content, id: nextHistId() });
        continue;
      }

      if (item.role === "assistant") {
        if (Array.isArray(item.tool_calls)) {
          flushPendingAssistant();
          const pendingIds = new Set();
          let hasId = false;
          for (const call of item.tool_calls) {
            const name = call?.function?.name;
            const toolId = call.id || createAnonymousToolId(name || "tool");
            const argsRaw = call?.function?.arguments;
            const args = normalizeToolArgs(argsRaw);
            if (toolId && name) {
              toolCallIdToName[toolId] = name;
              pendingIds.add(toolId);
              hasId = true;
            }
            const toolEvent = {
              type: "tool",
              id: toolId,
              name: name || "tool",
              args,
              output: null,
              status: "running",
            };
            result.push(toolEvent);
            if (toolId) {
              toolCallIdToIndex[toolId] = result.length - 1;
            }
            if (!call.id) {
              anonymousToolIds.push(toolId);
            }
          }
          if (item.content) {
            pendingAssistantContent = item.content;
            pendingToolCallIds = hasId ? pendingIds : null;
          }
        } else if (item.content) {
          flushPendingAssistant();
          result.push({ type: "text", delta: item.content, id: nextHistId() });
        }
        continue;
      }

      if (item.role === "tool") {
        const toolCallId = item.tool_call_id || anonymousToolIds.shift() || "";
        const name = toolCallIdToName[toolCallId] || "tool";
        if (toolCallId && Number.isInteger(toolCallIdToIndex[toolCallId])) {
          const index = toolCallIdToIndex[toolCallId];
          result[index] = {
            ...result[index],
            output: item.content,
            status: getToolResultStatus(item.content),
          };
        } else {
          result.push({
            type: "tool",
            id: toolCallId || null,
            name,
            args: {},
            output: item.content,
            status: getToolResultStatus(item.content),
          });
          if (toolCallId) {
            toolCallIdToIndex[toolCallId] = result.length - 1;
          }
        }
        if (pendingToolCallIds instanceof Set && toolCallId) {
          pendingToolCallIds.delete(toolCallId);
          if (pendingToolCallIds.size === 0) {
            flushPendingAssistant();
          }
        }
        continue;
      }
    }

    flushPendingAssistant();

    // Tool calls that never received a result (e.g. the turn was cancelled
    // mid-tool) stay "running" in history. Mark them as cancelled so the
    // activity indicator doesn't show a phantom running tool after the
    // session is reloaded.
    for (let index = 0; index < result.length; index += 1) {
      const entry = result[index];
      if (entry?.type === "tool" && entry.status === "running") {
        result[index] = { ...entry, status: "cancelled", output: entry.output ?? null };
      }
    }

    indexToolEvents(result);
    return result;
  }, [createAnonymousToolId, indexToolEvents]);

  return {
    toolEventIndexRef,
    toolRunningSinceRef,
    toolCompletionTimerRef,
    anonymousToolIdsRef,
    anonymousToolCounterRef,
    resetToolTracking,
    createAnonymousToolId,
    enqueueAnonymousToolId,
    consumeAnonymousToolId,
    indexToolEvents,
    findLatestRunningToolIndexByName,
    clearToolCompletionTimer,
    finalizeToolResult,
    markRunningToolsCancelled,
    ensureRunningToolEvent,
    appendToolProgress,
    mapHistoryToEvents,
  };
};

export default useToolTracking;
