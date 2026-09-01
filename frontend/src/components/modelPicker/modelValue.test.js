import { describe, it, expect } from "vitest";
import {
  parseCustomProviderModelValue,
  buildCustomProviderModelValue,
  formatUpdatedAt,
  getModelLabel,
} from "./modelValue.js";

describe("parseCustomProviderModelValue", () => {
  it("parses provider.model values", () => {
    expect(parseCustomProviderModelValue("openai.gpt-4o")).toEqual({
      providerName: "openai",
      modelName: "gpt-4o",
    });
  });

  it("is case-insensitive on the provider", () => {
    expect(parseCustomProviderModelValue(" OpenAI . gpt-4o ")).toEqual({
      providerName: "openai",
      modelName: "gpt-4o",
    });
  });

  it("rejects values without a separator or with empty parts", () => {
    expect(parseCustomProviderModelValue("gpt-4o")).toBeNull();
    expect(parseCustomProviderModelValue(".gpt-4o")).toBeNull();
    expect(parseCustomProviderModelValue("openai.")).toBeNull();
    expect(parseCustomProviderModelValue("")).toBeNull();
    expect(parseCustomProviderModelValue(null)).toBeNull();
  });
});

describe("buildCustomProviderModelValue", () => {
  it("joins provider and model", () => {
    expect(buildCustomProviderModelValue("OpenAI", " gpt-4o ")).toBe("openai.gpt-4o");
  });

  it("returns an empty string when either side is missing", () => {
    expect(buildCustomProviderModelValue("", "gpt-4o")).toBe("");
    expect(buildCustomProviderModelValue("openai", "")).toBe("");
  });
});

describe("formatUpdatedAt", () => {
  it("handles missing values", () => {
    expect(formatUpdatedAt(null)).toBe("not synced yet");
  });

  it("formats valid timestamps", () => {
    expect(formatUpdatedAt("2025-01-02T03:04:00Z")).toMatch(/^synced /);
  });
});

describe("getModelLabel", () => {
  const providers = [
    {
      providerName: "openai",
      models: [
        { id: "gpt-4o", name: "GPT-4o" },
        { id: "o1", name: null },
      ],
    },
  ];

  it("returns raw value when not a composite", () => {
    expect(getModelLabel(providers, "legacy-model")).toBe("legacy-model");
    expect(getModelLabel(providers, "")).toBe("Select model");
  });

  it("prefers display names", () => {
    expect(getModelLabel(providers, "openai.gpt-4o")).toBe("openai / GPT-4o");
  });

  it("falls back to the model id", () => {
    expect(getModelLabel(providers, "openai.o1")).toBe("openai / o1");
  });

  it("handles unknown providers", () => {
    expect(getModelLabel(providers, "anthropic.claude")).toBe("anthropic / claude");
  });
});
