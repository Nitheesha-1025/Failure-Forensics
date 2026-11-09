import { JsonViewer } from "../JsonViewer";
import type { Span } from "../../types/trace";
import { formatDateTime, formatDurationMs } from "../../utils/format";
import { SpanStatusBadge } from "./SpanStatusBadge";

interface SpanDetailPanelProps {
  span: Span | null;
}

function attributeModel(attributes: Record<string, unknown>): string | null {
  const model = attributes.model;
  if (typeof model === "string" && model.trim()) {
    return model;
  }
  return null;
}

export function SpanDetailPanel({ span }: SpanDetailPanelProps) {
  if (!span) {
    return (
      <section className="span-detail" aria-label="Selected span">
        <p className="muted">Select a span to inspect its input and output.</p>
      </section>
    );
  }

  const model = attributeModel(span.attributes);
  const hasAttributes = Object.keys(span.attributes).length > 0;

  return (
    <section className="span-detail" aria-label="Selected span">
      <h3>{span.name}</h3>
      <dl className="span-detail-meta">
        <div>
          <dt>Duration</dt>
          <dd>{formatDurationMs(span.duration_ms)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            <SpanStatusBadge status={span.status} />
          </dd>
        </div>
        {span.confidence != null ? (
          <div>
            <dt>Confidence</dt>
            <dd>{span.confidence.toFixed(2)}</dd>
          </div>
        ) : null}
        {model ? (
          <div>
            <dt>Model</dt>
            <dd>{model}</dd>
          </div>
        ) : null}
        <div>
          <dt>Started</dt>
          <dd>{formatDateTime(span.started_at)}</dd>
        </div>
        <div>
          <dt>Ended</dt>
          <dd>{formatDateTime(span.ended_at)}</dd>
        </div>
      </dl>
      {span.error ? (
        <div className="alert alert-error" role="alert">
          {span.error}
        </div>
      ) : null}
      <JsonViewer label="Input" value={span.input} />
      <JsonViewer label="Output" value={span.output} />
      {hasAttributes ? <JsonViewer label="Attributes" value={span.attributes} /> : null}
    </section>
  );
}
