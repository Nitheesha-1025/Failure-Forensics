/** Matches backend StepStatus / TraceDetailPublic / RunTraceResponse. */

export type StepStatus = "ok" | "error";

export interface Span {
  span_id: string;
  trace_id: string;
  name: string;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  status: StepStatus;
  error: string | null;
  confidence: number | null;
  input: Record<string, unknown>;
  output: unknown;
  attributes: Record<string, unknown>;
}

export interface TraceDetail {
  trace_id: string;
  schema_version: number;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  status: StepStatus;
  spans: Span[];
  final_output: Record<string, unknown> | null;
  flagged: boolean;
  flag_reason: string | null;
}

export interface RunTraceResponse {
  run_id: string;
  document_id: string;
  trace: TraceDetail;
}
