import type { ButtonHTMLAttributes } from "react";
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

/** Filter chip (pill). */
export function Chip({
  selected,
  className,
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { selected?: boolean }) {
  return (
    <button
      type={type}
      aria-pressed={selected}
      className={cx(
        "inline-flex min-h-11 items-center rounded-pill border border-line px-4 text-sm transition-colors",
        selected ? "bg-accent text-accent-fg" : "bg-surface text-muted hover:text-fg",
        className,
      )}
      {...rest}
    />
  );
}
