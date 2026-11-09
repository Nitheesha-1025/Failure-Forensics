import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { TraceExplorerPage } from "./TraceExplorerPage";
import { sampleRunTrace } from "../test/fixtures/trace";
import { ApiError } from "../api/client";

vi.mock("../api/traces", () => ({
  getRunTrace: vi.fn(),
  getTraceAnalysis: vi.fn(),
  analyzeTrace: vi.fn(),
  getTraceFeedback: vi.fn(),
  submitTraceFeedback: vi.fn(),
}));

import { getRunTrace, getTraceAnalysis, getTraceFeedback } from "../api/traces";

function renderExplorer(runId = sampleRunTrace.run_id) {
  return render(
    <MemoryRouter
      initialEntries={[`/documents/doc-abc/runs/${runId}/trace`]}
    >
      <Routes>
        <Route
          path="/documents/:documentId/runs/:runId/trace"
          element={<TraceExplorerPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("TraceExplorerPage", () => {
  beforeEach(() => {
    vi.mocked(getRunTrace).mockReset();
    vi.mocked(getTraceAnalysis).mockRejectedValue(new ApiError("no analysis", 404));
    vi.mocked(getTraceFeedback).mockRejectedValue(new ApiError("Feedback not found", 404));
  });

  it("loads and displays trace summary and spans", async () => {
    vi.mocked(getRunTrace).mockResolvedValue(sampleRunTrace);
    renderExplorer();

    expect(await screen.findByText("Trace Explorer")).toBeInTheDocument();
    expect(screen.getByText("trace-xyz")).toBeInTheDocument();
    expect(screen.getByText("842 ms")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Select span intake/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Select span extraction/i })).toBeInTheDocument();
  });

  it("shows span details when another span is selected", async () => {
    vi.mocked(getRunTrace).mockResolvedValue(sampleRunTrace);
    renderExplorer();
    await screen.findByText("Trace Explorer");

    const extractionButtons = screen.getAllByRole("button", {
      name: /Select span extraction/i,
    });
    await userEvent.click(extractionButtons[0]!);
    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("empty fields")).toBeInTheDocument();
    expect(screen.getByText(/0\.42/)).toBeInTheDocument();
  });

  it("shows trace not found on 404", async () => {
    vi.mocked(getRunTrace).mockRejectedValue(new ApiError("Trace not found", 404));
    renderExplorer();
    expect(await screen.findByText("Trace not found.")).toBeInTheDocument();
  });

  it("shows sign-in message on 401", async () => {
    vi.mocked(getRunTrace).mockRejectedValue(new ApiError("Unauthorized", 401));
    renderExplorer();
    expect(
      await screen.findByText("Please sign in to view this trace."),
    ).toBeInTheDocument();
  });

  it("shows retry on network failure", async () => {
    vi.mocked(getRunTrace).mockRejectedValue(new ApiError("Unable to reach the server. Check your connection.", 0));
    renderExplorer();
    expect(
      await screen.findByText(/Unable to reach the server/),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /try again/i }).length).toBeGreaterThan(0);
  });

  it("calls getRunTrace with run id", async () => {
    vi.mocked(getRunTrace).mockResolvedValue(sampleRunTrace);
    renderExplorer(sampleRunTrace.run_id);
    await waitFor(() => {
      expect(getRunTrace).toHaveBeenCalledWith(sampleRunTrace.run_id);
    });
  });
});
