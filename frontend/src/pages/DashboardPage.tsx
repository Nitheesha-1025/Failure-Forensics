import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAnalyticsSummary, type AnalyticsSummary } from "../api/analytics";
import { listDocuments } from "../api/documents";
import { ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { PageHeader } from "../components/ui/PageHeader";
import { StatsCard } from "../components/ui/StatsCard";
import type { Document } from "../types/api";
import { formatDateTime, statusLabel } from "../utils/format";

export function DashboardPage() {
  const [totalDocuments, setTotalDocuments] = useState<number | null>(null);
  const [recent, setRecent] = useState<Document[]>([]);
  const [metrics, setMetrics] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [docList, analytics] = await Promise.all([
        listDocuments({ page: 1, page_size: 5 }),
        getAnalyticsSummary().catch(() => null),
      ]);
      setTotalDocuments(docList.total);
      setRecent(docList.items);
      setMetrics(analytics);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to load dashboard. Try again.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return <Loading message="Loading dashboard…" />;
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={() => void load()} />;
  }

  return (
    <div className="page dashboard-grid">
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description="Documents, pipeline runs, and failure signals from your account."
        actions={
          <Link to="/upload" className="btn btn-primary">
            Upload document
          </Link>
        }
      />

      <section className="dashboard-metrics" aria-label="Key metrics">
        <StatsCard label="Documents" value={totalDocuments ?? 0} />
        <StatsCard
          label="Pipeline runs"
          value={metrics?.total_runs ?? "—"}
          hint={metrics ? undefined : "Load analytics for run totals"}
        />
        <StatsCard
          label="Failed runs"
          value={metrics?.failed_runs ?? "—"}
          tone="error"
        />
        <StatsCard
          label="Analyzed traces"
          value={metrics?.analyzed_traces ?? "—"}
          tone="success"
        />
      </section>

      {metrics && metrics.failed_runs > 0 ? (
        <div className="alert alert-error" role="status">
          {metrics.failed_runs} pipeline run{metrics.failed_runs === 1 ? "" : "s"} failed.
          Open a document run history or trace explorer to investigate.
        </div>
      ) : null}

      <section className="section card">
        <div className="section-header">
          <h2>Recent documents</h2>
          <Link to="/documents" className="link">
            View all
          </Link>
        </div>
        {recent.length === 0 ? (
          <EmptyState
            title="No documents yet"
            description="Upload your first document to run AI processing and capture traces."
            actionLabel="Upload your first document"
            actionTo="/upload"
          />
        ) : (
          <div className="table-wrap table-wrap--flush">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {recent.map((doc) => (
                  <tr key={doc.id}>
                    <td data-label="Filename">{doc.filename}</td>
                    <td data-label="Status">
                      <span className={`badge badge-${doc.processing_status}`}>
                        {statusLabel(doc.processing_status)}
                      </span>
                    </td>
                    <td data-label="Created">{formatDateTime(doc.created_at)}</td>
                    <td className="table-actions" data-label="Actions">
                      <Link to={`/documents/${doc.id}`} className="btn btn-secondary btn-sm">
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
