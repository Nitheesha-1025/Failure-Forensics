interface LoadingProps {
  message?: string;
}

export function Loading({ message = "Loading…" }: LoadingProps) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading-spinner" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}
