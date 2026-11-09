import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { HumanReviewSection } from "./HumanReviewSection";
import { ApiError } from "../../api/client";

vi.mock("../../api/traces", () => ({
  getTraceFeedback: vi.fn(),
  submitTraceFeedback: vi.fn(),
  analyzeTrace: vi.fn(),
  getTraceAnalysis: vi.fn(),
}));

import { analyzeTrace, getTraceFeedback, submitTraceFeedback } from "../../api/traces";

const savedFeedback = {
  id: "fb-1",
  trace_id: "trace-xyz",
  decision: "confirmed" as const,
  comment: "Agreed",
  created_at: "2026-04-08T12:00:00Z",
  updated_at: "2026-04-08T12:00:00Z",
};

describe("HumanReviewSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not show review form content until loaded when no feedback", async () => {
    vi.mocked(getTraceFeedback).mockRejectedValue(new ApiError("Feedback not found", 404));
    render(<HumanReviewSection traceId="trace-xyz" />);
    expect(await screen.findByText("Human review")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm diagnosis/i })).toBeInTheDocument();
    expect(screen.queryByText("Current review:")).not.toBeInTheDocument();
  });

  it("displays existing feedback", async () => {
    vi.mocked(getTraceFeedback).mockResolvedValue(savedFeedback);
    render(<HumanReviewSection traceId="trace-xyz" />);
    expect(await screen.findByText(/Current review:/)).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByText(/Comment:/)).toBeInTheDocument();
  });

  it("submits confirm decision with comment", async () => {
    vi.mocked(getTraceFeedback).mockRejectedValue(new ApiError("Feedback not found", 404));
    vi.mocked(submitTraceFeedback).mockResolvedValue(savedFeedback);
    render(<HumanReviewSection traceId="trace-xyz" />);
    await screen.findByText("Human review");
    await userEvent.click(screen.getByRole("button", { name: /confirm diagnosis/i }));
    await userEvent.type(screen.getByPlaceholderText(/Explain your review/), "Looks right");
    await userEvent.click(screen.getByRole("button", { name: /submit review/i }));
    await waitFor(() => {
      expect(submitTraceFeedback).toHaveBeenCalledWith("trace-xyz", {
        decision: "confirmed",
        comment: "Looks right",
      });
    });
    expect(analyzeTrace).not.toHaveBeenCalled();
  });

  it("submits override decision", async () => {
    vi.mocked(getTraceFeedback).mockRejectedValue(new ApiError("Feedback not found", 404));
    vi.mocked(submitTraceFeedback).mockResolvedValue({
      ...savedFeedback,
      decision: "overridden",
      comment: null,
    });
    render(<HumanReviewSection traceId="trace-xyz" />);
    await screen.findByText("Human review");
    await userEvent.click(screen.getByRole("button", { name: /override diagnosis/i }));
    await userEvent.click(screen.getByRole("button", { name: /submit review/i }));
    await waitFor(() => {
      expect(submitTraceFeedback).toHaveBeenCalledWith("trace-xyz", {
        decision: "overridden",
        comment: null,
      });
    });
  });

  it("disables submit while saving", async () => {
    vi.mocked(getTraceFeedback).mockRejectedValue(new ApiError("Feedback not found", 404));
    let resolveSubmit!: (v: typeof savedFeedback) => void;
    vi.mocked(submitTraceFeedback).mockImplementation(
      () => new Promise((resolve) => {
        resolveSubmit = resolve;
      }),
    );
    render(<HumanReviewSection traceId="trace-xyz" />);
    await screen.findByText("Human review");
    await userEvent.click(screen.getByRole("button", { name: /confirm diagnosis/i }));
    const submit = screen.getByRole("button", { name: /submit review/i });
    void userEvent.click(submit);
    await waitFor(() => {
      expect(submit).toBeDisabled();
    });
    expect(submitTraceFeedback).toHaveBeenCalledTimes(1);
    resolveSubmit(savedFeedback);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /submit review/i })).not.toBeDisabled();
    });
  });
});
