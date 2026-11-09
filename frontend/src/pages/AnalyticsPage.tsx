import { useCallback, useEffect, useState } from "react";
import { getAnalyticsSummary, type AnalyticsSummary } from "../api/analytics";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { PageHeader } from "../components/ui/PageHeader";
import { StatsCard } from "../components/ui/StatsCard";

export function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getAnalyticsSummary());
    } catch (err) {
      setData(null);
      setError(
        err instanceof ApiError ? err.message : "Unable to load analytics.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading message="Loading analytics…" />;
  if (error || !data) {
    return (
      <div className="page">
        <PageHeader title="Analytics" />
        <ErrorMessage message={error ?? "No data."} onRetry={() => void load()} />
      </div>
    );
  }

  const cards: {
    label: string;
    value: number;
    tone?: "neutral" | "success" | "warning" | "error";
  }[] = [
    { label: "Documents", value: data.total_documents },
    { label: "Pipeline runs", value: data.total_runs },
    { label: "Completed runs", value: data.completed_runs, tone: "success" },
    { label: "Failed runs", value: data.failed_runs, tone: "error" },
    { label: "Analyzed traces", value: data.analyzed_traces },
    { label: "Confirmed feedback", value: data.feedback_confirmed, tone: "success" },
    { label: "Overridden feedback", value: data.feedback_overridden, tone: "warning" },
    { label: "Evaluation cases", value: data.evaluation_cases },
  ];

  return (
    <div className="page">
      <PageHeader
        eyebrow="Account metrics"
        title="Analytics"
        description="Metrics from stored documents, runs, analyses, and human reviews."
      />
      <div className="dashboard-metrics">
        {cards.map((c) => (
          <StatsCard key={c.label} label={c.label} value={c.value} tone={c.tone} />
        ))}
      </div>
      <section className="section card">
        <h2>Top expected root causes (eval cases)</h2>
        {data.top_root_causes.length === 0 ? (
          <p className="muted">No evaluation cases with root-cause names yet.</p>
        ) : (
          <div className="table-wrap table-wrap--flush">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Span</th>
                  <th>Cases</th>
                </tr>
              </thead>
              <tbody>
                {data.top_root_causes.map((row) => (
                  <tr key={row.span_name}>
                    <td>{row.span_name}</td>
                    <td>{row.count}</td>
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
