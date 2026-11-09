import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { DocumentDetailsPage } from "./DocumentDetailsPage";
import type { Document, PipelineRun } from "../types/api";

vi.mock("../api/documents", () => ({
  getDocument: vi.fn(),
  listDocumentRuns: vi.fn(),
  createDocumentRun: vi.fn(),
}));

import { getDocument, listDocumentRuns } from "../api/documents";

const doc: Document = {
  id: "doc-abc",
  filename: "sample.txt",
  file_type: "txt",
  mime_type: "text/plain",
  file_size: 100,
  processing_status: "completed",
  created_at: "2026-04-08T12:00:00Z",
  updated_at: "2026-04-08T12:00:00Z",
};

const runWithTrace: PipelineRun = {
  id: "11111111-1111-1111-1111-111111111111",
  document_id: "doc-abc",
  trace_id: "trace-1",
  status: "completed",
  started_at: "2026-04-08T12:00:00Z",
  completed_at: "2026-04-08T12:00:01Z",
  duration_ms: 500,
  error_message: null,
  created_at: "2026-04-08T12:00:00Z",
};

const runWithoutTrace: PipelineRun = {
  ...runWithTrace,
  id: "22222222-2222-2222-2222-222222222222",
  trace_id: null,
  status: "failed",
};

describe("DocumentDetailsPage trace links", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getDocument).mockResolvedValue(doc);
  });

  it("shows View trace for runs with trace_id", async () => {
    vi.mocked(listDocumentRuns).mockReset();
    vi.mocked(listDocumentRuns).mockResolvedValue({
      items: [runWithTrace],
      page: 1,
      page_size: 20,
      total: 1,
      total_pages: 1,
    });
    render(
      <MemoryRouter initialEntries={["/documents/doc-abc"]}>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("link", { name: /view trace/i })).toHaveAttribute(
      "href",
      `/documents/doc-abc/runs/${runWithTrace.id}/trace`,
    );
  });

  it("does not show View trace when trace_id is missing", async () => {
    vi.mocked(listDocumentRuns).mockReset();
    vi.mocked(listDocumentRuns).mockResolvedValue({
      items: [runWithoutTrace],
      page: 1,
      page_size: 20,
      total: 1,
      total_pages: 1,
    });
    render(
      <MemoryRouter initialEntries={["/documents/doc-abc"]}>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetailsPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("sample.txt")).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: /view trace/i })).not.toBeInTheDocument();
  });
});
