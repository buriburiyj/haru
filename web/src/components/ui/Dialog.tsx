import { useEffect } from "react";
import type { ReactNode } from "react";
import { cx } from "./cx";

/** Modal window: centered card on desktop, full screen on phone. Esc and backdrop click close it. */
export default function Dialog({
  title,
  onClose,
  children,
  footer,
  className,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-fg/40 md:items-center md:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-label={title}
        className={cx(
          "flex h-full w-full flex-col bg-bg text-fg md:h-auto md:max-h-full md:max-w-lg md:rounded-card md:border md:border-line md:shadow-pop",
          className,
        )}
      >
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <h2 className="mr-auto text-base font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="닫기" className="flex h-11 w-11 items-center justify-center rounded-control text-muted hover:bg-surface-2 hover:text-fg">
            ✕
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer>}
      </div>
    </div>
  );
}
