// Derives the list of blocking setup issues shown before chatting is allowed.

export const getSetupIssues = ({ systemSettings, partIndexStatus, partIndexStatusError }) => {
  const issues = [];
  if (!systemSettings.generationModel) {
    issues.push({ key: "generation", label: "Choose a generation model.", target: "settings" });
  }
  if (systemSettings.validationEnabled && !systemSettings.validationModel) {
    issues.push({ key: "validation", label: "Choose a validation model or turn validation off.", target: "settings" });
  }
  if (partIndexStatusError) {
    issues.push({ key: "parts-status", label: partIndexStatusError, target: "parts" });
    return issues;
  }
  if (!partIndexStatus) {
    issues.push({ key: "parts-loading", label: "Checking component index status.", target: "parts" });
    return issues;
  }
  if (!partIndexStatus.embedding_model) {
    issues.push({ key: "embedding", label: "Choose a component embedding model.", target: "parts" });
  }
  if (Number(partIndexStatus.component_count || 0) <= 0) {
    issues.push({ key: "parts-empty", label: "Index KiCad parts before starting a chat.", target: "parts" });
  }
  if (partIndexStatus.needs_reindex) {
    const chroma = partIndexStatus.chromadb || {};
    const whoosh = partIndexStatus.whoosh || {};
    const expected = Number(partIndexStatus.expected_part_count ?? partIndexStatus.component_count ?? 0);
    const details = [];
    if (
      partIndexStatus.embedding_model &&
      partIndexStatus.embedding_model_match === false
    ) {
      const builtWith = (chroma.embedding_models || []).join(", ") || "an unknown model";
      details.push(`the embedding index was built with ${builtWith}, not "${partIndexStatus.embedding_model}"`);
    }
    if (expected > 0 && Number(chroma.count || 0) !== expected) {
      details.push(`ChromaDB holds ${Number(chroma.count || 0).toLocaleString()} of ${expected.toLocaleString()} parts`);
    }
    if (expected > 0 && (!whoosh.index_exists || Number(whoosh.count || 0) !== expected)) {
      details.push(`the text search index holds ${Number(whoosh.count || 0).toLocaleString()} of ${expected.toLocaleString()} parts`);
    }
    const detailText = details.length > 0 ? ` (${details.join("; ")})` : "";
    issues.push({
      key: "parts-reindex",
      label: `Part index needs attention${detailText}. Reindex the parts before starting a chat.`,
      target: "parts",
    });
  }
  return issues;
};
