import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AnalyticsPage } from "./AnalyticsPage";
import { ApiError } from "../api/client";

vi.mock("../api/analytics", () => ({
  getAnalyticsSummary: vi.fn(),
}));

import { getAnalyticsSummary } from "../api/analytics";

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders summary cards from API", async () => {
    vi.mocked(getAnalyticsSummary).mockResolvedValue({
      total_documents: 2,
      total_runs: 3,
      completed_runs: 2,
      failed_runs: 1,
      analyzed_traces: 1,
      feedback_confirmed: 1,
      feedback_overridden: 0,
      evaluation_cases: 1,
      top_root_causes: [{ span_name: "extraction", count: 1 }],
    });
    render(<AnalyticsPage />);
    expect(await screen.findByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("Pipeline runs")).toBeInTheDocument();
    expect(screen.getByText("extraction")).toBeInTheDocument();
  });

  it("shows error state", async () => {
    vi.mocked(getAnalyticsSummary).mockRejectedValue(new ApiError("Server error", 500));
    render(<AnalyticsPage />);
    expect(await screen.findByText("Server error")).toBeInTheDocument();
  });
});
