import React from "react";
import { getPartIndexStatus } from "../api/parts.js";

const usePartIndexStatus = () => {
  const [partIndexStatus, setPartIndexStatus] = React.useState(null);
  const [partIndexStatusError, setPartIndexStatusError] = React.useState("");

  const updatePartIndexStatus = React.useCallback((data) => {
    if (!data) return;
    setPartIndexStatus(data);
    setPartIndexStatusError("");
  }, []);

  const refreshPartIndexStatus = React.useCallback(async () => {
    try {
      const data = await getPartIndexStatus();
      updatePartIndexStatus(data);
      return data;
    } catch (error) {
      setPartIndexStatusError(error?.message || "Failed to load part index status.");
      return null;
    }
  }, [updatePartIndexStatus]);

  React.useEffect(() => {
    let cancelled = false;
    const loadPartIndexStatus = async () => {
      try {
        const data = await getPartIndexStatus();
        if (!cancelled) {
          updatePartIndexStatus(data);
        }
      } catch (error) {
        if (!cancelled) {
          setPartIndexStatusError(error?.message || "Failed to load part index status.");
        }
      }
    };
    loadPartIndexStatus();
    return () => { cancelled = true; };
  }, [updatePartIndexStatus]);

  return {
    partIndexStatus,
    partIndexStatusError,
    updatePartIndexStatus,
    refreshPartIndexStatus,
  };
};

export default usePartIndexStatus;
