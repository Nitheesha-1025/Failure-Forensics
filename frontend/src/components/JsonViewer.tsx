import { useId, useMemo, useState } from "react";

const COLLAPSE_CHAR_THRESHOLD = 4000;

interface JsonViewerProps {
  label: string;
  value: unknown;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "null";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function JsonViewer({ label, value }: JsonViewerProps) {
  const id = useId();
  const text = useMemo(() => formatValue(value), [value]);
  const isLong = text.length > COLLAPSE_CHAR_THRESHOLD;
  const [expanded, setExpanded] = useState(!isLong);

  const displayText =
    isLong && !expanded ? `${text.slice(0, COLLAPSE_CHAR_THRESHOLD)}\n…` : text;

  return (
    <div className="json-viewer">
      <div className="json-viewer-header">
        <h4 id={id}>{label}</h4>
        {isLong ? (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-expanded={expanded}
            aria-controls={`${id}-body`}
            onClick={() => setExpanded((e) => !e)}
          >
            {expanded ? "Collapse" : "Show full content"}
          </button>
        ) : null}
      </div>
      <pre id={`${id}-body`} className="json-viewer-body" tabIndex={0}>
        {displayText}
      </pre>
    </div>
  );
}
