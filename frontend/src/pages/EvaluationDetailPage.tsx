import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  deleteEvalCase,
  getEvalCase,
  runEvalRegression,
  type RegressionRunResult,
  type UserEvalCase,
} from "../api/evaluations";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { formatDateTime } from "../utils/format";

export function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [item, setItem] = useState<UserEvalCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RegressionRunResult | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setItem(await getEvalCase(id));
    } catch (err) {
      setItem(null);
      setError(
        err instanceof ApiError ? err.message : "Evaluation case not found.",
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRun() {
    if (!item) return;
    setRunning(true);
    setResult(null);
    try {
      setResult(await runEvalRegression(item.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Regression run failed.");
    } finally {
      setRunning(false);
    }
  }

  async function handleDelete() {
    if (!item || !window.confirm("Delete this evaluation case?")) return;
    try {
      await deleteEvalCase(item.id);
      navigate("/evaluations", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to delete.");
    }
  }

  if (!id) return <ErrorMessage message="Invalid evaluation link." />;
  if (loading) return <Loading message="Loading evaluation case…" />;
  if (error || !item) {
    return (
      <div className="page">
        <Link to="/evaluations" className="link back-link">
          ← Evaluations
        </Link>
        <ErrorMessage message={error ?? "Not found."} onRetry={() => void load()} />
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <Link to="/evaluations" className="link back-link">
            ← Evaluations
          </Link>
          <h1>Evaluation case</h1>
        </div>
        <div className="table-actions">
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={running}
            onClick={() => void handleRun()}
          >
            {running ? "Running regression…" : "Run regression"}
          </button>
          <button type="button" className="btn btn-danger btn-sm" onClick={() => void handleDelete()}>
            Delete
          </button>
        </div>
      </header>
      <dl className="detail-grid">
        <div>
          <dt>Trace ID</dt>
          <dd className="mono">{item.trace_id}</dd>
        </div>
        <div>
          <dt>Human decision</dt>
          <dd>{item.human_decision}</dd>
        </div>
        <div>
          <dt>Expected root cause</dt>
          <dd>{item.expected_root_cause_span_name ?? "—"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDateTime(item.created_at)}</dd>
        </div>
      </dl>
      {item.human_comment ? (
        <div className="card">
          <h3>Human comment</h3>
          <p>{item.human_comment}</p>
        </div>
      ) : null}
      <div className="card">
        <h3>Input snapshot</h3>
        <pre className="json-viewer-body">{item.raw_text}</pre>
      </div>
      {result ? (
        <div className="card regression-result">
          <h3>Regression result</h3>
          <p>{result.message}</p>
          {result.passed != null ? (
            <p>
              <strong>{result.passed ? "Passed" : "Failed"}</strong>
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
