import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { analyzeTrace, getTraceAnalysis } from "../../api/traces";
import type { RootCauseAnalysis, SpanCritique } from "../../types/analysis";
import { ErrorMessage } from "../ErrorMessage";
import { Loading } from "../Loading";
import { HumanReviewSection } from "./HumanReviewSection";

export type AnalysisUiState =
  | "loading_existing"
  | "none"
  | "available"
  | "running"
  | "failed";

interface FailureAnalysisPanelProps {
  traceId: string;
  hasSpans: boolean;
  onSelectSpan: (spanId: string) => void;
  onAnalysisChange?: (analysis: RootCauseAnalysis | null) => void;
}

function critiqueLabel(crit: SpanCritique, rootSpanId: string | null): string {
  if (crit.span_id === rootSpanId) {
    return "Root failure";
  }
  if (crit.is_root_cause_candidate) {
    return "Root-cause candidate";
  }
  return "Downstream step";
}

export function FailureAnalysisPanel({
  traceId,
  hasSpans,
  onSelectSpan,
  onAnalysisChange,
}: FailureAnalysisPanelProps) {
  const [uiState, setUiState] = useState<AnalysisUiState>("loading_existing");
  const [analysis, setAnalysis] = useState<RootCauseAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const analyzingRef = useRef(false);
  const onAnalysisChangeRef = useRef(onAnalysisChange);
  onAnalysisChangeRef.current = onAnalysisChange;

  const loadExisting = useCallback(async () => {
    setUiState("loading_existing");
    setError(null);
    try {
      const existing = await getTraceAnalysis(traceId);
      setAnalysis(existing);
      setUiState("available");
      onAnalysisChangeRef.current?.(existing);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setAnalysis(null);
        setUiState("none");
        onAnalysisChangeRef.current?.(null);
        return;
      }
      setUiState("failed");
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to load analysis. Try again.",
      );
      onAnalysisChangeRef.current?.(null);
    }
  }, [traceId]);

  const runAnalysis = useCallback(async () => {
    if (analyzingRef.current) return;
    analyzingRef.current = true;
    setUiState("running");
    setError(null);
    try {
      const result = await analyzeTrace(traceId);
      setAnalysis(result);
      setUiState("available");
      onAnalysisChangeRef.current?.(result);
      if (result.root_cause_span_id) {
        onSelectSpan(result.root_cause_span_id);
      }
    } catch (err) {
      setUiState("failed");
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to analyze this trace. Try again.",
      );
    } finally {
      analyzingRef.current = false;
    }
  }, [traceId, onSelectSpan]);

  useEffect(() => {
    setAnalysis(null);
    setError(null);
    onAnalysisChangeRef.current?.(null);
    void loadExisting();
  }, [traceId, loadExisting]);

  const rootId = analysis?.root_cause_span_id ?? null;
  const analyzeDisabled = uiState === "running" || uiState === "loading_existing";

  return (
    <section className="card failure-analysis" aria-labelledby="failure-analysis-heading">
      <div className="failure-analysis-header">
        <h2 id="failure-analysis-heading">Failure analysis</h2>
        {(uiState === "none" || uiState === "available") && hasSpans ? (
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={analyzeDisabled}
            onClick={() => void runAnalysis()}
          >
            {uiState === "available" ? "Re-analyze" : "Analyze failure"}
          </button>
        ) : null}
      </div>

      {uiState === "loading_existing" ? (
        <Loading message="Checking for saved analysis…" />
      ) : null}

      {uiState === "none" && !error ? (
        <div className="failure-analysis-empty">
          <p>No analysis has been generated yet.</p>
          {hasSpans ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={analyzeDisabled}
              onClick={() => void runAnalysis()}
            >
              Analyze failure
            </button>
          ) : (
            <p className="muted">This trace has no spans to analyze.</p>
          )}
        </div>
      ) : null}

      {uiState === "running" ? (
        <div className="failure-analysis-running" role="status">
          <Loading message="Analyzing trace…" />
          <p className="muted">Please wait. This may take a few seconds.</p>
        </div>
      ) : null}

      {uiState === "failed" && error ? (
        <div className="failure-analysis-failed">
          <ErrorMessage message={error} onRetry={() => void runAnalysis()} />
        </div>
      ) : null}

      {uiState === "available" && analysis ? (
        <>
          <AnalysisResultView
            analysis={analysis}
            rootId={rootId}
            onSelectSpan={onSelectSpan}
          />
          <HumanReviewSection traceId={traceId} />
        </>
      ) : null}
    </section>
  );
}

function AnalysisResultView({
  analysis,
  rootId,
  onSelectSpan,
}: {
  analysis: RootCauseAnalysis;
  rootId: string | null;
  onSelectSpan: (spanId: string) => void;
}) {
  const rootCritique = analysis.critiques.find((c) => c.span_id === rootId);

  return (
    <div className="failure-analysis-result">
      <div className="root-cause-block">
        <div className="root-cause-block-header">
          <h3>Root cause</h3>
          {rootCritique ? (
            <span
              className={
                rootCritique.quality < 0.5
                  ? "severity-pill severity-pill--high"
                  : "severity-pill severity-pill--medium"
              }
            >
              {rootCritique.quality < 0.5 ? "High severity" : "Review recommended"}
            </span>
          ) : null}
        </div>
        <p className="root-cause-text">{analysis.root_cause_explanation || "—"}</p>
        {rootId && rootCritique ? (
          <div className="root-cause-meta">
            <p>
              <strong>First significant failure:</strong>{" "}
              <button
                type="button"
                className="link-button"
                onClick={() => onSelectSpan(rootId)}
              >
                {rootCritique.name}
              </button>
            </p>
            <p className="muted">
              Judge quality score: {rootCritique.quality.toFixed(2)} · Model:{" "}
              {analysis.judge_model}
            </p>
          </div>
        ) : (
          <p className="muted">Judge model: {analysis.judge_model}</p>
        )}
      </div>

      {analysis.critiques.length > 0 ? (
        <div className="evidence-section">
          <h3>Evidence (span order)</h3>
          <ol className="evidence-list">
            {analysis.critiques.map((crit, index) => (
              <li key={crit.span_id} className="evidence-item">
                <div className="evidence-item-header">
                  <span className="evidence-index">{index + 1}.</span>
                  <button
                    type="button"
                    className="link-button evidence-span-name"
                    onClick={() => onSelectSpan(crit.span_id)}
                  >
                    {crit.name}
                  </button>
                  <span className="evidence-tag">{critiqueLabel(crit, rootId)}</span>
                  <span className="evidence-quality">Quality {crit.quality.toFixed(2)}</span>
                </div>
                <p className="evidence-reason">{crit.reason}</p>
                {index < analysis.critiques.length - 1 ? (
                  <span className="evidence-flow" aria-hidden="true">
                    ↓ downstream
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <p className="muted analysis-timestamp">
        Analysis saved {new Date(analysis.created_at).toLocaleString()}
      </p>
    </div>
  );
}
