import { apiRequest } from "./client";

export interface RootCauseCount {
  span_name: string;
  count: number;
}

export interface AnalyticsSummary {
  total_documents: number;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  analyzed_traces: number;
  feedback_confirmed: number;
  feedback_overridden: number;
  evaluation_cases: number;
  top_root_causes: RootCauseCount[];
}

export function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return apiRequest<AnalyticsSummary>("/v1/analytics/summary");
}
