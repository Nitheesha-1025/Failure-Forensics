import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { FailureAnalysisPanel } from "./FailureAnalysisPanel";
import { sampleAnalysis } from "../../test/fixtures/analysis";
import { ApiError } from "../../api/client";

vi.mock("../../api/traces", () => ({
  getTraceAnalysis: vi.fn(),
  analyzeTrace: vi.fn(),
  getTraceFeedback: vi.fn(),
  submitTraceFeedback: vi.fn(),
}));

vi.mock("../../api/evaluations", () => ({
  createEvalCase: vi.fn(),
}));

import { analyzeTrace, getTraceAnalysis, getTraceFeedback } from "../../api/traces";

describe("FailureAnalysisPanel", () => {
  const onSelectSpan = vi.fn();
  const onAnalysisChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    onSelectSpan.mockReset();
    onAnalysisChange.mockReset();
    vi.mocked(getTraceFeedback).mockRejectedValue(new ApiError("Feedback not found", 404));
  });

  it("loads and displays existing analysis", async () => {
    vi.mocked(getTraceAnalysis).mockResolvedValue(sampleAnalysis);
    render(
      <FailureAnalysisPanel
        traceId="trace-xyz"
        hasSpans
        onSelectSpan={onSelectSpan}
        onAnalysisChange={onAnalysisChange}
      />,
    );
    expect(await screen.findByText(/step 'extraction'/)).toBeInTheDocument();
    expect(screen.getByText("Evidence (span order)")).toBeInTheDocument();
    expect(getTraceAnalysis).toHaveBeenCalledWith("trace-xyz");
  });

  it("shows human review when analysis exists", async () => {
    vi.mocked(getTraceAnalysis).mockResolvedValue(sampleAnalysis);
    render(
      <FailureAnalysisPanel
        traceId="trace-xyz"
        hasSpans
        onSelectSpan={onSelectSpan}
      />,
    );
    expect(await screen.findByText("Human review")).toBeInTheDocument();
  });

  it("does not show human review when no analysis exists", async () => {
    vi.mocked(getTraceAnalysis).mockRejectedValue(new ApiError("no analysis", 404));
    render(
      <FailureAnalysisPanel traceId="trace-xyz" hasSpans onSelectSpan={onSelectSpan} />,
    );
    await screen.findByText("No analysis has been generated yet.");
    expect(screen.queryByText("Human review")).not.toBeInTheDocument();
  });

  it("shows analyze action when no analysis exists", async () => {
    vi.mocked(getTraceAnalysis).mockRejectedValue(new ApiError("no analysis", 404));
    render(
      <FailureAnalysisPanel
        traceId="trace-xyz"
        hasSpans
        onSelectSpan={onSelectSpan}
      />,
    );
    await screen.findByText("No analysis has been generated yet.");
    expect(screen.getAllByRole("button", { name: /analyze failure/i }).length).toBeGreaterThan(0);
  });

  it("runs analysis on button click and shows result", async () => {
    vi.mocked(getTraceAnalysis).mockRejectedValue(new ApiError("no analysis", 404));
    vi.mocked(analyzeTrace).mockResolvedValue(sampleAnalysis);
    render(
      <FailureAnalysisPanel
        traceId="trace-xyz"
        hasSpans
        onSelectSpan={onSelectSpan}
        onAnalysisChange={onAnalysisChange}
      />,
    );
    await screen.findByText("No analysis has been generated yet.");
    await userEvent.click(screen.getAllByRole("button", { name: /analyze failure/i })[0]!);
    expect(analyzeTrace).toHaveBeenCalledWith("trace-xyz");
    expect(await screen.findByText(/step 'extraction'/)).toBeInTheDocument();
    expect(onSelectSpan).toHaveBeenCalledWith("span-2");
  });

  it("disables duplicate analyze while running", async () => {
    vi.mocked(getTraceAnalysis).mockRejectedValue(new ApiError("no analysis", 404));
    let resolveAnalyze!: (value: typeof sampleAnalysis) => void;
    vi.mocked(analyzeTrace).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveAnalyze = resolve;
        }),
    );
    render(
      <FailureAnalysisPanel traceId="trace-xyz" hasSpans onSelectSpan={onSelectSpan} />,
    );
    await screen.findByText("No analysis has been generated yet.");
    const button = screen.getAllByRole("button", { name: /analyze failure/i })[0]!;
    await userEvent.click(button);
    expect(await screen.findByText(/Analyzing trace/)).toBeInTheDocument();
    expect(analyzeTrace).toHaveBeenCalledTimes(1);
    await userEvent.click(button);
    expect(analyzeTrace).toHaveBeenCalledTimes(1);
    resolveAnalyze(sampleAnalysis);
    await waitFor(() => {
      expect(screen.getByText(/step 'extraction'/)).toBeInTheDocument();
    });
  });

  it("shows error and retry on analyze failure", async () => {
    vi.mocked(getTraceAnalysis).mockRejectedValue(new ApiError("no analysis", 404));
    vi.mocked(analyzeTrace).mockRejectedValue(new ApiError("Server error", 500));
    render(
      <FailureAnalysisPanel traceId="trace-xyz" hasSpans onSelectSpan={onSelectSpan} />,
    );
    await screen.findByText("No analysis has been generated yet.");
    await userEvent.click(screen.getAllByRole("button", { name: /analyze failure/i })[0]!);
    expect(await screen.findByText("Server error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("selects span when evidence item is clicked", async () => {
    vi.mocked(getTraceAnalysis).mockResolvedValue(sampleAnalysis);
    render(
      <FailureAnalysisPanel
        traceId="trace-xyz"
        hasSpans
        onSelectSpan={onSelectSpan}
      />,
    );
    await screen.findByText(/step 'extraction'/);
    await userEvent.click(screen.getByRole("button", { name: "summarization" }));
    expect(onSelectSpan).toHaveBeenCalledWith("span-3");
  });
});
