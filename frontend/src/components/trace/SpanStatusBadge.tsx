import type { StepStatus } from "../../types/trace";

interface SpanStatusBadgeProps {
  status: StepStatus;
}

export function SpanStatusBadge({ status }: SpanStatusBadgeProps) {
  const label = status === "error" ? "Error" : "OK";
  const className = status === "error" ? "badge badge-error" : "badge badge-ok";
  return (
    <span className={className} role="status">
      {label}
    </span>
  );
}
