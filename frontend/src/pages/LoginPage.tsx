import { FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";

export function LoginPage() {
  const { login, isAuthenticated, isInitializing } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = location.state as {
    from?: string;
    registered?: boolean;
    email?: string;
  } | null;
  const from = locationState?.from ?? "/dashboard";
  const registeredNotice =
    locationState?.registered === true
      ? `Account created${locationState.email ? ` for ${locationState.email}` : ""}. Sign in to continue.`
      : null;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isInitializing) {
    return (
      <div className="page-center">
        <Loading message="Loading…" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }
    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      navigate(from, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to sign in. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page auth-page--split">
      <div className="auth-hero-panel">
        <p className="eyebrow">Failure Forensics</p>
        <h2>Investigate AI pipeline failures with clarity</h2>
        <p className="muted">
          Trace multi-step runs, analyze root causes, and capture human feedback for evaluation.
        </p>
        <ul className="auth-hero-list">
          <li>Document upload and pipeline execution</li>
          <li>Span-level trace explorer</li>
          <li>Root-cause analysis and review workflow</li>
        </ul>
      </div>
      <div className="card auth-card">
        <p className="eyebrow">Workspace access</p>
        <h1>Sign in</h1>
        <p className="muted">Access documents, pipeline runs, and trace investigation tools.</p>
        {registeredNotice ? (
          <div className="alert alert-success" role="status">
            {registeredNotice}
          </div>
        ) : null}
        {error ? <ErrorMessage message={error} /> : null}
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="form-footer">
          No account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}
