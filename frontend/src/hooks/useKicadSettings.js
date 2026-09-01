import React from "react";
import {
  checkKicadPaths,
  configureKicadPaths,
  setEmbeddingModel as persistEmbeddingModel,
  startReindex,
  pollReindexJob,
} from "../api/kicad.js";

// KiCad path configuration, embedding model selection and reindex progress.
const useKicadSettings = ({ opened, partIndexStatus, onPartIndexStatusChange, onReindexed }) => {
  const [kicadPaths, setKicadPaths] = React.useState(null);
  const [kicadSymbolPath, setKicadSymbolPath] = React.useState("");
  const [kicadFootprintPath, setKicadFootprintPath] = React.useState("");
  const [kicadModelPath, setKicadModelPath] = React.useState("");
  const [kicadChecking, setKicadChecking] = React.useState(false);
  const [kicadReindexing, setKicadReindexing] = React.useState(false);
  const [kicadError, setKicadError] = React.useState("");
  const [kicadNotice, setKicadNotice] = React.useState("");
  const [reindexProgress, setReindexProgress] = React.useState(null);
  const [embeddingModel, setEmbeddingModelState] = React.useState("");

  // Adopt the embedding model reported by the backend index status.
  React.useEffect(() => {
    if (partIndexStatus?.embedding_model) {
      setEmbeddingModelState(partIndexStatus.embedding_model);
    }
  }, [partIndexStatus]);

  React.useEffect(() => {
    if (!opened) return;
    let cancelled = false;
    const check = async () => {
      try {
        const data = await checkKicadPaths();
        if (cancelled) return;
        setKicadPaths(data);
        setKicadSymbolPath(data.symbol_path || "");
        setKicadFootprintPath(data.footprint_path || "");
        setKicadModelPath(data.model_path || "");
      } catch {
        // ignore
      }
    };
    check();
    return () => { cancelled = true; };
  }, [opened]);

  const setEmbeddingModel = React.useCallback((value) => {
    const nextValue = value || "";
    setEmbeddingModelState(nextValue);
    setKicadError("");
    if (!nextValue) {
      setKicadNotice("");
      return;
    }
    setKicadNotice("Embedding model saved. Reindex to rebuild component embeddings with this model.");
    persistEmbeddingModel(nextValue).catch(() => {});
  }, []);

  const handleCheck = React.useCallback(async () => {
    setKicadChecking(true);
    setKicadError("");
    setKicadNotice("");
    try {
      const data = await configureKicadPaths({
        symbolPath: kicadSymbolPath,
        footprintPath: kicadFootprintPath,
        modelPath: kicadModelPath,
      });
      setKicadPaths(data);
      const symbolValid = data?.kicad_symbol_valid ?? data?.symbol_path_valid ?? null;
      const footprintValid = data?.kicad_footprint_valid ?? data?.footprint_path_valid ?? null;
      const modelValid = data?.kicad_model_valid ?? data?.model_path_valid ?? null;
      if (!symbolValid || !footprintValid || !modelValid) {
        setKicadError("One or more KiCad paths are not valid.");
      }
    } catch (err) {
      setKicadError(`Connection error: ${err.message}`);
    } finally {
      setKicadChecking(false);
    }
  }, [kicadFootprintPath, kicadModelPath, kicadSymbolPath]);

  const handleReindex = React.useCallback(async () => {
    if (!embeddingModel) {
      setKicadError("Choose a component embedding model before reindexing.");
      setKicadNotice("");
      return;
    }
    setKicadReindexing(true);
    setKicadError("");
    setKicadNotice("");
    setReindexProgress({ progress: 0, message: "Queued", status: "queued" });
    try {
      const job = await startReindex({
        symbolPath: kicadSymbolPath,
        footprintPath: kicadFootprintPath,
        modelPath: kicadModelPath,
        embeddingModel,
      });
      if (!job?.job_id) {
        throw new Error("KiCad part reindex did not return a job id.");
      }

      const result = await pollReindexJob(job, setReindexProgress);
      const summary = result.result || {};
      setKicadNotice(
        `Reindexed ${summary.component_count || 0} symbols and ${summary.footprint_count || 0} footprints.`,
      );
      setKicadPaths((prevPaths) => ({
        ...(prevPaths || {}),
        kicad_symbol_valid: true,
        kicad_footprint_valid: true,
        kicad_model_valid: Boolean(summary.model_path),
      }));
      onPartIndexStatusChange?.(summary);
      if (summary.embedding_model) {
        setEmbeddingModelState(summary.embedding_model);
      }
      onReindexed?.();
    } catch (err) {
      setKicadError(err?.message || "KiCad part reindex failed.");
    } finally {
      setKicadReindexing(false);
    }
  }, [
    embeddingModel,
    kicadFootprintPath,
    kicadModelPath,
    kicadSymbolPath,
    onPartIndexStatusChange,
    onReindexed,
  ]);

  return {
    embeddingModel,
    setEmbeddingModel,
    kicadPaths,
    kicadSymbolPath,
    kicadFootprintPath,
    kicadModelPath,
    onSymbolPathChange: setKicadSymbolPath,
    onFootprintPathChange: setKicadFootprintPath,
    onModelPathChange: setKicadModelPath,
    kicadChecking,
    kicadReindexing,
    kicadError,
    kicadNotice,
    reindexProgress,
    handleCheck,
    handleReindex,
  };
};

export default useKicadSettings;
