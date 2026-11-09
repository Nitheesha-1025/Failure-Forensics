import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  createDocumentRun,
  getDocument,
  listDocumentRuns,
} from "../api/documents";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { Toast } from "../components/Toast";
import type { Document, PipelineRun } from "../types/api";
import {
  formatBytes,
  formatDateTime,
  formatDurationMs,
  statusLabel,
} from "../utils/format";

export function DocumentDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const documentId = id ?? "";

  const [doc, setDoc] = useState<Document | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);

  const load = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    try {
      const [document, runList] = await Promise.all([
        getDocument(documentId),
        listDocumentRuns(documentId, { page: 1, page_size: 20 }),
      ]);
      setDoc(document);
      setRuns(runList.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Document not found.");
      } else {
        setError(
          err instanceof ApiError
            ? err.message
            : "Unable to load document. Try again.",
        );
      }
      setDoc(null);
      setRuns([]);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const state = location.state as { uploaded?: boolean } | null;
    if (state?.uploaded) {
      setToast("Upload successful");
    }
  }, [location.state]);

  async function handleRunPipeline() {
    if (!documentId || runningRef.current) return;
    runningRef.current = true;
    setRunning(true);
    setError(null);
    try {
      const run = await createDocumentRun(documentId);
      setRuns((prev) => [run, ...prev]);
      setToast("Pipeline run completed");
      const updated = await getDocument(documentId);
      setDoc(updated);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Pipeline run failed. Please try again.",
      );
    } finally {
      runningRef.current = false;
      setRunning(false);
    }
  }

  if (!documentId) {
    return <ErrorMessage message="Invalid document link." />;
  }

  if (loading) {
    return <Loading message="Loading document…" />;
  }

  if (error && !doc) {
    return (
      <div className="page">
        <ErrorMessage message={error} onRetry={() => void load()} />
        <Link to="/documents" className="link">
          Back to documents
        </Link>
      </div>
    );
  }

  if (!doc) {
    return null;
  }

  return (
    <div className="page">
      {toast ? <Toast message={toast} onDismiss={() => setToast(null)} /> : null}
      <header className="page-header">
        <div>
          <Link to="/documents" className="link back-link">
            ← Documents
          </Link>
          <h1>{doc.filename}</h1>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={running}
          onClick={() => void handleRunPipeline()}
        >
          {running ? "Running pipeline…" : "Run processing"}
        </button>
      </header>

      {error ? <ErrorMessage message={error} /> : null}

      <dl className="detail-grid">
        <div>
          <dt>File type</dt>
          <dd>{doc.file_type.toUpperCase()}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(doc.file_size)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            <span className={`badge badge-${doc.processing_status}`}>
              {statusLabel(doc.processing_status)}
            </span>
          </dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{formatDateTime(doc.created_at)}</dd>
        </div>
        <div>
          <dt>Updated</dt>
          <dd>{formatDateTime(doc.updated_at)}</dd>
        </div>
      </dl>

      <section className="section">
        <h2>Processing runs</h2>
        {runs.length === 0 ? (
          <p className="muted">
            No runs yet. Use &quot;Run processing&quot; to execute the AI pipeline on this
            document.
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Started</th>
                  <th>Completed</th>
                  <th>Duration</th>
                  <th>Trace</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td data-label="Run" className="mono" title={run.id}>
                      {run.id.slice(0, 8)}…
                    </td>
                    <td data-label="Status">
                      <span className={`badge badge-${run.status}`}>
                        {statusLabel(run.status)}
                      </span>
                    </td>
                    <td data-label="Started">{formatDateTime(run.started_at)}</td>
                    <td data-label="Completed">{formatDateTime(run.completed_at)}</td>
                    <td data-label="Duration">{formatDurationMs(run.duration_ms)}</td>
                    <td data-label="Trace">
                      {run.trace_id ? (
                        <div className="trace-cell">
                          <span className="muted">Trace recorded</span>
                          <Link
                            to={`/documents/${documentId}/runs/${run.id}/trace`}
                            className="btn btn-secondary btn-sm"
                          >
                            View trace
                          </Link>
                        </div>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {runs.some((r) => r.error_message) ? (
          <div className="alert alert-error">
            {runs.find((r) => r.error_message)?.error_message}
          </div>
        ) : null}
      </section>
    </div>
  );
}
