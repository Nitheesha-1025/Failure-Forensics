import { FormEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { uploadDocument } from "../api/documents";
import { ApiError } from "../api/client";
import { ErrorMessage } from "../components/ErrorMessage";
import { PageHeader } from "../components/ui/PageHeader";
import { formatBytes } from "../utils/format";

const ACCEPT = ".pdf,.docx,.txt,.md";

export function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  function handleFileChange() {
    const selected = inputRef.current?.files?.[0] ?? null;
    setFile(selected);
    setError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const doc = await uploadDocument(file);
      navigate(`/documents/${doc.id}`, { replace: true, state: { uploaded: true } });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Intake"
        title="Upload document"
        description="PDF, DOCX, TXT, or Markdown — stored under your account."
      />
      <div className="card upload-card">
        <p className="muted">
          Supported types: PDF, DOCX, TXT, Markdown. Files are validated on the server.
        </p>
        {error ? <ErrorMessage message={error} /> : null}
        <form onSubmit={handleSubmit} className="form-stack">
          <label className="file-input-label">
            <span className="btn btn-secondary">Choose file</span>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              onChange={handleFileChange}
              className="visually-hidden"
            />
          </label>
          {file ? (
            <div className="file-preview">
              <strong>{file.name}</strong>
              <span>{formatBytes(file.size)}</span>
            </div>
          ) : (
            <p className="muted">No file selected.</p>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!file || uploading}
          >
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </form>
      </div>
    </div>
  );
}
