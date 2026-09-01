import { normalizeToolArgs } from "../utils/toolEvents";
import { mergeMetrics } from "../utils/metrics";
import {
  persistSessionId,
  replaceUrlForSession,
} from "../utils/sessionNavigation";

const MIN_TOOL_RUNNING_MS = 450;

// Applies session id / context updates that accompany most socket messages.
const adoptMessageEnvelope = (message, { setSessionId, setContext }) => {
  if (message.session_id) {
    setSessionId(message.session_id);
    persistSessionId(message.session_id);
    replaceUrlForSession(message.session_id);
  }
  if (message.context) {
    setContext(() => message.context);
  }
};

// Creates the socket onMessage handler. Kept outside of usePcbGPT so the
// hook stays focused on state ownership rather than protocol details.
export const createChatSocketHandler = ({
  sessionIdRef,
  setSessionId,
  setContext,
  setEvents,
  setSessions,
  setMetrics,
  markTurnActive,
  markTurnComplete,
  nextEventId,
  toolTrack,
}) => {
  const adopt = (message) => adoptMessageEnvelope(message, { setSessionId, setContext });

  return (message) => {
    const event = message.event;
    if (!event) return;

    if (event.type !== "sessions") {
      const activeSessionId = sessionIdRef.current;
      const incomingSessionId = message.session_id ?? null;
      if (activeSessionId && incomingSessionId && incomingSessionId !== activeSessionId) return;
    }

    if (event.type === "metrics") {
      setMetrics((prevMetrics) => mergeMetrics(prevMetrics, event.metrics ?? null));
      return;
    }

    if (event.type === "response.completed" || event.type === "done") {
      markTurnComplete();
      adopt(message);
      return;
    }

    if (event.type === "cancelled") {
      toolTrack.markRunningToolsCancelled();
      markTurnComplete();
      setEvents((prevEvents) => [
        ...prevEvents,
        { type: "info", info: event.message || "Generation stopped.", id: nextEventId() },
      ]);
      adopt(message);
      return;
    }

    if (event.type === "sessions") {
      setSessions(event.sessions ?? []);
      return;
    }

    if (event.type === "tool_call") {
      markTurnActive("keep");
      const explicitToolId = event.id || event.tool_call_id || null;
      const toolKey =
        explicitToolId ||
        (() => {
          const anonymousId = toolTrack.createAnonymousToolId(event.name || "tool");
          toolTrack.enqueueAnonymousToolId(event.name || "tool", anonymousId);
          return anonymousId;
        })();
      toolTrack.clearToolCompletionTimer(toolKey);
      toolTrack.toolRunningSinceRef.current.set(toolKey, Date.now());
      toolTrack.ensureRunningToolEvent(toolKey, event.name || "tool", normalizeToolArgs(event.args));
      setSessionId(message.session_id ?? null);
      adopt(message);
      return;
    }

    if (event.type === "tool_progress") {
      markTurnActive("keep");
      const toolId = event.id || event.tool_call_id || null;
      const progressText = typeof event.message === "string" ? event.message : "";
      toolTrack.appendToolProgress(toolId, event.name || "tool", progressText);
      adopt(message);
      setSessionId(message.session_id ?? null);
      return;
    }

    if (event.type === "tool_result") {
      markTurnActive("keep");
      const toolId =
        event.id ||
        event.tool_call_id ||
        toolTrack.consumeAnonymousToolId(event.name || "tool") ||
        toolTrack.createAnonymousToolId(event.name || "tool");
      const toolKey = toolId;
      let startedAt = toolTrack.toolRunningSinceRef.current.get(toolKey);
      if (typeof startedAt !== "number") {
        toolTrack.ensureRunningToolEvent(toolId, event.name || "tool", {});
        startedAt = Date.now();
        toolTrack.toolRunningSinceRef.current.set(toolKey, startedAt);
      }
      const elapsed = typeof startedAt === "number" ? Date.now() - startedAt : MIN_TOOL_RUNNING_MS;
      const finish = () => {
        toolTrack.clearToolCompletionTimer(toolKey);
        toolTrack.toolRunningSinceRef.current.delete(toolKey);
        toolTrack.finalizeToolResult(toolId, event);
      };

      if (elapsed < MIN_TOOL_RUNNING_MS) {
        toolTrack.clearToolCompletionTimer(toolKey);
        const timer = window.setTimeout(finish, MIN_TOOL_RUNNING_MS - elapsed);
        toolTrack.toolCompletionTimerRef.current.set(toolKey, timer);
      } else {
        finish();
      }
      setSessionId(message.session_id ?? null);
      adopt(message);
      return;
    }

    if (event.type === "error") {
      toolTrack.markRunningToolsCancelled();
      markTurnComplete();
    }

    if (event.type === "text" && (typeof event.delta !== "string" || event.delta.length === 0)) {
      return;
    }

    if (event.type === "text") {
      markTurnActive("keep");
    }

    setEvents((prevEvents) => {
      const updated = [...prevEvents];
      const last = updated[updated.length - 1];
      if (event.type === "text" && last?.type === "text") {
        updated[updated.length - 1] = {
          ...last,
          delta: (last.delta || "") + (event.delta || ""),
        };
        return updated;
      }
      return [...updated, { ...event, id: event.id || nextEventId() }];
    });
    setSessionId(message.session_id ?? null);
    adopt(message);
  };
};
