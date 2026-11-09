import type { RootCauseAnalysis } from "../../types/analysis";

export const sampleAnalysis: RootCauseAnalysis = {
  trace_id: "trace-xyz",
  created_at: "2026-04-08T12:05:00Z",
  judge_model: "gpt-4o",
  root_cause_span_id: "span-2",
  root_cause_explanation:
    "step 'extraction' was marked as root-cause candidate: fields are empty",
  critiques: [
    {
      span_id: "span-1",
      name: "intake",
      quality: 1,
      reason: "Input captured correctly",
      is_root_cause_candidate: false,
    },
    {
      span_id: "span-2",
      name: "extraction",
      quality: 0.42,
      reason: "fields are empty",
      is_root_cause_candidate: true,
    },
    {
      span_id: "span-3",
      name: "summarization",
      quality: 0.5,
      reason: "Summary based on bad extraction",
      is_root_cause_candidate: false,
    },
  ],
};
