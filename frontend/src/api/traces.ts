import { apiRequest } from "./client";
import type { RootCauseAnalysis } from "../types/analysis";
import type { AnalysisFeedback, SubmitAnalysisFeedbackPayload } from "../types/feedback";
import type { RunTraceResponse } from "../types/trace";

export function getRunTrace(runId: string): Promise<RunTraceResponse> {
  return apiRequest<RunTraceResponse>(`/v1/runs/${runId}/trace`);
}

export function analyzeTrace(traceId: string): Promise<RootCauseAnalysis> {
  return apiRequest<RootCauseAnalysis>(`/v1/traces/${traceId}/analyze`, {
    method: "POST",
  });
}

export function getTraceAnalysis(traceId: string): Promise<RootCauseAnalysis> {
  return apiRequest<RootCauseAnalysis>(`/v1/traces/${traceId}/analysis`);
}

export function getTraceFeedback(traceId: string): Promise<AnalysisFeedback> {
  return apiRequest<AnalysisFeedback>(`/v1/traces/${traceId}/feedback`);
}

export function submitTraceFeedback(
  traceId: string,
  payload: SubmitAnalysisFeedbackPayload,
): Promise<AnalysisFeedback> {
  return apiRequest<AnalysisFeedback>(`/v1/traces/${traceId}/feedback`, {
    method: "POST",
    body: payload,
  });
}
