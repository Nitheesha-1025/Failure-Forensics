import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { EvaluationDetailPage } from "./EvaluationDetailPage";

vi.mock("../api/evaluations", () => ({
  getEvalCase: vi.fn(),
  deleteEvalCase: vi.fn(),
  runEvalRegression: vi.fn(),
}));

import { getEvalCase } from "../api/evaluations";

describe("EvaluationDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows case detail", async () => {
    vi.mocked(getEvalCase).mockResolvedValue({
      id: "case-1",
      trace_id: "trace-abc",
      feedback_id: "fb-1",
      document_id: "doc-1",
      pipeline_run_id: "run-1",
      raw_text: "sample",
      human_decision: "overridden",
      human_comment: "wrong span",
      expected_root_cause_span_id: null,
      expected_root_cause_span_name: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    });
    render(
      <MemoryRouter initialEntries={["/evaluations/case-1"]}>
        <Routes>
          <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("overridden")).toBeInTheDocument();
    expect(screen.getByText(/trace-abc/i)).toBeInTheDocument();
  });
});
