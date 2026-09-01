import React from "react";
import useWebSocket from "./useWebSocket";
import { deleteDirectoryHandle } from "../utils/fileSystem.js";
import {
  clearPersistedSessionId,
  createSessionId,
  persistSessionId,
  readInitialSessionId,
  replaceUrlForSession,
} from "../utils/sessionNavigation.js";
import useSettings from "./useSettings.js";
import usePartIndexStatus from "./usePartIndexStatus";
import useToolTracking from "./useToolTracking";
import { createChatSocketHandler } from "./chatSocketHandler.js";
import {
  deleteSessionRequest,
  fetchSession,
  renameSessionRequest,
} from "../api/sessions.js";

const SYSTEM_SETTING_CONTEXT_KEYS = {
  generationModel: "generation_model_name",
  validationModel: "validation_model_name",
  validationEnabled: "validation_enabled",
};

const usePcbGPT = () => {
  const [chatboxInput, setChatboxInput] = React.useState("");
  const [context, setContext] = React.useState({});
  const [events, setEvents] = React.useState([]);
  const [isTurnPending, setIsTurnPending] = React.useState(false);
  const [sessionId, setSessionId] = React.useState(readInitialSessionId);
  const [sessions, setSessions] = React.useState([]);
  const [metrics, setMetrics] = React.useState(null);

  const settings = useSettings();
  const partIndex = usePartIndexStatus();
  const toolTrack = useToolTracking(setEvents);

  const hasHydratedInitialSessionRef = React.useRef(false);
  const eventIdCounterRef = React.useRef(0);
  const sessionIdRef = React.useRef(sessionId);
  const pendingClearTimerRef = React.useRef(null);

  const nextEventId = React.useCallback(() => {
    eventIdCounterRef.current += 1;
    return `evt_${eventIdCounterRef.current}`;
  }, []);

  React.useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  React.useEffect(() => {
    settings.hydrateSettingsFromContext(context);
  }, [
    context?.generation_model_name,
    context?.validation_model_name,
    context?.validation_enabled,
    settings.hydrateSettingsFromContext,
  ]);

  // ---- Turn lifecycle -----------------------------------------------------

  const clearPendingTimer = React.useCallback(() => {
    if (pendingClearTimerRef.current) {
      window.clearTimeout(pendingClearTimerRef.current);
      pendingClearTimerRef.current = null;
    }
  }, []);

  const markTurnActive = React.useCallback((mode = "keep") => {
    setIsTurnPending(true);
    clearPendingTimer();
    if (mode === "settle") {
      pendingClearTimerRef.current = window.setTimeout(() => {
        setIsTurnPending(false);
        pendingClearTimerRef.current = null;
      }, 1200);
    }
  }, [clearPendingTimer]);

  const markTurnComplete = React.useCallback(() => {
    clearPendingTimer();
    setIsTurnPending(false);
  }, [clearPendingTimer]);

  // ---- Context / event helpers --------------------------------------------

  const applyContextPatch = React.useCallback((partialCtx) => {
    if (!partialCtx) return;
    setContext((prev) => ({ ...prev, ...partialCtx }));
    if (partialCtx.session_id) {
      setSessionId(partialCtx.session_id);
    }
  }, []);

  const appendAssistantMessage = React.useCallback((content) => {
    const text = typeof content === "string" ? content.trim() : "";
    if (!text) return;
    setEvents((prevEvents) => [
      ...prevEvents,
      { type: "text", delta: text, id: nextEventId() },
    ]);
  }, [nextEventId]);

  const updateSystemSetting = React.useCallback((key, value) => {
    settings.settingsDirtyRef.current = true;
    settings.updateSystemSetting(key, value);
    const contextKey = SYSTEM_SETTING_CONTEXT_KEYS[key];
    if (contextKey) {
      setContext((prevContext) => ({
        ...prevContext,
        [contextKey]: value,
      }));
    }
  }, [settings.updateSystemSetting]);

  // ---- Socket protocol ----------------------------------------------------

  const handleSocketMessage = React.useMemo(
    () =>
      createChatSocketHandler({
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
      }),
    [
      markTurnActive,
      markTurnComplete,
      nextEventId,
      toolTrack.markRunningToolsCancelled,
      toolTrack.createAnonymousToolId,
      toolTrack.enqueueAnonymousToolId,
      toolTrack.clearToolCompletionTimer,
      toolTrack.ensureRunningToolEvent,
      toolTrack.consumeAnonymousToolId,
      toolTrack.finalizeToolResult,
    ],
  );

  const selectSessionById = React.useCallback(
    async (id) => {
      persistSessionId(id);
      replaceUrlForSession(id);
      // Update the active session state too - otherwise the next message is
      // still sent with the previous session id and the backend replies with
      // that session's history/context (e.g. its old circuit).
      setSessionId(id);
      sessionIdRef.current = id;
      setContext({});
      setMetrics(null);
      toolTrack.resetToolTracking();
      setEvents([]);
      markTurnComplete();
    },
    [toolTrack.resetToolTracking, markTurnComplete],
  );

  const { sendSocketMessage, isConnected } = useWebSocket({
    onMessage: handleSocketMessage,
    onReconnect: () => {
      if (sessionId) {
        selectSession(sessionId);
      }
    },
  });

  // ---- Session management -------------------------------------------------

  const selectSession = React.useCallback(
    async (id) => {
      if (!id) return;
      try {
        const data = await fetchSession(id);
        setSessionId(data.session_id);
        persistSessionId(data.session_id);
        replaceUrlForSession(data.session_id);
        setContext(() => data.context ?? {});
        setMetrics(data.context?.metrics ?? null);
        toolTrack.resetToolTracking();
        setEvents(toolTrack.mapHistoryToEvents(data.history ?? []));
        markTurnComplete();
      } catch {
        // ignore
      }
    },
    [toolTrack.resetToolTracking, toolTrack.mapHistoryToEvents, markTurnComplete],
  );

  const createNewSession = React.useCallback(() => {
    const newId = createSessionId();
    selectSessionById(newId);
  }, [selectSessionById]);

  const deleteSession = React.useCallback(
    async (id) => {
      if (!id) return false;
      try {
        await deleteDirectoryHandle(id);
        const data = await deleteSessionRequest(id);
        if (Array.isArray(data.sessions)) {
          setSessions(data.sessions);
        } else {
          setSessions((prev) => prev.filter((s) => s.session_id !== id));
        }
        if (id === sessionId) {
          clearPersistedSessionId();
          createNewSession();
        }
        return true;
      } catch {
        return false;
      }
    },
    [createNewSession, sessionId],
  );

  const renameSession = React.useCallback(async (id, title) => {
    if (!id) return false;
    try {
      const data = await renameSessionRequest(id, title);
      if (Array.isArray(data.sessions)) {
        setSessions(data.sessions);
      }
      return true;
    } catch {
      return false;
    }
  }, []);

  // ---- Chat actions -------------------------------------------------------

  const sendMessageFn = (message) => {
    const trimmedMessage = typeof message === "string" ? message.trim() : "";
    const hasEmbeddingModel = Boolean(partIndex.partIndexStatus?.embedding_model);
    const hasIndexedParts = Number(partIndex.partIndexStatus?.component_count || 0) > 0;
    const hasValidationModel =
      !settings.systemSettings.validationEnabled || Boolean(settings.systemSettings.validationModel);

    if (
      !trimmedMessage ||
      isTurnPending ||
      !settings.systemSettings.generationModel ||
      !hasValidationModel ||
      !hasEmbeddingModel ||
      !hasIndexedParts
    ) {
      return;
    }

    setEvents((prevEvents) => [
      ...prevEvents,
      { type: "user", content: trimmedMessage, id: nextEventId() },
    ]);
    markTurnActive("keep");
    sendSocketMessage({
      input: trimmedMessage,
      session_id: sessionId,
      system_settings: {
        generation_model: settings.systemSettings.generationModel,
        validation_model: settings.systemSettings.validationModel,
        validation_enabled: settings.systemSettings.validationEnabled,
      },
    });
    setChatboxInput("");
  };

  const cancelChat = React.useCallback(() => {
    if (!isTurnPending) return;
    sendSocketMessage({
      action: "cancel",
      session_id: sessionIdRef.current,
    });
  }, [isTurnPending, sendSocketMessage]);

  // ---- Lifecycle ----------------------------------------------------------

  React.useEffect(
    () => () => {
      clearPendingTimer();
      toolTrack.resetToolTracking();
    },
    [clearPendingTimer, toolTrack.resetToolTracking],
  );

  React.useEffect(() => {
    if (isConnected && sessionId && !hasHydratedInitialSessionRef.current) {
      hasHydratedInitialSessionRef.current = true;
      selectSession(sessionId);
    }
  }, [isConnected, sessionId, selectSession]);

  return {
    context,
    sendMessage: sendMessageFn,
    cancelChat,
    events,
    metrics,
    providers: settings.providers,
    systemSettings: settings.systemSettings,
    updateSystemSetting,
    customProviderSettings: settings.customProviderSettings,
    customProviders: settings.customProviders,
    saveCustomProvider: settings.saveCustomProvider,
    refreshProviderModels: settings.refreshProviderModels,
    updateProvider: settings.updateProvider,
    deleteProvider: settings.deleteProvider,
    saveModelRequestKwargs: settings.saveModelRequestKwargs,
    partIndexStatus: partIndex.partIndexStatus,
    partIndexStatusError: partIndex.partIndexStatusError,
    refreshPartIndexStatus: partIndex.refreshPartIndexStatus,
    updatePartIndexStatus: partIndex.updatePartIndexStatus,
    chatboxInput,
    setChatboxInput,
    isConnected,
    sessionId,
    isTurnPending,
    sessions,
    selectSession,
    createNewSession,
    deleteSession,
    renameSession,
    applyContextPatch,
    appendAssistantMessage,
  };
};

export default usePcbGPT;
