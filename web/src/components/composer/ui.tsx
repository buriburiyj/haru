import { useEffect, useRef, type ReactNode } from "react";

/** Calls onClose on outside mousedown or Esc while active. */
export function useDismiss(active: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!active) return;
    const down = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", down);
      document.removeEventListener("keydown", key);
    };
  }, [active, onClose]);
  return ref;
}

export const panelCls =
  "absolute z-20 min-w-56 rounded-xl border border-line bg-surface p-1 shadow-lg";

export function Row({
  label,
  hint,
  desc,
  checked,
  arrow,
  onClick,
  onHover,
  children,
}: {
  label: ReactNode;
  hint?: string;
  desc?: string;
  checked?: boolean;
  arrow?: boolean;
  onClick?: () => void;
  onHover?: () => void;
  children?: ReactNode;
}) {
  return (
    <div className="relative" onMouseEnter={onHover}>
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm text-fg hover:bg-surface-2"
      >
        <span className="flex-1">
          <span className="block">{label}</span>
          {desc && <span className="block text-xs text-muted">{desc}</span>}
        </span>
        {hint && <span className="text-xs text-muted">{hint}</span>}
        {checked && <span aria-hidden>✓</span>}
        {arrow && <span className="text-muted" aria-hidden>›</span>}
      </button>
      {children}
    </div>
  );
}
