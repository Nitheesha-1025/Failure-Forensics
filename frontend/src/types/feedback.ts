export type FeedbackDecision = "confirmed" | "overridden";

export interface AnalysisFeedback {
  id: string;
  trace_id: string;
  decision: FeedbackDecision;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmitAnalysisFeedbackPayload {
  decision: FeedbackDecision;
  comment?: string | null;
}
