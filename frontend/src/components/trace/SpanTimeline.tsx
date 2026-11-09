import type { Span } from "../../types/trace";
import { formatDurationMs } from "../../utils/format";
import { SpanStatusBadge } from "./SpanStatusBadge";

interface SpanTimelineProps {
  spans: Span[];
  selectedSpanId: string | null;
  onSelectSpan: (spanId: string) => void;
  emphasisSpanId?: string | null;
}

export function SpanTimeline({
  spans,
  selectedSpanId,
  onSelectSpan,
  emphasisSpanId = null,
}: SpanTimelineProps) {
  if (spans.length === 0) {
    return <p className="muted">This trace has no spans.</p>;
  }

  return (
    <ol className="span-timeline span-timeline--modern" aria-label="Pipeline timeline">
      {spans.map((span, index) => {
        const selected = span.span_id === selectedSpanId;
        const emphasized = span.span_id === emphasisSpanId;
        return (
          <li
            key={span.span_id}
            className={`span-timeline-item${emphasized ? " span-timeline-item-root" : ""}`}
          >
            {index > 0 ? (
              <span className="span-timeline-connector" aria-hidden="true">
                ↓
              </span>
            ) : null}
            <button
              type="button"
              className={`span-timeline-button${selected ? " span-timeline-button-selected" : ""}${emphasized ? " span-timeline-button-emphasis" : ""}`}
              aria-label={`Select span ${span.name}`}
              aria-current={selected ? "true" : undefined}
              onClick={() => onSelectSpan(span.span_id)}
            >
              <span className="span-timeline-name">{span.name}</span>
              <span className="span-timeline-meta">
                {formatDurationMs(span.duration_ms)} · <SpanStatusBadge status={span.status} />
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
