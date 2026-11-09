/** Metric card — visual pattern adapted from 21st.dev “Stats Card” (Kavi Katiyar). */

type StatsTone = "neutral" | "success" | "warning" | "error";

interface StatsCardProps {
  label: string;
  value: number | string;
  hint?: string;
  tone?: StatsTone;
}

export function StatsCard({ label, value, hint, tone = "neutral" }: StatsCardProps) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint ? <p className="stat-hint">{hint}</p> : null}
    </article>
  );
}
