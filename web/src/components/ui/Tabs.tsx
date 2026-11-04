import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cx } from "./cx";

/** Segmented tabs, e.g. 전체 / 내 항목 / 공유받음 or Chat · Work · Code. */
export function Tabs<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { id: T; label: string }[];
  onChange: (v: T) => void;
  label?: string;
}) {
  return (
    <div role="tablist" aria-label={label} className="inline-flex rounded-control bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="tab"
          aria-selected={o.id === value}
          onClick={() => onChange(o.id)}
          className={cx(
            "min-h-10 rounded-control px-3 text-sm transition-colors",
            o.id === value ? "bg-bg text-fg" : "text-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Pill chip. Plain = filter chip. With `caret` it is a dropdown chip (환경 ▾, 저장소 ▾, 모델 ▾, 권한 모드 ▾);
 * the parent shows a Menu next to it. `icon` goes before the label.
 */
export function Chip({
  selected,
  caret,
  icon,
  className,
  type = "button",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean; caret?: boolean; icon?: ReactNode }) {
  return (
    <button
      type={type}
      aria-pressed={caret ? undefined : selected}
      aria-haspopup={caret ? "menu" : undefined}
      className={cx(
        "inline-flex min-h-11 items-center gap-1.5 rounded-pill border border-line px-4 text-sm transition-colors",
        selected ? "bg-accent text-accent-fg" : "bg-surface text-muted hover:text-fg",
        className,
      )}
      {...rest}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      {children}
      {caret && <span aria-hidden="true" className="text-xs">▾</span>}
    </button>
  );
}
