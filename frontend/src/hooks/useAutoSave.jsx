import { useEffect, useRef } from "react";
import { downloadProjectZip } from "../api/sync.js";
import { writeZipToDirectory } from "../utils/fileSystem.js";
import { isDirectoryHandle } from "../utils/fileSystem.js";

const useAutoSave = ({
  activeSessionId,
  context,
  dirHandleRef,
  dirHandleSessionRef,
  dirNameRef,
  handleEpoch,
  lastSavedVersionRef,
  lastSavedBySessionRef,
}) => {
  const autoSaveInFlightRef = useRef(false);

  useEffect(() => {
    const version = context?.project_version;
    if (!activeSessionId || !version || version <= lastSavedVersionRef.current) return;
    if (!isDirectoryHandle(dirHandleRef.current) || dirHandleSessionRef.current !== activeSessionId) return;
    if (autoSaveInFlightRef.current) return;

    autoSaveInFlightRef.current = true;
    const targetVersion = version;

    const saveProject = async () => {
      try {
        const buffer = await downloadProjectZip({ sessionId: activeSessionId });
        const projectName =
          context?.sync_mode === "imported"
            ? context?.kicad_project_name ||
              context?.client_folder_name ||
              dirNameRef.current ||
              "pcbgpt_project"
            : context?.client_folder_name ||
              dirNameRef.current ||
              context?.kicad_project_name ||
              "pcbgpt_project";
        await writeZipToDirectory({
          zipBuffer: buffer,
          directoryHandle: dirHandleRef.current,
          projectName,
        });
        lastSavedVersionRef.current = targetVersion;
        lastSavedBySessionRef.current[activeSessionId] = targetVersion;
      } catch (err) {
        console.error("Auto-save failed", err);
      } finally {
        autoSaveInFlightRef.current = false;
      }
    };

    saveProject();
  }, [
    context?.project_version,
    context?.kicad_project_name,
    context?.client_folder_name,
    context?.sync_mode,
    activeSessionId,
    handleEpoch,
  ]);
};

export default useAutoSave;
