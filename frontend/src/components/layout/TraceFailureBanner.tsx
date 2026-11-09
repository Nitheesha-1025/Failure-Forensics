import type { Span, TraceDetail } from "../../types/trace";
import { IconAlert } from "../icons/Icons";

function firstFailedSpan(spans: Span[]): Span | undefined {
  return spans.find((s) => s.status === "error");
}

export function TraceFailureBanner({ trace }: { trace: TraceDetail }) {
  if (trace.status !== "error") {
    return null;
  }

  const failed = firstFailedSpan(trace.spans);
  const stage = failed?.name ?? "Unknown stage";
  const summary = failed?.error?.trim() || "Pipeline step reported an error without details.";

  return (
    <section className="investigation-banner investigation-banner--error" role="alert">
      <div className="investigation-banner-icon">
        <IconAlert size={20} />
      </div>
      <div className="investigation-banner-body">
        <p className="investigation-banner-eyebrow">Pipeline failure detected</p>
        <h2 className="investigation-banner-title">Failed at {stage}</h2>
        <p className="investigation-banner-summary mono">{summary}</p>
        <p className="investigation-banner-action muted">
          Review the timeline below, then run failure analysis for root-cause findings and
          recommended next steps.
        </p>
      </div>
      <div className="investigation-banner-meta">
        <span className="severity-pill severity-pill--high">High severity</span>
      </div>
    </section>
  );
}
