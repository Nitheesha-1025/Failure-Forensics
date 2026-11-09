/** Matches backend RootCauseAnalysis / SpanCritique. */

export interface SpanCritique {
  span_id: string;
  name: string;
  quality: number;
  reason: string;
  is_root_cause_candidate: boolean;
}

export interface RootCauseAnalysis {
  trace_id: string;
  created_at: string;
  judge_model: string;
  critiques: SpanCritique[];
  root_cause_span_id: string | null;
  root_cause_explanation: string;
}
