import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { deleteDocument, listDocuments } from "../api/documents";
import { ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorMessage } from "../components/ErrorMessage";
import { Loading } from "../components/Loading";
import { Toast } from "../components/Toast";
import { PageHeader } from "../components/ui/PageHeader";
import { TableToolbar } from "../components/ui/TableToolbar";
import type { Document } from "../types/api";
import { formatDateTime, statusLabel } from "../utils/format";

export function DocumentsPage() {
  const [items, setItems] = useState<Document[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const filteredItems = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter((doc) => doc.filename.toLowerCase().includes(q));
  }, [items, filter]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDocuments({ page, page_size: 20 });
      setItems(data.items);
      setTotalPages(Math.max(1, data.total_pages));
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to load documents. Try again.",
      );
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleDelete(doc: Document) {
    if (!window.confirm(`Delete "${doc.filename}"? This cannot be undone.`)) {
      return;
    }
    setDeletingId(doc.id);
    try {
      await deleteDocument(doc.id);
      setToast("Document deleted");
      await load();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Unable to delete document.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="page">
      {toast ? <Toast message={toast} onDismiss={() => setToast(null)} /> : null}
      <PageHeader
        eyebrow="Library"
        title="Documents"
        description="Uploaded files and processing status for your account."
        actions={
          <Link to="/upload" className="btn btn-primary">
            Upload
          </Link>
        }
      />

      {loading ? <Loading message="Loading documents…" /> : null}
      {!loading && error ? (
        <ErrorMessage message={error} onRetry={() => void load()} />
      ) : null}
      {!loading && !error && items.length === 0 ? (
        <EmptyState
          title="No documents yet"
          description="Upload your first document to get started."
          actionLabel="Upload"
          actionTo="/upload"
        />
      ) : null}
      {!loading && !error && items.length > 0 ? (
        <>
          <TableToolbar searchValue={filter} onSearchChange={setFilter} />
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((doc) => (
                  <tr key={doc.id}>
                    <td data-label="Filename">{doc.filename}</td>
                    <td data-label="Type">{doc.file_type.toUpperCase()}</td>
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
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        disabled={deletingId === doc.id}
                        onClick={() => void handleDelete(doc)}
                      >
                        {deletingId === doc.id ? "Deleting…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 ? (
            <div className="pagination">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
