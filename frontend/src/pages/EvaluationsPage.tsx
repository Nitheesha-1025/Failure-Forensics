import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteEvalCase,
  listEvalCases,
  runEvalRegression,
  type RegressionRunResult,
  type UserEvalCase,
} from "../api/evaluations";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { formatDateTime } from "../utils/format";

export function EvaluationsPage() {
  const [items, setItems] = useState<UserEvalCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<RegressionRunResult | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listEvalCases();
      setItems(data.items);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to load evaluation cases.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleDelete(item: UserEvalCase) {
    if (!window.confirm("Delete this evaluation case?")) return;
    try {
      await deleteEvalCase(item.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to delete case.");
    }
  }

  async function handleRun(item: UserEvalCase) {
    setRunningId(item.id);
    setLastResult(null);
    setError(null);
    try {
      const result = await runEvalRegression(item.id);
      setLastResult(result);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Regression run failed.",
      );
    } finally {
      setRunningId(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Quality"
        title="Evaluations"
        description="Cases are created from traces with human feedback (Trace Explorer → Failure analysis)."
        actions={
          <Link to="/analytics" className="btn btn-secondary btn-sm">
            Analytics
          </Link>
        }
      />
      {loading ? <Loading message="Loading evaluation cases…" /> : null}
      {error ? <ErrorMessage message={error} onRetry={() => void load()} /> : null}
      {!loading && !error && items.length === 0 ? (
        <EmptyState
          title="No evaluation cases"
          description="Review a failure analysis and save it as an evaluation case from Trace Explorer."
          actionLabel="Open documents"
          actionTo="/documents"
        />
      ) : null}
      {!loading && items.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Trace</th>
                <th>Human judgment</th>
                <th>Expected root cause</th>
                <th>Created</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td data-label="Trace" className="mono" title={item.trace_id}>
                    {item.trace_id.slice(0, 10)}…
                  </td>
                  <td data-label="Human judgment">{item.human_decision}</td>
                  <td data-label="Expected root cause">
                    {item.expected_root_cause_span_name ?? "—"}
                  </td>
                  <td data-label="Created">{formatDateTime(item.created_at)}</td>
                  <td className="table-actions" data-label="Actions">
                    <Link to={`/evaluations/${item.id}`} className="btn btn-secondary btn-sm">
                      View
                    </Link>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={runningId === item.id}
                      onClick={() => void handleRun(item)}
                    >
                      {runningId === item.id ? "Running…" : "Run regression"}
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      onClick={() => void handleDelete(item)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {lastResult ? (
        <div className="card regression-result" role="status">
          <h2>Regression result</h2>
          <p>{lastResult.message}</p>
          <p>
            Expected: {lastResult.expected_root_cause_span_name ?? "—"} · Actual:{" "}
            {lastResult.actual_root_cause_span_name ?? "—"}
          </p>
          {lastResult.passed != null ? (
            <p>
              <strong>{lastResult.passed ? "Passed" : "Failed"}</strong>
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
