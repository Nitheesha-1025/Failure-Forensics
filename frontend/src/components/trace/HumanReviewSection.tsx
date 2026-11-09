import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { createEvalCase } from "../../api/evaluations";
import { getTraceFeedback, submitTraceFeedback } from "../../api/traces";
import type { AnalysisFeedback, FeedbackDecision } from "../../types/feedback";
import { ErrorMessage } from "../ErrorMessage";
import { Loading } from "../Loading";

interface HumanReviewSectionProps {
  traceId: string;
  disabled?: boolean;
}

function decisionLabel(decision: FeedbackDecision): string {
  return decision === "confirmed" ? "Confirmed" : "Overridden";
}

export function HumanReviewSection({ traceId, disabled = false }: HumanReviewSectionProps) {
  const [feedback, setFeedback] = useState<AnalysisFeedback | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingDecision, setPendingDecision] = useState<FeedbackDecision | null>(null);
  const [comment, setComment] = useState("");
  const [evalSaving, setEvalSaving] = useState(false);
  const [evalMessage, setEvalMessage] = useState<string | null>(null);
  const submittingRef = useRef(false);

  const loadFeedback = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const row = await getTraceFeedback(traceId);
      setFeedback(row);
      setPendingDecision(row.decision);
      setComment(row.comment ?? "");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setFeedback(null);
        setPendingDecision(null);
        setComment("");
        return;
      }
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to load your review. Try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [traceId]);

  useEffect(() => {
    void loadFeedback();
  }, [loadFeedback]);

  async function handleSaveEvalCase() {
    if (!feedback || evalSaving) return;
    setEvalSaving(true);
    setEvalMessage(null);
    setError(null);
    try {
      await createEvalCase(traceId);
      setEvalMessage("Saved as evaluation case.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setEvalMessage("Already saved as an evaluation case.");
      } else {
        setError(
          err instanceof ApiError ? err.message : "Unable to save evaluation case.",
        );
      }
    } finally {
      setEvalSaving(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!pendingDecision || submittingRef.current || disabled) return;
    submittingRef.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const saved = await submitTraceFeedback(traceId, {
        decision: pendingDecision,
        comment: comment.trim() || null,
      });
      setFeedback(saved);
      setPendingDecision(saved.decision);
      setComment(saved.comment ?? "");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Unable to save review. Try again.",
      );
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  }

  if (loading) {
    return <Loading message="Loading your review…" />;
  }

  return (
    <section className="human-review" aria-labelledby="human-review-heading">
      <h3 id="human-review-heading">Human review</h3>
      {error ? <ErrorMessage message={error} onRetry={() => void loadFeedback()} /> : null}

      {feedback ? (
        <div className="human-review-current" role="status">
          <p>
            <strong>Current review:</strong> {decisionLabel(feedback.decision)}
          </p>
          {feedback.comment ? (
            <p>
              <strong>Comment:</strong> {feedback.comment}
            </p>
          ) : null}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={disabled || evalSaving}
            onClick={() => void handleSaveEvalCase()}
          >
            {evalSaving ? "Saving…" : "Save to evaluations"}
          </button>
          {evalMessage ? <p className="muted">{evalMessage}</p> : null}
        </div>
      ) : null}

      <form className="human-review-form" onSubmit={handleSubmit}>
        <div className="human-review-actions">
          <button
            type="button"
            className={`btn btn-sm${pendingDecision === "confirmed" ? " btn-primary" : " btn-secondary"}`}
            disabled={disabled || submitting}
            onClick={() => setPendingDecision("confirmed")}
          >
            Confirm diagnosis
          </button>
          <button
            type="button"
            className={`btn btn-sm${pendingDecision === "overridden" ? " btn-primary" : " btn-secondary"}`}
            disabled={disabled || submitting}
            onClick={() => setPendingDecision("overridden")}
          >
            Override diagnosis
          </button>
        </div>
        <label className="human-review-comment">
          Optional comment
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={disabled || submitting}
            rows={3}
            maxLength={2000}
            placeholder="Explain your review…"
          />
        </label>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={disabled || submitting || pendingDecision === null}
        >
          {submitting ? "Saving review…" : "Submit review"}
        </button>
      </form>
    </section>
  );
}
