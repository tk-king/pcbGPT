import { describe, it, expect } from "vitest";
import { getSetupIssues } from "./setupIssues.js";

const readySettings = {
  generationModel: "gen-model",
  validationModel: "val-model",
  validationEnabled: true,
};
const readyParts = { embedding_model: "embed", component_count: 5 };

describe("getSetupIssues", () => {
  it("returns no issues when everything is configured", () => {
    expect(
      getSetupIssues({
        systemSettings: readySettings,
        partIndexStatus: readyParts,
        partIndexStatusError: "",
      }),
    ).toEqual([]);
  });

  it("requires a generation model", () => {
    const issues = getSetupIssues({
      systemSettings: { ...readySettings, generationModel: null },
      partIndexStatus: readyParts,
      partIndexStatusError: "",
    });
    expect(issues).toHaveLength(1);
    expect(issues[0].target).toBe("settings");
  });

  it("requires a validation model only when validation is on", () => {
    const off = getSetupIssues({
      systemSettings: { ...readySettings, validationEnabled: false, validationModel: null },
      partIndexStatus: readyParts,
      partIndexStatusError: "",
    });
    expect(off).toHaveLength(0);

    const missing = getSetupIssues({
      systemSettings: { ...readySettings, validationModel: null },
      partIndexStatus: readyParts,
      partIndexStatusError: "",
    });
    expect(missing).toHaveLength(1);
    expect(missing[0].target).toBe("settings");
  });

  it("surfaces part index errors before checking status contents", () => {
    const issues = getSetupIssues({
      systemSettings: readySettings,
      partIndexStatus: null,
      partIndexStatusError: "index unreachable",
    });
    expect(issues).toEqual([
      { key: "parts-status", label: "index unreachable", target: "parts" },
    ]);
  });

  it("reports loading state when the index status is absent", () => {
    const issues = getSetupIssues({
      systemSettings: readySettings,
      partIndexStatus: null,
      partIndexStatusError: "",
    });
    expect(issues[0].key).toBe("parts-loading");
  });

  it("requires an embedding model and indexed parts", () => {
    const noEmbedding = getSetupIssues({
      systemSettings: readySettings,
      partIndexStatus: { embedding_model: null, component_count: 5 },
      partIndexStatusError: "",
    });
    expect(noEmbedding.map((issue) => issue.key)).toEqual(["embedding"]);

    const empty = getSetupIssues({
      systemSettings: readySettings,
      partIndexStatus: { embedding_model: "embed", component_count: 0 },
      partIndexStatusError: "",
    });
    expect(empty.map((issue) => issue.key)).toEqual(["parts-empty"]);
  });
});
