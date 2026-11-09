import { apiRequest } from "./client";
import type {
  Document,
  DocumentListResponse,
  PipelineRun,
  PipelineRunListResponse,
} from "../types/api";

export interface ListDocumentsParams {
  page?: number;
  page_size?: number;
}

export function listDocuments(
  params: ListDocumentsParams = {},
): Promise<DocumentListResponse> {
  const search = new URLSearchParams();
  if (params.page != null) search.set("page", String(params.page));
  if (params.page_size != null) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<DocumentListResponse>(
    `/v1/documents${qs ? `?${qs}` : ""}`,
  );
}

export function getDocument(documentId: string): Promise<Document> {
  return apiRequest<Document>(`/v1/documents/${documentId}`);
}

export function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  return apiRequest<Document>("/v1/documents", {
    method: "POST",
    formData: form,
  });
}

export function deleteDocument(documentId: string): Promise<void> {
  return apiRequest<void>(`/v1/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function listDocumentRuns(
  documentId: string,
  params: ListDocumentsParams = {},
): Promise<PipelineRunListResponse> {
  const search = new URLSearchParams();
  if (params.page != null) search.set("page", String(params.page));
  if (params.page_size != null) search.set("page_size", String(params.page_size));
  const qs = search.toString();
  return apiRequest<PipelineRunListResponse>(
    `/v1/documents/${documentId}/runs${qs ? `?${qs}` : ""}`,
  );
}

export function createDocumentRun(documentId: string): Promise<PipelineRun> {
  return apiRequest<PipelineRun>(`/v1/documents/${documentId}/runs`, {
    method: "POST",
  });
}
