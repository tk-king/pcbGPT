import { useCallback, useEffect, useRef, useState } from "react";
import {
  isDirectoryHandle,
  isFileSystemAPISupported,
  isNativeDirectoryPickerSupported,
  pickDirectoryAsArchive,
  pickNativeDirectory,
  archiveFromHandle,
  storeDirectoryHandle,
  loadDirectoryHandle,
} from "../utils/fileSystem.js";
import { importProject, reimportProject } from "../api/sync.js";

const isPickerCancelError = (err) =>
  err?.name === "AbortError" || /cancel/i.test(err?.message || "");

const useProjectSync = (activeSessionId, applyContextPatch, appendAssistantMessage, contextFields) => {
  const [isSyncing, setIsSyncing] = useState(false);
  const [handleEpoch, setHandleEpoch] = useState(0);
  const dirHandleRef = useRef(null);
  const dirHandleSessionRef = useRef(null);
  const dirNameRef = useRef(null);
  const lastSavedVersionRef = useRef(0);
  const lastSavedBySessionRef = useRef({});
  const currentSessionRef = useRef(null);
  const pendingSelectRef = useRef(null);

  const hasActiveDirectoryHandle =
    isDirectoryHandle(dirHandleRef.current) &&
    dirHandleSessionRef.current === activeSessionId;

  const handleSelectAndSync = useCallback(async () => {
    try {
      setIsSyncing(true);
      const nativePick = await pickNativeDirectory();
      if (nativePick) {
        if (!activeSessionId) {
          pendingSelectRef.current = nativePick;
          dirNameRef.current = nativePick.folderPath || nativePick.folderName;
          setHandleEpoch((prev) => prev + 1);
          return;
        }
        const data = await importProject({
          sessionId: activeSessionId,
          folderPath: nativePick.folderPath,
          folderName: nativePick.folderName,
        });
        applyContextPatch?.(data.context);
        if (data.import_message) {
          appendAssistantMessage?.(data.import_message);
        }
        const nextVersion = data?.context?.project_version || 0;
        lastSavedVersionRef.current = nextVersion;
        lastSavedBySessionRef.current[activeSessionId] = nextVersion;
        dirNameRef.current = nativePick.folderPath || nativePick.folderName;
        setHandleEpoch((prev) => prev + 1);
        return;
      }

      const { archiveBase64, handle, folderName } = await pickDirectoryAsArchive();
      const pickedHandle = isDirectoryHandle(handle) ? handle : null;
      if (pickedHandle) {
        dirHandleRef.current = pickedHandle;
        dirHandleSessionRef.current = activeSessionId || null;
        try {
          await pickedHandle.requestPermission({ mode: "readwrite" });
        } catch (permErr) {
          console.warn("Requesting write permission failed:", permErr);
        }
      }
      dirNameRef.current = folderName || pickedHandle?.name || dirNameRef.current;
      setHandleEpoch((prev) => prev + 1);

      if (!activeSessionId) {
        pendingSelectRef.current = {
          handle: pickedHandle || null,
          archiveBase64: pickedHandle ? null : archiveBase64,
          folderName: folderName || pickedHandle?.name || null,
        };
        return;
      }

      if (pickedHandle) {
        try {
          await storeDirectoryHandle(activeSessionId, pickedHandle);
        } catch (storeErr) {
          console.warn("Failed to store directory handle:", storeErr);
        }
      }
      const data = await importProject({
        sessionId: activeSessionId,
        archiveBase64,
        folderName,
      });
      applyContextPatch?.(data.context);
      if (data.import_message) {
        appendAssistantMessage?.(data.import_message);
      }
      const nextVersion = data?.context?.project_version || 0;
      lastSavedVersionRef.current = nextVersion;
      lastSavedBySessionRef.current[activeSessionId] = nextVersion;
      window.app = window.app || {};
      window.app.__internal = {
        ...(window.app.__internal || {}),
        dirHandleRef,
      };
    } catch (err) {
      if (!isPickerCancelError(err)) {
        console.error(err);
        alert(err.message || "Failed to sync folder");
      }
    } finally {
      setIsSyncing(false);
    }
  }, [activeSessionId, applyContextPatch, appendAssistantMessage]);

  const handleSyncClick = useCallback(async () => {
    try {
      if (!activeSessionId) {
        throw new Error("Session not ready yet. Please wait a moment.");
      }
      setIsSyncing(true);
      if (!isFileSystemAPISupported()) {
        const nativePick = await pickNativeDirectory();
        if (!nativePick) {
          throw new Error("Folder sync requires Chrome's File System Access API.");
        }
        const data = await reimportProject({
          sessionId: activeSessionId,
          folderPath: nativePick.folderPath,
          folderName: nativePick.folderName,
        });
        applyContextPatch?.(data.context);
        if (data.import_message) {
          appendAssistantMessage?.(data.import_message);
        }
        dirNameRef.current = nativePick.folderPath || nativePick.folderName || dirNameRef.current;
        setHandleEpoch((prev) => prev + 1);
        return;
      }

      let folderName =
        dirNameRef.current;

      if (!isDirectoryHandle(dirHandleRef.current) || dirHandleSessionRef.current !== activeSessionId) {
        const picked = await pickDirectoryAsArchive();
        if (!isDirectoryHandle(picked.handle)) {
          throw new Error("Folder sync requires selecting a folder (not just files).");
        }
        dirHandleRef.current = picked.handle;
        dirHandleSessionRef.current = activeSessionId;
        dirNameRef.current = picked.folderName || picked.handle?.name || dirNameRef.current;
        folderName = picked.folderName || folderName;
        setHandleEpoch((prev) => prev + 1);
        try {
          await storeDirectoryHandle(activeSessionId, picked.handle);
        } catch (storeErr) {
          console.warn("Failed to store directory handle:", storeErr);
        }
      }

      if (!isDirectoryHandle(dirHandleRef.current)) {
        throw new Error("Sync folder is invalid. Please reselect the folder.");
      }

      const archive = await archiveFromHandle(dirHandleRef.current);
      const archiveBase64 = archive.archiveBase64;
      folderName = archive.folderName || folderName;

      const data = await reimportProject({
        sessionId: activeSessionId,
        archiveBase64,
        folderName,
      });
      applyContextPatch?.(data.context);
      if (data.import_message) {
        appendAssistantMessage?.(data.import_message);
      }
    } catch (err) {
      if (!isPickerCancelError(err)) {
        console.error(err);
        alert(err.message || "Failed to sync project");
      }
    } finally {
      setIsSyncing(false);
    }
  }, [activeSessionId, applyContextPatch, appendAssistantMessage]);

  useEffect(() => {
    if (!activeSessionId) {
      currentSessionRef.current = null;
      dirHandleRef.current = null;
      dirHandleSessionRef.current = null;
      dirNameRef.current = null;
      return;
    }
    if (currentSessionRef.current !== activeSessionId) {
      if (currentSessionRef.current) {
        lastSavedBySessionRef.current[currentSessionRef.current] =
          lastSavedVersionRef.current;
      }
      currentSessionRef.current = activeSessionId;
      lastSavedVersionRef.current =
        lastSavedBySessionRef.current[activeSessionId] || 0;
      dirHandleRef.current = null;
      dirHandleSessionRef.current = null;
      dirNameRef.current = null;
      setHandleEpoch((prev) => prev + 1);
    }
  }, [activeSessionId]);

  useEffect(() => {
    if (!activeSessionId || !pendingSelectRef.current) return;
    let cancelled = false;
    const runPending = async () => {
      const pending = pendingSelectRef.current;
      if (!pending || cancelled) return;
      pendingSelectRef.current = null;
      setIsSyncing(true);
      try {
        let { archiveBase64, handle, folderName } = pending;
        const folderPath = pending.folderPath;
        if (folderPath) {
          const data = await importProject({
            sessionId: activeSessionId,
            folderPath,
            folderName,
          });
          applyContextPatch?.(data.context);
          const nextVersion = data?.context?.project_version || 0;
          lastSavedVersionRef.current = nextVersion;
          lastSavedBySessionRef.current[activeSessionId] = nextVersion;
          dirNameRef.current = folderPath || folderName || dirNameRef.current;
          setHandleEpoch((prev) => prev + 1);
          return;
        }
        if (handle && !isDirectoryHandle(handle)) handle = null;
        if (handle) {
          dirHandleRef.current = handle;
          dirHandleSessionRef.current = activeSessionId;
          try {
            await handle.requestPermission({ mode: "readwrite" });
          } catch (permErr) {
            console.warn("Requesting write permission failed:", permErr);
          }
          if (!archiveBase64) {
            const archive = await archiveFromHandle(handle);
            archiveBase64 = archive.archiveBase64;
            folderName = archive.folderName || folderName;
          }
          try {
            await storeDirectoryHandle(activeSessionId, handle);
          } catch (storeErr) {
            console.warn("Failed to store directory handle:", storeErr);
          }
        }
        if (!archiveBase64) {
          throw new Error("No folder selected. Please choose a folder first.");
        }
        const data = await importProject({
          sessionId: activeSessionId,
          archiveBase64,
          folderName,
        });
        applyContextPatch?.(data.context);
        const nextVersion = data?.context?.project_version || 0;
        lastSavedVersionRef.current = nextVersion;
        lastSavedBySessionRef.current[activeSessionId] = nextVersion;
        dirNameRef.current = folderName || dirNameRef.current;
        setHandleEpoch((prev) => prev + 1);
      } catch (err) {
        if (!isPickerCancelError(err)) {
          console.error(err);
          alert(err.message || "Failed to sync folder");
        }
      } finally {
        if (!cancelled) setIsSyncing(false);
      }
    };
    runPending();
    return () => { cancelled = true; };
  }, [activeSessionId, applyContextPatch]);

  useEffect(() => {
    let cancelled = false;
    const rehydrateHandle = async () => {
      if (!activeSessionId || !isFileSystemAPISupported()) return;
      if (pendingSelectRef.current) return;
      if (hasActiveDirectoryHandle) return;
      if (dirHandleRef.current && !isDirectoryHandle(dirHandleRef.current)) {
        dirHandleRef.current = null;
        dirHandleSessionRef.current = null;
      }
      if (dirHandleRef.current && dirHandleSessionRef.current === activeSessionId) return;
      try {
        const storedHandle = await loadDirectoryHandle(activeSessionId);
        if (!storedHandle || !isDirectoryHandle(storedHandle) || cancelled) return;
        let permission = "granted";
        if (storedHandle.queryPermission) {
          permission = await storedHandle.queryPermission({ mode: "readwrite" });
        }
        if (permission !== "granted" && storedHandle.requestPermission) {
          permission = await storedHandle.requestPermission({ mode: "readwrite" });
        }
        if (permission !== "granted" || cancelled) return;
        dirHandleRef.current = storedHandle;
        dirHandleSessionRef.current = activeSessionId;
        dirNameRef.current = storedHandle.name || dirNameRef.current;
        setHandleEpoch((prev) => prev + 1);
      } catch (err) {
        console.warn("Failed to rehydrate directory handle:", err);
      }
    };
    rehydrateHandle();
    return () => { cancelled = true; };
  }, [activeSessionId, hasActiveDirectoryHandle]);

  useEffect(() => {
    if (!activeSessionId) return;
    const nextName = contextFields?.client_folder_name || contextFields?.sync_display_path;
    if (nextName) {
      dirNameRef.current = nextName;
    }
  }, [activeSessionId, contextFields?.client_folder_name, contextFields?.sync_display_path]);

  return {
    isSyncing,
    handleEpoch,
    dirHandleRef,
    dirHandleSessionRef,
    dirNameRef,
    lastSavedVersionRef,
    lastSavedBySessionRef,
    hasActiveDirectoryHandle,
    handleSelectAndSync,
    handleSyncClick,
    setHandleEpoch,
    isFileSystemAPISupported: isFileSystemAPISupported(),
    isNativeDirectoryPickerSupported: isNativeDirectoryPickerSupported(),
    // Whether the "Sync" button can re-sync the currently active session.
    canSyncActiveSession:
      Boolean(activeSessionId) &&
      (isNativeDirectoryPickerSupported() ||
        (isFileSystemAPISupported() && hasActiveDirectoryHandle)),
  };
};

export default useProjectSync;
