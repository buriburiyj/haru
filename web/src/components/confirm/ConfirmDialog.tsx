import { useEffect, useRef } from "react";

/** Confirmation window. Every delete in the UI must go through this. Props only, no data access. */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "삭제",
  danger = true,
  onConfirm,
  onCancel,
}: {
  title: string;
  message?: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    cancelRef.current?.focus(); // the safe choice has focus, so Enter never deletes by accident
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-fg/40 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onCancel()}
    >
      <div role="alertdialog" aria-label={title} className="w-full max-w-sm rounded-2xl border border-line bg-bg p-5 text-fg">
        <h2 className="text-base font-semibold">{title}</h2>
        {message && <p className="mt-2 text-sm text-muted">{message}</p>}
        <div className="mt-5 flex justify-end gap-2">
          <button ref={cancelRef} type="button" onClick={onCancel} className="min-h-11 rounded-lg border border-line px-4 text-sm text-fg hover:bg-surface-2">
            취소
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`min-h-11 rounded-lg px-4 text-sm ${danger ? "bg-danger text-accent-fg" : "bg-accent text-accent-fg"}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
