interface ToastProps {
  message: string;
  variant?: "success" | "error";
  onDismiss: () => void;
}

export function Toast({ message, variant = "success", onDismiss }: ToastProps) {
  return (
    <div className={`toast toast-${variant}`} role="status">
      <span>{message}</span>
      <button type="button" className="toast-dismiss" onClick={onDismiss} aria-label="Dismiss">
        ×
      </button>
    </div>
  );
}
