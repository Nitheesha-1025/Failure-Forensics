import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { EvaluationsPage } from "./EvaluationsPage";
import { ApiError } from "../api/client";

vi.mock("../api/evaluations", () => ({
  listEvalCases: vi.fn(),
}));

import { listEvalCases } from "../api/evaluations";

describe("EvaluationsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("lists evaluation cases", async () => {
    vi.mocked(listEvalCases).mockResolvedValue({
      items: [
        {
          id: "case-1",
          trace_id: "trace-1",
          feedback_id: "fb-1",
          document_id: "doc-1",
          pipeline_run_id: "run-1",
          raw_text: "doc text",
          human_decision: "confirmed",
          human_comment: null,
          expected_root_cause_span_id: "span-1",
          expected_root_cause_span_name: "extraction",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
    });
    render(
      <MemoryRouter>
        <EvaluationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Evaluations")).toBeInTheDocument();
    expect(screen.getByText("confirmed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View" })).toBeInTheDocument();
  });

  it("shows empty state", async () => {
    vi.mocked(listEvalCases).mockResolvedValue({ items: [], total: 0 });
    render(
      <MemoryRouter>
        <EvaluationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/no evaluation cases/i)).toBeInTheDocument();
  });

  it("shows error state", async () => {
    vi.mocked(listEvalCases).mockRejectedValue(new ApiError("Forbidden", 403));
    render(
      <MemoryRouter>
        <EvaluationsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Forbidden")).toBeInTheDocument();
  });
});
