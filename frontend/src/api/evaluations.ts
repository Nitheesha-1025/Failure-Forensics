import { apiRequest } from "./client";

export interface UserEvalCase {
  id: string;
  trace_id: string;
  feedback_id: string;
  document_id: string | null;
  pipeline_run_id: string | null;
  raw_text: string;
  human_decision: string;
  human_comment: string | null;
  expected_root_cause_span_id: string | null;
  expected_root_cause_span_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserEvalCaseListResponse {
  items: UserEvalCase[];
  total: number;
}

export interface RegressionRunResult {
  eval_case_id: string;
  passed: boolean | null;
  human_decision: string;
  expected_root_cause_span_id: string | null;
  expected_root_cause_span_name: string | null;
  actual_root_cause_span_id: string | null;
  actual_root_cause_span_name: string | null;
  message: string;
}

export function listEvalCases(): Promise<UserEvalCaseListResponse> {
  return apiRequest<UserEvalCaseListResponse>("/v1/evaluations");
}

export function createEvalCase(traceId: string): Promise<UserEvalCase> {
  return apiRequest<UserEvalCase>("/v1/evaluations", {
    method: "POST",
    body: { trace_id: traceId },
  });
}

export function getEvalCase(caseId: string): Promise<UserEvalCase> {
  return apiRequest<UserEvalCase>(`/v1/evaluations/${caseId}`);
}

export function deleteEvalCase(caseId: string): Promise<void> {
  return apiRequest<void>(`/v1/evaluations/${caseId}`, { method: "DELETE" });
}

export function runEvalRegression(caseId: string): Promise<RegressionRunResult> {
  return apiRequest<RegressionRunResult>(`/v1/evaluations/${caseId}/run`, {
    method: "POST",
  });
}
