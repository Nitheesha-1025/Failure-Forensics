import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";

export function RegisterPage() {
  const { register, isAuthenticated, isInitializing } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
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
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await register({ email: email.trim(), password });
      navigate("/login", {
        replace: true,
        state: { registered: true, email: email.trim() },
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unable to create account. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page auth-page--split">
      <div className="auth-hero-panel">
        <p className="eyebrow">Failure Forensics</p>
        <h2>Create your investigation workspace</h2>
        <p className="muted">
          One account for documents, traces, evaluations, and analytics — all scoped to you.
        </p>
        <ul className="auth-hero-list">
          <li>Upload documents and run the AI pipeline</li>
          <li>Explore traces and failure analysis</li>
          <li>Track evaluations and account analytics</li>
        </ul>
      </div>
      <div className="card auth-card">
        <p className="eyebrow">New workspace</p>
        <h1>Create account</h1>
        <p className="muted">Register to upload documents and run pipeline forensics.</p>
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <label>
            Confirm password
            <input
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              minLength={8}
              required
            />
          </label>
          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Creating account…" : "Register"}
          </button>
        </form>
        <p className="form-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
