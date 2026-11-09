import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "./client";

describe("ApiError", () => {
  it("carries status for UI handling", () => {
    const err = new ApiError("Not found", 404);
    expect(err.message).toBe("Not found");
    expect(err.status).toBe(404);
  });
});

describe("apiRequest errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("surfaces backend detail for HTTP 429", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
        json: async () => ({
          detail: "The AI provider rate-limited this analysis request.",
        }),
      }),
    );
    await expect(apiRequest("/v1/traces/x/analyze", { method: "POST" })).rejects.toEqual(
      expect.objectContaining({
        message: "The AI provider rate-limited this analysis request.",
        status: 429,
      }),
    );
  });

  it("uses network message only when fetch throws", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiRequest("/v1/health", { auth: false })).rejects.toEqual(
      expect.objectContaining({
        message: "Unable to reach the server. Check your connection.",
        status: 0,
      }),
    );
  });
});
