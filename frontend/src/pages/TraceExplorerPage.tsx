import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getRunTrace } from "../api/traces";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { FailureAnalysisPanel } from "../components/trace/FailureAnalysisPanel";
import { SpanDetailPanel } from "../components/trace/SpanDetailPanel";
import { SpanTimeline } from "../components/trace/SpanTimeline";
import { TraceFailureBanner } from "../components/layout/TraceFailureBanner";
import { SpanStatusBadge } from "../components/trace/SpanStatusBadge";
import type { RootCauseAnalysis } from "../types/analysis";
import type { RunTraceResponse } from "../types/trace";
import { formatDateTime, formatDurationMs } from "../utils/format";

export function TraceExplorerPage() {
  const { documentId, runId } = useParams<{ documentId: string; runId: string }>();
  const [data, setData] = useState<RunTraceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<RootCauseAnalysis | null>(null);
  const timelineRef = useRef<HTMLElement | null>(null);

  const handleSelectSpan = useCallback((spanId: string) => {
    setSelectedSpanId(spanId);
    timelineRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, []);

  const handleAnalysisChange = useCallback((value: RootCauseAnalysis | null) => {
    setAnalysis(value);
  }, []);

  const load = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await getRunTrace(runId);
      setData(response);
      const firstSpan = response.trace.spans[0];
      setSelectedSpanId(firstSpan?.span_id ?? null);
    } catch (err) {
      setData(null);
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setError("Trace not found.");
        } else if (err.status === 401) {
          setError("Please sign in to view this trace.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Unable to load trace. Check your connection and try again.");
      }
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  const trace = data?.trace ?? null;
  const selectedSpan = useMemo(
    () => trace?.spans.find((s) => s.span_id === selectedSpanId) ?? null,
    [trace, selectedSpanId],
  );

  const backHref = documentId ? `/documents/${documentId}` : "/documents";

  if (!runId) {
    return <ErrorMessage message="Invalid run link." />;
  }

  if (loading) {
    return <Loading message="Loading trace…" />;
  }

  if (error || !trace || !data) {
    return (
      <div className="page">
        <Link to={backHref} className="link back-link">
          ← Back to document
        </Link>
        <ErrorMessage
          message={error ?? "Trace not found."}
          onRetry={error && error !== "Please sign in to view this trace." ? () => void load() : undefined}
        />
      </div>
    );
  }

  return (
    <div className="page trace-explorer">
      <header className="page-header trace-explorer-header">
        <div>
          <Link to={backHref} className="link back-link">
            ← Back to document
          </Link>
          <h1>Trace Explorer</h1>
          <p className="muted trace-breadcrumb">
            Document → Run {data.run_id.slice(0, 8)}… → Trace
          </p>
        </div>
      </header>

      <TraceFailureBanner trace={trace} />

      <section className="trace-summary card" aria-label="Trace summary">
        <dl className="trace-summary-grid">
          <div>
            <dt>Trace ID</dt>
            <dd className="mono" title={trace.trace_id}>
              {trace.trace_id}
            </dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>
              <SpanStatusBadge status={trace.status} />
            </dd>
          </div>
          <div>
            <dt>Spans</dt>
            <dd>{trace.spans.length}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{formatDurationMs(trace.duration_ms)}</dd>
          </div>
          <div>
            <dt>Started</dt>
            <dd>{formatDateTime(trace.started_at)}</dd>
          </div>
          <div>
            <dt>Completed</dt>
            <dd>{formatDateTime(trace.ended_at)}</dd>
          </div>
        </dl>
      </section>

      <div className="trace-explorer-panels">
        <section
          className="card trace-panel"
          aria-labelledby="timeline-heading"
          ref={timelineRef}
        >
          <h2 id="timeline-heading">Pipeline timeline</h2>
          <SpanTimeline
            spans={trace.spans}
            selectedSpanId={selectedSpanId}
            onSelectSpan={handleSelectSpan}
            emphasisSpanId={analysis?.root_cause_span_id ?? null}
          />
        </section>
        <SpanDetailPanel span={selectedSpan} />
      </div>

      <FailureAnalysisPanel
        traceId={trace.trace_id}
        hasSpans={trace.spans.length > 0}
        onSelectSpan={handleSelectSpan}
        onAnalysisChange={handleAnalysisChange}
      />
    </div>
  );
}
